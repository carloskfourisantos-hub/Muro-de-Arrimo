"""Memorial de cálculo em PDF (reportlab)."""
from __future__ import annotations

import io
from datetime import datetime

import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from core.campos import CAMPOS, SECOES
from core.fases import Resultado
from core.premissas import DIFERENCAS_DA_PLANILHA, PREMISSAS
from ui import armacao, graficos
from ui.formato import fs, num

AZUL = colors.HexColor("#2a78d6")
VERDE, VERMELHO, CINZA = colors.HexColor("#0a7d0a"), colors.HexColor("#c02f2f"), colors.HexColor("#52514e")
_S = getSampleStyleSheet()
H1 = ParagraphStyle("h1", parent=_S["Heading1"], fontSize=15, spaceAfter=4, textColor=colors.HexColor("#0b0b0b"))
H2 = ParagraphStyle("h2", parent=_S["Heading2"], fontSize=11.5, spaceBefore=10, spaceAfter=4, textColor=AZUL)
P = ParagraphStyle("p", parent=_S["BodyText"], fontSize=8.5, leading=11, alignment=TA_LEFT)
PEQ = ParagraphStyle("peq", parent=P, fontSize=7.5, leading=9.5, textColor=CINZA)
CEL = ParagraphStyle("cel", parent=P, fontSize=7.8, leading=9.5)


def _fig(fig, largura_cm: float) -> Image:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200)
    w, h = fig.get_size_inches()
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=largura_cm * cm, height=largura_cm * cm * h / w)


def _tabela(dados, larguras, cabecalho=True, zebra=True) -> Table:
    linhas = [[Paragraph(str(c), CEL) if isinstance(c, str) else c for c in ln] for ln in dados]
    t = Table(linhas, colWidths=[w * cm for w in larguras], repeatRows=1 if cabecalho else 0)
    est = [("FONTSIZE", (0, 0), (-1, -1), 7.8), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
           ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e1e0d9")),
           ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2)]
    if cabecalho:
        est += [("BACKGROUND", (0, 0), (-1, 0), AZUL), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)]
        linhas[0] = [Paragraph(f"<font color='white'><b>{c}</b></font>", CEL) for c in dados[0]]
        t = Table(linhas, colWidths=[w * cm for w in larguras], repeatRows=1)
    if zebra:
        est.append(("ROWBACKGROUNDS", (0, 1 if cabecalho else 0), (-1, -1), [colors.white, colors.HexColor("#f6f6f3")]))
    t.setStyle(TableStyle(est))
    return t


def _sit(ok) -> str:
    if ok is None or ok == "—":
        return "—"
    if ok is True or ok == "OK":
        return "<font color='#0a7d0a'><b>OK</b></font>"
    return "<font color='#c02f2f'><b>NÃO OK</b></font>"


def _veredito(txt: str, ok: bool) -> Paragraph:
    cor = "#0a7d0a" if ok else "#c02f2f"
    return Paragraph(f"<b>{txt}: <font color='{cor}'>{'ATENDE' if ok else 'NÃO ATENDE'}</font></b>", P)


def _rodape(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(CINZA)
    canvas.drawString(1.8 * cm, 1.0 * cm, "Muro de arrimo de flexão — NBR 11682 / NBR 6118 — memorial gerado pelo "
                                          "aplicativo; conferência e responsabilidade técnica do engenheiro.")
    canvas.drawRightString(A4[0] - 1.8 * cm, 1.0 * cm, f"pág. {doc.page}")
    canvas.restoreState()


def gerar_pdf(res: Resultado, meta: dict | None = None) -> bytes:
    e, g = res.entrada, res.geo
    meta = meta or {}
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.6 * cm,
                            bottomMargin=1.6 * cm, title="Memorial de cálculo — muro de arrimo",
                            author=meta.get("autor", ""))
    el: list = [Paragraph("Memorial de cálculo — muro de arrimo de flexão em concreto armado", H1),
                Paragraph("Estabilidade externa (ABNT NBR 11682) e dimensionamento estrutural (ABNT NBR 6118) — "
                          "análise por metro linear de muro.", P)]
    cab = " &nbsp;|&nbsp; ".join(f"<b>{k.capitalize()}:</b> {meta[k]}" for k in ("nome", "obra", "autor")
                                 if meta.get(k))
    el.append(Paragraph((cab + " &nbsp;|&nbsp; " if cab else "") + f"<b>Data:</b> "
                        f"{datetime.now():%d/%m/%Y %H:%M}", PEQ))
    el.append(Spacer(1, 6))

    # ---------------------------------------------------------------- 1. resultado
    el.append(Paragraph("1. Resultado", H2))
    el.append(_veredito("Estabilidade externa (todas as fases)", res.atende_estabilidade))
    el.append(_veredito("Dimensionamento estrutural", res.dim.atende))
    fases = [res.fase1] + ([res.fase2] if res.tem_fase2 else [])
    dados = [["Verificação"] + [f"Fase {f.numero}" for f in fases] + ["Limite", "Situação"]]

    def lin(rot, vals, lim, oks):
        dados.append([rot] + vals + [lim, _sit(all(oks))])
    lin("FS ao tombamento", [fs(f.verif.R_FSt) for f in fases], f"≥ {num(e.FSt_min)}", [f.verif.ok_tomb for f in fases])
    lin("FS ao deslizamento", [fs(f.verif.R_FSd) for f in fases], f"≥ {num(e.FSd_min)}",
        [f.verif.ok_desl for f in fases])
    lin("Excentricidade e/B", [num(f.verif.R_eB, 3) for f in fases], f"≤ {num(e.eB_lim, 3)}",
        [f.verif.ok_exc for f in fases])
    lin("FS à capacidade de carga", [fs(f.verif.R_FScc) for f in fases], f"≥ {num(e.FScc_min)}",
        [f.verif.ok_cap for f in fases])
    larg = [6.2] + [2.6] * len(fases) + [2.6, 2.6]
    el.append(Spacer(1, 4))
    el.append(_tabela(dados, larg))
    for f in fases:
        for a in f.avisos:
            el.append(Paragraph(f"<font color='#c02f2f'>Aviso (Fase {f.numero}):</font> {a.texto}", P))
    leg = e.opcoes_legadas_ativas()
    if leg:
        el.append(Paragraph("<b>Opções legadas (compatibilidade GEO5) ativas:</b> " + "; ".join(leg), P))
    el.append(Spacer(1, 4))
    el.append(_fig(graficos.croqui(res, 1), 13.5))
    if res.tem_fase2:
        el.append(_fig(graficos.croqui(res, 2), 13.5))

    # --------------------------------------------------------------- 2. dados
    el.append(PageBreak())
    el.append(Paragraph("2. Dados de entrada", H2))
    plan = e.para_planilha(so_app=True)
    opcionais = {"2.": e.cf_usar, "2b.": e.anc_usar, "2c.": e.bl_usar, "2d.": e.trav_usar, "10b.": e.cf_usar}
    for sec in SECOES:
        ativo = opcionais.get(sec.split(" ")[0], True)
        campos = [c for c in CAMPOS if c.secao == sec]
        if not ativo:               # seção opcional desligada: só a chave Sim/Não
            if sec.startswith("10b."):
                continue
            campos = campos[:1]
        dados = [[sec, "Valor", "Un."]]
        for c in campos:
            v = plan[c.nome]
            dados.append([c.rotulo, num(v, 3).rstrip("0").rstrip(",") if isinstance(v, float) else str(v),
                          c.unidade])
        el.append(KeepTogether([_tabela(dados, [11.6, 3.6, 1.8]), Spacer(1, 5)]))

    # ----------------------------------------------------- 3. geometria e empuxo
    el.append(PageBreak())
    el.append(Paragraph("3. Geometria e empuxo", H2))
    dados = [["Parcela", "Área (m²)", "x centroide (m)", "z centroide (m)"]]
    for p in (g.cortina, g.sapata, g.solo, g.solo_na, g.contraforte, g.solo_ponta):
        dados.append([p.nome, num(p.A, 3), num(p.x, 3), num(p.z, 3)])
    el.append(_tabela(dados, [7.4, 3.2, 3.2, 3.2]))
    el.append(Paragraph(f"Largura da base B = {num(g.B_base)} m; inclinação do plano da cunha com a vertical "
                        f"θ = {num(g.th_c * 57.29578, 2)}°; cota do topo do plano de cálculo = {num(g.z_top_pl)} m.",
                        P))
    for f in fases:
        emp = f.emp
        el.append(Spacer(1, 4))
        dados = [[f"Empuxo — Fase {f.numero}", "Valor", "Un."],
                 ["Empuxo resultante Pa", num(emp.p_Pa), "kN/m"],
                 ["Componente horizontal Pa,h (solo + sobrecarga)", num(emp.p_Pah), "kN/m"],
                 ["   parcela do solo / da sobrecarga", f"{num(emp.p_Pah_s)} / {num(emp.p_Pah_q)}", "kN/m"],
                 ["Cota de aplicação de Pa,h", num(emp.p_zPa, 3), "m"],
                 ["Componente vertical Pa,v adotada", num(emp.p_Pav), "kN/m"],
                 ["x de aplicação de Pa,v", num(emp.p_xPav, 3), "m"],
                 ["Empuxo hidrostático atrás / na frente", f"{num(emp.p_U)} / {num(emp.p_Uf)}", "kN/m"],
                 ["Subpressão resultante", num(emp.p_Usub), "kN/m"],
                 ["K0 / Ka Rankine (c = 0)", f"{num(emp.p_K0, 3)} / {num(emp.p_KaR, 3)}", "-"]]
        el.append(_tabela(dados, [11.6, 3.6, 1.8]))
    el.append(Spacer(1, 4))
    el.append(_fig(graficos.diagrama_empuxo(res, 1), 9.5))

    # ------------------------------------------------------------- 4. forças
    el.append(PageBreak())
    el.append(Paragraph("4. Forças e momentos (em torno da aresta da ponta)", H2))
    for f in fases:
        dados = [[f"Força — Fase {f.numero}", "Fx", "Fz", "x", "z", "M estab.", "M tomb."]]
        for ln in f.forcas.linhas:
            if abs(ln.Fx) < 1e-12 and abs(ln.Fz) < 1e-12:
                continue
            dados.append([ln.nome, num(ln.Fx), num(ln.Fz), num(ln.x, 3), num(ln.z, 3), num(ln.Mres), num(ln.Movr)])
        F = f.forcas
        dados.append(["<b>TOTAIS</b>", num(F.F_Hnet), num(F.F_N), "", "", num(F.F_Mres), num(F.F_Movr)])
        el.append(_tabela(dados, [6.6, 1.7, 1.7, 1.5, 1.5, 2.0, 2.0]))
        el.append(Paragraph("Unidades: forças em kN/m, distâncias em m, momentos em kN·m/m. Fx &gt; 0 empurra o "
                            "muro para a frente; Fz &gt; 0 para baixo.", PEQ))
        el.append(Spacer(1, 6))

    # --------------------------------------------------------- 5. verificações
    el.append(Paragraph("5. Verificações de estabilidade — NBR 11682", H2))
    for f in fases:
        v, F, c = f.verif, f.forcas, f.verif.cap
        dados = [[f"Fase {f.numero}", "Valor", "Un."],
                 ["Tombamento: FS = Mres / Movr = " f"{num(F.F_Mres)} / {num(F.F_Movr)}", fs(v.R_FSt), "-"],
                 [f"Deslizamento: N·tan δb (δb = {num(v.delta_b)}°)", num(v.Hres_atrito), "kN/m"],
                 [f"Deslizamento: a·B' (a = {num(v.adesao)} kPa)", num(v.Hres_adesao), "kN/m"],
                 ["Deslizamento: forças horizontais resistentes + estacas",
                  num(v.Hres_externas + v.Hres_estacas), "kN/m"],
                 [f"Deslizamento: FS = H_res / H_act = {num(v.R_Hres)} / {num(v.R_Hact)}", fs(v.R_FSd), "-"],
                 ["Posição da resultante xR = (Mres − Movr)/N", num(v.R_xR, 3), "m"],
                 [f"Excentricidade e = B/2 − xR (σmáx na {v.sig_max_em})", num(v.R_e, 3), "m"],
                 ["Base efetiva B'", num(v.R_Bef, 3), "m"],
                 ["Tensões σmáx / σmín (distribuição linear)",
                  f"{num(v.sig_max, 1, 'fora da base')} / {num(v.sig_min, 1)}", "kPa"],
                 ["Tensão média de Meyerhof σef = N / B'", num(v.R_sef, 1, "fora da base"), "kPa"],
                 [f"Vesic: Nq = {num(c.CC_Nq)}; Nc = {num(c.CC_Nc)}; Nγ = {num(c.CC_Ng)}; iq = {num(c.CC_iq, 3)}; "
                  f"iγ = {num(c.CC_ig, 3)}; ic = {num(c.CC_ic, 3)}; q0 = {num(c.CC_q0, 1)} kPa", "", ""],
                 ["Capacidade de carga de ruptura qult", num(v.R_qult, 1), "kPa"],
                 ["FS à capacidade de carga = qult / σef", fs(v.R_FScc), "-"]]
        el.append(KeepTogether([_tabela(dados, [11.6, 3.6, 1.8]), Spacer(1, 6)]))
    el.append(_fig(graficos.diagrama_base(res), 9.5))

    # --------------------------------------------------------- 6. dimensionamento
    el.append(PageBreak())
    el.append(Paragraph("6. Dimensionamento estrutural — NBR 6118", H2))
    d, c = res.dim, res.dim.concreto
    el.append(Paragraph(f"fck = {num(e.fck_c, 0)} MPa; fcd = {num(c.fcd)} MPa; fyd = {num(c.fyd, 1)} MPa; "
                        f"fctd = {num(c.fctd, 3)} MPa; ρmín = {num(c.rho_min * 100, 3)} %; γf = {num(e.gf_f)}. "
                        f"Cobrimentos: cortina {num(e.cob_ct, 1)} cm, base {num(e.cob_bs, 1)} cm.", P))
    el.append(Spacer(1, 3))
    dados = [["Verificação", "Solicitante", "Resistente / limite", "Un.", "Situação"]]
    for ch in d.checks + d.extras:
        if ch.situacao == "—":
            continue
        nome = ch.nome + (" <font color='#52514e'>[aplicativo]</font>" if ch.extra else "")
        sol = "insuficiente" if (ch.solicitante < 0 and "As" in ch.nome) else num(ch.solicitante, 3 if ch.unidade == "-" else 2)
        dados.append([nome, sol, num(ch.resistente, 3 if ch.unidade == "-" else 2), ch.unidade, _sit(ch.situacao)])
    el.append(_tabela(dados, [8.6, 2.4, 2.8, 1.4, 1.8]))
    for n in d.notas:
        el.append(Paragraph("• " + n, PEQ))
    el.append(PageBreak())
    el.append(Paragraph("Armaduras", H2))
    el.append(_fig(armacao.desenho(res), 15.5))
    quadro = armacao.tabela(armacao.quadro_de_ferros(res))
    el.append(_tabela([["Pos.", "Armadura", "Onde", "As ef.", "As nec.", "Un.", "Situação"]]
                      + [[q["Pos."], q["Armadura"], q["Onde"], q["As ef."], q["As nec."], q["Un."],
                          q["Situação"].replace("✔ ", "").replace("✖ ", "")] for q in quadro],
                      [1.0, 2.6, 7.0, 1.5, 1.7, 1.2, 2.0]))
    el.append(Paragraph("Desenho esquemático (cobrimentos fora de escala). Ancoragens, emendas, dobras e estribos "
                        "do contraforte não são detalhados.", PEQ))
    el.append(Spacer(1, 4))
    fig_placa = armacao.diagrama_placa(res)
    if fig_placa is not None:
        el.append(_fig(fig_placa, 15.5))
    if e.cf_usar:
        el.append(Paragraph("Muro com contrafortes: a cortina é verificada como laje entre contrafortes (tabela "
                            "acima). Os esforços em balanço abaixo são os transmitidos ao contraforte e não "
                            "governam a armadura da cortina.", PEQ))
    el.append(_fig(graficos.diagrama_cortina(res), 15.5))
    s = d.secoes
    dados = [["z (m)", "h (m)", "Mk+ (kN·m/m)", "Vk (kN/m)", "MSd+", "As nec (cm²/m)", "MRd+", "MSd/MRd"]]
    for i in range(0, len(s["y"]), 2):
        dados.append([num(s["y"][i]), num(s["h"][i], 3), num(s["Mkp"][i]), num(s["Vk"][i]), num(s["MSdp"][i]),
                      "insuf." if s["Asp"][i] < 0 else num(s["Asp"][i]), num(s["MRdp"][i]), num(s["utp"][i], 3)])
    el.append(Spacer(1, 4))
    el.append(_tabela(dados, [1.6, 1.6, 2.4, 2.1, 2.1, 2.6, 2.1, 2.1]))

    # ------------------------------------------------------------ 7. premissas
    el.append(PageBreak())
    el.append(Paragraph("7. Premissas, formulação e limitações", H2))
    for tema, itens in PREMISSAS.items():
        el.append(Paragraph(f"<b>{tema}</b>", P))
        for it in itens:
            el.append(Paragraph("• " + it, PEQ))
        el.append(Spacer(1, 3))
    el.append(Paragraph("<b>Diferenças em relação à planilha de origem</b>", P))
    for it in DIFERENCAS_DA_PLANILHA:
        el.append(Paragraph("• " + it, PEQ))
    doc.build(el, onFirstPage=_rodape, onLaterPages=_rodape)
    return buf.getvalue()
