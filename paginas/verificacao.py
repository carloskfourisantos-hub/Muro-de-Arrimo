"""Página: Verificação de muro de arrimo — NBR 11682 / NBR 6118.

Aplicativo equivalente à planilha ``Verificacao_Muro_Arrimo_NBR11682.xlsx``.
"""
import hashlib
import json

import streamlit as st

from core.fases import calcular
from core.models import Entrada
from io_ import excel, memorial, projeto
from ui import estado, inputs, painel

dados = estado.iniciar()
meta = st.session_state["meta"]

# ------------------------------------------------------------------ barra lateral
with st.sidebar:
    st.subheader("Projeto")
    meta["nome"] = st.text_input("Identificação do muro", meta["nome"], placeholder="Muro M1")
    meta["obra"] = st.text_input("Obra", meta["obra"])
    meta["autor"] = st.text_input("Responsável", meta["autor"])
    refino = st.select_slider("Refinamento da integração do empuxo", [1, 2, 5, 10], 1,
                              format_func=lambda k: f"{100 * k} fatias" + (" (planilha)" if k == 1 else ""),
                              help="A planilha usa 40 + 40 + 20 fatias. Mais fatias só refinam o braço de "
                                   "alavanca e a fenda de tração (casos com coesão).")
    with st.expander("Abrir / importar"):
        arq = st.file_uploader("Projeto (.json)", type="json", key="up_json")
        if arq is not None and st.session_state.get("_up_json") != arq.file_id:
            st.session_state["_up_json"] = arq.file_id
            try:
                ent, m = projeto.carregar(arq.getvalue())
                st.session_state["meta"] = {k: m.get(k, "") for k in ("nome", "obra", "autor")}
                estado.aplicar(ent)
            except Exception as ex:
                st.error(f"Não foi possível abrir o projeto: {ex}")
        arq = st.file_uploader("Planilha original (.xlsx)", type="xlsx", key="up_xlsx",
                               help="Lê as células da aba 'Entrada' de Verificacao_Muro_Arrimo_NBR11682.xlsx")
        if arq is not None and st.session_state.get("_up_xlsx") != arq.file_id:
            st.session_state["_up_xlsx"] = arq.file_id
            try:
                estado.aplicar(excel.importar(arq))
            except Exception as ex:
                st.error(f"Não foi possível importar a planilha: {ex}")
        if st.button("Restaurar o exemplo da planilha", width="stretch"):
            estado.aplicar(Entrada())

# ------------------------------------------------------------------------- título
st.title("Verificação de muro de arrimo de flexão")
st.caption("Estabilidade externa pela ABNT NBR 11682 (tombamento, deslizamento, excentricidade, tensões e "
           "capacidade de carga) e dimensionamento estrutural pela ABNT NBR 6118 — análise por metro linear.")

col_e, col_r = st.columns([5, 7], gap="large")
with col_e:
    st.subheader("Dados de entrada")
    with st.container(height=900):
        inputs.render(dados)

entrada, erro = estado.entrada_atual()
with col_r:
    st.subheader("Resultado")
    if entrada is None:
        st.error("Dados de entrada inválidos — corrija para calcular:\n\n- " + erro.replace(" | ", "\n- "))
        st.stop()
    try:
        res = calcular(entrada, fatias=(40 * refino, 40 * refino, 20 * refino))
    except Exception as ex:  # geometria degenerada etc.
        st.error(f"Não foi possível calcular com estes dados: {ex}")
        st.stop()
    painel.resumo(res)

# ---------------------------------------------------------------------- downloads
with st.sidebar:
    st.subheader("Salvar / exportar")
    base = (meta["nome"] or "muro").strip().replace(" ", "_")
    st.download_button("Projeto (.json)", projeto.salvar(entrada, **meta), f"{base}.json", "application/json",
                       width="stretch")
    st.download_button("Resultados (.xlsx)", excel.exportar(res, meta), f"{base}_resultados.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
    marca = hashlib.md5((json.dumps(entrada.model_dump(mode="json"), sort_keys=True) + json.dumps(meta)
                         + str(refino)).encode()).hexdigest()
    if st.button("Gerar memorial de cálculo (PDF)", width="stretch"):
        with st.spinner("Montando o memorial…"):
            st.session_state["pdf"] = (marca, memorial.gerar_pdf(res, meta))
    if st.session_state.get("pdf", ("", b""))[0] == marca:
        st.download_button("Baixar memorial (.pdf)", st.session_state["pdf"][1], f"{base}_memorial.pdf",
                           "application/pdf", width="stretch", type="primary")

# ------------------------------------------------------------------- detalhamento
st.divider()
secao = st.segmented_control("Detalhamento", painel.SECOES, default="Resultados", key="secao",
                             label_visibility="collapsed") or "Resultados"
if secao == "Premissas":
    painel.secao_premissas()
else:
    painel.RENDER[secao](res)
