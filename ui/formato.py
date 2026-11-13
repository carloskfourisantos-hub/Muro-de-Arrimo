"""Formatação pt-BR (vírgula decimal) e pequenos componentes HTML."""
from __future__ import annotations

import math

OK_COR, NOK_COR, NEUTRO = "#0ca30c", "#d03b3b", "#898781"


def num(v, casas: int = 2, vazio: str = "—") -> str:
    """Número com vírgula decimal; ``inf``/``None`` viram travessão."""
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return vazio
    s = f"{v:,.{casas}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def fs(v, casas: int = 2) -> str:
    """Fator de segurança: infinito = sem ação instabilizante."""
    if isinstance(v, float) and math.isinf(v):
        return "∞"
    return num(v, casas)


def selo(ok: bool | None, sim: str = "OK", nao: str = "NÃO OK") -> str:
    if ok is None:
        return f"<span style='color:{NEUTRO}'>—</span>"
    cor, txt, ic = (OK_COR, sim, "✔") if ok else (NOK_COR, nao, "✖")
    return f"<span style='color:{cor};font-weight:600'>{ic} {txt}</span>"


def cartao(titulo: str, valor: str, limite: str, ok: bool) -> str:
    cor = OK_COR if ok else NOK_COR
    return (
        f"<div style='border:1px solid rgba(128,128,128,.25);border-left:5px solid {cor};border-radius:8px;"
        f"padding:.55rem .8rem;margin-bottom:.5rem'>"
        f"<div style='font-size:.78rem;opacity:.75'>{titulo}</div>"
        f"<div style='font-size:1.55rem;font-weight:650;line-height:1.25'>{valor}</div>"
        f"<div style='font-size:.78rem'>{limite} &nbsp; {selo(ok)}</div></div>")


def faixa(texto: str, ok: bool) -> str:
    cor = OK_COR if ok else NOK_COR
    ic = "✔" if ok else "✖"
    return (f"<div style='border:1px solid {cor};border-radius:8px;padding:.5rem .8rem;margin-bottom:.5rem;"
            f"font-weight:650'><span style='color:{cor}'>{ic}</span> {texto}</div>")
