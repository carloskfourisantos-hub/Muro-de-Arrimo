"""Página: parâmetros de solo recomendados por NSPT (anteprojeto)."""
import pandas as pd
import streamlit as st

from core import solos
from ui import estado
from ui.formato import num

estado.iniciar()
st.title("Parâmetros do solo por NSPT")
st.caption("Faixas de literatura para uso preliminar/anteprojeto (tabelas de Parametros_do_solo_Recomendado.xlsx). "
           "Nenhuma correlação substitui sondagem e ensaios quando a obra justificar.")

c1, c2 = st.columns([2, 3], gap="large")
with c1:
    tipo = st.selectbox("Tipo de solo", solos.TIPOS)
    nspt = st.number_input("NSPT", 0, 80, 12)
    eh_argila = tipo.startswith("Argila")
    nao_dren = st.toggle("Condição não drenada (curto prazo): φu = 0 e c = Su", value=False, disabled=not eh_argila,
                         help="Argila saturada em fase construtiva, escavação ou carregamento rápido.")
    postura = st.slider("Posição dentro da faixa", 0.0, 1.0, 0.0, 0.05,
                        help="0 = limite inferior da faixa (conservador para resistência); 1 = limite superior.")
    s = solos.sugerir(tipo, nspt, postura, nao_dren and eh_argila)
    cl = s.classe
    st.markdown(f"**Classificação:** {cl.nome.lower()} — NSPT {cl.nspt[0]:g} a "
                + ("∞" if cl.nspt[1] == float("inf") else f"{cl.nspt[1]:g}"))

with c2:
    m = st.columns(4)
    m[0].metric("γ (kN/m³)", num(s.gama, 1))
    m[1].metric("φ (°)", num(s.phi, 1))
    m[2].metric("c (kPa)", num(s.c, 1))
    m[3].metric("δ solo-estrutura (°)", num(s.delta, 1))
    faixa = lambda f, casas=0: f"{num(f[0], casas)} a {num(f[1], casas)}"  # noqa: E731
    linhas = [
        {"Parâmetro": "Peso específico γ", "Faixa": faixa(cl.gama), "Un.": "kN/m³"},
        {"Parâmetro": "Ângulo de atrito φ" + ("' (drenado)" if eh_argila else ""), "Faixa": faixa(cl.phi), "Un.": "°"},
        {"Parâmetro": "Coesão c" + ("' (drenado)" if eh_argila else ""), "Faixa": faixa(cl.c), "Un.": "kPa"},
        {"Parâmetro": "δ / φ (atrito solo-estrutura)", "Faixa": faixa(cl.delta_phi, 2), "Un.": "-"},
        {"Parâmetro": "Ligação limite / adesão", "Faixa": faixa(cl.adesao), "Un.": "kPa"},
        {"Parâmetro": "Capacidade de carga última indicativa", "Faixa": faixa(cl.qult), "Un.": "kPa"},
    ]
    if cl.su:
        linhas.insert(3, {"Parâmetro": "Su (não drenado, φu = 0)", "Faixa": faixa(cl.su), "Un.": "kPa"})
    st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")
    for o in s.obs:
        st.info(o)

st.subheader("Usar na verificação do muro")
a1, a2 = st.columns(2)
with a1:
    st.markdown(f"**Como solo arrimado (aterro):** γ = {num(s.gama, 1)} · φ' = {num(s.phi, 1)} · c' = {num(s.c, 1)} · "
                f"δ estrutura-solo = {num(s.delta, 1)}")
    if s.phi < 5:
        st.warning("φ < 5° não é aceito para o aterro (teorias de empuxo com atrito). Use a condição drenada.")
    elif st.button("Aplicar ao aterro", width="stretch"):
        ent, _ = estado.entrada_atual()
        if ent is not None:
            st.session_state["_aplicado"] = "aterro"
            estado.aplicar(ent, gam_at=round(s.gama, 1), gsat_at=max(ent.gsat_at, round(s.gama, 1)),
                           phi_at=round(s.phi, 1), c_at=round(s.c, 1), delta_est=round(s.delta, 1),
                           beta_t=min(ent.beta_t, round(s.phi, 1)))
with a2:
    st.markdown(f"**Como solo de fundação:** γf = {num(s.gama, 1)} · φf = {num(s.phi, 1)} · cf = {num(s.c, 1)}")
    if st.button("Aplicar à fundação", width="stretch"):
        ent, _ = estado.entrada_atual()
        if ent is not None:
            st.session_state["_aplicado"] = "fundação"
            estado.aplicar(ent, gam_f=round(s.gama, 1), gsat_f=max(ent.gsat_f, round(s.gama, 1)),
                           phi_f=round(s.phi, 1), c_f=round(s.c, 1))
if "_aplicado" in st.session_state:
    st.success(f"Parâmetros aplicados ao solo de {st.session_state.pop('_aplicado')}. Abra a página "
               "“Verificação NBR 11682” para ver o resultado. O peso específico saturado só foi ajustado se "
               "estava menor que o natural — confira-o.")

with st.expander("Tabelas completas"):
    for nome, tab in solos.TABELAS.items():
        st.markdown(f"**{nome}**")
        st.dataframe(pd.DataFrame([{
            "Classe": c.nome, "NSPT": f"{c.nspt[0]:g} a {c.nspt[1]:g}".replace("a inf", "ou mais"),
            "γ (kN/m³)": faixa(c.gama), "φ (°)": faixa(c.phi), "c (kPa)": faixa(c.c),
            **({"Su (kPa)": faixa(c.su)} if c.su else {}), "δ/φ": faixa(c.delta_phi, 2),
            "Adesão (kPa)": faixa(c.adesao), "qult indicativa (kPa)": faixa(c.qult)} for c in tab]),
            hide_index=True, width="stretch")
    st.markdown("**Solos mistos — correção sobre o solo base**")
    st.dataframe(pd.DataFrame([{
        "Solo": k, "Solo base": b, "φ": f"{d:+g}°", "Coesão": {"x": f"× {v:g}", "+": f"+ {v:g} kPa",
                                                              "=": f"= {v:g} kPa"}[op].replace(".", ","),
        "δ": f"{dd:+g}°"} for k, (b, d, (op, v), dd) in solos.MISTOS.items()]), hide_index=True, width="stretch")
with st.expander("Correlações rápidas para o NSPT informado"):
    st.dataframe(pd.DataFrame([{"Correlação": k, "Valor": num(v, 1)} for k, v in solos.correlacoes(nspt).items()]),
                 hide_index=True, width="stretch")
with st.expander("Fontes"):
    st.markdown("\n".join(f"- {f}" for f in solos.FONTES))
