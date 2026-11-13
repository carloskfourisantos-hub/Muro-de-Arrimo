"""Estado da sessão: os dados do muro ficam em ``st.session_state['dados']``.

Os widgets usam chaves ``w_<campo>``; como o Streamlit descarta o estado de
widgets que não são desenhados (troca de página), o dicionário ``dados`` é a
fonte de verdade e as chaves dos widgets são reconstruídas a partir dele.
"""
from __future__ import annotations

import streamlit as st

from core.campos import CAMPOS
from core.models import Entrada


def _de_entrada(e: Entrada) -> dict:
    d = e.model_dump(mode="json")
    for c in CAMPOS:
        if c.vinculo:
            d["vinc_" + c.nome] = d[c.nome] is None
            if d[c.nome] is None:
                d[c.nome] = d[c.vinculo]
    return d


def iniciar() -> dict:
    ss = st.session_state
    if "dados" not in ss:
        ss["dados"] = _de_entrada(Entrada())
        ss["meta"] = {"nome": "", "obra": "", "autor": ""}
    for k, v in _de_entrada(Entrada()).items():   # sessão antiga: campos criados depois
        ss["dados"].setdefault(k, v)
    if "_pendente" in ss:                      # projeto carregado / sugestão aplicada
        ss["dados"] = _de_entrada(Entrada(**ss.pop("_pendente")))
        for k in [k for k in ss if k.startswith("w_")]:
            del ss[k]
    return ss["dados"]


def aplicar(entrada: Entrada | None = None, **mudancas) -> None:
    """Agenda a troca dos dados (efetivada no início da próxima execução) e reexecuta."""
    base = entrada if entrada is not None else entrada_atual()[0]
    if base is None:
        return
    st.session_state["_pendente"] = (base.com(**mudancas) if mudancas else base).model_dump(mode="json")
    st.rerun()


def entrada_atual() -> tuple[Entrada | None, str]:
    """Constrói a Entrada validada a partir dos dados da sessão."""
    d = dict(st.session_state["dados"])
    for c in CAMPOS:
        if c.vinculo and d.pop("vinc_" + c.nome, False):
            d[c.nome] = None
    try:
        return Entrada(**d), ""
    except Exception as ex:  # pydantic.ValidationError
        msgs = []
        for err in getattr(ex, "errors", lambda: [])():
            loc = ".".join(str(p) for p in err.get("loc", ()))
            msgs.append((loc + ": " if loc else "") + err.get("msg", "").replace("Value error, ", ""))
        return None, " | ".join(msgs) or str(ex)
