"""Recalcula a planilha no Excel para cada cenário e grava ``tests/data/cenarios.json``.

A planilha é aberta SOMENTE LEITURA numa instância própria do Excel e nunca é
salva: as entradas são alteradas apenas em memória.

Uso:  .venv\\Scripts\\python tools\\gerar_cenarios.py
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

import openpyxl
import win32com.client as win32
from openpyxl.utils import column_index_from_string

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from core.models import Entrada  # noqa: E402
from tests.cenarios import CENARIOS  # noqa: E402

PLANILHA = RAIZ / "Verificacao_Muro_Arrimo_NBR11682.xlsx"
SAIDA = RAIZ / "tests" / "data" / "cenarios.json"

# células sem nome que também são comparadas
EXTRAS = {
    "sig_max": ("Resumo", "C25"), "sig_min": ("Resumo", "C26"), "resultado": ("Resumo", "C33"),
    "avisos": ("Resumo", "C35"), "resultado_geral": ("Resumo", "I37"),
    "sig_max_2": ("Resumo F2", "C25"), "sig_min_2": ("Resumo F2", "C26"), "resultado_2": ("Resumo F2", "C33"),
    "avisos_2": ("Resumo F2", "C35"),
}
for r in range(6, 32):
    EXTRAS[f"chk_{r}_sol"] = ("Dimensionamento", f"M{r}")
    EXTRAS[f"chk_{r}_res"] = ("Dimensionamento", f"N{r}")
    EXTRAS[f"chk_{r}_st"] = ("Dimensionamento", f"O{r}")
for r in range(5, 22):
    for col, k in zip("CDEFGH", ("Fx", "Fz", "x", "z", "Mres", "Movr")):
        EXTRAS[f"F1_{r}_{k}"] = ("Forças", f"{col}{r}")
        EXTRAS[f"F2_{r}_{k}"] = ("Forças F2", f"{col}{r}")


def _rc(cel: str) -> tuple[int, int]:
    m = re.fullmatch(r"([A-Z]+)(\d+)", cel)
    return int(m.group(2)), column_index_from_string(m.group(1))


def main() -> None:
    wb0 = openpyxl.load_workbook(PLANILHA, data_only=False)
    nomes = {}
    for nome, dn in wb0.defined_names.items():
        aba, cel = dn.value.replace("$", "").replace("'", "").split("!")
        nomes[nome] = (aba, cel)
    entradas = {n: v for n, v in nomes.items() if v[0] == "Entrada"}
    saidas = {n: v for n, v in nomes.items() if v[0] != "Entrada"}
    alvo = dict(saidas)
    alvo.update(EXTRAS)

    xl = win32.DispatchEx("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False
    resultado = []
    try:
        wb = xl.Workbooks.Open(str(PLANILHA), UpdateLinks=0, ReadOnly=True)
        xl.Calculation = -4135  # manual
        abas = {ws.Name: ws for ws in wb.Worksheets}
        cel_in = {n: abas["Entrada"].Range(c) for n, (_, c) in entradas.items()}
        # CONCAT não existe no Excel 2016 (→ #NOME? em C35/C33/I37). Só em memória,
        # troca por CONCATENATE para obter a referência dos avisos e do veredito.
        for aba in ("Resumo", "Resumo F2"):
            cel = abas[aba].Range("C35")
            cel.Formula = cel.Formula.replace("_xlfn.CONCAT(", "CONCATENATE(")
        for i, (nome_cen, mud) in enumerate(CENARIOS.items(), 1):
            ent = Entrada(**mud)
            for n, val in ent.para_planilha().items():
                cel_in[n].Value = val
            xl.CalculateFull()
            grade = {}
            for aba in {a for a, _ in alvo.values()}:
                ur = abas[aba].UsedRange
                vals = ur.Value
                grade[aba] = (ur.Row, ur.Column, vals)
            out = {}
            for chave, (aba, cel) in alvo.items():
                r0, c0, vals = grade[aba]
                r, c = _rc(cel)
                v = vals[r - r0][c - c0]
                if isinstance(v, int) and v < -2146000000:   # erro do Excel (#DIV/0!, #NUM! ...)
                    v = None
                out[chave] = v
            resultado.append({"nome": nome_cen, "entrada": ent.model_dump(mode="json"), "saidas": out})
            print(f"[{i:2d}/{len(CENARIOS)}] {nome_cen}: FSt={out.get('R_FSt')}  dm={out.get('dm_geral')}")
        wb.Close(SaveChanges=False)
    finally:
        xl.Quit()
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    io.open(SAIDA, "w", encoding="utf-8").write(json.dumps(resultado, ensure_ascii=False, indent=1))
    print(f"{len(resultado)} cenários -> {SAIDA}")


if __name__ == "__main__":
    main()
