"""Paridade célula a célula: núcleo Python × planilha recalculada no Excel.

Para cada cenário de ``tests/cenarios.py`` são comparados TODOS os nomes
definidos nas abas de cálculo (~250), as 17 linhas da tabela de forças das duas
fases, as 26 verificações do dimensionamento, os avisos e os vereditos.
Tolerância: 1e-8 (relativa e absoluta).

Referência gerada por ``tools/gerar_cenarios.py`` (Excel, planilha somente leitura).
"""
import pytest

from core.fases import calcular
from core.models import Entrada
from tests.paridade import carregar, comparar

CENARIOS = carregar()

# Desvio DELIBERADO em relação à planilha: com a resultante fora da base
# (|e| ≥ B/2) a aba Dimensionamento segue calculando ponta e talão com tensões
# de solo negativas. O aplicativo reprova o dimensionamento da base.
_BASE = ("dm_MtP", "dm_VtP", "dm_Mtp", "dm_MtT", "dm_Mtt", "dm_MSd_pt", "dm_MSd_tl", "dm_As_pt", "dm_As_tl",
         "dm_VSd_pt", "dm_geral") + tuple(f"chk_{r}_" for r in (16, 17, 19, 20, 21))


# Segundo desvio DELIBERADO: a planilha multiplica por γf a resistência do solo da frente
# (ação favorável) no dimensionamento da cortina em balanço. O aplicativo a mantém com 1,0
# (NBR 8681), o que aumenta um pouco MSd e VSd da cortina — e da ponta, quando herda o momento dela.
_FRONTAL = ("dm_MSdp", "dm_Asnp", "dm_utp", "dm_VSd:", "dm_MSdn", "dm_Asnn", "dm_utn", "dm_MSd_pt", "dm_As_pt",
            "dm_geral") + tuple(f"chk_{r}_" for r in (6, 8, 10, 12, 16, 17))


# Terceiro desvio DELIBERADO: a planilha desconta a força da ancoragem (estacas sob a ponta) do momento e
# do cortante da ponta. A ancoragem é resistência passiva, mobilizada por inteiro só na ruptura; o
# aplicativo não a desconta (como o GEO5), e os esforços da ponta ficam maiores.
_ANCORAGEM = ("dm_MtP", "dm_VtP", "dm_Mtp", "dm_MSd_pt", "dm_As_pt", "dm_VSd_pt", "dm_geral") + tuple(
    f"chk_{r}_" for r in (16, 17, 18, 19))

@pytest.mark.parametrize("cenario", CENARIOS, ids=[c["nome"] for c in CENARIOS])
def test_paridade(cenario):
    dif, sem, n = comparar(cenario)
    ent = cenario["entrada"]
    res = calcular(Entrada(**ent))
    if res.dim.base_invalida:
        dif = [d for d in dif if not d.startswith(_BASE)]
        assert not res.dim.atende
    if ent["ff_tipo"] == "Em repouso" and ent["D_frente"] > ent["h_sap"]:
        dif = [d for d in dif if not d.startswith(_FRONTAL)]
        xl = cenario["saidas"]
        assert res.dim.v["dm_MSdp"] >= xl["dm_MSdp"] - 1e-9          # sempre a favor da segurança
        assert res.dim.v["dm_VSd"] >= xl["dm_VSd"] - 1e-9
        assert res.dim.v["dm_MSdp"] <= 1.02 * xl["dm_MSdp"]          # e por pouco
    if ent["anc_usar"]:
        dif = [d for d in dif if not d.startswith(_ANCORAGEM)]
        xl = cenario["saidas"]
        if not res.dim.base_invalida:
            assert res.dim.v["dm_VtP"] >= xl["dm_VtP"] - 1e-9            # sempre a favor da segurança
            assert res.dim.v["dm_MtP1"] >= xl["dm_MtP1"] - 1e-9
    assert not sem, f"nomes da planilha sem equivalente no núcleo: {sem}"
    assert n > 550
    assert not dif, f"{len(dif)} divergência(s) em {n} valores:\n  " + "\n  ".join(dif[:20])


def test_cobertura_dos_cenarios():
    """Os cenários exercitam todas as opções de lista e os dois estados de cada Sim/Não."""
    from core.campos import CAMPOS
    from core.enums import ENUM_DO_CAMPO
    vistos: dict[str, set] = {}
    for c in CENARIOS:
        for k, v in c["entrada"].items():
            vistos.setdefault(k, set()).add(v)
    for campo in CAMPOS:
        if not campo.celula:            # campo só do aplicativo: não existe na planilha
            continue
        if campo.tipo == "bool":
            assert vistos[campo.nome] == {True, False}, campo.nome
        elif campo.tipo == "enum":
            esperado = {m.value for m in ENUM_DO_CAMPO[campo.nome]}
            assert vistos[campo.nome] == esperado, campo.nome


def test_resistencia_frontal_nao_e_majorada_na_cortina():
    """Favorável entra com 1,0: MSd = γf·(solo + sobrecarga + água) − frente."""
    e = Entrada(ff_tipo="Em repouso", D_frente=1.2, gf_f=1.4)
    com, sem = calcular(e), calcular(e.com(ff_tipo="Nenhuma"))
    s = com.dim.secoes
    f = com.dim.fatias
    dy = com.geo.h_cort / 100
    Mf = float((f["s_frente"] * dy * (f["y"] - e.h_sap)).sum())      # momento da frente na base da cortina
    Vf = float((f["s_frente"] * dy).sum())
    assert Mf > 0
    assert s["MSdp"][0] == pytest.approx(sem.dim.secoes["MSdp"][0] - Mf, rel=1e-12)
    assert s["VSd"][0] == pytest.approx(sem.dim.secoes["VSd"][0] - Vf, rel=1e-12)
    assert com.dim.v["dm_Mk0"] == pytest.approx(sem.dim.v["dm_Mk0"] - Mf, rel=1e-12)   # característico não muda
    # sem resistência frontal nada muda em relação à regra antiga (γf·Mk)
    assert sem.dim.v["dm_MSdp"] == e.gf_f * sem.dim.v["dm_Mkp"]


def test_casos_com_resultante_fora_da_base_existem():
    assert sum(calcular(Entrada(**c["entrada"])).dim.base_invalida for c in CENARIOS) >= 2
