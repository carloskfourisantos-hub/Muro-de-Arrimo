"""Bloco "Estudo de solo" da página inicial: anexa a sondagem, define o trecho do muro,
mostra o esforço lateral e preenche a verificação."""
from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from core import perfil
from core.campos import CAMPO
from io_ import sondagem
from ui import estado, graficos
from ui.formato import num

_COLS = ["Topo (m)", "Base (m)", "Tipo de solo", "NSPT", "Aterro", "Descrição do boletim"]


def _tabela(furo: perfil.Furo) -> pd.DataFrame:
    return pd.DataFrame([{"Topo (m)": c.topo, "Base (m)": c.base, "Tipo de solo": c.tipo,
                          "NSPT": c.nspt, "Aterro": c.aterro, "Descrição do boletim": c.descricao}
                         for c in furo.camadas], columns=_COLS)


def _furo_editado(furo: perfil.Furo, df: pd.DataFrame, na: float | None) -> perfil.Furo:
    camadas = []
    for _, r in df.iterrows():
        if pd.isna(r["Topo (m)"]) or pd.isna(r["Base (m)"]) or r["Base (m)"] <= r["Topo (m)"]:
            continue
        camadas.append(perfil.Camada(float(r["Topo (m)"]), float(r["Base (m)"]), str(r["Descrição do boletim"] or ""),
                                     r["Tipo de solo"] or perfil.SEM_SOLO,
                                     None if pd.isna(r["NSPT"]) else float(r["NSPT"]), bool(r["Aterro"])))
    camadas.sort(key=lambda c: c.topo)
    return perfil.Furo(furo.nome, tuple(camadas), furo.spt, na, furo.cota, furo.avisos)


def render() -> None:
    ss = st.session_state
    st.subheader("Estudo de solo")
    st.caption("Anexe o relatório de sondagem SPT (PDF com texto). O aplicativo lê os boletins, você indica em que "
               "profundidade o muro começa e termina, e os dados do solo vão para a verificação.")
    arq = st.file_uploader("Relatório de sondagem (PDF)", type="pdf", key="up_sondagem")
    if arq is not None and ss.get("_sond_id") != arq.file_id:
        ss["_sond_id"] = arq.file_id
        try:
            leitura = sondagem.ler_pdf(arq.getvalue())
            ss["sondagem"] = {"arquivo": arq.name, "furos": leitura.furos, "avisos": leitura.avisos}
            for k in [k for k in ss if k.startswith(("sond_", "ed_sond_"))]:     # estado do estudo anterior
                del ss[k]
        except ValueError as ex:
            ss.pop("sondagem", None)
            st.error(str(ex))
    if "sondagem" not in ss:
        if st.button("Montar o perfil manualmente (sem PDF)"):
            ss["sondagem"] = {"arquivo": "perfil manual", "avisos": [], "furos": [perfil.Furo("Manual", (
                perfil.Camada(0.0, 3.0, "", "Argila siltosa", 6.0), perfil.Camada(3.0, 8.0, "", "Areia argilosa", 15.0)))]}
            st.rerun()
        return
    dados = ss["sondagem"]
    for a in dados["avisos"]:
        st.warning(a)
    furos: list[perfil.Furo] = dados["furos"]
    if not furos:
        return
    nomes = [f.nome for f in furos]
    c1, c2 = st.columns([2, 3])
    nome = c1.selectbox(f"Furo — {dados['arquivo']}", nomes, key="sond_furo")
    furo = furos[nomes.index(nome)]
    c2.markdown(f"**{len(furo.spt)}** ensaios SPT até **{num(furo.profundidade)} m** · NA lido: "
                + (f"**{num(furo.na)} m**" if furo.na is not None else "**não identificado**")
                + (f" · cota da boca: **{num(furo.cota, 3)} m**" if furo.cota is not None else ""))
    for a in furo.avisos:
        st.warning(f"{furo.nome}: {a}")

    # ---------------------------------------------------- perfil (editável)
    with st.expander("Camadas lidas do boletim — confira e corrija se preciso", expanded=bool(furo.avisos)):
        base_k = f"sond_tab_{nome}"
        if base_k not in ss:
            ss[base_k] = _tabela(furo)
        df = st.data_editor(
            ss[base_k], key=f"ed_sond_{nome}", num_rows="dynamic", hide_index=True, width="stretch",
            column_config={
                "Topo (m)": st.column_config.NumberColumn(format="%.2f", min_value=0.0, step=0.05),
                "Base (m)": st.column_config.NumberColumn(format="%.2f", min_value=0.0, step=0.05),
                "Tipo de solo": st.column_config.SelectboxColumn(options=perfil.TIPOS, required=True),
                "NSPT": st.column_config.NumberColumn(format="%.1f", min_value=0.0, max_value=100.0,
                                                      help="Média dos ensaios dentro da camada"),
                "Aterro": st.column_config.CheckboxColumn(),
                "Descrição do boletim": st.column_config.TextColumn(width="large"),
            })
        st.caption("Tipo de solo e NSPT médio saem da descrição e dos ensaios; 'Não considerar' exclui a camada "
                   "(piso, concreto, concreções, rocha).")
    tem_na = c1.checkbox("Há nível d'água", value=furo.na is not None, key=f"sond_tem_na_{nome}")
    na = None
    if tem_na:
        na = c1.number_input("Profundidade do NA (m)", 0.0, 60.0, float(furo.na if furo.na is not None else 5.0),
                             0.1, key=f"sond_na_{nome}")
    furo_ed = _furo_editado(furo, df, na)
    if not furo_ed.camadas:
        st.error("O perfil não tem camadas válidas.")
        return

    # ------------------------------------------------------ trecho do muro
    st.markdown("**Posição do muro no perfil** (profundidades medidas a partir da boca do furo)")
    prof = max(furo_ed.profundidade, 1.0)
    ent, _ = estado.entrada_atual()
    B = (ent.b_ponta + ent.t_base + ent.b_talao) if ent else 3.0
    k1, k2, k3, k4 = st.columns(4)
    z_ini = k1.number_input("Onde o muro começa — topo do terreno arrimado (m)", 0.0, float(prof - 0.5), 0.0, 0.1,
                            key=f"sond_zi_{nome}",
                            help="0 = terreno natural na boca do furo. Use um valor maior se o terreno será "
                                 "rebaixado antes do muro.")
    z_fim = k2.number_input("Onde o muro termina — fundo da sapata (m)", float(z_ini + 0.5), float(prof),
                            float(min(prof, max(z_ini + 0.5, z_ini + (ent.H_muro if ent else 4.0)))), 0.1,
                            key=f"sond_zf_{nome}")
    q = k3.number_input("Sobrecarga no terrapleno q (kPa)", 0.0, 1000.0, float(ent.q_sc if ent else 10.0), 1.0,
                        key="sond_q")
    criterio = k4.selectbox("Solo homogêneo adotado", [perfil.MEDIA, perfil.DESFAVORAVEL], key="sond_crit",
                            help="O cálculo do muro usa uma camada só de solo arrimado. O gráfico compara o "
                                 "resultado com o perfil por camadas.")
    o1, o2, o3 = st.columns(3)
    postura = o1.slider("Posição dentro da faixa de parâmetros", 0.0, 1.0, 0.0, 0.05, key="sond_post",
                        help="0 = limite inferior da faixa de literatura (a favor da segurança); 1 = superior.")
    sem_c = o2.checkbox("Desprezar a coesão do solo arrimado (c' = 0)", True, key="sond_semc",
                        help="Prática usual em muros permanentes: a coesão efetiva de longo prazo é incerta e "
                             "reduz muito o empuxo calculado.")
    nd = o3.checkbox("Fundação em argila na condição não drenada (φ = 0, c = Su)", False, key="sond_nd",
                     help="Curto prazo / fase construtiva em argila saturada.")
    if furo.cota is not None:
        st.caption(f"Em cotas: o muro vai de {num(furo.cota - z_ini)} m (topo) a {num(furo.cota - z_fim)} m "
                   "(fundo da sapata).")

    prop = perfil.propor(furo_ed, z_ini, z_fim, B, q, postura, criterio, sem_c, nd, ent.gam_w if ent else 10.0)

    # ------------------------------------------------- gráfico e parâmetros
    g1, g2 = st.columns([3, 2], gap="large")
    with g1:
        fig = graficos.grafico_esforco_lateral(furo_ed, prop, z_ini, z_fim, q)
        st.pyplot(fig, width="stretch")
        plt.close(fig)
        st.caption("Paramento vertical e terreno horizontal: ativo de Rankine por camada (σa = Ka·σ'v − 2c·√Ka, "
                   "tração zerada), repouso por Jaky (K0 = 1 − sen φ) e água à parte. É um diagrama de "
                   "anteprojeto; a verificação do muro usa a teoria e a geometria escolhidas lá.")
    with g2:
        st.markdown("**Parâmetros por camada no trecho do muro**")
        linhas = [{"Camada (m)": f"{num(e.topo)} – {num(e.base)}", "Solo": e.tipo, "NSPT": num(e.nspt, 1),
                   "γ": num(e.gama, 1), "φ (°)": num(e.phi, 1), "c (kPa)": num(e.c, 1)} for e in prop.arrimado]
        if prop.arrimado_eq:
            e = prop.arrimado_eq
            linhas.append({"Camada (m)": "ADOTADO", "Solo": criterio.split(" ")[0] + "…", "NSPT": num(e.nspt, 1),
                           "γ": num(e.gama, 1), "φ (°)": num(e.phi, 1), "c (kPa)": num(e.c, 1)})
        st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")
        st.markdown(f"**Solo de fundação** (de {num(z_fim)} m até ≈ 1,5·B abaixo)")
        linhas = [{"Camada (m)": f"{num(e.topo)} – {num(e.base)}", "Solo": e.tipo, "NSPT": num(e.nspt, 1),
                   "γ": num(e.gama, 1), "φ (°)": num(e.phi, 1), "c (kPa)": num(e.c, 1)} for e in prop.fundacao]
        if prop.fundacao_eq:
            e = prop.fundacao_eq
            linhas.append({"Camada (m)": "ADOTADO", "Solo": "", "NSPT": num(e.nspt, 1), "γ": num(e.gama, 1),
                           "φ (°)": num(e.phi, 1), "c (kPa)": num(e.c, 1)})
        st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")
        if prop.por_camadas:
            cam = prop.por_camadas
            m = st.columns(3)
            m[0].metric("Empuxo ativo", f"{num(cam.E_ativo, 1)} kN/m")
            m[1].metric("Em repouso", f"{num(cam.E_repouso, 1)} kN/m")
            m[2].metric("Água", f"{num(cam.E_agua, 1)} kN/m")
    for a in prop.avisos:
        st.warning(a)

    # --------------------------------------------- preencher a verificação
    st.markdown("**O que será preenchido na verificação**")
    st.dataframe(pd.DataFrame([{"Dado": CAMPO[k].rotulo, "Valor": num(v, 2), "Un.": CAMPO[k].unidade,
                                "Atual": num(getattr(ent, k), 2) if ent and getattr(ent, k) is not None else "—"}
                               for k, v in prop.campos.items()]), hide_index=True, width="stretch")
    st.caption("γsat é estimado como γ + 1 kN/m³ (as tabelas de solo não trazem γsat). A sobrecarga q informada "
               "acima também é levada. Larguras da base, espessuras e demais opções não são alteradas — "
               "confira-as na verificação.")
    b1, b2 = st.columns([1, 3])
    if b1.button("Preencher a verificação", type="primary", width="stretch", disabled=ent is None):
        mud = dict(prop.campos)
        mud["q_sc"] = q
        mud["beta_t"] = min(ent.beta_t, mud.get("phi_at", ent.phi_at))
        mud["cf_h"] = min(ent.cf_h, max(0.0, mud["H_muro"] - ent.h_sap))
        mud["trav_z"] = min(ent.trav_z, mud["H_muro"])
        try:
            nova = ent.com(**mud)
        except Exception as ex:
            st.error(f"Os dados do estudo não formam um muro válido: {ex}")
        else:
            ss["_sond_ok"] = f"{furo.nome}, de {num(z_ini)} a {num(z_fim)} m"
            estado.aplicar(nova)
    if "_sond_ok" in ss:
        b2.success(f"Verificação preenchida com o furo {ss.pop('_sond_ok')}.")
        st.page_link("paginas/verificacao.py", label="Abrir a verificação", icon=":material/foundation:")
