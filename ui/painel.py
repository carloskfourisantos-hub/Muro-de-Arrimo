"""Painel de resultados da página de verificação."""
from __future__ import annotations

import math

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

from core.campos import CAMPO, CAMPOS
from core.fases import Resultado, calcular, travamento_minimo_exato
from core.premissas import DIFERENCAS_DA_PLANILHA, PREMISSAS
from core.solver import base_minima, estabilidade_ok, estudo_parametrico, menor_valor, sugerir_armaduras
from ui import armacao, estado, graficos
from ui.formato import cartao, faixa, fs, num

SECOES = ["Resultados", "Forças", "Empuxo", "Geometria", "Capacidade de carga", "Ferramentas", "Premissas"]
_OK = {True: "✔ OK", False: "✖ NÃO OK", None: "—"}


def _fig(fig) -> None:
    st.pyplot(fig, width="stretch")
    plt.close(fig)


def _tabela(linhas: list[dict], altura: int | None = None) -> None:
    kw = {"height": altura} if altura else {}
    st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch", **kw)


def _fases(res: Resultado):
    return [res.fase1] + ([res.fase2] if res.tem_fase2 else [])


# ============================================================================ topo
def resumo(res: Resultado) -> None:
    e = res.entrada
    fases = _fases(res)
    st.markdown(faixa("Estabilidade externa (NBR 11682): " + ("ATENDE" if res.atende_estabilidade else "NÃO ATENDE"),
                      res.atende_estabilidade)
                + faixa("Dimensionamento estrutural (NBR 6118): " + ("ATENDE" if res.dim.atende else "NÃO ATENDE"),
                        res.dim.atende), unsafe_allow_html=True)
    st.page_link("paginas/dimensionamento.py", label="Abrir o dimensionamento e o desenho das armaduras",
                 icon=":material/construction:")
    pior = lambda attr, f=min: f(getattr(x.verif, attr) for x in fases)  # noqa: E731
    na_faixa = any(f.verif.exc_faixa for f in fases)
    cols = st.columns(4)
    itens = [
        ("FS tombamento", fs(pior("R_FSt")), f"mín. {num(e.FSt_min)}", all(f.verif.ok_tomb for f in fases)),
        ("FS deslizamento", fs(pior("R_FSd")), f"mín. {num(e.FSd_min)}", all(f.verif.ok_desl for f in fases)),
        ("Excentricidade e/B", num(pior("R_eB", max), 3),
         f"máx. {num(e.eB_lim, 3)}" + (" · até 0,250 com base verificada" if na_faixa else ""),
         all(f.verif.exc_aceita for f in fases)),
        ("FS capacidade de carga", fs(pior("R_FScc")), f"mín. {num(e.FScc_min)}", all(f.verif.ok_cap for f in fases)),
    ]
    for col, (t, v, lim, ok) in zip(cols, itens):
        col.markdown(cartao(t, v, lim, ok), unsafe_allow_html=True)
    if na_faixa:
        d = res.dim.v
        falta = [f"{rot}: faltam {num(d[k])} cm²/m na face {d[fc]}" if d[k] == d[k] else f"{rot}: seção insuficiente"
                 for rot, k, fc in (("ponta", "ex_dAs_pt", "ex_face_pt"), ("talão", "ex_dAs_tl", "ex_face_tl"))
                 if d[k] != 0]
        st.warning(f"Excentricidade entre o limite ({num(e.eB_lim, 3)}) e B/4: a base descola em "
                   f"{num(d['ex_Ldesc'])} m ({num(100 * d['ex_frac'], 0)} % de B comprimidos). A excentricidade só é aceita "
                   "porque a base foi verificada à flexão com a distribuição triangular de tensões — "
                   + ("a armadura adotada na base é suficiente." if not falta else "; ".join(falta) + ".")
                   + " Detalhes nas verificações “Base com descolamento” do dimensionamento.")
    if res.tem_fase2:
        st.caption("Com travamento: os cartões mostram o pior valor entre a Fase 1 (construtiva) e a Fase 2 "
                   "(muro travado).")
    for f in fases:
        for a in f.avisos:
            (st.error if a.nivel == "erro" else st.warning if a.nivel == "alerta" else st.info)(
                f"Fase {f.numero}: {a.texto}" if res.tem_fase2 else a.texto)
    if res.atende_estabilidade is False and all(f.verif.verificacoes_ok for f in fases):
        st.caption("As quatro verificações passam, mas há avisos de consistência pendentes — como na planilha, "
                   "o resultado só é 'ATENDE' sem avisos.")
    leg = e.opcoes_legadas_ativas()
    if leg:
        st.warning("**Opções legadas (compatibilidade GEO5) ativas:** " + "; ".join(leg))
    fase = 1
    if res.tem_fase2:
        fase = st.segmented_control("Croqui", [1, 2], default=1, format_func=lambda n: f"Fase {n}",
                                    key="croqui_fase", label_visibility="collapsed") or 1
    _fig(graficos.croqui(res, fase))


# ====================================================================== resultados
def secao_resultados(res: Resultado) -> None:
    e = res.entrada
    fases = _fases(res)

    def lin(rot, vals, lim, oks, un):
        d = {"Verificação": rot}
        for f, v in zip(fases, vals):
            d[f"Fase {f.numero}"] = v
        d.update({"Mínimo / limite": lim, "Unidade": un, "Situação": _OK[oks]})
        return d
    V, F = [f.verif for f in fases], [f.forcas for f in fases]
    linhas = [
        lin("Momento estabilizante Mres", [num(f.F_Mres) for f in F], "", None, "kN·m/m"),
        lin("Momento tombador Movr", [num(f.F_Movr) for f in F], "", None, "kN·m/m"),
        lin("FS ao tombamento = Mres / Movr", [fs(v.R_FSt) for v in V], f"≥ {num(e.FSt_min)}",
            all(v.ok_tomb for v in V), "-"),
        lin("Força normal na base N", [num(f.F_N) for f in F], "", None, "kN/m"),
        lin("Força horizontal atuante H_act", [num(v.R_Hact) for v in V], "", None, "kN/m"),
        lin("Resistência: N·tan δb", [num(v.Hres_atrito) for v in V], "", None, "kN/m"),
        lin("Resistência: a·B'", [num(v.Hres_adesao) for v in V], "", None, "kN/m"),
        lin("Resistência: forças horizontais resistentes", [num(v.Hres_externas) for v in V], "", None, "kN/m"),
        lin("Resistência: carga lateral das estacas", [num(v.Hres_estacas) for v in V], "", None, "kN/m"),
        lin("Força resistente total H_res", [num(v.R_Hres) for v in V], "", None, "kN/m"),
        lin("FS ao deslizamento = H_res / H_act", [fs(v.R_FSd) for v in V], f"≥ {num(e.FSd_min)}",
            all(v.ok_desl for v in V), "-"),
        lin("Posição da resultante xR", [num(v.R_xR, 3) for v in V], "", None, "m"),
        lin("Excentricidade e = B/2 − xR", [num(v.R_e, 3) for v in V], "", None, "m"),
        lin("e / B", [num(v.R_eB, 3) for v in V], f"≤ {num(e.eB_lim, 3)}" + (" (até 0,250 com base verificada)" if any(v.exc_faixa for v in V) else ""),
            all(v.exc_aceita for v in V), "-"),
        lin("Fração comprimida da base (linear, sem tração)", [num(100 * v.frac_comp, 0) + " %" for v in V],
            "", None, "-"),
        lin("Base efetiva B'", [num(v.R_Bef, 3) for v in V], "", None, "m"),
        lin("Tensão máxima σmáx (linear)", [num(v.sig_max, 1, "fora da base") + f" ({v.sig_max_em})" for v in V],
            "", None, "kPa"),
        lin("Tensão mínima σmín (linear)", [num(v.sig_min, 1) for v in V], "", None, "kPa"),
        lin("Tensão de Meyerhof σef = N / B'", [num(v.R_sef, 1, "fora da base") for v in V], "", None, "kPa"),
        lin("Capacidade de carga de ruptura qult", [num(v.R_qult, 1) for v in V], "", None, "kPa"),
        lin("FS à capacidade de carga = qult / σef", [fs(v.R_FScc) for v in V], f"≥ {num(e.FScc_min)}",
            all(v.ok_cap for v in V), "-"),
        lin("Resultado da fase", ["ATENDE" if f.atende else "NÃO ATENDE" for f in fases], "",
            all(f.atende for f in fases), ""),
    ]
    c1, c2 = st.columns([3, 2])
    with c1:
        _tabela(linhas, 775)
    with c2:
        _fig(graficos.diagrama_base(res))
        if res.tem_fase2:
            t = res.trav
            st.markdown("**Força mínima no travamento (estimativa da planilha, e fixo)**")
            _tabela([
                {"Item": "Força considerada agora", "kN/m": num(t.TR_T)},
                {"Item": "Mínima para FS ao tombamento", "kN/m": num(t.TR_Ft)},
                {"Item": "Mínima para FS ao deslizamento", "kN/m": num(t.TR_Fd)},
                {"Item": "Mínima necessária", "kN/m": num(t.TR_Freq)},
                {"Item": "Referência: empuxo horizontal total", "kN/m": num(t.TR_Fd_k0)},
            ])
            st.caption("O valor exato (recalculando a Fase 2) está em **Ferramentas**.")


# ========================================================================== forças
def secao_forcas(res: Resultado) -> None:
    st.caption("Convenção: Fx > 0 empurra o muro para a frente (instabilizante); Fz > 0 para baixo. x a partir da "
               "ponta; z a partir do fundo da sapata. Momentos em torno da aresta inferior da ponta.")
    for f in _fases(res):
        st.markdown(f"**Fase {f.numero}** — " + ("construtiva, sem travamento" if f.numero == 1 else "muro travado"))
        linhas = [{"Força": ln.nome, "Fx (kN/m)": ln.Fx, "Fz (kN/m)": ln.Fz, "x (m)": ln.x, "z (m)": ln.z,
                   "M estabilizante (kN·m/m)": ln.Mres, "M tombador (kN·m/m)": ln.Movr, "Observação": ln.obs}
                  for ln in f.forcas.linhas]
        F = f.forcas
        linhas.append({"Força": "TOTAIS", "Fx (kN/m)": F.F_Hnet, "Fz (kN/m)": F.F_N, "x (m)": None, "z (m)": None,
                       "M estabilizante (kN·m/m)": F.F_Mres, "M tombador (kN·m/m)": F.F_Movr, "Observação": ""})
        df = pd.DataFrame(linhas)
        cols_num = [c for c in df.columns if "(" in c]
        fmt = {c: (lambda v, casas=(3 if "(m)" in c else 2): num(v, casas, "")) for c in cols_num}
        st.dataframe(df.style.format(fmt, na_rep=""), hide_index=True, width="stretch", height=668)
        a = F.anc
        if res.entrada.anc_usar or res.entrada.bl_usar:
            st.caption(f"Ancoragem: arrancamento Tp = {num(a.anc_Tp, 1)} kN; barra Rt = {num(a.anc_Rt, 1)} kN; "
                       f"força por estaca = {num(a.anc_Fe, 1)} kN; total = {num(a.anc_F, 1)} kN/m; resistência "
                       f"horizontal = {num(a.anc_Hm, 1)} kN/m; peso de um bloco = {num(a.bl_P, 1)} kN.")


# ========================================================================== empuxo
def secao_empuxo(res: Resultado) -> None:
    fases = _fases(res)
    fase = fases[0]
    if len(fases) > 1:
        n = st.segmented_control("Fase", [1, 2], default=1, format_func=lambda n: f"Fase {n}", key="emp_fase") or 1
        fase = fases[n - 1]
    emp = fase.emp
    c1, c2 = st.columns([2, 3])
    with c1:
        _tabela([
            {"Grandeza": "Empuxo resultante Pa", "Valor": num(emp.p_Pa), "Un.": "kN/m"},
            {"Grandeza": "Componente horizontal Pa,h", "Valor": num(emp.p_Pah), "Un.": "kN/m"},
            {"Grandeza": "   parcela do solo", "Valor": num(emp.p_Pah_s), "Un.": "kN/m"},
            {"Grandeza": "   parcela da sobrecarga", "Valor": num(emp.p_Pah_q), "Un.": "kN/m"},
            {"Grandeza": "Cota de aplicação de Pa,h", "Valor": num(emp.p_zPa, 3), "Un.": "m"},
            {"Grandeza": "Componente vertical Pa,v adotada", "Valor": num(emp.p_Pav), "Un.": "kN/m"},
            {"Grandeza": "x de aplicação de Pa,v", "Valor": num(emp.p_xPav, 3), "Un.": "m"},
            {"Grandeza": "Empuxo hidrostático atrás Uh", "Valor": num(emp.p_U), "Un.": "kN/m"},
            {"Grandeza": "Empuxo hidrostático na frente Uf", "Valor": num(emp.p_Uf), "Un.": "kN/m"},
            {"Grandeza": "Resistência na face frontal Rff", "Valor": num(emp.p_Rff), "Un.": "kN/m"},
            {"Grandeza": "Subpressão (ponta / talão)", "Valor": f"{num(emp.p_u0, 1)} / {num(emp.p_uB, 1)}",
             "Un.": "kPa"},
            {"Grandeza": "Subpressão resultante", "Valor": num(emp.p_Usub), "Un.": "kN/m"},
            {"Grandeza": "K0 (repouso)", "Valor": num(emp.p_K0, 4), "Un.": "-"},
            {"Grandeza": "Ka Rankine (c = 0)", "Valor": num(emp.p_KaR, 4), "Un.": "-"},
        ], 528)
        st.caption("Empuxo em repouso (K0)" if emp.p_rep else f"Teoria: {res.entrada.metodo_emp.value} — cunha "
                   f"{res.entrada.modo_cunha.value}")
    with c2:
        _fig(graficos.diagrama_empuxo(res, fase.numero))
    with st.expander("Tabela de fatias da integração (auditoria)"):
        t = emp.fatias
        df = pd.DataFrame({
            "z (m)": t["z"], "Trecho": t["trecho"], "α (°)": np.degrees(t["alfa"]), "δ (°)": np.degrees(t["delta"]),
            "x do plano (m)": t["x"], "σz' (kPa)": t["sz"], "K' Mazindrani": t["Kp"], "Ka Coulomb": t["Ka"],
            "Kac": t["Kac"], "σa (kPa)": t["sa"], "Δ (m)": t["dz"], "dPa,h (kN/m)": t["dPah"],
            "dPa,v (kN/m)": t["dPav"]})
        st.dataframe(df, hide_index=True, width="stretch", height=380)


# ======================================================================= geometria
def secao_geometria(res: Resultado) -> None:
    g, e = res.geo, res.entrada
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Parâmetros derivados**")
        _tabela([
            {"Parâmetro": "Altura da cortina hc = H − hs", "Valor": num(g.h_cort, 3), "Un.": "m"},
            {"Parâmetro": "Largura da base B", "Valor": num(g.B_base, 3), "Un.": "m"},
            {"Parâmetro": "x da face frontal (base / topo)", "Valor": f"{num(g.x_fb, 3)} / {num(g.x_ft, 3)}",
             "Un.": "m"},
            {"Parâmetro": "x do tardoz (base / topo)", "Valor": f"{num(g.x_tb, 3)} / {num(g.x_tt, 3)}", "Un.": "m"},
            {"Parâmetro": "Cota do terreno junto ao tardoz", "Valor": num(g.z_ter, 3), "Un.": "m"},
            {"Parâmetro": "Altura do dorso virtual (x = B)", "Valor": num(g.z_dv, 3), "Un.": "m"},
            {"Parâmetro": "Inclinação do tardoz com a vertical α", "Valor": num(math.degrees(g.a_t), 2), "Un.": "°"},
            {"Parâmetro": "Inclinação do plano da cunha θ", "Valor": num(math.degrees(g.th_c), 2), "Un.": "°"},
            {"Parâmetro": "Ponto P (topo do plano inclinado) x / z", "Valor": f"{num(g.x_P, 3)} / {num(g.z_P, 3)}",
             "Un.": "m"},
            {"Parâmetro": "Cota do topo do plano de cálculo", "Valor": num(g.z_top_pl, 3), "Un.": "m"},
            {"Parâmetro": "Dorso virtual vertical ativo?", "Valor": "sim" if g.cv else "não", "Un.": "-"},
            {"Parâmetro": "Plano atinge o terreno antes do tardoz?", "Valor": "sim" if g.hit_t else "não",
             "Un.": "-"},
        ], 458)
    with c2:
        st.markdown("**Polígonos — área e centroide (por metro de muro)**")
        _tabela([{"Polígono": p.nome, "Área (m²)": num(p.A, 4), "x (m)": num(p.x, 4), "z (m)": num(p.z, 4)}
                 for p in (g.cortina, g.sapata, g.solo, g.solo_na, g.contraforte, g.solo_ponta)])
        vol = g.cortina.A + g.sapata.A + (g.contraforte.A * e.cf_t / e.cf_esp if e.cf_usar else 0.0)
        st.metric("Volume de concreto", f"{num(vol, 3)} m³/m")
        st.caption("Origem na aresta inferior da ponta; x positivo para o aterro, z para cima.")


# ====================================================================== capacidade
def secao_capacidade(res: Resultado) -> None:
    e = res.entrada
    if e.cc_modo.value == "Informada":
        st.info(f"qult informada pelo usuário: {num(e.qult_inf, 1)} kPa. Os fatores abaixo são apenas referência.")
    linhas = []
    itens = [("φf", "CC_phi", "rad", 4), ("Nq = e^(π·tanφ)·tan²(45° + φ/2)", "CC_Nq", "-", 3),
             ("Nc = (Nq − 1)·cotφ (5,14 para φ = 0)", "CC_Nc", "-", 3), ("Nγ = 2·(Nq + 1)·tanφ (Vesic)", "CC_Ng", "-", 3),
             ("Sobrecarga no nível da base q0", "CC_q0", "kPa", 2), ("γ abaixo da base", "CC_g", "kN/m³", 2),
             ("Força horizontal líquida H", "CC_H", "kN/m", 2), ("1 − H/(N + B'·c·cotφ)", "CC_m", "-", 4),
             ("iq = (…)²", "CC_iq", "-", 4), ("iγ = (…)³", "CC_ig", "-", 4), ("ic", "CC_ic", "-", 4),
             ("qult = c·Nc·ic + q0·Nq·iq + 0,5·γ·B'·Nγ·iγ", "CC_qult", "kPa", 1)]
    fases = _fases(res)
    for rot, k, un, casas in itens:
        d = {"Grandeza": rot}
        for f in fases:
            d[f"Fase {f.numero}"] = num(getattr(f.verif.cap, k), casas)
        d["Un."] = un
        linhas.append(d)
    _tabela(linhas)
    st.caption("Vesic, sapata corrida (m = 2), base efetiva B' = B − 2|e|, com fatores de inclinação e sem fatores "
               "de profundidade (a favor da segurança).")


# ================================================================== dimensionamento
def secao_dimensionamento(res: Resultado) -> None:
    d, e, c = res.dim, res.entrada, res.dim.concreto
    st.caption(f"fcd = {num(c.fcd)} MPa · fyd = {num(c.fyd, 1)} MPa · fctm = {num(c.fctm, 3)} MPa · fctd = "
               f"{num(c.fctd, 3)} MPa · ρmín = {num(c.rho_min * 100, 3)} % · γf = {num(e.gf_f)} · K0 = "
               f"{num(d.v['dm_K0'], 3)} · Ka (tardoz) = {num(d.v['dm_KaC'], 3)}")
    linhas = []
    for ch in d.checks + d.extras:
        if ch.situacao == "—":
            continue
        casas = 3 if ch.unidade == "-" else 2
        sol = "insuficiente" if (ch.solicitante < 0 and "As ef" in ch.nome) else num(ch.solicitante, casas)
        linhas.append({"Elemento": ch.grupo, "Verificação": ch.nome, "Solicitante": sol,
                       "Resistente / limite": num(ch.resistente, casas), "Un.": ch.unidade,
                       "Situação": _OK[ch.situacao == "OK"], "Origem": "aplicativo" if ch.extra else "planilha"})
    _tabela(linhas, min(38 * len(linhas) + 40, 760))
    for n in d.notas:
        st.info(n) if "Resultante fora" not in n else st.error(n)
    if st.button("Sugerir armaduras (menor área de aço que atende)", key="bt_sug"):
        nova, sug = sugerir_armaduras(e)
        st.session_state["sugestao"] = (nova.model_dump(mode="json"), sug)
    if "sugestao" in st.session_state:
        dados, sug = st.session_state["sugestao"]
        _tabela([{"Posição": s.posicao, "Sugestão": f"ϕ {s.phi:g} c/ {s.s:g} cm".replace(".", ","),
                  "As (cm²/m)": num(s.As), "Atende": _OK[s.atende]} for s in sug])
        if not all(s.atende for s in sug):
            st.warning("Em alguma posição nem a armadura mais pesada resolve: aumente a espessura da seção.")
        if st.button("Aplicar sugestão às entradas", key="bt_sug_ap"):
            del st.session_state["sugestao"]
            st.session_state["_pendente"] = dados
            st.rerun()
    st.markdown("**Cortina — esforços e armadura vertical ao longo da altura**")
    if e.cf_usar:
        st.caption("Muro com contrafortes: a cortina é verificada como laje entre contrafortes (tabela acima). Os "
                   "esforços em balanço abaixo são os que o contraforte recebe — não governam a armadura da cortina.")
    _fig(graficos.diagrama_cortina(res))
    with st.expander("Tabela das 21 seções da cortina"):
        s = d.secoes
        st.dataframe(pd.DataFrame({
            "z (m)": s["y"], "h (m)": s["h"], "Mk caso A": s["MkA"], "Vk caso A": s["VkA"], "Mk caso B": s["MkB"],
            "Vk caso B": s["VkB"], "MSd+": s["MSdp"], "As+ nec (cm²/m)": s["Asp"], "MRd+": s["MRdp"],
            "Aprov. +": s["utp"], "MSd−": s["MSdn"], "As− nec (cm²/m)": s["Asn"], "MRd−": s["MRdn"],
            "Aprov. −": s["utn"]}).round(3), hide_index=True, width="stretch", height=420)
        st.caption("Caso A = muro livre (empuxo conforme 'Empuxo para dimensionamento'); caso B = muro travado. "
                   "As nec = −1 indica seção insuficiente.")
    with st.expander("Base — ponta e talão em balanço"):
        v = d.v
        _tabela([
            {"Grandeza": "Mk ponta pelas pressões — Fase 1 / Fase 2", "Valor": f"{num(v['dm_MtP1'])} / {num(v['dm_MtP2'])}", "Un.": "kN·m/m"},
            {"Grandeza": "Mk ponta adotado (tração na face inferior)", "Valor": num(v["dm_Mtp"]), "Un.": "kN·m/m"},
            {"Grandeza": "Vk ponta (envoltória)", "Valor": num(v["dm_VtP"]), "Un.": "kN/m"},
            {"Grandeza": "Mk talão — Fase 1 / Fase 2", "Valor": f"{num(v['dm_MtT1'])} / {num(v['dm_MtT2'])}", "Un.": "kN·m/m"},
            {"Grandeza": "Mk talão adotado (tração na face superior)", "Valor": num(v["dm_Mtt"]), "Un.": "kN·m/m"},
            {"Grandeza": "Vk talão (envoltória) — verificação do aplicativo", "Valor": num(v["dm_VtT"]), "Un.": "kN/m"},
            {"Grandeza": "d da base (inferior / superior)", "Valor": f"{num(v['dm_db_i'], 3)} / {num(v['dm_db_s'], 3)}", "Un.": "m"},
            {"Grandeza": "As mínima da base", "Valor": num(v["dm_Asminb"]), "Un.": "cm²/m"},
        ])
        b = d.base
        st.dataframe(pd.DataFrame({"x (m)": b["x"], "Zona": b["zona"], "σ solo F1 (kPa)": b["sig1"],
                                   "σ solo F2 (kPa)": b["sig2"], "u subpressão": b["u"], "peso sapata": b["peso"],
                                   "carga sobre o talão": b["carga_talao"], "q líq. F1 (↑ +)": b["q1"],
                                   "q líq. F2 (↑ +)": b["q2"]}).round(2), hide_index=True, width="stretch",
                     height=300)
    if e.cf_usar and "cortina" in d.placas:
        pc, pb = d.placas["cortina"], d.placas.get("base")
        with st.expander("Contrafortes — cortina e base como laje com uma borda livre (placa)", expanded=True):
            st.markdown(f"Painel da cortina: vão livre **{num(d.v['cs_l'])} m** × altura **{num(res.geo.h_cort)} m** "
                        f"(altura/vão = {num(pc['razao'])}) — {pc['tipo']}.")
            linhas = [
                {"Esforço de cálculo": "Cortina — momento horizontal nos contrafortes (face do tardoz)",
                 "Placa": num(pc["Mht"]), "Coef. GEO5": num(d.v["cs_Mht"]), "Un.": "kN·m/m"},
                {"Esforço de cálculo": "Cortina — momento horizontal no vão (face frontal)",
                 "Placa": num(pc["Mhf"]), "Coef. GEO5": num(d.v["cs_Mhf"]), "Un.": "kN·m/m"},
                {"Esforço de cálculo": "Cortina — momento vertical no engaste da base (face do tardoz)",
                 "Placa": num(pc["Mvt"]), "Coef. GEO5": num(d.v["cs_Mvt"]), "Un.": "kN·m/m"},
                {"Esforço de cálculo": "Cortina — momento vertical no campo (face frontal)",
                 "Placa": num(pc["Mvf"]), "Coef. GEO5": num(d.v["cs_Mvf"]), "Un.": "kN·m/m"},
                {"Esforço de cálculo": "Cortina — cortante na base / nos contrafortes",
                 "Placa": f"{num(pc['Vb'])} / {num(pc['Vs'])}", "Coef. GEO5": num(d.v["cs_V"]), "Un.": "kN/m"},
            ]
            if pb:
                linhas += [
                    {"Esforço de cálculo": "Base — momento paralelo ao muro nos contrafortes",
                     "Placa": num(pb["M_sup"]), "Coef. GEO5": num(d.v["bd_M12"]), "Un.": "kN·m/m"},
                    {"Esforço de cálculo": "Base — momento paralelo ao muro no vão",
                     "Placa": num(pb["M_vao"]), "Coef. GEO5": num(d.v["bd_M20"]), "Un.": "kN·m/m"},
                    {"Esforço de cálculo": "Base — momento transversal na junção com a cortina",
                     "Placa": num(pb["M_tr_j"]), "Coef. GEO5": "—", "Un.": "kN·m/m"},
                    {"Esforço de cálculo": "Base — momento transversal no campo",
                     "Placa": num(pb["M_tr_pos"]), "Coef. GEO5": "—", "Un.": "kN·m/m"},
                ]
            _tabela(linhas)
            fig = armacao.diagrama_placa(res)
            if fig is not None:
                _fig(fig)
            v = d.v
            st.caption(f"Contraforte (viga em balanço): MSd = {num(v['cf_MSd'])} kN·m · VSd = {num(v['cf_VSd'])} kN · "
                       f"seção {num(v['cf_bw'])} × {num(v['cf_h2'])} m (d = {num(v['cf_d'], 3)}) · As nec / ef / mín = "
                       f"{num(v['cf_Asn'])} / {num(v['cf_As'])} / {num(v['cf_Asm'])} cm².")
    elif e.cf_usar:
        with st.expander("Contrafortes — coeficientes do GEO5 (planilha)", expanded=True):
            v = d.v
            _tabela([
                {"Grandeza": "Vão livre entre contrafortes l", "Valor": num(v["cs_l"]), "Un.": "m"},
                {"Grandeza": "σH de cálculo / σp de cálculo", "Valor": f"{num(v['cs_sH'])} / {num(v['cs_sP'])}", "Un.": "kPa"},
                {"Grandeza": "M vertical tardoz / frontal", "Valor": f"{num(v['cs_Mvt'])} / {num(v['cs_Mvf'])}", "Un.": "kN·m/m"},
                {"Grandeza": "M horizontal apoios / vão", "Valor": f"{num(v['cs_Mht'])} / {num(v['cs_Mhf'])}", "Un.": "kN·m/m"},
                {"Grandeza": "Cortante da cortina σp·l/2", "Valor": num(v["cs_V"]), "Un.": "kN/m"},
                {"Grandeza": "Base: carga da laje w", "Valor": num(v["bd_w"], 2, "fora da base"), "Un.": "kPa"},
                {"Grandeza": "Base: M apoios / vão", "Valor": f"{num(v['bd_M12'])} / {num(v['bd_M20'])}", "Un.": "kN·m/m"},
                {"Grandeza": "Contraforte: MSd / VSd", "Valor": f"{num(v['cf_MSd'])} / {num(v['cf_VSd'])}", "Un.": "kN·m / kN"},
                {"Grandeza": "Contraforte: seção b × h (d)", "Valor": f"{num(v['cf_bw'])} × {num(v['cf_h2'])} ({num(v['cf_d'], 3)})", "Un.": "m"},
                {"Grandeza": "Contraforte: As nec / As ef / As mín", "Valor": f"{num(v['cf_Asn'])} / {num(v['cf_As'])} / {num(v['cf_Asm'])}", "Un.": "cm²"},
            ])


# ====================================================================== ferramentas
def secao_ferramentas(res: Resultado) -> None:
    e = res.entrada
    st.caption("Recursos que a planilha não oferece. Todos apenas recalculam o muro várias vezes.")
    t1, t2, t3 = st.tabs(["Dimensionar a base", "Força mínima de travamento", "Estudo paramétrico"])

    with t1:
        st.markdown("Procura a menor geometria que atende **tombamento, deslizamento, excentricidade e capacidade "
                    "de carga** em todas as fases, mantendo os demais dados.")
        modo = st.radio("O que variar", ["Só o talão", "Só a ponta", "Ponta e talão (menor B)"], horizontal=True,
                        key="fer_modo")
        if st.button("Calcular", key="bt_base"):
            if modo.startswith("Ponta e"):
                b = base_minima(e)
                st.session_state["fer_base"] = (b.b_ponta, b.b_talao) if b.encontrado else None
            else:
                campo = "b_talao" if "talão" in modo else "b_ponta"
                v, _ = menor_valor(e.com(**{campo: 0.0}), campo, 2.0 * e.H_muro)
                st.session_state["fer_base"] = None if v is None else (
                    (e.b_ponta, v) if campo == "b_talao" else (v, e.b_talao))
        if "fer_base" in st.session_state:
            sol = st.session_state["fer_base"]
            if sol is None:
                st.error("Nenhuma geometria dentro da faixa pesquisada atende. Reveja solo, sobrecarga ou "
                         "considere ancoragem/travamento.")
            else:
                r = calcular(e.com(b_ponta=sol[0], b_talao=sol[1]))
                v1 = r.fase1.verif
                st.success(f"Ponta = **{num(sol[0])} m**, talão = **{num(sol[1])} m** → B = "
                           f"**{num(r.geo.B_base)} m** | FSt {fs(v1.R_FSt)} · FSd {fs(v1.R_FSd)} · e/B "
                           f"{num(v1.R_eB, 3)} · FScc {fs(v1.R_FScc)}"
                           + ("" if r.dim.atende else " — o dimensionamento estrutural precisa ser revisto."))
                pend = {a.texto for f in ([r.fase1] + ([r.fase2] if r.tem_fase2 else [])) for a in f.avisos}
                if pend:
                    st.warning("Esta geometria passa nas quatro verificações, mas mantém aviso(s) de consistência "
                               "e, como na planilha, o resultado continua 'NÃO ATENDE': " + "; ".join(sorted(pend))
                               + ". Para o aviso de talão longo, use a cunha 'Vertical' (dorso virtual).")
                if st.button("Aplicar às entradas", key="bt_base_ap"):
                    del st.session_state["fer_base"]
                    estado.aplicar(e, b_ponta=sol[0], b_talao=sol[1])

    with t2:
        st.markdown("Menor força horizontal no travamento (na cota informada) que atende os FS de tombamento e "
                    "deslizamento da **Fase 2**, recalculando a fase inteira a cada tentativa — a planilha estima "
                    "o deslizamento com a excentricidade fixa.")
        st.caption(f"Cota do travamento: {num(e.trav_z)} m · convenção: {e.trav_conv.value} · empuxo da Fase 2: "
                   f"{e.trav_emp.value}")
        if st.button("Calcular", key="bt_trav"):
            st.session_state["fer_trav"] = travamento_minimo_exato(e)
        if "fer_trav" in st.session_state:
            t = st.session_state["fer_trav"]
            if math.isinf(t.F_min):
                st.error(t.obs)
            else:
                c = st.columns(3)
                c[0].metric("Para o tombamento", f"{num(t.F_tomb, 1)} kN/m")
                c[1].metric("Para o deslizamento", f"{num(t.F_desl, 1)} kN/m")
                c[2].metric("Força mínima", f"{num(t.F_min, 1)} kN/m")
                v2 = t.resultado.fase2.verif
                st.write(f"Com essa força, na Fase 2: FSt {fs(v2.R_FSt)} · FSd {fs(v2.R_FSd)} · e/B "
                         f"{num(v2.R_eB, 3)} · FScc {fs(v2.R_FScc)}")
                if t.obs:
                    st.warning(t.obs)
                if st.button("Aplicar (ativa o travamento com essa força)", key="bt_trav_ap"):
                    f = math.ceil(t.F_min * 10) / 10
                    del st.session_state["fer_trav"]
                    estado.aplicar(e, trav_usar=True, trav_F=f)

    with t3:
        numericos = [c for c in CAMPOS if c.tipo == "float" and not c.nome.startswith(("ar_", "cf_phi"))]
        c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
        campo = c1.selectbox("Variável", [c.nome for c in numericos], index=[c.nome for c in numericos].index("q_sc"),
                             format_func=lambda n: f"{CAMPO[n].rotulo} ({CAMPO[n].unidade})", key="par_campo")
        cp = CAMPO[campo]
        atual = getattr(e, campo)
        atual = float(atual if atual is not None else getattr(e, cp.vinculo))
        ini = c2.number_input("De", value=max(float(cp.minimo), round(atual * 0.5, 2)), key=f"par_ini_{campo}")
        fim = c3.number_input("Até", value=min(float(cp.maximo), round(max(atual * 1.5, atual + 1), 2)),
                              key=f"par_fim_{campo}")
        n = c4.number_input("Pontos", 3, 41, 11, key="par_n")
        if fim > ini:
            linhas = estudo_parametrico(e, campo, [float(x) for x in np.linspace(ini, fim, int(n))])
            if linhas:
                _fig(graficos.grafico_parametrico(linhas, f"{cp.rotulo[:38]} ({cp.unidade})",
                                                  dict(FSt=e.FSt_min, FSd=e.FSd_min, eB=e.eB_lim, FScc=e.FScc_min)))
                with st.expander("Tabela"):
                    _tabela([{cp.rotulo: num(ln["valor"], 3), "Fase": ln["fase"], "FSt": fs(ln["FSt"]),
                              "FSd": fs(ln["FSd"]), "e/B": num(ln["eB"], 3), "FScc": fs(ln["FScc"]),
                              "Estabilidade": _OK[ln["ok"]], "Dimensionamento": _OK[ln["dim_ok"]]}
                             for ln in linhas])
            else:
                st.warning("Nenhum valor da faixa gera um muro válido.")
        else:
            st.warning("O valor final deve ser maior que o inicial.")
    _ = estabilidade_ok


# ======================================================================== premissas
def secao_premissas() -> None:
    for tema, itens in PREMISSAS.items():
        st.markdown(f"**{tema}**")
        st.markdown("\n".join(f"- {i}" for i in itens))
    st.markdown("**Diferenças em relação à planilha de origem**")
    st.markdown("\n".join(f"- {i}" for i in DIFERENCAS_DA_PLANILHA))


RENDER = {
    "Resultados": secao_resultados, "Forças": secao_forcas, "Empuxo": secao_empuxo, "Geometria": secao_geometria,
    "Capacidade de carga": secao_capacidade, "Ferramentas": secao_ferramentas,
}
