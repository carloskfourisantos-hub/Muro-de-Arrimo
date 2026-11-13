"""Verificações de estabilidade externa — port das abas ``Resumo`` / ``Resumo F2``.

Critérios da ABNT NBR 11682 (muros de arrimo): tombamento, deslizamento,
excentricidade/tensões na base e capacidade de carga (Vesic, sapata corrida).

Onde a planilha usa sentinelas (FS = 999, σ = 10 000 kPa — convenção do GEO5),
o núcleo devolve ``math.inf``; ``core.planilha`` reconverte para comparação.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .enums import ConvResistentes, ConvTravamento, LarguraEfetiva, ModoCapacidade
from .forcas import Forcas
from .geometria import Geometria

INF = math.inf


@dataclass(frozen=True)
class Capacidade:
    CC_phi: float
    CC_Nq: float
    CC_Nc: float
    CC_Ng: float
    CC_q0: float
    CC_g: float
    CC_H: float
    CC_m: float
    CC_iq: float
    CC_ig: float
    CC_ic: float
    CC_qult: float


@dataclass(frozen=True)
class Verificacoes:
    fase: int
    # tombamento
    R_FSt: float
    ok_tomb: bool
    # deslizamento
    R_Hact: float
    delta_b: float
    adesao: float
    Hres_atrito: float
    Hres_adesao: float
    Hres_externas: float
    Hres_estacas: float
    R_Hres: float
    R_FSd: float
    ok_desl: bool
    # excentricidade e tensões
    R_xR: float
    R_e: float
    R_eB: float
    ok_exc: bool
    R_Bef: float
    sig_max: float
    sig_min: float
    sig_max_em: str
    R_sef: float
    # capacidade de carga
    cap: Capacidade
    R_qult: float
    R_FScc: float
    ok_cap: bool

    @property
    def verificacoes_ok(self) -> bool:
        return self.ok_tomb and self.ok_desl and self.ok_exc and self.ok_cap


def tensoes_lineares(N: float, e: float, B: float) -> tuple[float, float]:
    """σmax, σmin da distribuição linear (triangular se |e| > B/6)."""
    if N <= 0:
        return 0.0, 0.0
    ae = abs(e)
    if ae >= B / 2:
        return INF, 0.0
    if ae <= B / 6:
        return N / B * (1 + 6 * ae / B), N / B * (1 - 6 * ae / B)
    return 2 * N / (3 * (B / 2 - ae)), 0.0


def calcular_capacidade(e, F: Forcas, Bef: float) -> Capacidade:
    phi = math.radians(e.phi_f)
    Nq = math.exp(math.pi * math.tan(phi)) * math.tan(math.pi / 4 + phi / 2) ** 2
    Nc = 5.14 if e.phi_f == 0 else (Nq - 1) / math.tan(phi)
    Ng = 2 * (Nq + 1) * math.tan(phi)
    q0 = e.gam_f * max(0.0, e.D_frente - e.hw_fr) + (e.gsat_f - e.gam_w) * min(e.D_frente, e.hw_fr)
    gam = e.gsat_f - e.gam_w if max(e.hw_at, e.hw_fr) > 0 else e.gam_f
    H = max(0.0, F.F_Hnet)
    if e.phi_f == 0:
        m = 1.0
    else:
        m = max(0.0, 1 - H / (max(1e-9, F.F_N) + Bef * e.c_f / math.tan(phi)))
    iq, ig = m**2, m**3
    if e.phi_f == 0:
        ic = max(0.0, 1 - 2 * H / max(1e-9, Bef * e.c_f * Nc))
    else:
        ic = iq - (1 - iq) / (Nc * math.tan(phi))
    qult = e.c_f * Nc * ic + q0 * Nq * iq + 0.5 * gam * Bef * Ng * ig
    return Capacidade(phi, Nq, Nc, Ng, q0, gam, H, m, iq, ig, ic, qult)


def calcular_verificacoes(e, g: Geometria, F: Forcas) -> Verificacoes:
    B = g.B_base
    somar_res = e.conv_res == ConvResistentes.SOMAR
    somar_trav = e.trav_conv == ConvTravamento.SOMAR

    # ---- tombamento
    FSt = F.F_Mres / F.F_Movr if F.F_Movr > 0 else INF

    # ---- excentricidade (necessária para a adesão no deslizamento)
    xR = (F.F_Mres - F.F_Movr) / F.F_N if F.F_N > 0 else 0.0
    exc = B / 2 - xR
    eB = abs(exc) / B
    Bef = max(0.0, B - 2 * (max(0.0, exc) if e.bef_desl == LarguraEfetiva.GEO5 else abs(exc)))

    # ---- deslizamento
    Hact = F.F_Hact - (0.0 if somar_res else F.F_Hres_ext) - (0.0 if somar_trav else F.F_Htrav)
    delta_b = e.k_phi * e.phi_f
    adesao = e.k_c * e.c_f
    H_atr = max(0.0, F.F_N) * math.tan(math.radians(delta_b))
    H_ade = adesao * Bef
    H_ext = (F.F_Hres_ext if somar_res else 0.0) + (F.F_Htrav if somar_trav else 0.0)
    H_est = F.anc.anc_Hm
    Hres = H_atr + H_ade + H_ext + H_est
    FSd = Hres / Hact if Hact > 0 else INF

    # ---- tensões
    smax, smin = tensoes_lineares(F.F_N, exc, B)
    if F.F_N <= 0:
        sef = 0.0
    else:
        sef = F.F_N / Bef if Bef > 0 else INF

    # ---- capacidade de carga
    cap = calcular_capacidade(e, F, Bef)
    qult = e.qult_inf if e.cc_modo == ModoCapacidade.INFORMADA else cap.CC_qult
    if F.F_N <= 0:
        FScc = 0.0
    else:
        FScc = qult / sef if sef > 0 else INF
        if math.isinf(sef):
            FScc = 0.0

    return Verificacoes(
        F.fase, FSt, FSt >= e.FSt_min,
        Hact, delta_b, adesao, H_atr, H_ade, H_ext, H_est, Hres, FSd, FSd >= e.FSd_min,
        xR, exc, eB, eB <= e.eB_lim, Bef, smax, smin, "ponta" if exc >= 0 else "talão", sef,
        cap, qult, FScc, FScc >= e.FScc_min)
