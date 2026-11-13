"""Página: Dimensionamento estrutural (NBR 6118) e apresentação das armaduras."""
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from core.fases import calcular
from ui import armacao, estado, inputs, painel
from ui.formato import faixa

dados = estado.iniciar()

st.title("Dimensionamento estrutural — NBR 6118")
st.caption("Cortina, base e contrafortes do muro definido na verificação. Geometria, solos e cargas são editados na "
           "página “Verificação NBR 11682”; aqui ficam os materiais, os cobrimentos e as armaduras.")

col_e, col_r = st.columns([4, 8], gap="large")
with col_e:
    st.subheader("Materiais e armaduras")
    with st.container(height=880):
        inputs.render(dados, estrutural=True)

entrada, erro = estado.entrada_atual()
with col_r:
    st.subheader("Geometria e armaduras")
    if entrada is None:
        st.error("Dados de entrada inválidos — corrija para calcular:\n\n- " + erro.replace(" | ", "\n- "))
        st.stop()
    try:
        res = calcular(entrada)
    except Exception as ex:
        st.error(f"Não foi possível calcular com estes dados: {ex}")
        st.stop()
    st.markdown(faixa("Dimensionamento estrutural (NBR 6118): " + ("ATENDE" if res.dim.atende else "NÃO ATENDE"),
                      res.dim.atende), unsafe_allow_html=True)
    if not res.atende_estabilidade:
        st.warning("A estabilidade externa (NBR 11682) ainda não atende: a geometria pode mudar, e com ela os "
                   "esforços deste dimensionamento.")
    fig = armacao.desenho(res)
    st.pyplot(fig, width="stretch")
    plt.close(fig)
    ferros = armacao.quadro_de_ferros(res)
    st.dataframe(pd.DataFrame(armacao.tabela(ferros)), hide_index=True, width="stretch")
    if any(f.sugerido for f in ferros):
        st.caption("Posições marcadas como “sugestão” são armaduras de distribuição mínimas (NBR 6118 Tab. 19.1), "
                   "que o muro sem contrafortes não tem como dado de entrada.")
    st.caption("Desenho esquemático: posições e sentidos das barras. Comprimentos de ancoragem, emendas, dobras e "
               "estribos do contraforte não são detalhados.")

st.divider()
st.subheader("Verificações")
painel.secao_dimensionamento(res)
