"""Ponte do aplicativo Android (``android/ponte.py``): o mesmo núcleo, com entrada e saída em JSON."""
import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "android"))
import ponte  # noqa: E402

from core.campos import CAMPOS  # noqa: E402
from core.fases import calcular  # noqa: E402
from core.models import Entrada  # noqa: E402


def test_esquema_cobre_todos_os_campos():
    esq = json.loads(ponte.esquema())
    nomes = [c["nome"] for s in esq["secoes"] for c in s["campos"]]
    assert sorted(nomes) == sorted(c.nome for c in CAMPOS)
    por_nome = {c["nome"]: c for s in esq["secoes"] for c in s["campos"]}
    assert por_nome["k_phi"]["padrao"] == 0.75 and por_nome["ff_tipo"]["padrao"] == "Em repouso"
    assert por_nome["delta_dv"]["padrao"] is None and por_nome["delta_dv"]["vinculo"] == "phi_at"
    assert por_nome["ar_tz_phi"]["tipo"] == "bitola" and 12.5 in por_nome["ar_tz_phi"]["opcoes"]
    assert any(o["legada"] for o in por_nome["conv_res"]["opcoes"])
    # os padrões do esquema formam uma entrada válida, igual à do aplicativo de computador
    assert Entrada(**{n: c["padrao"] for n, c in por_nome.items()}) == Entrada()


def test_calculo_igual_ao_do_nucleo():
    dados = dict(b_talao=1.2, q_sc=15.0, sc_ln_Q=30.0, sc_ln_x=2.5, cf_usar=False)
    r = json.loads(ponte.calcular_json(json.dumps(dados)))
    ref = calcular(Entrada(**dados))
    v = ref.fase1.verif
    assert r["ok"] and r["estab"] == ref.atende_estabilidade and r["dim"] == ref.dim.atende
    assert [c["v"] for c in r["cartoes"]] == [ponte.fs(v.R_FSt), ponte.fs(v.R_FSd), ponte.num(v.R_eB, 3),
                                              ponte.fs(v.R_FScc)]
    assert len(r["checks"]) == sum(c.situacao != "—" for c in ref.dim.checks + ref.dim.extras)
    assert r["notas"] == list(ref.dim.notas)
    assert r["croqui"]["B"] == pytest.approx(ref.geo.B_base) and r["croqui"]["linha"] == [30.0, 2.5]
    assert Entrada(**r["entrada"]) == Entrada(**dados)          # serve de arquivo de projeto
    json.dumps(r, allow_nan=False)                              # nada de inf/nan na saída


@pytest.mark.parametrize("dados", [dict(trav_usar=True), dict(cf_usar=True), dict(anc_usar=True, bl_usar=True),
                                   dict(b_talao=0.0, b_ponta=0.1, q_sc=40.0), dict(hw_at=2.0, hw_fr=0.5)],
                         ids=["travado", "contrafortes", "estacas_e_bloco", "fora_da_base", "agua"])
def test_casos_variados_saem_em_json_valido(dados):
    r = json.loads(ponte.calcular_json(json.dumps(dados)))
    assert r["ok"] and len(r["verif"]) == 20 and len(r["fases"]) == (2 if dados.get("trav_usar") else 1)
    json.dumps(r, allow_nan=False)


def test_dados_invalidos_viram_mensagens():
    r = json.loads(ponte.calcular_json(json.dumps(dict(H_muro=99, phi_at=2))))
    assert not r["ok"] and len(r["erros"]) == 2
    assert "Altura total H" in r["erros"][0] and "menor ou igual a 30" in r["erros"][0]
    assert not json.loads(ponte.calcular_json("isto não é json"))["ok"]


def test_campos_desabilitados_e_solo():
    off = json.loads(ponte.desabilitados_json("{}"))
    assert "cf_esp" in off and "qult_inf" in off and "rk_conv" in off and "H_muro" not in off
    assert "cf_esp" not in json.loads(ponte.desabilitados_json(json.dumps(dict(cf_usar=True))))
    s = json.loads(ponte.solo_json(json.dumps(dict(tipo="Argila", nspt=6))))
    assert s["alfa"] == pytest.approx(0.67) and s["classe"] == "Média" and len(s["faixas"]) == 5


def test_montagem_empacota_o_nucleo_inteiro():
    """O zip do aplicativo leva todos os módulos de core/ — nenhuma cópia paralela do cálculo."""
    montar = (RAIZ / "android" / "montar.py").read_text(encoding="utf-8")
    assert '(RAIZ / "core").glob("*.py")' in montar and 'z.write(AQUI / "ponte.py", "ponte.py")' in montar
    import importlib
    for mod in ("core.fases", "core.solos", "core.campos", "core.enums", "core.models"):
        assert not any(dep in importlib.import_module(mod).__dict__ for dep in ("streamlit", "matplotlib", "pandas"))
