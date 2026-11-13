"""Muro de arrimo — ponto de entrada do Streamlit.

Executar:  .venv\\Scripts\\streamlit run app.py
"""
import streamlit as st

st.set_page_config(page_title="Muro de arrimo", page_icon=":material/foundation:", layout="wide")

pagina = st.navigation([
    st.Page("paginas/inicio.py", title="Início", icon=":material/home:", default=True),
    st.Page("paginas/verificacao.py", title="Verificação NBR 11682", icon=":material/foundation:"),
    st.Page("paginas/dimensionamento.py", title="Dimensionamento NBR 6118", icon=":material/construction:"),
    st.Page("paginas/solos.py", title="Parâmetros do solo", icon=":material/landslide:"),
])
pagina.run()
