"""Confere a Revisão 01 da planilha contra o núcleo do aplicativo, cenário por cenário.

    .venv/bin/python tools/conferir_revisao.py [--rapido]

Para cada cenário: escreve as entradas na planilha revisada, recalcula no LibreOffice (que
reproduz o Excel célula a célula na planilha original — conferido em 17/11/2026) e compara todos
os nomes definidos e as verificações do dimensionamento com o resultado do aplicativo. O
aplicativo roda com a laje entre contrafortes pelos coeficientes do GEO5, que é o que a planilha
faz. Cenários: os 75 da paridade (tests/cenarios.py), os quatro memoriais do GEO5
(tests/test_geo5.py) e os das novidades da revisão.

Diferença esperada (não portada para a planilha): concreto acima de C40 (ηc e grupo II).
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import openpyxl

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from core.campos import CAMPOS  # noqa: E402
from core.fases import calcular  # noqa: E402
from core.models import Entrada  # noqa: E402
from core.planilha import nomes_planilha  # noqa: E402
from tests.cenarios import CENARIOS  # noqa: E402

REVISAO = RAIZ / "Verificacao_Muro_Arrimo_NBR11682_Rev01.xlsx"
RECALC = next(Path("/root/.claude/skills").rglob("xlsx/scripts/recalc.py"), None)
LAJE = {"laje_cf": "Coeficientes do GEO5 (planilha)"}
TOL = 1e-7

EXTRAS = {
    "rev_cargas": dict(sc_fx_q=20.0, sc_fx_a=1.0, sc_fx_b=2.0, sc_ln_Q=30.0, sc_ln_x=2.5, sc_pt_P=100.0, sc_pt_x=3.0),
    "rev_cargas_sobre_talao": dict(sc_fx_q=15.0, sc_fx_a=0.5, sc_fx_b=1.0, sc_pt_P=90.0, sc_pt_x=0.5, q_estab=True),
    "rev_cargas_parede_flexivel": dict(sc_ln_Q=50.0, sc_ln_x=0.5, sc_bq="Parede que se desloca (×1 — Boussinesq)"),
    "rev_cargas_rankine_beta": dict(metodo_emp="Rankine", beta_t=10, sc_fx_q=20.0, sc_fx_a=3.0, sc_fx_b=2.0),
    "rev_faixa_B4": dict(b_talao=0.8, cc_modo="Informada", qult_inf=2000),
    "rev_faixa_travado": dict(b_talao=0.8, cc_modo="Informada", qult_inf=2000, trav_usar=True, trav_F=5.0),
    "rev_todas_locais": dict(comb_base="Equilíbrio + todas as locais (mais severo)"),
    "rev_todas_locais_agua": dict(comb_base="Equilíbrio + todas as locais (mais severo)", hw_at=2.0, hw_fr=0.5, gw_f=1.2),
    "rev_bloco_informado": dict(anc_usar=True, bl_usar=True, bl_pos="Posição informada", bl_x=0.6),
    "rev_bloco_nas_estacas": dict(anc_usar=True, bl_usar=True, bl_pos="Centrado nas estacas (planilha)"),
    "rev_sem_talao_no": dict(b_talao=0.0, b_ponta=1.5),
    "rev_ponta_pressoes": dict(ponta_mod="Pressões na base", sig_dim="Retangular (Meyerhof)"),
    "rev_resultante_fora": dict(b_talao=0.0, b_ponta=0.1, q_sc=40.0),
}


def _cenarios(rapido: bool) -> dict[str, dict]:
    from tests import test_geo5 as g
    geo5 = {
        "geo5_sem_talao": {**g.MURO, **g.CRITERIOS_GEO5},
        "geo5_ancoragem": {**g.MURO_ANC, **g.CRITERIOS_ANC},
        "geo5_contrafortes": {**g.MURO_CF, **g.CRITERIOS_CF},
        "geo5_talao": {**g.MURO_TALAO, **g.CRITERIOS_TALAO},
    }
    todos = {**({} if rapido else CENARIOS), **geo5, **EXTRAS}
    if rapido:
        todos = {"base": {}, **todos}
    return todos


def _alvos(wb) -> dict[str, tuple[str, str]]:
    alvo = {}
    for nome, dn in wb.defined_names.items():
        ref = dn.attr_text
        if "!" not in ref or ":" in ref:
            continue
        aba, cel = ref.split("!")
        alvo[nome] = (aba.strip("'"), cel.replace("$", ""))
    for r in range(6, 32):
        for col, suf in (("M", "sol"), ("N", "res"), ("O", "st")):
            alvo[f"chk_{r}_{suf}"] = ("Dimensionamento", f"{col}{r}")
    alvo.update(resultado=("Resumo", "C33"), resultado_2=("Resumo F2", "C33"), resultado_geral=("Resumo", "I37"))
    return alvo


def _app(dados: dict) -> dict:
    res = calcular(Entrada(**{**dados, **LAJE}))
    d = nomes_planilha(res)
    for i, c in enumerate(res.dim.checks):
        d[f"chk_{6 + i}_sol"], d[f"chk_{6 + i}_res"], d[f"chk_{6 + i}_st"] = c.solicitante, c.resistente, c.situacao
    d["dm_atende"] = "ATENDE" if res.dim.atende else "NÃO ATENDE"
    return d


def _igual(a, b) -> bool:
    if isinstance(a, str) or isinstance(b, str):
        return str(a) == str(b)
    if a is None or b is None:
        return a is b
    if isinstance(a, bool) or isinstance(b, bool):
        return bool(a) == bool(b)
    if math.isinf(a):
        return b >= 9999
    return math.isclose(float(a), float(b), rel_tol=TOL, abs_tol=TOL)


def conferir(rapido: bool = False) -> int:
    if RECALC is None:
        sys.exit("recalc.py (LibreOffice) não encontrado.")
    wb = openpyxl.load_workbook(REVISAO)
    alvo = _alvos(wb)
    entradas = {c.nome: alvo[c.nome] for c in CAMPOS if c.nome in alvo}
    relatorio, falhas = [], 0
    cenarios = _cenarios(rapido)
    with tempfile.TemporaryDirectory() as tmp:
        arq = Path(tmp) / "cenario.xlsx"
        for i, (nome, mud) in enumerate(cenarios.items(), 1):
            ent = Entrada(**{**mud, **LAJE})
            for campo, val in ent.para_planilha(so_app=True).items():
                if campo in entradas:
                    aba, cel = entradas[campo]
                    wb[aba][cel] = val
            wb.save(arq)
            r = subprocess.run([sys.executable, str(RECALC), str(arq), "180"], capture_output=True, text=True)
            info = json.loads(r.stdout)
            vals = openpyxl.load_workbook(arq, data_only=True)
            xl = {k: vals[a][c].value for k, (a, c) in alvo.items()}
            py = _app(mud)
            dif = [f"{k}: planilha={xl[k]!r} app={py[k]!r}" for k in sorted(set(xl) & set(py))
                   if not (xl[k] is None and py[k] is None) and not _igual(py[k], xl[k])]
            esperado = ent.fck_c > 40
            ok = not dif and info.get("total_errors", 1) == 0
            falhas += 0 if (ok or esperado) else 1
            n = len(set(xl) & set(py))
            print(f"[{i:2d}/{len(cenarios)}] {nome:34s} {n} valores  " +
                  ("OK" if ok else f"{len(dif)} diferença(s)" + (" (fck > 40: esperado)" if esperado else "")) +
                  (f"  erros de fórmula: {info.get('total_errors')}" if info.get("total_errors") else ""), flush=True)
            for d in dif[:8]:
                print("      ", d)
            relatorio.append(dict(cenario=nome, comparados=n, diferencas=dif, erros=info.get("total_errors")))
    saida = Path(tempfile.gettempdir()) / "conferencia_revisao.json"
    saida.write_text(json.dumps(relatorio, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{len(cenarios) - falhas}/{len(cenarios)} cenários sem diferença não explicada. Relatório: {saida}")
    return falhas


if __name__ == "__main__":
    sys.exit(1 if conferir("--rapido" in sys.argv) else 0)
