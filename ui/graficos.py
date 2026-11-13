"""Croqui e diagramas em matplotlib (sem Streamlit: o memorial em PDF reutiliza).

Todas as funções devolvem uma ``Figure``; quem chama é responsável por fechá-la.
"""
from __future__ import annotations

import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import FancyArrowPatch, Polygon, Rectangle  # noqa: E402

from core.empuxo import DORSO, PLANO, SAPATA, TARDOZ  # noqa: E402
from ui.formato import num  # noqa: E402

# paleta (slots categóricos 1–3 validados + tinta/cromo)
AZUL, LARANJA, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
TINTA, TINTA2, MUDO, GRADE, EIXO, FUNDO = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
CONCRETO, SOLO, SOLO_F, AGUA = "#cfcec8", "#eadcc3", "#e3d3b6", "#2a78d6"
BOM, CRITICO = "#0ca30c", "#d03b3b"

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans"], "font.size": 8.5, "axes.edgecolor": EIXO,
    "axes.labelcolor": TINTA2, "xtick.color": MUDO, "ytick.color": MUDO, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "grid.color": GRADE, "grid.linewidth": 0.6,
    "figure.facecolor": FUNDO, "axes.facecolor": FUNDO, "savefig.facecolor": FUNDO, "axes.titlesize": 9.5,
    "axes.titleweight": "bold", "axes.titlecolor": TINTA, "legend.frameon": False, "lines.linewidth": 2,
})


def _seta(ax, p0, p1, cor, rotulo=None, ha="left", va="center", dx=0.06, dy=0.0):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=11, lw=1.8, color=cor, zorder=6))
    if rotulo:
        ax.text(p0[0] + dx, p0[1] + dy, rotulo, color=TINTA, fontsize=8, ha=ha, va=va, zorder=7,
                bbox=dict(boxstyle="round,pad=0.15", fc=FUNDO, ec="none", alpha=0.85))


def _cota(ax, p0, p1, texto, desloc=(0, 0), rot=0):
    ax.annotate("", p0, p1, arrowprops=dict(arrowstyle="<->", color=MUDO, lw=0.8), zorder=4)
    ax.text((p0[0] + p1[0]) / 2 + desloc[0], (p0[1] + p1[1]) / 2 + desloc[1], texto, color=TINTA2, fontsize=7.5,
            ha="center", va="center", rotation=rot,
            bbox=dict(boxstyle="round,pad=0.1", fc=FUNDO, ec="none", alpha=0.9), zorder=5)


# ============================================================================ croqui
def croqui(res, fase: int = 1, forcas: bool = True, largura: float = 7.2):
    e, g = res.entrada, res.geo
    f = res.fase1 if fase == 1 else res.fase2
    B, H, hs = g.B_base, e.H_muro, e.h_sap
    xr = B + max(1.5, 0.35 * H)
    xl = -max(1.0, 0.25 * H)
    tb = math.tan(math.radians(e.beta_t))
    z_r = g.z_ter + (xr - g.x_bt) * tb
    hd = min(0.75, 0.2 * H)                       # altura do diagrama de tensões
    L = max(0.6, 0.16 * H)                        # comprimento das setas
    z_cota = -(hd + L + 0.55) - (e.bl_H + 0.6 if (e.bl_usar or e.anc_usar) else 0.0)
    z_fundo = z_cota - 0.35

    fig, ax = plt.subplots(figsize=(largura, largura * 0.78), dpi=150)
    ax.set_aspect("equal")
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])

    # solo de fundação, aterro e solo da frente
    ax.add_patch(Rectangle((xl, z_fundo), xr - xl, -z_fundo, fc=SOLO_F, ec="none", zorder=0))
    ax.add_patch(Polygon([(g.x_bt, g.z_ter), (xr, z_r), (xr, 0), (B, 0), (B, hs), (g.x_tb, hs)], closed=True,
                         fc=SOLO, ec="none", zorder=1))
    ax.plot([g.x_bt, xr], [g.z_ter, z_r], color=TINTA2, lw=1.0, zorder=3)
    D = e.D_frente
    if D > 0:
        if D <= hs:
            pts = [(xl, 0), (0, 0), (0, D), (xl, D)]
        else:
            pts = [(xl, 0), (0, 0), (0, hs), (g.x_fb, hs), (g.x_frontal(min(D, H), hs), min(D, H)), (xl, min(D, H))]
        ax.add_patch(Polygon(pts, closed=True, fc=SOLO, ec="none", zorder=1))
        ax.plot([xl, pts[-2][0]], [pts[-1][1]] * 2, color=TINTA2, lw=1.0, zorder=3)
    ax.plot([xl, 0], [0, 0], color=EIXO, lw=0.8, zorder=2)

    # água
    def nivel(x0, x1, z, txt):
        ax.plot([x0, x1], [z, z], color=AGUA, lw=1.2, ls=(0, (5, 3)), zorder=5)
        ax.plot([(x0 + x1) / 2], [z + 0.07], marker="v", color=AGUA, ms=5, zorder=5)
        ax.text((x0 + x1) / 2 + 0.12, z + 0.05, txt, color=AGUA, fontsize=7.5, va="bottom", zorder=5)
    if e.hw_at > 0:
        za = min(e.hw_at, g.z_dv)
        nivel(g.x_tardoz(min(za, H), hs) if za > hs else B, xr, za, f"NA {num(e.hw_at)} m")
    if e.hw_fr > 0:
        nivel(xl, 0 if e.hw_fr <= hs else g.x_frontal(min(e.hw_fr, H), hs), e.hw_fr, f"NA {num(e.hw_fr)} m")

    # muro, contraforte, blocos e estacas
    if e.cf_usar:
        ax.add_patch(Polygon(g.contraforte.vertices, closed=True, fc="#e3e2dc", ec=TINTA2, lw=0.8, hatch="////",
                             zorder=3))
    ax.add_patch(Polygon(g.croqui["muro"][:-1], closed=True, fc=CONCRETO, ec=TINTA, lw=1.2, zorder=4))
    a = f.forcas.anc
    if e.bl_usar:
        ax.add_patch(Rectangle((a.bl_xe - e.bl_B / 2, -e.bl_H), e.bl_B, e.bl_H, fc=CONCRETO, ec=TINTA, lw=1.0,
                               zorder=4))
    if e.anc_usar:
        topo = -e.bl_H if e.bl_usar else 0.0
        for x, n in ((a.anc_xe, e.anc_n1), (e.anc_x2, e.anc_n2)):
            if n > 0:
                ax.plot([x, x], [topo, z_fundo + 0.15], color=TINTA, lw=2.6, zorder=3, solid_capstyle="butt")
        ax.text(B + 0.1, z_fundo + 0.08, f"estacas L = {num(e.anc_L, 1)} m", fontsize=7, color=TINTA2, ha="left",
                va="bottom", zorder=5)

    # plano de cálculo do empuxo
    pl = g.croqui["plano"]
    ax.plot([p[0] for p in pl], [p[1] for p in pl], color=LARANJA, lw=1.4, ls=(0, (4, 2)), zorder=6)
    zt = pl[2][1] + 0.82 * (pl[1][1] - pl[2][1])
    xt_ = pl[2][0] + 0.82 * (pl[1][0] - pl[2][0])
    ax.text(xt_ + 0.1, zt, "plano de cálculo", color=LARANJA, fontsize=7, va="center", ha="left", zorder=6,
            bbox=dict(boxstyle="round,pad=0.12", fc=SOLO, ec="none", alpha=0.9))

    # tensões na base
    v = f.verif
    esc = 0.0
    if forcas and f.forcas.F_N > 0 and not math.isinf(v.sig_max) and v.sig_max > 0:
        esc = hd / v.sig_max
        if abs(v.R_e) <= B / 6:
            s0, s1 = (v.sig_max, v.sig_min) if v.R_e >= 0 else (v.sig_min, v.sig_max)
            pts = [(0, 0), (B, 0), (B, -s1 * esc), (0, -s0 * esc)]
        else:
            c = 3 * (B / 2 - abs(v.R_e))
            pts = [(0, 0), (c, 0), (0, -v.sig_max * esc)] if v.R_e >= 0 else \
                [(B, 0), (B - c, 0), (B, -v.sig_max * esc)]
        ax.add_patch(Polygon(pts, closed=True, fc=AQUA, ec=AQUA, alpha=0.28, lw=1.0, zorder=5))
        x_max = 0 if v.R_e >= 0 else B
        ax.text(x_max + (-0.08 if v.R_e >= 0 else 0.08), -v.sig_max * esc, f"σmáx\n{num(v.sig_max, 1)} kPa",
                color=TINTA, fontsize=7.5, ha="right" if v.R_e >= 0 else "left", va="center", zorder=7)

    # forças
    if forcas:
        emp = f.emp
        if emp.p_Pah > 0:
            xp = float(np.interp(emp.p_zPa, emp.fatias["z"][::-1], emp.fatias["x"][::-1]))
            _seta(ax, (xp + L + 0.25, emp.p_zPa), (xp + 0.03, emp.p_zPa), AZUL,
                  f"Pa,h = {num(emp.p_Pah, 1)} kN/m\nz = {num(emp.p_zPa)} m", dx=0.08)
        if emp.p_Pav > 1e-6:
            _seta(ax, (emp.p_xPav, emp.p_zPa + L + 0.25), (emp.p_xPav, emp.p_zPa + 0.05), AZUL,
                  f"Pa,v = {num(emp.p_Pav, 1)}", ha="center", va="bottom", dx=0, dy=0.05)
        if emp.p_U > 0:
            _seta(ax, (B + L + 0.25, emp.p_zU), (B + 0.03, emp.p_zU), AGUA, f"U = {num(emp.p_U, 1)} kN/m", dx=0.08)
        if f.forcas.F_Htrav > 0:
            xt = g.x_frontal(min(max(e.trav_z, hs), H), hs) if e.trav_z > hs else 0.0
            _seta(ax, (xt - L - 0.25, e.trav_z), (xt - 0.03, e.trav_z), LARANJA,
                  f"travamento\n{num(f.forcas.F_Htrav, 1)} kN/m", ha="right", dx=-0.08)
        if f.forcas.F_N > 0 and 0 <= v.R_xR <= B:
            _seta(ax, (v.R_xR, -(hd + L)), (v.R_xR, -0.02), AQUA,
                  f"N = {num(f.forcas.F_N, 1)} kN/m\ne = {num(v.R_e)} m", ha="left", va="center", dx=0.1, dy=0.12)

    # cotas
    _cota(ax, (xl + 0.25, 0), (xl + 0.25, H), f"H = {num(H)}", desloc=(-0.02, 0), rot=90)
    _cota(ax, (0, z_cota), (B, z_cota), f"B = {num(B)} m")
    if e.b_ponta > 0.15:
        ax.text(e.b_ponta / 2, hs / 2, num(e.b_ponta), fontsize=7, color=TINTA2, ha="center", va="center", zorder=8)
    if e.b_talao > 0.15:
        ax.text(g.x_tb + e.b_talao / 2, hs / 2, num(e.b_talao), fontsize=7, color=TINTA2, ha="center",
                va="center", zorder=8)
    if e.q_sc > 0:
        ax.text((g.x_bt + xr) / 2, (g.z_ter + z_r) / 2 + 0.12, f"q = {num(e.q_sc, 1)} kPa", fontsize=7.5,
                color=TINTA2, ha="center", va="bottom", zorder=5)
    ax.set_xlim(xl - 0.05, xr + 0.9)
    ax.set_ylim(z_fundo, max(H, z_r) + 0.55)
    ax.set_title(f"Fase {fase} — " + ("muro em balanço" if fase == 1 else "muro travado"), loc="left")
    fig.tight_layout(pad=0.4)
    return fig


# =========================================================================== empuxo
def diagrama_empuxo(res, fase: int = 1):
    f = res.fase1 if fase == 1 else res.fase2
    t = f.emp.fatias
    fig, ax = plt.subplots(figsize=(5.2, 4.2), dpi=150)
    cores = {TARDOZ: AZUL, DORSO: AZUL, PLANO: LARANJA, SAPATA: AQUA}
    for nome in (TARDOZ, DORSO, PLANO, SAPATA):
        m = (t["trecho"] == nome) & (t["dz"] > 1e-12)
        if m.any():
            ax.fill_betweenx(t["z"][m], 0, t["sa"][m], color=cores[nome], alpha=0.30, lw=0)
            ax.plot(t["sa"][m], t["z"][m], color=cores[nome], label=nome)
    if res.entrada.q_sc > 0:
        rot = "só solo (sem q)"
        for nome in (TARDOZ, DORSO, PLANO, SAPATA):
            m = (t["trecho"] == nome) & (t["dz"] > 1e-12)
            if m.any():
                ax.plot(t["sa_solo"][m], t["z"][m], color=MUDO, lw=1.2, ls=(0, (3, 2)), label=rot)
                rot = None
    if f.emp.p_Pah > 0:
        ax.axhline(f.emp.p_zPa, color=TINTA2, lw=0.8, ls=(0, (2, 2)))
        ax.text(ax.get_xlim()[1], f.emp.p_zPa, f" resultante z = {num(f.emp.p_zPa)} m", va="bottom", ha="right",
                fontsize=7.5, color=TINTA2)
    ax.set_xlabel("σa na direção do empuxo (kPa)")
    ax.set_ylabel("cota z acima do fundo da sapata (m)")
    ax.set_xlim(left=0)
    ax.set_ylim(0, None)
    ax.legend(loc="upper right", fontsize=7.5)
    ax.set_title(f"Diagrama de empuxo — Fase {fase}"
                 + (" (repouso K0)" if f.emp.p_rep else f" ({res.entrada.metodo_emp.value})"), loc="left")
    fig.tight_layout(pad=0.5)
    return fig


# ============================================================================= base
def _sigma_linear(x, N, exc, B):
    if N <= 0 or abs(exc) >= B / 2:
        return np.zeros_like(x)
    if abs(exc) <= B / 6:
        return N / B + 12 * N * exc * (B / 2 - x) / B**3
    c = B / 2 - abs(exc)
    return 2 * N / (3 * c) * np.maximum(0.0, 1 - (x if exc >= 0 else B - x) / (3 * c))


def diagrama_base(res):
    B = res.geo.B_base
    x = np.linspace(0, B, 241)
    fig, ax = plt.subplots(figsize=(5.2, 3.5), dpi=150)
    fases = [(res.fase1, AZUL, "Fase 1")] + ([(res.fase2, LARANJA, "Fase 2")] if res.tem_fase2 else [])
    for f, cor, rot in fases:
        s = _sigma_linear(x, f.forcas.F_N, f.verif.R_e, B)
        ax.fill_between(x, 0, s, color=cor, alpha=0.18, lw=0)
        ax.plot(x, s, color=cor, label=f"{rot} — linear")
        v = f.verif
        if 0 < v.R_Bef and not math.isinf(v.R_sef):
            x0 = 0 if v.R_e >= 0 else B - v.R_Bef
            ax.plot([x0, x0, x0 + v.R_Bef, x0 + v.R_Bef], [0, v.R_sef, v.R_sef, 0], color=cor, lw=1.2,
                    ls=(0, (4, 2)), label=f"{rot} — Meyerhof (B' = {num(v.R_Bef)} m)")
        if not math.isinf(v.sig_max):
            xm = 0 if v.R_e >= 0 else B
            ax.annotate(f"{rot}: {num(v.sig_max, 1)} kPa", (xm, v.sig_max), textcoords="offset points",
                        xytext=(8 if xm == 0 else -8, 6 if cor == AZUL else -12),
                        ha="left" if xm == 0 else "right", fontsize=7.5, color=TINTA,
                        bbox=dict(boxstyle="round,pad=0.12", fc=FUNDO, ec="none", alpha=0.85))
    ax.set_xlabel("x a partir da ponta (m)")
    ax.set_ylabel("tensão no solo (kPa)")
    ax.set_xlim(0, B)
    ax.set_ylim(bottom=0)
    topo = ax.get_ylim()[1] * 1.12
    ax.set_ylim(0, topo)
    ax.invert_yaxis()
    for xv, rot in ((res.geo.x_fb, "face frontal"), (res.geo.x_tb, "tardoz")):
        ax.axvline(xv, color=EIXO, lw=0.8)
        ax.text(xv, topo * 0.99, f"{rot} ", fontsize=7, color=MUDO, va="bottom", rotation=90, ha="right")
    ax.legend(loc="upper center", fontsize=7, ncol=2, bbox_to_anchor=(0.5, -0.2))
    ax.set_title("Tensões na base (ponta à esquerda)", loc="left")
    fig.tight_layout(pad=0.5)
    return fig


# ========================================================================== cortina
def diagrama_cortina(res):
    s = res.dim.secoes
    v = res.dim.v
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.4, 4.4), dpi=150, sharey=True)
    a1.plot(s["MSdp"], s["y"], color=AZUL, label="MSd (tração no tardoz)")
    a1.plot(s["MRdp"], s["y"], color=AZUL, lw=1.2, ls=(0, (4, 2)), label="MRd — armadura do tardoz")
    if s["MSdn"].max() > 0:
        a1.plot(-s["MSdn"], s["y"], color=LARANJA, label="MSd (tração na face frontal)")
        a1.plot(-s["MRdn"], s["y"], color=LARANJA, lw=1.2, ls=(0, (4, 2)), label="MRd — armadura frontal")
    a1.axvline(0, color=EIXO, lw=0.8)
    a1.set_xlabel("momento de cálculo (kN·m/m)")
    a1.set_ylabel("cota z (m)")
    a1.set_title("Cortina — momentos", loc="left")
    a1.legend(fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=2)

    nec = np.where(s["Asp"] < 0, np.nan, s["Asp"])
    a2.plot(nec, s["y"], color=AZUL, label="As necessária (tardoz)")
    a2.axvline(v["dm_Ast"], color=AZUL, lw=1.2, ls=(0, (4, 2)), label=f"As efetiva = {num(v['dm_Ast'])}")
    a2.axvline(v["dm_Asmin"], color=MUDO, lw=1.0, ls=(0, (1, 2)), label=f"As mín = {num(v['dm_Asmin'])}")
    if s["Asn"].max() > 0:
        a2.plot(np.where(s["Asn"] < 0, np.nan, s["Asn"]), s["y"], color=LARANJA, label="As necessária (frontal)")
    a2.set_xlabel("área de aço (cm²/m)")
    a2.set_xlim(left=0)
    a2.set_title("Cortina — armadura vertical", loc="left")
    a2.legend(fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=2)
    fig.tight_layout(pad=0.6)
    return fig


# ================================================================ sondagem / lateral
def grafico_esforco_lateral(furo, prop, z_ini: float, z_fim: float, q: float = 0.0):
    """Perfil da sondagem (NSPT e camadas) e esforço lateral no trecho do muro."""
    z_a = max(0.0, z_ini - 1.0)
    z_b = min(max(furo.profundidade, z_fim + 0.5), z_fim + max(3.0, 0.6 * (z_fim - z_ini)))
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.6, 5.4), dpi=150, sharey=True,
                                 gridspec_kw={"width_ratios": [1, 1.25]})
    # ---- painel 1: NSPT e camadas
    ps = [p + 0.225 for p, _ in furo.spt if z_a - 1 <= p <= z_b + 1]
    ns = [n for p, n in furo.spt if z_a - 1 <= p <= z_b + 1]
    n_max = max(ns + [10])
    a1.axhspan(z_ini, z_fim, color=CONCRETO, alpha=0.45, lw=0)
    a1.plot(ns, ps, color=AZUL, marker="o", ms=4, label="NSPT")
    for n, p in zip(ns, ps):
        a1.annotate(f"{n}", (n, p), textcoords="offset points", xytext=(6, -2), fontsize=7, color=TINTA2)
    for c in furo.camadas:
        if z_a <= c.topo <= z_b:
            a1.axhline(c.topo, color=EIXO, lw=0.7)
        meio = (max(c.topo, z_a) + min(c.base, z_b)) / 2
        if min(c.base, z_b) - max(c.topo, z_a) >= 0.55:
            rot = c.tipo if c.tipo != "Não considerar" else c.descricao[:22]
            a1.text(n_max * 1.36, meio, rot + (" (aterro)" if c.aterro else ""), fontsize=7, color=TINTA2,
                    ha="right", va="center")
    a1.set_xlim(0, n_max * 1.4)
    a1.set_xlabel("NSPT (golpes / 30 cm finais)")
    a1.set_ylabel("profundidade abaixo da boca do furo (m)")
    a1.set_title(f"Sondagem {furo.nome} — muro de {num(z_ini)} a {num(z_fim)} m (faixa cinza)", loc="left")
    # ---- painel 2: esforço lateral
    a2.axhspan(z_ini, z_fim, color=CONCRETO, alpha=0.18, lw=0)
    cam, hom = prop.por_camadas, prop.homogeneo
    if cam is not None:
        a2.fill_betweenx(cam.z, 0, cam.ativo, color=AZUL, alpha=0.22, lw=0)
        a2.plot(cam.ativo, cam.z, color=AZUL, label=f"Ativo, por camadas — {num(cam.E_ativo, 1)} kN/m")
        a2.plot(cam.repouso, cam.z, color=LARANJA, label=f"Repouso, por camadas — {num(cam.E_repouso, 1)} kN/m")
        if cam.E_agua > 0:
            a2.plot(cam.agua, cam.z, color=AQUA, label=f"Água — {num(cam.E_agua, 1)} kN/m")
        if hom is not None:
            a2.plot(hom.ativo, hom.z, color=MUDO, lw=1.3, ls=(0, (4, 2)),
                    label=f"Ativo, solo homogêneo adotado — {num(hom.E_ativo, 1)} kN/m")
        for e in prop.arrimado[1:]:
            a2.axhline(e.topo, color=EIXO, lw=0.7)
        if cam.E_ativo > 0:
            zr = z_fim - cam.z_ativo
            a2.annotate(f"resultante ativa a {num(cam.z_ativo)} m do fundo", (0, zr), textcoords="offset points",
                        xytext=(8, -3), fontsize=7, color=TINTA2)
            a2.plot([0], [zr], marker=">", ms=6, color=AZUL, clip_on=False)
    else:
        a2.text(0.5, 0.5, "sem camadas com parâmetros\nno trecho do muro", transform=a2.transAxes, ha="center",
                va="center", color=MUDO)
    if furo.na is not None and z_a <= furo.na <= z_b:
        for ax in (a1, a2):
            ax.axhline(furo.na, color=AGUA, lw=1.1, ls=(0, (5, 3)))
        a2.text(a2.get_xlim()[1], furo.na, f"NA {num(furo.na)} m ", fontsize=7.5, color=AGUA, ha="right", va="bottom")
    a2.set_xlim(left=0)
    a2.set_xlabel("pressão lateral (kPa)")
    a2.set_title("Esforço lateral no muro" + (f" — sobrecarga q = {num(q, 1)} kPa" if q else ""), loc="left")
    a2.legend(fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=1)
    a1.set_ylim(z_b, z_a)
    fig.tight_layout(pad=0.6)
    return fig


# ====================================================================== paramétrico
def grafico_parametrico(linhas: list[dict], rotulo_x: str, limites: dict):
    paineis = (("FSt", "FS tombamento", "min"), ("FSd", "FS deslizamento", "min"), ("eB", "e / B", "max"),
               ("FScc", "FS capacidade de carga", "min"))
    fig, eixos = plt.subplots(1, 4, figsize=(10.5, 2.7), dpi=150)
    fases = sorted({ln["fase"] for ln in linhas})
    for ax, (chave, titulo, tipo) in zip(eixos, paineis):
        for fase, cor in zip(fases, (AZUL, LARANJA)):
            xs = [ln["valor"] for ln in linhas if ln["fase"] == fase]
            ys = [min(ln[chave], 99) if not math.isinf(ln[chave]) else np.nan for ln in linhas if ln["fase"] == fase]
            ax.plot(xs, ys, color=cor, marker="o", ms=3, label=f"Fase {fase}")
        lim = limites[chave]
        ax.axhline(lim, color=CRITICO, lw=1.0, ls=(0, (4, 2)))
        ax.text(ax.get_xlim()[0], lim, f" {'mín' if tipo == 'min' else 'máx'} {num(lim, 2)}", fontsize=7,
                color=TINTA2, va="bottom")
        ax.set_title(titulo, loc="left")
        ax.set_xlabel(rotulo_x, fontsize=7.5)
        ax.set_ylim(bottom=0)
    if len(fases) > 1:
        eixos[0].legend(fontsize=7)
    fig.tight_layout(pad=0.5)
    return fig
