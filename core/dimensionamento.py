"""Dimensionamento estrutural (ABNT NBR 6118) — port da aba ``Dimensionamento``.

Cortina em balanço (21 seções), ponta e talão em balanço, e — para muro com
contrafortes — cortina e base como lajes entre contrafortes e o contraforte
como viga em balanço. Os valores ficam em ``Dimensionamento.v`` com os nomes
definidos na planilha (``dm_*``, ``cs_*``, ``bd_*``, ``cf_*``).

Momento positivo = tração na face do tardoz (aterro).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import placa
from .concreto import Concreto, area_barras, criar_concreto
from .empuxo import SEM_NA, k_mazindrani
from .enums import (CombinacoesBase, LimiteXd, MetodoEmpuxo, ModeloCortante, ModeloLajeCF, MomentoPonta, PesoNA, PosicaoContraforte,
                    PressaoLaje, ResFrontal, Subpressao, TensaoDim, TipoEmpuxo)
from .forcas import PREFIXOS_EMPUXO
from .geometria import TOL, Geometria
from .verificacoes import EB_FAIXA, INF, tensoes_lineares

OK, NAO_OK, NA = "OK", "NÃO OK", "—"
N_SECOES, N_FATIAS, N_BASE = 20, 100, 40
N_PLACA = 14        # divisões da malha da placa em cada direção


@dataclass(frozen=True)
class Check:
    nome: str
    solicitante: float
    resistente: float
    situacao: str
    grupo: str            # Cortina | Base | Lajes entre contrafortes | Contraforte
    extra: bool = False   # True = verificação do aplicativo (não existe na planilha)
    unidade: str = ""


@dataclass(frozen=True)
class Dimensionamento:
    concreto: Concreto
    v: dict                    # valores nomeados (dm_*, cs_*, bd_*, cf_*)
    secoes: dict               # tabela das 21 seções da cortina
    fatias: dict               # 100 fatias de pressão na cortina
    base: dict                 # 40 fatias ao longo da base
    checks: tuple[Check, ...]  # 26 verificações da planilha
    extras: tuple[Check, ...]  # verificações adicionais (NBR 6118)
    notas: tuple[str, ...] = field(default_factory=tuple)
    base_invalida: bool = False  # resultante fora da base: ponta/talão sem tensões válidas
    placas: dict = field(default_factory=dict)   # painéis resolvidos como placa (muro com contrafortes)

    @property
    def dm_geral(self) -> bool:
        """Mesmo critério de ``Dimensionamento!O33``."""
        return all(c.situacao != NAO_OK for c in self.checks)

    @property
    def atende(self) -> bool:
        return (self.dm_geral and not self.base_invalida
                and all(c.situacao != NAO_OK for c in self.extras))


def _st_as(nec: float, ef: float) -> str:
    return NAO_OK if nec < 0 else (OK if ef >= nec - 1e-9 else NAO_OK)


def _st_max(sol: float, res: float) -> str:
    return OK if sol <= res + 1e-9 else NAO_OK


def _sigma_base(x: np.ndarray, N: float, exc: float, Bef: float, sef: float, B: float, retangular: bool):
    if N <= 0:
        return np.zeros_like(x)
    if retangular:
        dentro = (x <= Bef) if exc >= 0 else (x >= B - Bef)
        return np.where(dentro, sef, 0.0)
    ae = abs(exc)
    if ae <= B / 6:
        return N / B + 12 * N * exc * (B / 2 - x) / B**3
    if ae >= B / 2:      # resultante fora da base: sem distribuição de tensões válida
        return np.zeros_like(x)
    c = B / 2 - ae
    dist = x if exc >= 0 else B - x
    return 2 * N / (3 * c) * np.maximum(0.0, 1 - dist / (3 * c))


def calcular_dimensionamento(e, g: Geometria, f1, f2) -> Dimensionamento:
    """``f1``/``f2`` = resultados das fases (com .emp, .forcas, .verif)."""
    hs, H, B = e.h_sap, e.H_muro, g.B_base
    c = criar_concreto(e.fck_c, e.fyk_s, e.gc_c, e.gs_s)
    gf, gw = e.gf_f, e.gw_f
    trav = e.trav_usar
    frente = e.cf_tipo == PosicaoContraforte.FRENTE
    rep_dim = e.emp_dim == TipoEmpuxo.REPOUSO
    phi, beta = math.radians(e.phi_at), math.radians(e.beta_t)
    cb, cphi, sphi = math.cos(beta), math.cos(phi), math.sin(phi)
    v: dict = {}

    def vrd(As, d, b=1.0):
        return c.vrd1(As, d, b) if e.v_mod == ModeloCortante.VRD1 else c.vrd_geo5(d, b)

    # ------------------------------------------------------------------ materiais
    K0 = (1 - sphi) * (1 + math.sin(beta))
    K0f = 1 - math.sin(math.radians(e.phi_f))
    dt = math.radians(e.delta_est)
    a_t = g.a_t
    num = max(0.0, math.sin(phi + dt) * math.sin(math.radians(e.phi_at - e.beta_t)))
    KaC = math.cos(phi - a_t) ** 2 / (math.cos(a_t) ** 2 * math.cos(a_t + dt) * (
        1 + math.sqrt(num / (math.cos(a_t + dt) * math.cos(a_t - beta)))) ** 2)
    KacC = cphi * cb * math.cos(a_t) ** 2 / (1 + math.sin(phi + dt - a_t - beta))
    dw = max(0.0, g.z_ter - e.hw_at) if e.hw_at > 0 else SEM_NA
    dy = g.h_cort / N_FATIAS
    v.update(dm_fcd=c.fcd, dm_fyd=c.fyd, dm_fctm=c.fctm, dm_fctd=c.fctd, dm_rmin=c.rho_min, dm_K0=K0,
             dm_K0f=K0f, dm_dt=dt, dm_KaC=KaC, dm_KacC=KacC, dm_dw=dw, dm_dy=dy)

    # --------------------------------------------------- pressões na cortina (100 fatias)
    i = np.arange(N_FATIAS)
    y = H - (i + 0.5) * dy
    D = g.z_ter - y
    sz0 = np.where(D <= 0, 0.0, e.gam_at * np.minimum(D, dw) + (e.gsat_at - e.gam_w) * np.maximum(0.0, D - dw))
    u = e.gam_w * np.maximum(0.0, min(e.hw_at, g.z_ter) - y) if e.hw_at > 0 else np.zeros_like(y)
    sz = np.where(D <= 0, 0.0, sz0 + e.q_sc)
    sh_rep = K0 * sz
    r = np.where(sz > 1e-6, e.c_at / np.where(sz > 1e-6, sz, 1.0), 1e6)
    Kp = k_mazindrani(r, cb, cphi, sphi)
    if e.metodo_emp == MetodoEmpuxo.RANKINE:
        sh_at = np.maximum(0.0, sz * Kp * cb) * cb
    else:
        sh_at = np.maximum(0.0, sz * KaC - 2 * e.c_at * KacC) * math.cos(a_t + dt)
    if e.ff_tipo == ResFrontal.REPOUSO:
        s_fr = np.where(y < e.D_frente, K0f * e.gam_f * (e.D_frente - y), 0.0)
    else:
        s_fr = np.zeros_like(y)
    # cargas em faixa, em linha e concentradas (Boussinesq): somam-se ao empuxo, ativo ou em repouso
    conc = f1.forcas.conc
    sh_bq = conc.na_cortina(e, g, y) if conc is not None else np.zeros_like(y)
    sh_rep, sh_at = sh_rep + sh_bq, sh_at + sh_bq
    sh_dim = sh_rep if rep_dim else sh_at
    dFA = (sh_dim + u - s_fr) * dy
    dFB = (sh_rep + u - s_fr) * dy
    dFs, dFw, dFf = sh_dim * dy, u * dy, s_fr * dy
    fatias = dict(y=y, prof=D, sz=sz, u=u, sh_repouso=sh_rep, sh_ativo=sh_at, s_frente=s_fr, dFA=dFA, dFB=dFB,
                  sh_concentradas=sh_bq)

    # ----------------------------------------------------------- 21 seções da cortina
    j = np.arange(N_SECOES + 1)
    ys = hs + j * g.h_cort / N_SECOES
    hsec = e.t_base + (e.t_topo - e.t_base) * (ys - hs) / g.h_cort
    acima = y[None, :] > ys[:, None]
    braco = y[None, :] - ys[:, None]
    MkA = (acima * dFA[None, :] * braco).sum(axis=1)
    VkA = (acima * dFA[None, :]).sum(axis=1)
    if trav:
        MkB = (acima * dFB[None, :] * braco).sum(axis=1) - e.trav_F * np.maximum(0.0, min(e.trav_z, H) - ys)
        VkB = (acima * dFB[None, :]).sum(axis=1) - np.where(e.trav_z > ys, e.trav_F, 0.0)
    else:
        MkB, VkB = np.zeros_like(ys), np.zeros_like(ys)
    Mkp = np.maximum(0.0, np.maximum(MkA, MkB if trav else 0.0))
    Mkn = np.maximum(0.0, np.maximum(-MkA, -MkB if trav else 0.0))
    Vk = np.maximum(np.abs(VkA), np.abs(VkB) if trav else 0.0)
    Ast = area_barras(e.ar_tz_phi, e.ar_tz_s)
    Asf = area_barras(e.ar_fr_phi, e.ar_fr_s)
    dp = hsec - e.cob_ct / 100 - e.ar_tz_phi / 2000
    dn = hsec - e.cob_ct / 100 - e.ar_fr_phi / 2000
    # Esforços de cálculo: γf só nas ações desfavoráveis (solo, sobrecarga, água). A resistência do
    # solo da frente é favorável e entra com 1,0 (NBR 8681) — a planilha a multiplica por γf.
    Mf = (acima * dFf[None, :] * braco).sum(axis=1)
    Vf = (acima * dFf[None, :]).sum(axis=1)
    MSdA, VSdA = gf * MkA + (gf - 1) * Mf, gf * VkA + (gf - 1) * Vf
    MSdB, VSdB = (gf * MkB + (gf - 1) * Mf, gf * VkB + (gf - 1) * Vf) if trav else (MSdA, VSdA)
    MSdp = np.maximum(0.0, np.maximum(MSdA, MSdB))
    MSdn = np.maximum(0.0, np.maximum(-MSdA, -MSdB))
    VSd = np.maximum(np.abs(VSdA), np.abs(VSdB))
    Asp = np.array([c.as_nec(m, d) for m, d in zip(MSdp, dp)])
    Asn = np.array([c.as_nec(m, d) for m, d in zip(MSdn, dn)])
    MRdp = np.array([c.mrd(Ast, d) for d in dp])
    MRdn = np.array([c.mrd(Asf, d) for d in dn])
    utp = np.where(MRdp > 0, MSdp / np.where(MRdp > 0, MRdp, 1.0), 0.0)
    utn = np.where(MRdn > 0, MSdn / np.where(MRdn > 0, MRdn, 1.0), 0.0)
    secoes = dict(y=ys, h=hsec, MkA=MkA, VkA=VkA, MkB=MkB, VkB=VkB, Mkp=Mkp, Mkn=Mkn, Vk=Vk, dp=dp, MSdp=MSdp,
                  Asp=Asp, MRdp=MRdp, utp=utp, dn=dn, MSdn=MSdn, Asn=Asn, MRdn=MRdn, utn=utn, VSd=VSd)
    Asmin = c.rho_min * 100 * e.t_base * 100
    v.update(dm_Ast=Ast, dm_Asf=Asf, dm_Mk0=MkA[0], dm_Vk0=VkA[0], dm_Mk0B=MkB[0], dm_Mkp=Mkp.max(),
             dm_Mkn=Mkn.max(), dm_Vk=Vk.max(), dm_MSdp=MSdp.max(),
             dm_Asnp=-1.0 if Asp.min() < 0 else Asp.max(), dm_Asmin=Asmin, dm_MRdp=MRdp[0], dm_utp=utp.max(),
             dm_xd=c.xd(Ast, dp[0]), dm_MSdn=MSdn.max(), dm_Asnn=-1.0 if Asn.min() < 0 else Asn.max(),
             dm_utn=utn.max(), dm_VSd=VSd.max(), dm_dct=dp[0], dm_VRd=vrd(Ast, dp[0]))

    # ------------------------------------------------------ base: 40 fatias ao longo de B
    k = np.arange(N_BASE)
    xb = (k + 0.5) * B / N_BASE
    ret = e.sig_dim == TensaoDim.RETANGULAR
    V1, V2 = f1.verif, f2.verif
    sig1 = _sigma_base(xb, f1.forcas.F_N, V1.R_e, V1.R_Bef, V1.R_sef, B, ret)
    sig2 = _sigma_base(xb, f2.forcas.F_N, V2.R_e, V2.R_Bef, V2.R_sef, B, ret)
    emp1, emp2 = f1.emp, f2.emp
    usub = emp1.p_u0 + (emp1.p_uB - emp1.p_u0) * xb / B if e.subp == Subpressao.LINEAR else np.zeros_like(xb)
    w_sap = e.gam_c * hs
    larg_q = max(0.0, B - g.x_bt if g.cv == 1 else g.x_P - g.x_bt)
    d_gam = (e.gsat_at - e.gam_w - e.gam_at) if e.peso_na == PesoNA.SUBMERSO else (e.gsat_at - e.gam_at)
    tem_talao, tem_ponta = e.b_talao > TOL, e.b_ponta > TOL
    W_conc = conc.W_talao if conc is not None else 0.0     # cargas em faixa/linha/ponto sobre o talão
    w_tal = (e.gam_at * g.solo.A + d_gam * g.solo_na.A + e.q_sc * larg_q + W_conc) / e.b_talao if tem_talao else 0.0
    eh_ponta, eh_talao = xb < g.x_fb, xb > g.x_tb
    carga_tal = np.where(eh_talao, w_tal, 0.0) if tem_talao else np.zeros_like(xb)
    q1 = sig1 + usub - w_sap - carga_tal
    q2 = sig2 + usub - w_sap - carga_tal
    base = dict(x=xb, sig1=sig1, sig2=sig2, u=usub, peso=np.full_like(xb, w_sap), carga_talao=carga_tal,
                zona=np.where(eh_ponta, "Ponta", np.where(eh_talao, "Talão", "Cortina")), q1=q1, q2=q2)
    dx = B / N_BASE
    a = f1.forcas.anc
    Fe_m = a.anc_Fe / e.anc_esp if e.anc_usar else 0.0
    n1, n2, xe, x2 = e.anc_n1, e.anc_n2, a.anc_xe, e.anc_x2
    # Ancoragem sob a ponta: é resistência passiva, que só se mobiliza por inteiro na ruptura. Descontá-la
    # aliviaria o momento e o cortante da ponta; por isso não é descontada (a planilha desconta).
    anc_M_tl = (n1 * max(0.0, xe - g.x_tb) + n2 * max(0.0, x2 - g.x_tb)) * Fe_m
    anc_V_tl = (n1 * (xe > g.x_tb) + n2 * (x2 > g.x_tb)) * Fe_m

    def ponta(q):
        return (float((eh_ponta * q * (g.x_fb - xb)).sum()) * dx,
                float((eh_ponta * q).sum()) * dx)

    def talao(q, emp, kpav=1.0):
        pav_on = tem_talao and emp.p_xPav > g.x_tb
        M = -float((eh_talao * q * (xb - g.x_tb)).sum()) * dx + anc_M_tl + (
            kpav * emp.p_Pav * (emp.p_xPav - g.x_tb) if pav_on else 0.0)
        V = -float((eh_talao * q).sum()) * dx + anc_V_tl + (kpav * emp.p_Pav if pav_on else 0.0)
        return M, V

    # ------------------------------------------------ combinações de ações para dimensionar a base
    # Cada grupo de ações (empuxo; pesos, ancoragem e resistências; água) entra com 1,0 ou com γf, em todas
    # as combinações possíveis (NBR 8681: favorável 1,0, desfavorável γf). A reação do solo sai do equilíbrio
    # de cada combinação. Além disso, combinações locais com a reação de serviço × 1,0 ou γf contra os pesos
    # e o empuxo vertical × 1,0 ou γf. O dimensionamento usa o pior caso; "γf × serviço" (planilha) é uma delas.
    fases_dim = (f1, f2) if trav else (f1,)
    tem_agua = any(ln.grupo == "agua" and (ln.Fx or ln.Fz) for f in fases_dim for ln in f.forcas.linhas)
    COMBOS = [(kE, kP, kA) for kE in (1.0, gf) for kP in (1.0, gf) for kA in ((1.0, gw) if tem_agua else (1.0,))]
    K_FAV = (gf, 1.0, gw if tem_agua else 1.0)        # só empuxo e água majorados (critério do GEO5)

    def comb(f, k):
        kE, kP, kA = k
        N = M = 0.0
        for ln in f.forcas.linhas:
            if ln.nome.startswith(PREFIXOS_EMPUXO):
                kk = kE
            elif ln.grupo == "agua":
                kk = kA
            elif ln.grupo == "solo_ponta":
                kk = e.gf_sp if kP > 1.0 else min(e.gf_sp, 1.0)
            else:
                kk = kP
            N += kk * ln.Fz
            M += kk * (ln.Mres - ln.Movr)
        return N, (B / 2 - M / N if N > 0 else 0.0)

    def q_comb(f, k, linear=False):
        """Carga líquida de cálculo na base (kPa) numa combinação; None se a resultante sai da base."""
        N, ex = comb(f, k)
        if N <= 0 or abs(ex) >= B / 2:
            return None
        Bef = B - 2 * abs(ex)
        emp = f.emp
        us = k[2] * (emp.p_u0 + (emp.p_uB - emp.p_u0) * xb / B) if e.subp == Subpressao.LINEAR else 0.0
        return _sigma_base(xb, N, ex, Bef, N / Bef, B, ret and not linear) + us - k[1] * (w_sap + carga_tal)

    fav_fora = False
    _zero = lambda: dict(M_pt=0.0, V_pt=0.0, M_tl=0.0, V_tl=0.0, N_pt=0.0, N_tl=0.0)   # noqa: E731
    # M_* = sentido usual (ponta tracionada embaixo, talão em cima); N_* = sentido contrário
    E_eq, E_geo, E_loc, fav = _zero(), _zero(), _zero(), _zero()

    def _acumula(env, q, emp, kpav):
        if tem_ponta:
            m, s = ponta(q)
            env.update(M_pt=max(env["M_pt"], m), V_pt=max(env["V_pt"], abs(s)), N_pt=max(env["N_pt"], -m))
        if tem_talao:
            m, s = talao(q, emp, kpav)
            env.update(M_tl=max(env["M_tl"], m), V_tl=max(env["V_tl"], abs(s)), N_tl=max(env["N_tl"], -m))

    for f, sig_s in zip(fases_dim, (sig1, sig2)):
        for k in COMBOS:                                     # combinações em equilíbrio
            qk = q_comb(f, k)
            if qk is None:
                fav_fora = fav_fora or f.forcas.F_N > 0
                continue
            _acumula(E_eq, qk, f.emp, k[0])
            if k == K_FAV:
                _acumula(fav, qk, f.emp, k[0])
        if f.forcas.F_N > 0 and abs(f.verif.R_e) < B / 2:    # combinações locais: reação de serviço
            # critério do GEO5: empuxo vertical × γf, pesos × 1,0, reação do solo de serviço × 1,0
            _acumula(E_geo, (sig_s + usub) - (w_sap + carga_tal), f.emp, gf)
            for kR in (1.0, gf):                             # todas: reação × pesos × empuxo vertical
                for kW in (1.0, gf):
                    for kV in (1.0, gf):
                        _acumula(E_loc, kR * (sig_s + usub) - kW * (w_sap + carga_tal), f.emp, kV)
    todas_locais = e.comb_base == CombinacoesBase.TODAS
    E_ad = E_loc if todas_locais else E_geo
    MB_pt, VB_pt = max(E_eq["M_pt"], E_ad["M_pt"]), max(E_eq["V_pt"], E_ad["V_pt"])
    MB_tl, VB_tl = max(E_eq["M_tl"], E_ad["M_tl"]), max(E_eq["V_tl"], E_ad["V_tl"])
    MN_pt, MN_tl = max(E_eq["N_pt"], E_ad["N_pt"]), max(E_eq["N_tl"], E_ad["N_tl"])
    Nf1, ef1 = comb(f1, K_FAV)
    v.update(dm_N_fav=Nf1, dm_e_fav=ef1, dm_MSd_pt_fav=fav["M_pt"], dm_VSd_pt_fav=fav["V_pt"],
             dm_MSd_tl_fav=fav["M_tl"], dm_VSd_tl_fav=fav["V_tl"], dm_MSd_pt_comb=MB_pt, dm_VSd_pt_comb=VB_pt,
             dm_MSd_tl_comb=MB_tl, dm_VSd_tl_comb=VB_tl, dm_MSd_pt_sup=MN_pt, dm_MSd_tl_inf=MN_tl,
             dm_n_comb=len(COMBOS) + (8 if todas_locais else 1))
    for suf, env in (("eq", E_eq), ("geo", E_geo), ("loc", E_loc)):
        v.update({f"dm_MSd_pt_{suf}": env["M_pt"], f"dm_VSd_pt_{suf}": env["V_pt"],
                  f"dm_MSd_tl_{suf}": env["M_tl"], f"dm_VSd_tl_{suf}": env["V_tl"]})

    MtP1, VtP1 = ponta(q1)
    MtP2, VtP2 = ponta(q2) if trav else (0.0, 0.0)
    VtP = max(abs(VtP1), abs(VtP2) if trav else 0.0)
    MtT1, VtT1 = talao(q1, emp1) if tem_talao else (0.0, 0.0)
    MtT2, VtT2 = talao(q2, emp2) if (tem_talao and trav) else (0.0, 0.0)
    Mtt = max(0.0, MtT1, MtT2)
    VtT = max(abs(VtT1), abs(VtT2))
    MSd_tl = max(gf * Mtt, MB_tl)
    # Equilíbrio do nó cortina-sapata: o momento de cálculo da base da cortina tem de ser absorvido pela
    # ponta e pelo talão. A ponta recebe o que o talão (com o momento para o qual é armado) não absorve.
    # Sem talão, a ponta recebe o momento inteiro da cortina (regra da planilha).
    M_no = max(0.0, float(MSdA[0]) - MSd_tl) if (not tem_talao or not e.cf_usar) else 0.0
    no_gov = False
    if not tem_ponta:
        Mtp = MSd_pt = 0.0
    elif e.ponta_mod == MomentoPonta.GEO5:
        Mtp, MSd_pt = MkA[0], float(MSdA[0])
    elif e.ponta_mod == MomentoPonta.PRESSOES:
        Mtp = max(MtP1, MtP2)
        MSd_pt = max(gf * Mtp, MB_pt)
    else:
        Mtp = max(MtP1, MtP2, MkA[0] if not tem_talao else 0.0)
        MSd_pt = max(gf * MtP1, gf * MtP2, MB_pt, M_no)
        no_gov = tem_talao and M_no > max(gf * MtP1, gf * MtP2, MB_pt) + 1e-9
    v.update(dm_M_no=M_no, dm_no_gov=no_gov)
    gov_bal = (MB_pt > gf * max(MtP1, MtP2) + 1e-9 or VB_pt > gf * VtP + 1e-9 or MB_tl > gf * Mtt + 1e-9
               or VB_tl > gf * VtT + 1e-9 or no_gov)
    Abi = area_barras(e.ar_bi_phi, e.ar_bi_s)
    Abs_ = area_barras(e.ar_bs_phi, e.ar_bs_s)
    db_i = hs - e.cob_bs / 100 - e.ar_bi_phi / 2000
    db_s = hs - e.cob_bs / 100 - e.ar_bs_phi / 2000
    Asminb = c.rho_min * 100 * hs * 100
    v.update(dm_Abi=Abi, dm_Abs=Abs_, dm_MtP1=MtP1, dm_MtP2=MtP2, dm_VtP=VtP, dm_Mtp=Mtp, dm_MtT1=MtT1,
             dm_MtT2=MtT2, dm_Mtt=Mtt, dm_db_i=db_i, dm_db_s=db_s, dm_MSd_pt=MSd_pt,
             dm_As_pt=c.as_nec(MSd_pt, db_i), dm_MRd_pt=c.mrd(Abi, db_i), dm_MSd_tl=MSd_tl,
             dm_As_tl=c.as_nec(MSd_tl, db_s), dm_MRd_tl=c.mrd(Abs_, db_s), dm_Asminb=Asminb,
             dm_VSd_pt=max(gf * VtP, VB_pt), dm_VRd_pt=vrd(Abi, db_i))

    # ------------------------------------------- cortina como laje entre contrafortes
    l = max(0.01, e.cf_esp - e.cf_t)
    H1 = max(0.0, g.z_ter - hs)
    Dp = g.z_ter if e.laje_pres == PressaoLaje.FUNDO else max(0.001, g.z_ter - hs)
    Kh = K0 if (rep_dim or trav) else KaC * math.cos(a_t + dt)
    seco, sub = min(Dp, dw), max(0.0, Dp - dw)
    solo_D = e.gam_at * seco + (e.gsat_at - e.gam_w) * sub
    agua_D = e.gam_w * sub
    int_solo = e.gam_at * seco**2 / 2 + e.gam_at * seco * sub + (e.gsat_at - e.gam_w) * sub**2 / 2
    int_agua = e.gam_w * sub**2 / 2
    sH = e.gf_cs * Kh * (solo_D + e.q_sc) + gw * agua_D
    sP = (e.gf_cs * Kh * (int_solo + e.q_sc * Dp) + gw * int_agua) / Dp
    Mvt = 0.03 * sH * H1 * l
    Mvf, Mht, Mhf, Vcs = Mvt / 4, sP * l**2 / 12, sP * l**2 / 20, sP * l / 2
    dvt = e.t_base - e.cob_ct / 100 - e.ar_tz_phi / 2000
    dvf = e.t_base - e.cob_ct / 100 - e.ar_fr_phi / 2000
    tm = (e.t_topo + e.t_base) / 2
    dht = tm - e.cob_ct / 100 - e.ar_hz_tz_phi / 2000
    dhf = tm - e.cob_ct / 100 - e.ar_hz_fr_phi / 2000
    Ahzt = area_barras(e.ar_hz_tz_phi, e.ar_hz_tz_s)
    Ahzf = area_barras(e.ar_hz_fr_phi, e.ar_hz_fr_s)
    v.update(cs_l=l, cs_H1=H1, cs_D=Dp, cs_Kh=Kh, cs_sHk=Kh * (solo_D + e.q_sc) + agua_D,
             cs_sPk=(Kh * (int_solo + e.q_sc * Dp) + int_agua) / Dp, cs_sH=sH, cs_sP=sP, cs_Mvt=Mvt, cs_Mvf=Mvf,
             cs_Mht=Mht, cs_Mhf=Mhf, cs_V=Vcs, cs_dvt=dvt, cs_dvf=dvf, cs_tm=tm, cs_dht=dht, cs_dhf=dhf,
             cs_Ahzt=Ahzt, cs_Ahzf=Ahzf, cs_Asvt=c.as_nec(Mvt, dvt), cs_Asvf=c.as_nec(Mvf, dvf),
             cs_Asht=c.as_nec(Mht, dht), cs_Ashf=c.as_nec(Mhf, dhf), cs_MRvt=c.mrd(Ast, dvt),
             cs_MRht=c.mrd(Ahzt, dht), cs_MRhf=c.mrd(Ahzf, dhf), cs_VR=vrd(Ast, dvt),
             cs_xd=max(c.xd(Ast, dvt), c.xd(Ahzt, dht), c.xd(Ahzf, dhf)), cs_Asmh=c.rho_min * 100 * tm * 100)

    # --------------------------------------------- base como laje entre contrafortes
    fat = {"peso": gf, "solo_ponta": e.gf_sp, "agua": gw}
    lin = f1.forcas.linhas
    bd_N = sum(f.Fz * fat[f.grupo] for f in lin)
    bd_M = sum(f.Mres * fat[f.grupo] for f in lin) - sum(f.Movr * fat[f.grupo] for f in lin)
    bd_e = B / 2 - bd_M / bd_N if bd_N > 0 else 0.0
    bd_s = tensoes_lineares(bd_N, bd_e, B)[0]
    # envoltória com a combinação de ações favoráveis em 1,0
    bd_s_fav = max((tensoes_lineares(*comb(f, K_FAV), B)[0] for f in fases_dim), default=0.0)
    bd_s_comb = max((t for t in (tensoes_lineares(*comb(f, k), B)[0] for f in fases_dim for k in COMBOS)
                     if math.isfinite(t)), default=0.0)
    v.update(bd_s_fav=bd_s_fav, bd_s_comb=bd_s_comb, bd_s_plan=bd_s)
    bd_s = max(bd_s, bd_s_comb)
    bd_qh = gf * ((e.gam_at * g.solo.A + e.q_sc * larg_q) / e.b_talao + e.gam_c * hs) if tem_talao else 0.0
    bd_w = bd_s if frente else bd_qh
    M12, M20, bd_V = bd_w * l**2 / 12, bd_w * l**2 / 20, bd_w * l / 2
    bd_Ai = area_barras(e.ar_bl_i_phi, e.ar_bl_i_s)
    bd_As = area_barras(e.ar_bl_s_phi, e.ar_bl_s_s)
    bd_di = hs - e.cob_bs / 100 - e.ar_bl_i_phi / 2000
    bd_ds = hs - e.cob_bs / 100 - e.ar_bl_s_phi / 2000
    bd_Mi, bd_Ms = (M12, M20) if frente else (M20, M12)
    v.update(bd_N=bd_N, bd_M=bd_M, bd_e=bd_e, bd_s=bd_s, bd_qh=bd_qh, bd_w=bd_w, bd_M12=M12, bd_M20=M20,
             bd_V=bd_V, bd_Ai=bd_Ai, bd_As=bd_As, bd_di=bd_di, bd_ds=bd_ds, bd_Mi=bd_Mi, bd_Ms=bd_Ms,
             bd_Asi=c.as_nec(bd_Mi, bd_di), bd_Ass=c.as_nec(bd_Ms, bd_ds), bd_MRi=c.mrd(bd_Ai, bd_di),
             bd_MRs=c.mrd(bd_As, bd_ds), bd_VR=vrd(bd_Ai, bd_di),
             bd_xd=max(c.xd(bd_Ai, bd_di), c.xd(bd_As, bd_ds)))

    # ------------------------------------------------- contraforte como viga em balanço
    bz = y - hs
    cf_Ms, cf_Mw, cf_Mf = float((dFs * bz).sum()), float((dFw * bz).sum()), float((dFf * bz).sum())
    cf_Vs, cf_Vw, cf_Vf = float(dFs.sum()), float(dFw.sum()), float(dFf.sum())
    cf_MSd = (gf * cf_Ms + gw * cf_Mw - cf_Mf) * e.cf_esp
    cf_VSd = (gf * cf_Vs + gw * cf_Vw - cf_Vf) * e.cf_esp
    bw = e.cf_t
    h2 = (min(e.cf_Lb, e.b_ponta) if frente else min(e.cf_Lb, e.b_talao)) + e.t_base
    cf_d = h2 - e.cob_ct / 100 - e.cf_phi / 2000
    cf_As = e.cf_n * math.pi * (e.cf_phi / 10) ** 2 / 4
    v.update(cf_Ms=cf_Ms, cf_Mw=cf_Mw, cf_Mf=cf_Mf, cf_Vs=cf_Vs, cf_Vw=cf_Vw, cf_Vf=cf_Vf, cf_MSd=cf_MSd,
             cf_VSd=cf_VSd, cf_bw=bw, cf_h2=h2, cf_d=cf_d, cf_As=cf_As, cf_Asn=c.as_nec(cf_MSd, cf_d, bw),
             cf_Asm=c.rho_min * bw * h2 * 10000, cf_MRd=c.mrd(cf_As, cf_d, bw), cf_xd=c.xd(cf_As, cf_d, bw),
             cf_VRd=vrd(cf_As, cf_d, bw))

    # ------------------- muro com contrafortes: painéis como laje com uma borda livre
    cf = e.cf_usar
    placa_on = cf and e.laje_cf == ModeloLajeCF.PLACA
    placas: dict = {}
    pc = pb = None
    if placa_on:
        p_d = e.gf_cs * (sh_rep if (rep_dim or trav) else sh_at) + gw * u - s_fr
        pc = _painel_cortina(e, g, c, l, y, p_d, vrd)
        placas["cortina"] = pc
        v.update({"pl_" + k: val for k, val in pc.items() if isinstance(val, float)})
        b_cf = e.b_ponta if frente else e.b_talao
        if b_cf > TOL and math.isfinite(bd_w) and bd_w > 0:
            pb = _painel_base(e, c, l, b_cf, bd_w, frente, vrd)
            placas["base"] = pb
            v.update({"pl_bd_" + k: val for k, val in pb.items() if isinstance(val, float)})

    # ------------------------------------------------------------- 26 verificações
    xd_lim = 0.259 if e.xd_lim == LimiteXd.GEO5 else c.xd_lim_nbr
    so_cf = lambda st: st if cf else NA                     # noqa: E731
    pt_on = not (cf and frente)
    tl_on = not (cf and not frente)
    so_pt = lambda st: st if pt_on else NA                  # noqa: E731
    so_tl = lambda st: st if tl_on else NA                  # noqa: E731
    C, Bs, L, K = "Cortina", "Base", "Lajes entre contrafortes", "Contraforte"
    as_vt = v["cs_Asvt"] if cf else v["dm_Asnp"]
    ut_t = Mvt / v["cs_MRvt"] if cf else v["dm_utp"]
    xd_c = v["cs_xd"] if cf else v["dm_xd"]
    as_vf = v["cs_Asvf"] if cf else v["dm_Asnn"]
    Vc, VRc = (Vcs, v["cs_VR"]) if cf else (v["dm_VSd"], v["dm_VRd"])
    as_ht, as_hf = v["cs_Asht"], v["cs_Ashf"]
    bdAsi, bdAss, bdxd, bdV, bdVR = v["bd_Asi"], v["bd_Ass"], v["bd_xd"], bd_V, v["bd_VR"]
    if pc is not None:
        as_vt, ut_t, xd_c, as_vf = pc["Asvt"], pc["ut_vt"], pc["xd"], pc["Asvf"]
        Vc, VRc = pc["V"], pc["VR"]
        as_ht, as_hf = pc["Asht"], pc["Ashf"]
    if pb is not None:
        bdAsi, bdAss, bdxd, bdV, bdVR = pb["Asi"], pb["Ass"], pb["xd"], pb["V_cf"], pb["VR_cf"]
    checks = (
        Check("Cortina vertical tardoz: As ef ≥ As nec", as_vt, Ast, _st_as(as_vt, Ast), C, unidade="cm²/m"),
        Check("Cortina vertical tardoz: As ef ≥ As mín", Asmin, Ast, _st_max(Asmin, Ast), C, unidade="cm²/m"),
        Check("Cortina vertical tardoz: MSd ≤ MRd", ut_t, 1.0, _st_max(ut_t, 1.0), C, unidade="-"),
        Check("Cortina: x/d ≤ limite", xd_c, xd_lim, _st_max(xd_c, xd_lim), C, unidade="-"),
        Check("Cortina vertical frontal: As ef ≥ As nec", as_vf, Asf, _st_as(as_vf, Asf), C, unidade="cm²/m"),
        Check("Cortina vertical frontal: As ef ≥ As mín", Asmin, Asf, _st_max(Asmin, Asf), C, unidade="cm²/m"),
        Check("Cortina: VSd ≤ VRd", Vc, VRc, _st_max(Vc, VRc), C, unidade="kN/m"),
        Check("Cortina horizontal tardoz (apoios): As ef ≥ As nec", as_ht, Ahzt,
              so_cf(_st_as(as_ht, Ahzt)), L, unidade="cm²/m"),
        Check("Cortina horizontal frontal (vão): As ef ≥ As nec", as_hf, Ahzf,
              so_cf(_st_as(as_hf, Ahzf)), L, unidade="cm²/m"),
        Check("Cortina horizontal: As ef ≥ As mín (cada face)", v["cs_Asmh"], min(Ahzt, Ahzf),
              so_cf(_st_max(v["cs_Asmh"], min(Ahzt, Ahzf))), L, unidade="cm²/m"),
        Check("Ponta em balanço: As ef ≥ As nec", v["dm_As_pt"], Abi, so_pt(_st_as(v["dm_As_pt"], Abi)), Bs,
              unidade="cm²/m"),
        Check("Ponta em balanço: MSd ≤ MRd", v["dm_MSd_pt"], v["dm_MRd_pt"],
              so_pt(_st_max(v["dm_MSd_pt"], v["dm_MRd_pt"])), Bs, unidade="kN·m/m"),
        Check("Base: As inferior ≥ As mín", Asminb, Abi, _st_max(Asminb, Abi), Bs, unidade="cm²/m"),
        Check("Ponta em balanço: VSd ≤ VRd", v["dm_VSd_pt"], v["dm_VRd_pt"],
              so_pt(_st_max(v["dm_VSd_pt"], v["dm_VRd_pt"])), Bs, unidade="kN/m"),
        Check("Talão em balanço: As ef ≥ As nec", v["dm_As_tl"], Abs_, so_tl(_st_as(v["dm_As_tl"], Abs_)), Bs,
              unidade="cm²/m"),
        Check("Talão em balanço: MSd ≤ MRd", v["dm_MSd_tl"], v["dm_MRd_tl"],
              so_tl(_st_max(v["dm_MSd_tl"], v["dm_MRd_tl"])), Bs, unidade="kN·m/m"),
        Check("Base: As superior ≥ As mín", Asminb, Abs_, _st_max(Asminb, Abs_), Bs, unidade="cm²/m"),
        Check("Base entre contrafortes: As inferior ≥ As nec", bdAsi, bd_Ai,
              so_cf(_st_as(bdAsi, bd_Ai)), L, unidade="cm²/m"),
        Check("Base entre contrafortes: As superior ≥ As nec", bdAss, bd_As,
              so_cf(_st_as(bdAss, bd_As)), L, unidade="cm²/m"),
        Check("Base entre contrafortes: x/d ≤ limite", bdxd, xd_lim, so_cf(_st_max(bdxd, xd_lim)), L,
              unidade="-"),
        Check("Base entre contrafortes: VSd ≤ VRd (senão, estribos)", bdV, bdVR,
              so_cf(_st_max(bdV, bdVR)), L, unidade="kN/m"),
        Check("Contraforte: As ef ≥ As nec", v["cf_Asn"], cf_As, so_cf(_st_as(v["cf_Asn"], cf_As)), K,
              unidade="cm²"),
        Check("Contraforte: As ef ≥ As mín", v["cf_Asm"], cf_As, so_cf(_st_max(v["cf_Asm"], cf_As)), K,
              unidade="cm²"),
        Check("Contraforte: MSd ≤ MRd", cf_MSd, v["cf_MRd"], so_cf(_st_max(cf_MSd, v["cf_MRd"])), K,
              unidade="kN·m"),
        Check("Contraforte: x/d ≤ limite", v["cf_xd"], xd_lim, so_cf(_st_max(v["cf_xd"], xd_lim)), K, unidade="-"),
        Check("Contraforte: VSd ≤ VRd (senão, estribos)", cf_VSd, v["cf_VRd"],
              so_cf(_st_max(cf_VSd, v["cf_VRd"])), K, unidade="kN"),
    )

    # ---------------------------- verificações adicionais do aplicativo (NBR 6118)
    VSd_tl, VRd_tl = max(gf * VtT, VB_tl), vrd(Abs_, db_s)
    fav_gov = gov_bal or (frente and cf and bd_s > v["bd_s_plan"] + 1e-9)
    v["dm_fav_gov"] = bool(fav_gov)
    v.update(dm_VtT=VtT, dm_VSd_tl=VSd_tl, dm_VRd_tl=VRd_tl, dm_xd_lim=xd_lim)
    extras = [
        Check("Talão em balanço: VSd ≤ VRd (NBR 6118 19.4.1)", VSd_tl, VRd_tl,
              (_st_max(VSd_tl, VRd_tl) if (tl_on and tem_talao) else NA), Bs, True, "kN/m"),
    ]
    if MN_tl > 1e-6 and tem_talao and tl_on:
        as_n = c.as_nec(MN_tl, db_i)
        extras.append(Check("Talão em balanço — face inferior (peso com 1,0 e reação do solo majorada): "
                            "As ef ≥ As nec", as_n, Abi, _st_as(as_n, Abi), Bs, True, "cm²/m"))
    if MN_pt > 1e-6 and tem_ponta and pt_on:
        as_n = c.as_nec(MN_pt, db_s)
        extras.append(Check("Ponta em balanço — face superior (peso majorado e reação do solo com 1,0): "
                            "As ef ≥ As nec", as_n, Abs_, _st_as(as_n, Abs_), Bs, True, "cm²/m"))
    for rot, s_cm, h_m, on in (
        ("Cortina — face do tardoz", e.ar_tz_s, e.t_base, True),
        ("Cortina — face frontal", e.ar_fr_s, e.t_base, True),
        ("Base — face inferior", e.ar_bi_s, hs, True),
        ("Base — face superior", e.ar_bs_s, hs, True),
    ):
        s_max = min(20.0, 2 * h_m * 100)
        extras.append(Check(f"{rot}: espaçamento ≤ mín(20 cm; 2h) (NBR 6118 20.1)", s_cm, s_max,
                            _st_max(s_cm, s_max), C if "Cortina" in rot else Bs, True, "cm"))
    if pb is not None:
        Ac, dc_, Ao, do_ = (Abi, db_i, Abs_, db_s) if frente else (Abs_, db_s, Abi, db_i)
        face_c, face_o = ("inferior", "superior") if frente else ("superior", "inferior")
        as_j, as_o = c.as_nec(pb["M_tr_j"], dc_), c.as_nec(pb["M_tr_pos"], do_)
        extras += [
            Check(f"Base entre contrafortes — transversal na junção com a cortina (face {face_c}): "
                  "As ef ≥ As nec", as_j, Ac, _st_as(as_j, Ac), L, True, "cm²/m"),
            Check(f"Base entre contrafortes — transversal no campo (face {face_o}): As ef ≥ As nec", as_o, Ao,
                  _st_as(as_o, Ao), L, True, "cm²/m"),
            Check("Base entre contrafortes — cortante na junção com a cortina: VSd ≤ VRd", pb["V_j"],
                  vrd(Ac, dc_), _st_max(pb["V_j"], vrd(Ac, dc_)), L, True, "kN/m"),
        ]
    notas = []
    if pc is not None:
        notas.append(f"Cortina entre contrafortes: vão livre {l:.2f} m × altura {g.h_cort:.2f} m "
                     f"(altura/vão = {pc['razao']:.2f}) — {pc['tipo']}. Momentos de cálculo da placa: "
                     f"horizontal {pc['Mht']:.1f} (apoios) e {pc['Mhf']:.1f} (vão); vertical {pc['Mvt']:.1f} "
                     f"(base) e {pc['Mvf']:.1f} (campo) kN·m/m. Pelos coeficientes do GEO5: {Mht:.1f}, {Mhf:.1f}, "
                     f"{Mvt:.1f} e {Mvf:.1f}.")
        notas.append("Placa de espessura constante (a variação de espessura da cortina entra só na altura útil "
                     "de cada faixa); armadura horizontal considerada por dentro da vertical.")
        if trav:
            notas.append("Com travamento, a borda superior deixa de ser livre: a placa com borda livre é "
                         "conservadora para os momentos horizontais junto ao topo.")
        b_cf = e.b_ponta if frente else e.b_talao
        if e.cf_Lb < b_cf - 0.05:
            notas.append("O contraforte não cobre toda a largura da base desse lado: a laje da base foi "
                         "calculada como se cobrisse; a faixa além do contraforte trabalha em balanço.")
    # ---- excentricidade entre o limite e B/4: base com descolamento parcial (distribuição triangular)
    fases_faixa = [f for f in ((f1, f2) if trav else (f1,)) if f.verif.exc_faixa]
    v["ex_faixa"] = bool(fases_faixa)
    if fases_faixa:
        # esforços com a distribuição linear sem tração, qualquer que seja a opção de tensão para dimensionar
        Mp = Vp = Mt = Vt = 0.0          # envoltória; M com sinal do maior módulo
        for f in fases_faixa:
            V_ = f.verif
            q_ = _sigma_base(xb, f.forcas.F_N, V_.R_e, V_.R_Bef, V_.R_sef, B, False) + usub - w_sap - carga_tal
            casos = [(q_, 1.0, gf)]                      # serviço × γf
            for k in COMBOS:                             # combinações 1,0 / γf (já de cálculo)
                qB = q_comb(f, k, linear=True)
                if qB is not None:
                    casos.append((qB, k[0], 1.0))
            for qq, kpav, mult in casos:
                m, s = ponta(qq) if tem_ponta else (0.0, 0.0)
                Mp, Vp = (mult * m if abs(mult * m) > abs(Mp) else Mp), max(Vp, abs(mult * s))
                m, s = talao(qq, f.emp, kpav) if tem_talao else (0.0, 0.0)
                Mt, Vt = (mult * m if abs(mult * m) > abs(Mt) else Mt), max(Vt, abs(mult * s))
        pior = max(fases_faixa, key=lambda f: f.verif.R_eB).verif
        L_comp = pior.frac_comp * B
        # ponta: M > 0 traciona a face inferior; talão: M > 0 traciona a face superior
        inf_, sup_ = ("inferior", Abi, db_i), ("superior", Abs_, db_s)
        fp, Ap, dp_ = inf_ if Mp >= 0 else sup_
        ft, At, dt_ = sup_ if Mt >= 0 else inf_
        As_p, As_t = c.as_nec(abs(Mp), dp_), c.as_nec(abs(Mt), dt_)
        falta = lambda nec, ef: 0.0 if 0 <= nec <= ef else (nec - ef if nec > 0 else math.nan)  # noqa: E731
        v.update(ex_eB=pior.R_eB, ex_frac=pior.frac_comp, ex_Lcomp=L_comp, ex_Ldesc=B - L_comp,
                 ex_sig_max=pior.sig_max, ex_M_pt=Mp, ex_M_tl=Mt, ex_MSd_pt=abs(Mp), ex_MSd_tl=abs(Mt),
                 ex_As_pt=As_p, ex_As_tl=As_t, ex_dAs_pt=falta(As_p, Ap), ex_dAs_tl=falta(As_t, At),
                 ex_face_pt=fp, ex_face_tl=ft, ex_VSd_pt=Vp, ex_VSd_tl=Vt)
        rot = "Base com descolamento (e entre o limite e B/4)"
        extras += [
            Check(f"{rot}: área comprimida ≥ 2/3 da base (NBR 6122 7.6.2)", 2 / 3, pior.frac_comp,
                  _st_max(2 / 3, pior.frac_comp), Bs, True, "-"),
            Check(f"{rot} — ponta, face {fp}: As ef ≥ As nec", As_p, Ap,
                  _st_as(As_p, Ap) if (tem_ponta and pt_on) else NA, Bs, True, "cm²/m"),
            Check(f"{rot} — ponta: VSd ≤ VRd", Vp, vrd(Ap, dp_),
                  _st_max(Vp, vrd(Ap, dp_)) if (tem_ponta and pt_on) else NA, Bs, True, "kN/m"),
            Check(f"{rot} — talão, face {ft}: As ef ≥ As nec", As_t, At,
                  _st_as(As_t, At) if (tem_talao and tl_on) else NA, Bs, True, "cm²/m"),
            Check(f"{rot} — talão: VSd ≤ VRd", Vt, vrd(At, dt_),
                  _st_max(Vt, vrd(At, dt_)) if (tem_talao and tl_on) else NA, Bs, True, "kN/m"),
        ]
        fm = lambda x, n=2: f"{x:.{n}f}".replace(".", ",")  # noqa: E731
        def txt_falta(d_, face):
            if d_ != d_:
                return f"a seção não resiste (aumente a espessura da sapata) na face {face}"
            return (f"faltam {fm(d_)} cm²/m na face {face}" if d_ > 0
                    else f"a armadura adotada na face {face} é suficiente")
        notas.append(
            f"Excentricidade e/B = {fm(pior.R_eB, 3)}, entre o limite ({fm(e.eB_lim, 3)}) e B/4: a resultante sai do "
            f"núcleo central e a base descola em {fm(B - L_comp)} m do lado oposto à tensão máxima (comprimidos "
            f"{fm(L_comp)} m = {fm(100 * pior.frac_comp, 0)} % de B; σmáx = {fm(pior.sig_max, 1)} kPa). O solo não "
            "resiste à tração (NBR 6122 7.6.2), então a base foi verificada com a distribuição triangular: "
            f"ponta, MSd = {fm(abs(Mp), 1)} kN·m/m, As nec = {fm(max(As_p, 0))} cm²/m — "
            f"{txt_falta(v['ex_dAs_pt'], fp)}; talão, MSd = {fm(abs(Mt), 1)} kN·m/m, As nec = "
            f"{fm(max(As_t, 0))} cm²/m — {txt_falta(v['ex_dAs_tl'], ft)}. O trecho descolado do talão trabalha "
            "sem reação do solo, carregado pelo peso do aterro e pelo peso próprio. Acima de B/4 o muro é "
            "reprovado; prefira aumentar a base quando o descolamento ocorrer sob cargas permanentes.")
    if (tem_ponta and pt_on) or (tem_talao and tl_on):
        fm1 = lambda x: f"{x:.1f}".replace(".", ",")   # noqa: E731
        def _linha(rot, env):
            partes = []
            if tem_ponta and pt_on:
                partes.append(f"ponta M = {fm1(env['M_pt'])} kN·m/m e V = {fm1(env['V_pt'])} kN/m")
            if tem_talao and tl_on:
                partes.append(f"talão M = {fm1(env['M_tl'])} kN·m/m e V = {fm1(env['V_tl'])} kN/m")
            return f"{rot}: " + "; ".join(partes)
        notas.append(
            "Combinações de ações na base (esforços de cálculo). "
            + _linha(f"(a) em equilíbrio — {len(COMBOS)} combinações com cada grupo (empuxo; pesos, ancoragem e "
                     "resistências; água) em 1,0 ou γf e a reação do solo do equilíbrio de cada uma", E_eq) + ". "
            + _linha("(b) local, critério do GEO5 — empuxo vertical × γf, pesos × 1,0 e reação do solo de "
                     "serviço × 1,0", E_geo) + ". "
            + _linha("(c) locais, todas — reação de serviço, pesos e empuxo vertical em 1,0 ou γf (8 combinações, "
                     "não equilibradas)", E_loc) + ". "
            + ("Adotado: pior caso entre (a) e (c)." if todas_locais else
               "Adotado: pior caso entre (a) e (b), que é o padrão; (c) é só informativo e pode ser adotado na "
               "opção 'Combinações de ações na base'."))
    if fav_gov:
        notas.append("Base dimensionada por uma combinação de ações mais desfavorável que γf × esforços de serviço "
                     "(critério da planilha) — ver a nota das combinações.")
    if no_gov:
        notas.append("Momento da ponta definido pelo equilíbrio do nó cortina-sapata: momento de cálculo da base da "
                     "cortina menos o momento para o qual o talão é armado ("
                     + f"{float(MSdA[0]):.1f} − {MSd_tl:.1f} = {M_no:.1f}".replace(".", ",") + " kN·m/m).")
    if conc is not None and conc.ativo:
        notas.append("Cargas em faixa, em linha e concentrada: pressões pela teoria da elasticidade (Boussinesq, "
                     "na forma de Terzaghi/NAVFAC), horizontais, somadas ao empuxo de terra e majoradas por γf. "
                     "Resultante na estabilidade: " + f"{conc.Fh:.1f}".replace(".", ",") + " kN/m a "
                     + f"{conc.zF:.2f}".replace(".", ",") + " m do fundo da sapata."
                     + (" Essas pressões entram no contraforte, mas NÃO nas lajes entre contrafortes: verifique as lajes "
                        "à parte." if cf else ""))
    fora = lambda f: f.forcas.F_N > 0 and abs(f.verif.R_e) >= B / 2   # noqa: E731
    base_invalida = fora(f1) or (trav and fora(f2))
    if fav_fora and not base_invalida:
        base_invalida = True
        notas.append("Com o empuxo majorado por γf e os pesos com 1,0 (combinação de ações favoráveis, NBR 8681) a "
                     "resultante de cálculo sai da base: não há distribuição de tensões para dimensionar ponta e "
                     "talão. Aumente a base.")
    elif base_invalida:
        notas.append("Resultante fora da base (|e| ≥ B/2): não existe distribuição de tensões no solo, então "
                     "ponta e talão não podem ser dimensionados. A planilha segue calculando com tensões "
                     "negativas nesse caso; o aplicativo reprova o dimensionamento da base.")
    if c.desvio_planilha:
        notas.append(f"fck = {e.fck_c:g} MPa > 40: aplicada a NBR 6118 (ηc"
                     + (", λ, αc, fctm e ρmin do grupo II" if e.fck_c > 50 else "")
                     + "); a planilha usa 0,85·fcd·0,8x em qualquer fck, então os resultados diferem dela.")
    if e.xd_lim == LimiteXd.NBR and c.xd_lim_nbr != 0.45:
        notas.append("fck > 50 MPa: limite de ductilidade x/d = 0,35 (NBR 6118 14.6.4.3).")
    if cf:
        notas.append("Contraforte é viga: armadura transversal mínima obrigatória mesmo com VSd ≤ VRd "
                     "(NBR 6118 17.4.1.1); dimensione os estribos e a ligação com a cortina e a base.")
    if not cf:
        dist = max(0.2 * max(as_vt, 0.0), 0.9, 0.5 * Asmin)
        v["dm_Asdist"] = dist
        notas.append("Armadura de distribuição (horizontal) mínima da cortina: "
                     + f"{dist:.2f}".replace(".", ",") + " cm²/m por face "
                     "— NBR 6118 Tab. 19.1 (≥ 20 % da principal, ≥ 0,9 cm²/m, ≥ 0,5·ρmín).")
    if min(e.cob_ct, e.cob_bs) < 3.0:
        notas.append("Cobrimento < 3,0 cm: abaixo do mínimo da NBR 6118 Tab. 7.2 para elementos em contato "
                     "com o solo.")
    if e.fck_c < 20:
        notas.append("fck < 20 MPa: abaixo da classe mínima da NBR 6118 para concreto armado (C20).")
    return Dimensionamento(c, v, secoes, fatias, base, checks, tuple(extras), tuple(notas), base_invalida, placas)


# ------------------------------------------------------------------ painéis (placa)
def _faixas(c: Concreto, M: np.ndarray, d: np.ndarray, As_ef: float) -> tuple[float, float, float]:
    """Dimensiona faixa a faixa: (As necessária máxima ou −1, aproveitamento máximo, x/d máximo)."""
    As = np.array([c.as_nec(float(m), float(dd)) if dd > 0 else -1.0 for m, dd in zip(M, d)])
    MR = np.array([c.mrd(As_ef, float(dd)) if dd > 0 else 0.0 for dd in d])
    ut = np.where(MR > 0, M / np.where(MR > 0, MR, 1.0), np.where(M > 0, np.inf, 0.0))
    ativo = M > 0.02 * max(float(M.max()), 1e-9)
    xd = max((c.xd(As_ef, float(dd)) for dd, a in zip(d, ativo) if a and dd > 0), default=0.0)
    return (-1.0 if As.min() < 0 else float(As.max())), float(ut.max()), float(xd)


def _painel_cortina(e, g: Geometria, c: Concreto, l: float, y_fat: np.ndarray, p_fat: np.ndarray, vrd) -> dict:
    """Cortina entre contrafortes: engastada na sapata e nos contrafortes, borda superior livre."""
    yj = np.linspace(0.0, g.h_cort, N_PLACA + 1)
    pj = np.interp(e.h_sap + yj, y_fat[::-1], p_fat[::-1])
    P = placa.resolver(round(l, 4), round(g.h_cort, 4), tuple(float(x) for x in np.round(pj, 6)))
    t = e.t_base + (e.t_topo - e.t_base) * yj / g.h_cort
    cob = e.cob_ct / 100
    d_vt = t - cob - e.ar_tz_phi / 2000
    d_vf = t - cob - e.ar_fr_phi / 2000
    d_ht = t - cob - e.ar_tz_phi / 1000 - e.ar_hz_tz_phi / 2000       # horizontal por dentro da vertical
    d_hf = t - cob - e.ar_fr_phi / 1000 - e.ar_hz_fr_phi / 2000
    Mvt, Mvf = np.maximum(0.0, -P.My.min(axis=1)), np.maximum(0.0, P.My.max(axis=1))
    Mht, Mhf = np.maximum(0.0, -P.Mx.min(axis=1)), np.maximum(0.0, P.Mx.max(axis=1))
    Ast, Asf = area_barras(e.ar_tz_phi, e.ar_tz_s), area_barras(e.ar_fr_phi, e.ar_fr_s)
    Aht, Ahf = area_barras(e.ar_hz_tz_phi, e.ar_hz_tz_s), area_barras(e.ar_hz_fr_phi, e.ar_hz_fr_s)
    Asvt, ut_vt, xd1 = _faixas(c, Mvt, d_vt, Ast)
    Asvf, ut_vf, xd2 = _faixas(c, Mvf, d_vf, Asf)
    Asht, ut_ht, xd3 = _faixas(c, Mht, d_ht, Aht)
    Ashf, ut_hf, xd4 = _faixas(c, Mhf, d_hf, Ahf)
    Vb = float(np.nanmax(P.Vy0))
    VRb = vrd(Ast, float(d_vt[0]))
    Vs = np.nan_to_num(np.maximum(P.Vx0, P.Vx1))
    VRs = np.array([vrd(Aht, float(dd)) if dd > 0 else 1e-9 for dd in d_ht])
    k = int(np.argmax(Vs / VRs))
    V, VR = (Vb, VRb) if Vb / VRb >= Vs[k] / VRs[k] else (float(Vs[k]), float(VRs[k]))
    razao, tipo = placa.classificar(l, g.h_cort)
    return dict(P=P, y=yj, t=t, Mvt_y=Mvt, Mvf_y=Mvf, Mht_y=Mht, Mhf_y=Mhf, tipo=tipo, razao=float(razao),
                Mvt=float(Mvt.max()), Mvf=float(Mvf.max()), Mht=float(Mht.max()), Mhf=float(Mhf.max()),
                Asvt=Asvt, Asvf=Asvf, Asht=Asht, Ashf=Ashf, ut_vt=ut_vt, ut_vf=ut_vf, ut_ht=ut_ht, ut_hf=ut_hf,
                xd=max(xd1, xd2, xd3, xd4), Vb=Vb, VRb=float(VRb), Vs=float(Vs.max()), V=float(V), VR=float(VR))


def _painel_base(e, c: Concreto, l: float, b: float, w: float, frente: bool, vrd) -> dict:
    """Base do lado dos contrafortes: engastada na cortina e nos contrafortes, borda externa livre.

    Carga uniforme ``w`` (a mesma da planilha: σ máx. de cálculo na ponta, carga descendente no talão).
    Face carregada: inferior na ponta (reação do solo), superior no talão (peso de terra).
    """
    P = placa.resolver(round(l, 4), round(b, 4), tuple([round(float(w), 6)] * (N_PLACA + 1)))
    M_sup, M_vao = float(max(0.0, -P.Mx.min())), float(max(0.0, P.Mx.max()))
    M_tr_j, M_tr_pos = float(max(0.0, -P.My[0].min())), float(max(0.0, P.My.max()))
    cob = e.cob_bs / 100
    Ai, As_ = area_barras(e.ar_bl_i_phi, e.ar_bl_i_s), area_barras(e.ar_bl_s_phi, e.ar_bl_s_s)
    di = e.h_sap - cob - e.ar_bi_phi / 1000 - e.ar_bl_i_phi / 2000    # paralela ao muro, por dentro da transversal
    ds = e.h_sap - cob - e.ar_bs_phi / 1000 - e.ar_bl_s_phi / 2000
    Mi, Ms = (M_sup, M_vao) if frente else (M_vao, M_sup)
    V_cf = float(np.nanmax(np.maximum(P.Vx0, P.Vx1)))
    A_cf, d_cf = (Ai, di) if frente else (As_, ds)
    return dict(P=P, M_sup=M_sup, M_vao=M_vao, M_tr_j=M_tr_j, M_tr_pos=M_tr_pos, Mi=Mi, Ms=Ms, di=di, ds=ds,
                Asi=c.as_nec(Mi, di), Ass=c.as_nec(Ms, ds), xd=max(c.xd(Ai, di), c.xd(As_, ds)),
                V_cf=V_cf, VR_cf=float(vrd(A_cf, d_cf)), V_j=float(np.nanmax(P.Vy0)), w=float(w), b=float(b))
