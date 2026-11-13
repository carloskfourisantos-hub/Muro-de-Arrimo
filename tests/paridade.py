"""Comparação núcleo Python × planilha recalculada no Excel (apoio aos testes)."""
from __future__ import annotations

import json
import math
from pathlib import Path

from core.fases import calcular
from core.models import Entrada
from core.planilha import MODO_PLANILHA, nomes_planilha

DADOS = Path(__file__).parent / "data" / "cenarios.json"
REL, ABS = 1e-8, 1e-8
_KS = ("Fx", "Fz", "x", "z", "Mres", "Movr")


def carregar() -> list[dict]:
    return json.loads(DADOS.read_text(encoding="utf-8"))


def valores_python(entrada: Entrada) -> dict:
    res = calcular(entrada)
    d = nomes_planilha(res)
    for suf, fase in (("F1", res.fase1), ("F2", res.fase2)):
        for i, f in enumerate(fase.forcas.linhas):
            for k in _KS:
                d[f"{suf}_{5 + i}_{k}"] = getattr(f, k)
    for i, c in enumerate(res.dim.checks):
        d[f"chk_{6 + i}_sol"] = c.solicitante
        d[f"chk_{6 + i}_res"] = c.resistente
        d[f"chk_{6 + i}_st"] = c.situacao
    return d


def _igual(a, b) -> bool:
    if isinstance(b, str) or isinstance(a, str):
        return str(a) == str(b)
    if isinstance(a, bool):
        a = int(a)
    if math.isinf(a):
        return False
    return math.isclose(float(a), float(b), rel_tol=REL, abs_tol=ABS)


def comparar(cenario: dict) -> tuple[list[str], list[str], int]:
    """Devolve (divergências, nomes da planilha sem equivalente, nº comparado)."""
    py = valores_python(Entrada(**{**cenario["entrada"], **MODO_PLANILHA}))
    xl = cenario["saidas"]
    dif, sem, n = [], [], 0
    for nome, vx in xl.items():
        if nome not in py:
            sem.append(nome)
            continue
        if vx is None:          # erro (#DIV/0!, #NUM!) na planilha: não comparável
            continue
        n += 1
        if not _igual(py[nome], vx):
            dif.append(f"{nome}: python={py[nome]!r} planilha={vx!r}")
    return dif, sem, n
