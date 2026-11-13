"""Empuxo no plano de cálculo — port das abas ``Empuxo`` / ``Empuxo F2``.

Integração numérica por fatias de altura vertical (ponto médio). Três trechos:
tardoz real (ou dorso virtual), plano inclinado da cunha e altura da sapata.
A planilha usa 40 + 40 + 20 fatias; aqui o refinamento é um parâmetro.

Colunas da planilha → arrays: ver comentários ``# col X`` ao lado de cada linha.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .enums import ConvRankine, MetodoEmpuxo, ResFrontal, ScVertical, TipoEmpuxo
from .geometria import TOL, Geometria

SEM_NA = 1e9
FATIAS_PLANILHA = (40, 40, 20)

TARDOZ, DORSO, PLANO, SAPATA = "Tardoz", "Dorso virtual", "Plano inclinado", "Sapata"


def k_mazindrani(r, cb: float, cphi: float, sphi: float):
    """K' de Mazindrani-Ganjali (Rankine com coesão e terreno inclinado)."""
    raiz = np.sqrt(np.maximum(0.0, 4 * cb**2 * (cb**2 - cphi**2) + 4 * r**2 * cphi**2
                              + 8 * r * cb**2 * sphi * cphi))
    return (2 * cb**2 + 2 * r * cphi * sphi - raiz) / cphi**2 - 1


def ka_coulomb(phi: float, alfa, delta, beta: float):
    """Ka de Müller-Breslau (α = inclinação do paramento com a vertical)."""
    num = np.maximum(0.0, np.sin(phi + delta) * np.sin(phi - beta))
    return np.cos(phi - alfa) ** 2 / (
        np.cos(alfa) ** 2 * np.cos(alfa + delta)
        * (1 + np.sqrt(num / (np.cos(alfa + delta) * np.cos(alfa - beta)))) ** 2)


def kac_coulomb(phi: float, alfa, delta, beta: float):
    """Coeficiente da coesão (forma que reproduz o relatório do GEO5)."""
    return math.cos(phi) * math.cos(beta) * np.cos(alfa) ** 2 / (1 + np.sin(phi + delta - alfa - beta))


@dataclass(frozen=True)
class Empuxo:
    fase: int
    p_Hv: float
    zA_top: float
    zA_bot: float
    zB_bot: float
    p_dw: float
    p_b: float
    p_phi: float
    p_rep: int
    p_K0: float
    p_KaR: float
    p_Pa: float
    p_Pah: float
    p_zPa: float
    p_Pah_s: float
    p_Pah_q: float
    p_Pav_c: float
    p_Pav_s: float
    p_Pav_q: float
    p_Pav: float
    p_xPav: float
    p_U: float
    p_zU: float
    p_Uf: float
    p_zUf: float
    p_K0f: float
    p_Rff: float
    p_zRff: float
    p_u0: float
    p_uB: float
    p_Usub: float
    p_xUsub: float
    fatias: dict  # colunas da tabela de fatias (arrays numpy)


def _pontos_medios(topo: float, base: float, n: int) -> np.ndarray:
    i = np.arange(n)
    return topo - (i + 0.5) * (topo - base) / n


def calcular_empuxo(e, g: Geometria, fase: int = 1, fatias: tuple[int, int, int] = FATIAS_PLANILHA) -> Empuxo:
    hs, B = e.h_sap, g.B_base
    nA, nB, nS = fatias
    p_Hv = g.z_top_pl
    zA_top = p_Hv
    zA_bot = hs if (g.cv == 1 or e.b_talao <= TOL) else max(hs, min(g.z_P, p_Hv))
    zB_bot = hs
    p_dw = p_Hv - min(e.hw_at, p_Hv) if e.hw_at > 0 else SEM_NA
    p_b = math.radians(e.beta_t)
    p_phi = math.radians(e.phi_at)
    cb, cphi, sphi = math.cos(p_b), math.cos(p_phi), math.sin(p_phi)
    p_rep = 1 if (fase == 2 and e.trav_usar and e.trav_emp == TipoEmpuxo.REPOUSO) else 0
    p_K0 = (1 - sphi) * (1 + math.sin(p_b))
    rz = math.sqrt(max(0.0, cb**2 - cphi**2))
    p_KaR = cb * (cb - rz) / (cb + rz)
    rankine = e.metodo_emp == MetodoEmpuxo.RANKINE
    geo5_rk = e.rk_conv == ConvRankine.GEO5

    # ---- geometria das fatias
    z = np.concatenate([_pontos_medios(zA_top, zA_bot, nA),          # col D
                        _pontos_medios(zA_bot, zB_bot, nB),
                        _pontos_medios(hs, 0.0, nS)])
    dz = np.concatenate([np.full(nA, (zA_top - zA_bot) / nA),        # col AF
                         np.full(nB, (zA_bot - zB_bot) / nB),
                         np.full(nS, hs / nS)])
    trecho = np.array([DORSO if g.cv == 1 else TARDOZ] * nA + [PLANO] * nB + [SAPATA] * nS)  # col E
    eh_plano, eh_tardoz = trecho == PLANO, trecho == TARDOZ
    eh_sapata, eh_dorso = trecho == SAPATA, trecho == DORSO
    alfa = np.where(eh_plano, g.th_c, np.where(eh_tardoz, g.a_t, 0.0))                      # col F
    delta = np.where(eh_sapata | eh_tardoz, math.radians(e.delta_est), math.radians(e.delta_dv))  # col G
    x = np.where(eh_sapata | eh_dorso, B,                                                    # col H
                 np.where(eh_tardoz, g.x_tb + (g.x_tt - g.x_tb) * (z - hs) / g.h_cort,
                          B - (z - hs) * math.tan(g.th_c)))
    d = p_Hv - z                                                                             # col C

    # ---- tensões e coeficientes
    sz = e.q_sc + e.gam_at * np.minimum(d, p_dw) + (e.gsat_at - e.gam_w) * np.maximum(0.0, d - p_dw)  # col I
    r = np.where(sz > 1e-6, e.c_at / np.where(sz > 1e-6, sz, 1.0), 1e6)                     # col J
    Kp = k_mazindrani(r, cb, cphi, sphi)                                                     # col K
    sz0 = sz - e.q_sc                                                                        # col W
    r0 = np.where(sz0 > 1e-6, e.c_at / np.where(sz0 > 1e-6, sz0, 1.0), 1e6)                 # col X
    Kp0 = k_mazindrani(r0, cb, cphi, sphi)                                                   # col Y
    Ka = ka_coulomb(p_phi, alfa, delta, p_b)                                                 # col M
    Kac = kac_coulomb(p_phi, alfa, delta, p_b)                                               # col N
    Kq = np.where(eh_sapata, Ka, p_KaR)                                                      # col AG
    if geo5_rk:                                                                              # col L
        sa_rk = np.maximum(0.0, sz0 * Kp0 + e.q_sc * Kq)
    else:
        sa_rk = np.maximum(0.0, sz * Kp * cb)
    sa_cl = np.maximum(0.0, sz * Ka - 2 * e.c_at * Kac)                                      # col O
    if p_rep == 1:
        incl = np.zeros_like(z)                                                              # col P
        sa = sz * p_K0                                                                       # col Q
        sa0 = sz0 * p_K0                                                                     # col Z
    elif rankine:
        incl = np.full_like(z, p_b)
        sa = sa_rk
        sa0 = np.maximum(0.0, sz0 * Kp0 * (1.0 if geo5_rk else cb))
    else:
        incl = alfa + delta
        sa = sa_cl
        sa0 = np.maximum(0.0, sz0 * Ka - 2 * e.c_at * Kac)

    dPa = sa * dz                                                                            # col R
    dPah = dPa * np.cos(incl)                                                                # col S
    dPav = dPa * np.sin(incl)                                                                # col T
    dPav0 = sa0 * dz * np.sin(incl)                                                          # col AA
    dPavq = (Kq if rankine else Ka) * e.q_sc * dz * np.sin(incl)                             # col AC
    dPah0 = sa0 * dz * np.cos(incl)                                                          # col AE

    p_Pa = float(dPa.sum())
    p_Pah = float(dPah.sum())
    p_zPa = float((dPah * z).sum() / p_Pah) if p_Pah > 0 else 0.0
    p_Pah_s = float(dPah0.sum())
    p_Pav_c = float(dPav.sum())
    p_Pav_s = float(dPav0.sum())
    p_Pav_q = float(dPavq.sum())
    geo5_v = e.sc_vert == ScVertical.GEO5
    p_Pav = p_Pav_s + p_Pav_q if geo5_v else p_Pav_c
    if p_Pav > 0:
        if geo5_v:
            p_xPav = float(((dPav0 * x).sum() + (dPavq * x).sum()) / p_Pav)
        else:
            p_xPav = float((dPav * x).sum() / p_Pav)
    else:
        p_xPav = B

    # ---- água e solo da frente
    hw = min(e.hw_at, p_Hv)
    p_U = 0.5 * e.gam_w * hw**2
    p_Uf = 0.5 * e.gam_w * e.hw_fr**2
    p_K0f = 1 - math.sin(math.radians(e.phi_f))
    if e.ff_tipo == ResFrontal.REPOUSO and e.D_frente > 0:
        p_Rff = 0.5 * p_K0f * (e.gam_f * max(0.0, e.D_frente - e.hw_fr)
                               + (e.gsat_f - e.gam_w) * min(e.D_frente, e.hw_fr)) * e.D_frente
    else:
        p_Rff = 0.0
    p_u0 = e.gam_w * e.hw_fr
    p_uB = e.gam_w * hw
    p_Usub = (p_u0 + p_uB) / 2 * B
    p_xUsub = B * (p_u0 + 2 * p_uB) / (3 * (p_u0 + p_uB)) if p_u0 + p_uB > 0 else 0.0

    tabela = dict(z=z, d=d, trecho=trecho, alfa=alfa, delta=delta, x=x, sz=sz, Kp=Kp, Ka=Ka, Kac=Kac,
                  sa_rankine=sa_rk, sa_coulomb=sa_cl, incl=incl, sa=sa, sa_solo=sa0, dz=dz,
                  dPa=dPa, dPah=dPah, dPav=dPav)
    return Empuxo(fase, p_Hv, zA_top, zA_bot, zB_bot, p_dw, p_b, p_phi, p_rep, p_K0, p_KaR,
                  p_Pa, p_Pah, p_zPa, p_Pah_s, p_Pah - p_Pah_s, p_Pav_c, p_Pav_s, p_Pav_q, p_Pav, p_xPav,
                  p_U, hw / 3, p_Uf, e.hw_fr / 3, p_K0f, p_Rff, e.D_frente / 3,
                  p_u0, p_uB, p_Usub, p_xUsub, tabela)
