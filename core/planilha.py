"""Compatibilidade com a planilha: resultado → nomes definidos do ``.xlsx``.

Usado pelos testes de paridade e pela exportação. Reaplica as sentinelas da
planilha (FS = 999, σ = 10 000 kPa) que o núcleo representa como ``inf``.
"""
from __future__ import annotations

import math

from .avisos import texto_planilha
from .fases import Fase, Resultado

# Opções do aplicativo que reproduzem o comportamento da planilha (os padrões do
# aplicativo são outros: bloco alinhado ao tardoz e cortina como placa com borda livre).
MODO_PLANILHA = {"bl_pos": "Centrado nas estacas (planilha)", "laje_cf": "Coeficientes do GEO5 (planilha)"}

# Padrões da planilha nos campos em que o aplicativo adota outro padrão (decisão de 16/11/2026).
PADROES_PLANILHA = {"k_phi": 0.666666666666667, "k_c": 0.0, "ff_tipo": "Nenhuma"}

FS_SENTINELA = 999.0
SIG_SENTINELA = 10000.0

_GEO = ("h_cort B_base x_fb x_tb x_ft x_tt z_ter x_bt z_dv cv eps_r th_c a_t u_w u_t hit_t z_P x_P "
        "z_top_pl z_na z_naw z_cf z_D").split()
_POL = {"pCort": "cortina", "pSap": "sapata", "pSolo": "solo", "pSoloNA": "solo_na", "pCF": "contraforte",
        "pPonta": "solo_ponta"}
_EMP = ("p_Hv zA_top zA_bot zB_bot p_dw p_b p_phi p_rep p_K0 p_KaR p_Pa p_Pah p_zPa p_Pah_s p_Pah_q p_Pav_c "
        "p_Pav_s p_Pav_q p_Pav p_xPav p_U p_zU p_Uf p_zUf p_K0f p_Rff p_zRff p_u0 p_uB p_Usub p_xUsub").split()
_FOR = "F_Hnet F_N F_Mres F_Movr F_Hact F_Hres_ext F_Htrav".split()
_ANC = "anc_Tp anc_Rt anc_xe bl_xe anc_Fe anc_F anc_Hm bl_P".split()
_VER = "R_Hact R_Hres R_xR R_e R_eB R_Bef R_qult".split()
_CAP = "CC_phi CC_Nq CC_Nc CC_Ng CC_q0 CC_g CC_H CC_m CC_iq CC_ig CC_ic CC_qult".split()
_TRV = "TR_T TR_Mres0 TR_Movr0 TR_Ft TR_Fd TR_Freq TR_Fd_k0".split()
# nomes que só existem na Fase 1 dentro do grupo de empuxo (a planilha não nomeou os _2)
_SEM_F2 = {"p_Pa", "p_Pah_s", "p_Pah_q", "p_Pav_c", "p_U", "p_zU"}


def _fs(v: float) -> float:
    return FS_SENTINELA if math.isinf(v) else v


def _sig(v: float) -> float:
    return SIG_SENTINELA if math.isinf(v) else v


def _fase(f: Fase, suf: str) -> dict:
    d: dict = {}
    for n in _EMP:
        d[n + suf] = getattr(f.emp, n)
    d["F_fase" + suf] = f.numero
    for n in _FOR:
        d[n + suf] = getattr(f.forcas, n)
    for n in _ANC:
        d[n + suf] = getattr(f.forcas.anc, n)
    v = f.verif
    for n in _VER:
        d[n + suf] = getattr(v, n)
    for n in _CAP:
        d[n + suf] = getattr(v.cap, n)
    d["R_FSt" + suf] = _fs(v.R_FSt)
    d["R_FSd" + suf] = _fs(v.R_FSd)
    d["R_sef" + suf] = _sig(v.R_sef)
    if f.forcas.F_N <= 0:
        d["R_FScc" + suf] = 0.0
    elif math.isinf(v.R_sef):
        d["R_FScc" + suf] = v.R_qult / SIG_SENTINELA
    else:
        d["R_FScc" + suf] = _fs(v.R_FScc)
    d["sig_max" + suf] = _sig(v.sig_max)
    d["sig_min" + suf] = v.sig_min
    d["avisos" + suf] = texto_planilha(f.avisos)
    d["resultado" + suf] = "ATENDE" if f.atende else "NÃO ATENDE"
    return d


def nomes_planilha(res: Resultado) -> dict:
    """Dicionário {nome definido na planilha: valor} (+ algumas células sem nome)."""
    d: dict = {}
    g = res.geo
    for n in _GEO:
        d[n] = getattr(g, n)
    for pre, attr in _POL.items():
        p = getattr(g, attr)
        d[pre + "_A"], d[pre + "_x"], d[pre + "_z"] = p.A, p.x, p.z
    d.update(_fase(res.fase1, ""))
    d.update(_fase(res.fase2, "_2"))
    for n in _TRV:
        d[n + "_2"] = getattr(res.trav, n)
    for k, val in res.dim.v.items():
        d[k] = _sig(val) if k in ("bd_s", "bd_w") and isinstance(val, float) else val
    d["dm_geral"] = "ATENDE" if res.dim.dm_geral else "NÃO ATENDE"
    d["resultado_geral"] = "ATENDE" if res.atende_estabilidade else "NÃO ATENDE"
    return d
