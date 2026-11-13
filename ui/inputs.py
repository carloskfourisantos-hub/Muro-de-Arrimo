"""Widgets de entrada, gerados a partir de ``core.campos.CAMPOS`` (espelho da aba Entrada)."""
from __future__ import annotations

import streamlit as st

from core.campos import CAMPO, CAMPOS, SECOES
from core.enums import ENUM_DO_CAMPO, OPCOES_LEGADAS

BITOLAS = [5.0, 6.3, 8.0, 10.0, 12.5, 16.0, 20.0, 25.0, 32.0]
TITULOS = {
    "1.": "1 · Geometria do muro", "2.": "2 · Contrafortes", "2b.": "2b · Ancoragem na base (estacas)",
    "2c.": "2c · Blocos de coroamento", "2d.": "2d · Travamento do muro", "3.": "3 · Terrapleno e sobrecarga",
    "4.": "4 · Solo arrimado (aterro)", "5.": "5 · Solo de fundação", "6.": "6 · Água", "7.": "7 · Material",
    "8.": "8 · Capacidade de carga da fundação", "9.": "9 · Fatores de segurança mínimos (NBR 11682)",
    "10.": "10 · Dimensionamento estrutural (NBR 6118)", "10b.": "10b · Contrafortes — lajes e viga (NBR 6118)",
}
CHAVE_DA_SECAO = {"2.": "cf_usar", "2b.": "anc_usar", "2c.": "bl_usar", "2d.": "trav_usar", "10b.": "cf_usar"}
PASSO = {"m": 0.05, "°": 1.0, "kPa": 1.0, "kN/m³": 0.5, "-": 0.05, "cm": 0.5, "mm": 1.0, "MPa": 5.0, "kN": 5.0,
         "kN/m": 5.0, "un": 1.0}
FORMATO = {"m": "%.2f", "°": "%.1f", "kPa": "%.1f", "kN/m³": "%.1f", "-": "%.3f", "cm": "%.1f", "mm": "%.1f",
           "MPa": "%.0f", "kN": "%.1f", "kN/m": "%.1f"}


def _habilitado(nome: str, d: dict, sec: str) -> bool:
    chave = CHAVE_DA_SECAO.get(sec)
    if chave and nome != chave and not d[chave]:
        return False
    if nome == "rk_conv":
        return d["metodo_emp"] == "Rankine"
    if nome == "delta_dv":
        return d["metodo_emp"] == "Coulomb"
    if nome == "qult_inf":
        return d["cc_modo"] == "Informada"
    if nome == "anc_x2":
        return d["anc_n2"] > 0
    if nome == "bl_x":
        return d["bl_pos"] == "Posição informada"
    if nome == "anc_x":          # com bloco de posição própria e uma só linha, a estaca fica no eixo do bloco
        return not (d["bl_usar"] and d["bl_pos"] != "Centrado nas estacas (planilha)" and d["anc_n2"] == 0)
    if nome in ("trav_z", "trav_F", "trav_conv", "trav_emp"):
        return d["trav_usar"]
    return True


def _rotulo(c) -> str:
    return c.rotulo if c.unidade in ("-", "un") else f"{c.rotulo} ({c.unidade})"


def _widget(c, d: dict, sec: str) -> None:
    ss = st.session_state
    k = "w_" + c.nome
    off = not _habilitado(c.nome, d, sec)
    ajuda = c.ajuda or None
    if c.tipo == "bool":
        ss.setdefault(k, bool(d[c.nome]))
        d[c.nome] = st.toggle(_rotulo(c), key=k, help=ajuda, disabled=off)
        return
    if c.tipo == "enum":
        opcoes = [m.value for m in ENUM_DO_CAMPO[c.nome]]
        legadas = {m.value for m in OPCOES_LEGADAS.get(c.nome, ())}
        ss.setdefault(k, d[c.nome])
        d[c.nome] = st.selectbox(_rotulo(c), opcoes, key=k, help=ajuda, disabled=off,
                                 format_func=lambda o: o + ("  ·  legado" if o in legadas else ""))
        if d[c.nome] in legadas and not off:
            st.caption("⚠ Opção legada: reproduz o GEO5 e se afasta do critério padrão.")
        return
    if c.nome.endswith("_phi") and c.unidade == "mm":
        opcoes = sorted(set(BITOLAS) | {float(d[c.nome])})
        ss.setdefault(k, float(d[c.nome]))
        d[c.nome] = st.selectbox(_rotulo(c), opcoes, key=k, help=ajuda, disabled=off,
                                 format_func=lambda v: f"ϕ {v:g}".replace(".", ","))
        return
    if c.vinculo:
        kv = "w_vinc_" + c.nome
        ss.setdefault(kv, bool(d["vinc_" + c.nome]))
        d["vinc_" + c.nome] = st.checkbox(f"{c.rotulo}: igual a “{CAMPO[c.vinculo].rotulo}”", key=kv,
                                          help=ajuda, disabled=off)
        if d["vinc_" + c.nome]:
            d[c.nome] = d[c.vinculo]
            return
    if c.tipo == "int":
        ss.setdefault(k, int(d[c.nome]))
        d[c.nome] = st.number_input(_rotulo(c), min_value=int(c.minimo), max_value=int(c.maximo), step=1, key=k,
                                    help=ajuda, disabled=off)
        return
    ss.setdefault(k, float(d[c.nome]))
    d[c.nome] = st.number_input(_rotulo(c), min_value=float(c.minimo), max_value=float(c.maximo),
                                step=PASSO.get(c.unidade, 0.1), format=FORMATO.get(c.unidade, "%.2f"), key=k,
                                help=ajuda, disabled=off)


ESTRUTURAL = ("10.", "10b.")      # seções da página de Dimensionamento


def render(d: dict, estrutural: bool = False) -> None:
    """Desenha as seções de entrada e atualiza ``d`` (dados da sessão).

    ``estrutural=False``: seções 1 a 9 (página de verificação); ``True``: seções 10 e 10b.
    """
    for sec in SECOES:
        pref = sec.split(" ")[0]
        if (pref in ESTRUTURAL) != estrutural:
            continue
        chave = CHAVE_DA_SECAO.get(pref)
        titulo = TITULOS.get(pref, sec)
        if chave and pref != "10b.":
            titulo += "  — ativo" if d[chave] else ""
        with st.expander(titulo, expanded=pref in ("1.", "10.") or (pref == "10b." and d["cf_usar"])):
            if pref == "10b." and not d["cf_usar"]:
                st.caption("Só se aplica a muro com contrafortes (seção 2).")
            for c in (x for x in CAMPOS if x.secao == sec):
                _widget(c, d, pref)
