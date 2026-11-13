"""Página inicial."""
import streamlit as st

from core.premissas import DIFERENCAS_DA_PLANILHA
from ui import estado, estudo_solo

st.title("Muro de arrimo")
st.markdown(
    "Aplicativo para **verificação e dimensionamento de muro de arrimo de flexão em concreto armado**, "
    "construído a partir das planilhas do escritório.")
c1, c2 = st.columns(2)
with c1:
    st.subheader("Verificação NBR 11682")
    st.markdown(
        "- Empuxo por Rankine (Mazindrani-Ganjali) ou Coulomb, com coesão, terreno inclinado, água e sobrecarga\n"
        "- Tombamento, deslizamento, excentricidade, tensões e capacidade de carga (Vesic)\n"
        "- Contrafortes, ancoragem na base, blocos de coroamento e travamento em duas fases\n"
        "- Croqui, memorial de cálculo em PDF e exportação para Excel")
    st.page_link("paginas/verificacao.py", label="Abrir a verificação", icon=":material/foundation:")
    st.subheader("Dimensionamento NBR 6118")
    st.markdown(
        "- Cortina, base e contrafortes; com contrafortes, painéis como laje com uma borda livre\n"
        "- Desenho da seção com cada armadura indicada (bitola e espaçamento)")
    st.page_link("paginas/dimensionamento.py", label="Abrir o dimensionamento", icon=":material/construction:")
with c2:
    st.subheader("Parâmetros do solo")
    st.markdown(
        "- Faixas de γ, φ, c e δ por tipo de solo e NSPT\n"
        "- Argila em condição drenada e não drenada\n"
        "- Aplicação direta ao aterro ou à fundação da verificação")
    st.page_link("paginas/solos.py", label="Abrir os parâmetros do solo", icon=":material/landslide:")

st.divider()
estado.iniciar()
estudo_solo.render()

st.divider()
st.subheader("O que muda em relação à planilha")
st.markdown("\n".join(f"- {i}" for i in DIFERENCAS_DA_PLANILHA))
st.caption("O núcleo de cálculo é conferido contra a planilha recalculada no Excel em 75 cenários (≈ 45 mil "
           "valores, tolerância 1e-8). Ferramenta de apoio: a conferência e a responsabilidade técnica são do "
           "engenheiro.")
