"""Apresentação das armaduras: quadro de ferros e desenho da seção com as posições indicadas."""
from __future__ import annotations

import math
from dataclasses import dataclass

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Polygon

from core.concreto import area_barras
from core.dimensionamento import NAO_OK
from core.enums import PosicaoContraforte
from core.solver import BITOLAS
from ui.formato import num
from ui.graficos import AZUL, CONCRETO, CRITICO, EIXO, FUNDO, LARANJA, MUDO, TINTA, TINTA2


@dataclass(frozen=True)
class Ferro:
    pos: str            # N1, N2 ...
    onde: str
    descricao: str      # "ϕ 12,5 c/ 10"
    As_ef: float | None
    As_nec: float | None
    unidade: str
    ok: bool | None     # None = sem verificação (armadura de distribuição sugerida)
    sugerido: bool = False


def _fi(phi: float) -> str:
    return f"ϕ {phi:g}".replace(".", ",")


def _barras(phi: float, s: float) -> str:
    return f"{_fi(phi)} c/ {s:g}".replace(".", ",")


def menor_distribuicao(As_min: float, s_max: float = 20.0) -> tuple[float, float]:
    """Menor ϕ × espaçamento (cm) com área ≥ As_min, para armadura de distribuição."""
    opcoes = sorted((area_barras(p, s), p, s) for p in BITOLAS[:5] for s in (20.0, 17.5, 15.0, 12.5, 10.0)
                    if s <= s_max)
    for A, p, s in opcoes:
        if A >= As_min:
            return p, s
    return opcoes[-1][1], opcoes[-1][2]


def quadro_de_ferros(res) -> list[Ferro]:
    e, d = res.entrada, res.dim
    ch, ex = d.checks, d.extras
    cf = e.cf_usar
    frente = e.cf_tipo == PosicaoContraforte.FRENTE

    def ferro(pos, onde, phi, s, idx, extras=(), un="cm²/m"):
        cs = [ch[i] for i in idx] + [x for x in ex if any(k in x.nome for k in extras)]
        cs = [c for c in cs if c.situacao != "—"]
        de_area = [c for c in cs if c.unidade in ("cm²/m", "cm²")]
        nec = [c.solicitante for c in de_area]
        insuf = any(n < 0 for n in nec)
        As_ef = area_barras(phi, s)
        As_nec = (-1.0 if insuf else max(nec)) if nec else None
        outras = all(c.situacao != NAO_OK for c in cs if c not in de_area)
        ok = None if not cs else (outras and not insuf and (As_nec is None or As_ef >= As_nec - 1e-9))
        return Ferro(pos, onde, _barras(phi, s), As_ef, As_nec, un, ok)

    def sugestao(pos, onde, As_min):
        p, s = menor_distribuicao(As_min)
        return Ferro(pos, onde, _barras(p, s), area_barras(p, s), As_min, "cm²/m", None, True)

    f = [
        ferro("N1", "Cortina — vertical, face do tardoz (terra)", e.ar_tz_phi, e.ar_tz_s, (0, 1, 2, 3, 6),
              ("Cortina — face do tardoz",)),
        ferro("N2", "Cortina — vertical, face frontal", e.ar_fr_phi, e.ar_fr_s, (4, 5), ("Cortina — face frontal",)),
        ferro("N3", "Base — inferior, transversal ao muro", e.ar_bi_phi, e.ar_bi_s, (10, 11, 12, 13),
              ("Base — face inferior", "(face inferior)") + (("cortante na junção",) if frente else ())),
        ferro("N4", "Base — superior, transversal ao muro", e.ar_bs_phi, e.ar_bs_s, (14, 15, 16),
              ("Base — face superior", "(face superior)", "Talão em balanço")
              + (() if frente else ("cortante na junção",))),
    ]
    if cf:
        f += [
            ferro("N5", "Cortina — horizontal, face do tardoz (apoios nos contrafortes)", e.ar_hz_tz_phi,
                  e.ar_hz_tz_s, (7, 9)),
            ferro("N6", "Cortina — horizontal, face frontal (meio do vão)", e.ar_hz_fr_phi, e.ar_hz_fr_s, (8, 9)),
            ferro("N7", "Base — inferior, paralela ao muro", e.ar_bl_i_phi, e.ar_bl_i_s, (17, 19, 20)),
            ferro("N8", "Base — superior, paralela ao muro", e.ar_bl_s_phi, e.ar_bl_s_s, (18, 19)),
        ]
        c9 = [ch[i] for i in (21, 22, 23, 24)]
        nec9 = max(ch[21].solicitante, ch[22].solicitante) if ch[21].solicitante >= 0 else -1.0
        f.append(Ferro("N9", "Contraforte — barras tracionadas junto à borda inclinada",
                       f"{e.cf_n} {_fi(e.cf_phi)}", d.v["cf_As"], nec9, "cm²",
                       all(c.situacao != NAO_OK for c in c9)))
    else:
        as_c = d.v.get("dm_Asdist", 0.9)
        as_b = max(0.2 * max(d.v["dm_As_pt"], d.v["dm_As_tl"], 0.0), 0.9, 0.5 * d.v["dm_Asminb"])
        f += [sugestao("N5", "Cortina — horizontal (distribuição), face do tardoz", as_c),
              sugestao("N6", "Cortina — horizontal (distribuição), face frontal", as_c),
              sugestao("N7", "Base — inferior, paralela ao muro (distribuição)", as_b),
              sugestao("N8", "Base — superior, paralela ao muro (distribuição)", as_b)]
    return f


def tabela(ferros: list[Ferro]) -> list[dict]:
    def sit(x: Ferro) -> str:
        return "sugestão" if x.sugerido else ("—" if x.ok is None else ("✔ OK" if x.ok else "✖ NÃO OK"))
    return [{"Pos.": x.pos, "Armadura": x.descricao, "Onde": x.onde,
             "As ef.": "—" if x.As_ef is None else num(x.As_ef),
             "As nec.": "—" if x.As_nec is None else ("insuficiente" if x.As_nec < 0 else num(x.As_nec)),
             "Un.": x.unidade, "Situação": sit(x)} for x in ferros]


# ----------------------------------------------------------------------- desenho
def desenho(res, largura: float = 7.6):
    """Seção transversal com as armaduras e a indicação de bitola e espaçamento de cada posição."""
    e, g = res.entrada, res.geo
    F = {x.pos: x for x in quadro_de_ferros(res)}
    B, H, hs = g.B_base, e.H_muro, e.h_sap
    cf, frente = e.cf_usar, e.cf_tipo == PosicaoContraforte.FRENTE
    off = max(e.cob_ct / 100, 0.05, 0.016 * H)           # cobrimento exagerado para ser legível
    offb = max(e.cob_bs / 100, 0.05, 0.016 * H)
    offb = min(offb, hs / 3.2)
    off = min(off, e.t_topo / 3.2)

    xd, xe = B + max(0.55, 0.14 * H), -max(0.55, 0.14 * H)
    lim_x, lim_z = (xe - 2.1, xd + 2.1), (-0.02 * H - 0.55, H + 0.3)
    fig, ax = plt.subplots(figsize=(largura, largura * (lim_z[1] - lim_z[0]) / (lim_x[1] - lim_x[0]) + 0.35),
                           dpi=150)
    ax.set_aspect("equal")
    ax.grid(False)
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    if cf:
        ax.add_patch(Polygon(g.contraforte.vertices, closed=True, fc="#f1f0ec", ec=TINTA2, lw=0.9,
                             ls=(0, (4, 2)), zorder=1))
    ax.add_patch(Polygon(g.croqui["muro"][:-1], closed=True, fc=CONCRETO, ec=TINTA, lw=1.1, alpha=0.55, zorder=2))

    def xt(z):
        return g.x_tb + (g.x_tt - g.x_tb) * (max(z, hs) - hs) / g.h_cort

    def xf(z):
        return g.x_fb + (g.x_ft - g.x_fb) * (max(z, hs) - hs) / g.h_cort

    def cor(pos):
        x = F.get(pos)
        return CRITICO if (x and x.ok is False) else TINTA

    def barra(pts, pos, **kw):
        xs, zs = zip(*pts)
        ax.plot(xs, zs, color=AZUL if cor(pos) == TINTA else CRITICO, lw=2.0, solid_capstyle="round", zorder=5,
                **kw)

    def pontos(xs, zs, pos):
        x = F.get(pos)
        ax.plot(xs, zs, ls="none", marker="o", ms=3.4, mfc=LARANJA if cor(pos) == TINTA else CRITICO,
                mec="none", alpha=0.55 if (x and x.sugerido) else 1.0, zorder=6)

    def rotulo(pos, alvo, texto_xy, ha):
        x = F.get(pos)
        if x is None:
            return
        marca = " ✖" if x.ok is False else ""
        compl = " (sugestão)" if x.sugerido else ""
        ax.annotate(f"{pos}  {x.descricao}{marca}\n{x.onde.split(' — ')[1].split(' (')[0]}{compl}", alvo, texto_xy,
                    ha=ha, va="center", fontsize=7.6, color=cor(pos), zorder=8,
                    arrowprops=dict(arrowstyle="-", color=MUDO, lw=0.8, shrinkA=2, shrinkB=1),
                    bbox=dict(boxstyle="round,pad=0.25", fc=FUNDO, ec=EIXO, lw=0.6))

    z_topo = H - off
    # N1 — vertical do tardoz, ancorada na base com dobra para a ponta
    perna = min(0.55, max(0.2, g.x_tb - off - offb - 0.05))
    barra([(xt(z_topo) - off, z_topo), (g.x_tb - off, hs), (g.x_tb - off, offb + 0.012 * H),
           (g.x_tb - off - perna, offb + 0.012 * H)], "N1")
    # N2 — vertical da face frontal
    barra([(xf(z_topo) + off, z_topo), (g.x_fb + off, hs), (g.x_fb + off, offb + 0.012 * H)], "N2")
    # N3 / N4 — base, transversais ao muro
    dob = min(0.18, hs - 2 * offb)
    barra([(offb, offb + dob), (offb, offb), (B - offb, offb), (B - offb, offb + dob)], "N3")
    barra([(offb, hs - offb - dob), (offb, hs - offb), (B - offb, hs - offb), (B - offb, hs - offb - dob)], "N4")

    # barras perpendiculares à seção (pontos)
    def esp(pos, padrao):
        txt = F[pos].descricao.split("c/")[-1].strip().replace(",", ".")
        try:
            return float(txt) / 100
        except ValueError:
            return padrao
    r = 0.022 * max(1.0, H / 4)
    for pos, fx, sinal in (("N5", xt, -1), ("N6", xf, +1)):
        zs = np.arange(hs + esp(pos, 0.2) / 2, H - off, esp(pos, 0.2))
        pontos([fx(z) + sinal * (off + r) for z in zs], zs, pos)
    for pos, z0 in (("N7", offb + r), ("N8", hs - offb - r)):
        xs = np.arange(offb + esp(pos, 0.2) / 2, B - offb, esp(pos, 0.2))
        pontos(xs, np.full_like(xs, z0), pos)

    # N9 — contraforte
    if cf:
        v = g.contraforte.vertices
        (xa, za), (xb, zb) = (v[0], v[3]) if frente else (v[1], v[2])     # borda inclinada (externa)
        mx, mz = (xa + xb) / 2, (za + zb) / 2
        ix, iz = g.contraforte.x - mx, g.contraforte.z - mz              # para dentro do contraforte
        n = math.hypot(ix, iz) or 1.0
        ix, iz = ix / n * off * 1.6, iz / n * off * 1.6
        barra([(xa + ix, za + iz), (xb + ix, zb + iz)], "N9", ls=(0, (5, 1.5)))

    # ---------------------------------------------------------------- rótulos
    hc = g.h_cort
    rotulo("N1", (xt(hs + 0.66 * hc) - off, hs + 0.66 * hc), (xd, hs + 0.80 * hc), "left")
    rotulo("N5", (xt(hs + 0.42 * hc) - off - r, hs + 0.42 * hc), (xd, hs + 0.56 * hc), "left")
    rotulo("N2", (xf(hs + 0.66 * hc) + off, hs + 0.66 * hc), (xe, hs + 0.80 * hc), "right")
    rotulo("N6", (xf(hs + 0.42 * hc) + off + r, hs + 0.42 * hc), (xe, hs + 0.56 * hc), "right")
    if cf:
        v = g.contraforte.vertices
        meio = ((v[0][0] + v[3][0]) / 2, (v[0][1] + v[3][1]) / 2) if frente else \
            ((v[1][0] + v[2][0]) / 2, (v[1][1] + v[2][1]) / 2)
        rotulo("N9", meio, (xe if frente else xd, hs + 0.30 * hc), "right" if frente else "left")
    rotulo("N4", (B - offb - 0.25 * max(e.b_talao, 0.3), hs - offb), (xd, hs + 0.06 * hc), "left")
    rotulo("N8", (B - offb - 0.55 * max(e.b_talao, 0.3), hs - offb - r), (xd, -0.02 * H - 0.16), "left")
    rotulo("N3", (offb + 0.25 * max(e.b_ponta, 0.3), offb), (xe, hs + 0.06 * hc), "right")
    rotulo("N7", (offb + 0.55 * max(e.b_ponta, 0.3), offb + r), (xe, -0.02 * H - 0.16), "right")

    ax.text(g.x_tt + 0.08, H + 0.05, "terra", fontsize=7.5, color=TINTA2, va="bottom")
    ax.text(g.x_ft - 0.08, H + 0.05, "frente", fontsize=7.5, color=TINTA2, va="bottom", ha="right")
    ax.set_xlim(*lim_x)
    ax.set_ylim(*lim_z)
    ax.set_title("Seção transversal — armaduras (cobrimentos fora de escala)", loc="left")
    fig.tight_layout(pad=0.4)
    return fig


def diagrama_placa(res):
    """Momentos de cálculo do painel da cortina entre contrafortes, ao longo da altura."""
    pc = res.dim.placas.get("cortina")
    if pc is None:
        return None
    y = pc["y"] + res.entrada.h_sap
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.4, 3.9), dpi=150, sharey=True)
    a1.plot(pc["Mht_y"], y, color=AZUL, label="nos contrafortes (face do tardoz)")
    a1.plot(pc["Mhf_y"], y, color=LARANJA, label="no meio do vão (face frontal)")
    a1.set_title("Momento horizontal — armadura horizontal", loc="left")
    a1.set_xlabel("momento de cálculo (kN·m/m)")
    a1.set_ylabel("cota z (m)")
    a2.plot(pc["Mvt_y"], y, color=AZUL, label="face do tardoz (engaste na base)")
    a2.plot(pc["Mvf_y"], y, color=LARANJA, label="face frontal (campo)")
    a2.set_title("Momento vertical — armadura vertical", loc="left")
    a2.set_xlabel("momento de cálculo (kN·m/m)")
    for ax in (a1, a2):
        ax.set_xlim(left=0)
        ax.legend(fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=1)
    fig.tight_layout(pad=0.6)
    return fig
