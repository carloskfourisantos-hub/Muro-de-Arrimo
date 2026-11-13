"""Forças e momentos — port das abas ``Forças`` / ``Forças F2``.

Convenção: Fx > 0 empurra o muro para a frente (instabilizante); Fz > 0 para
baixo. x a partir da ponta; z a partir do fundo da sapata. Momentos em torno
da aresta inferior da ponta.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .empuxo import Empuxo
from .enums import ConvResistentes, ConvTravamento, PesoNA, PosicaoBloco, PosicaoContraforte, Subpressao
from .geometria import TOL, Geometria


@dataclass(frozen=True)
class Forca:
    nome: str
    Fx: float
    Fz: float
    x: float
    z: float
    Mres: float
    Movr: float
    obs: str = ""
    grupo: str = "peso"   # peso | solo_ponta | agua  (fator de majoração no dimensionamento)


@dataclass(frozen=True)
class Ancoragem:
    anc_Tp: float
    anc_Rt: float
    anc_xe: float
    bl_xe: float
    anc_Fe: float
    anc_F: float
    anc_Hm: float
    bl_P: float


@dataclass(frozen=True)
class Forcas:
    fase: int
    linhas: tuple[Forca, ...]
    F_Hnet: float
    F_N: float
    F_Mres: float
    F_Movr: float
    F_Hact: float
    F_Hres_ext: float
    F_Htrav: float
    anc: Ancoragem


def calcular_ancoragem(e, g: Geometria) -> Ancoragem:
    Tp = math.pi * e.anc_d * e.anc_L * e.anc_a / e.anc_FS
    Rt = math.pi * (e.anc_ds / 1000) ** 2 / 4 * e.anc_fy * 1000 / e.anc_FS
    um_lado = e.b_ponta <= TOL or e.b_talao <= TOL
    xe = g.B_base / 2 if (e.anc_n2 == 0 and um_lado) else e.anc_x
    bl_xe = (xe + e.anc_x2) / 2 if e.anc_n2 > 0 else xe          # planilha: bloco centrado nas estacas
    if e.bl_usar and e.bl_pos != PosicaoBloco.ESTACAS:
        # bloco com posição própria: face alinhada ao tardoz (lado da terra), avançando para a ponta,
        # ou onde o projetista informar. Com uma só linha, a estaca fica no eixo do bloco.
        x0 = g.x_tb - e.bl_B if e.bl_pos == PosicaoBloco.TARDOZ else e.bl_x
        bl_xe = x0 + e.bl_B / 2
        if e.anc_n2 == 0:
            xe = bl_xe
    Fe = min(Tp, Rt)
    F = (e.anc_n1 + e.anc_n2) * Fe / e.anc_esp if e.anc_usar else 0.0
    Hm = (e.anc_n1 + e.anc_n2) * e.anc_H / e.anc_esp if e.anc_usar else 0.0
    gam_bloco = e.gam_c - (e.gam_w if max(e.hw_at, e.hw_fr) > 0 else 0.0)
    bl_P = gam_bloco * e.bl_B * e.bl_L * e.bl_H if e.bl_usar else 0.0
    return Ancoragem(Tp, Rt, xe, bl_xe, Fe, F, Hm, bl_P)


def calcular_forcas(e, g: Geometria, emp: Empuxo, fase: int = 1) -> Forcas:
    B = g.B_base
    anc = calcular_ancoragem(e, g)
    somar_res = e.conv_res == ConvResistentes.SOMAR
    trav_em_mres = e.trav_conv in (ConvTravamento.SOMAR, ConvTravamento.GEO5)
    frente = e.cf_tipo == PosicaoContraforte.FRENTE

    def vertical(nome, Fz, x, z, obs="", grupo="peso"):
        return Forca(nome, 0.0, Fz, x, z, Fz * x, 0.0, obs, grupo)

    def resistente(nome, Fx, z, em_mres: bool, obs="", grupo="peso"):
        # força horizontal contrária ao empuxo (Fx <= 0)
        return Forca(nome, Fx, 0.0, 0.0, z, -Fx * z if em_mres else 0.0,
                     0.0 if em_mres else Fx * z, obs, grupo)

    # 3 — contrafortes
    if e.cf_usar and e.cf_peso:
        if frente:
            desloc = e.gam_f * max(0.0, g.z_D - e.h_sap) * min(e.cf_Lb, e.b_ponta) if e.solo_ponta else 0.0
            w_cf = (e.gam_c * g.contraforte.A - desloc) * e.cf_t / e.cf_esp
        else:
            w_cf = (e.gam_c - e.gam_at) * g.contraforte.A * e.cf_t / e.cf_esp
    else:
        w_cf = 0.0
    # 5 — correção abaixo do NA
    d_gam = (e.gsat_at - e.gam_w - e.gam_at) if e.peso_na == PesoNA.SUBMERSO else (e.gsat_at - e.gam_at)
    # 7 — sobrecarga sobre o talão
    if e.q_estab:
        larg = B - g.x_bt if g.cv == 1 else (g.x_P - g.x_bt if (g.hit_t == 1 and e.b_talao > TOL) else 0.0)
        w_q = e.q_sc * larg
    else:
        w_q = 0.0
    x_q = (g.x_bt + B) / 2 if g.cv == 1 else (g.x_bt + g.x_P) / 2
    F_trav = e.trav_F if (e.trav_usar and fase == 2) else 0.0
    U = 0.0 if e.subp == Subpressao.NAO else -emp.p_Usub

    linhas = (
        vertical("Peso da cortina", e.gam_c * g.cortina.A, g.cortina.x, g.cortina.z),
        vertical("Peso da sapata", e.gam_c * g.sapata.A, g.sapata.x, g.sapata.z),
        vertical("Contrafortes (peso líquido — só se ativado)", w_cf, g.contraforte.x, g.contraforte.z,
                 "Distribuído por metro: × t / espaçamento"),
        vertical("Solo sobre o talão (γ natural)", e.gam_at * g.solo.A, g.solo.x, g.solo.z),
        vertical("Solo sobre o talão — correção abaixo do NA", d_gam * g.solo_na.A, g.solo_na.x, g.solo_na.z),
        vertical("Solo sobre a ponta", e.gam_f * g.solo_ponta.A if e.solo_ponta else 0.0,
                 g.solo_ponta.x, g.solo_ponta.z, "Somente se ativado na Entrada", "solo_ponta"),
        vertical("Sobrecarga sobre o talão", w_q, x_q, (g.z_ter + g.z_dv) / 2, "Somente se ativado na Entrada"),
        Forca("Empuxo — componente horizontal", emp.p_Pah, 0.0, B, emp.p_zPa, 0.0, emp.p_Pah * emp.p_zPa,
              "Solo + sobrecarga"),
        vertical("Empuxo — componente vertical", emp.p_Pav, emp.p_xPav, emp.p_zPa,
                 "Rankine: inclinação β | Coulomb: δ"),
        Forca("Água atrás — empuxo hidrostático", emp.p_U, 0.0, B, emp.p_zU, 0.0, emp.p_U * emp.p_zU, "", "agua"),
        resistente("Resistência na face frontal (empuxo em repouso)", -emp.p_Rff, emp.p_zRff, somar_res,
                   "Estabilizante ou redução do Movr, conforme a convenção"),
        resistente("Travamento (força contrária ao empuxo — só na Fase 2)", -F_trav, e.trav_z, trav_em_mres,
                   "Conforme a convenção da força do travamento"),
        resistente("Água na frente — empuxo hidrostático (resistente)", -emp.p_Uf, emp.p_zUf, somar_res,
                   "Estabilizante ou redução do Movr, conforme a convenção", "agua"),
        vertical("Ancoragem na base — 1ª linha de estacas",
                 e.anc_n1 * anc.anc_Fe / e.anc_esp if e.anc_usar else 0.0, anc.anc_xe, 0.0,
                 "n1 · mín(arrancamento; barra) / v"),
        vertical("Ancoragem na base — 2ª linha de estacas",
                 e.anc_n2 * anc.anc_Fe / e.anc_esp if e.anc_usar else 0.0, e.anc_x2, 0.0,
                 "n2 · mín(arrancamento; barra) / v"),
        vertical("Blocos de coroamento (peso, submerso se houver NA)",
                 anc.bl_P / e.anc_esp if e.bl_usar else 0.0, anc.bl_xe, -e.bl_H / 2,
                 "Peso do bloco por metro de muro"),
        Forca("Subpressão na base", 0.0, U, emp.p_xUsub, 0.0, 0.0, -U * emp.p_xUsub, "Distribuição linear", "agua"),
    )
    Hnet = sum(f.Fx for f in linhas)
    N = sum(f.Fz for f in linhas)
    Mres = sum(f.Mres for f in linhas)
    Movr = sum(f.Movr for f in linhas)
    Hact = sum(f.Fx for f in linhas if f.Fx > 0)
    Hres_ext = -sum(f.Fx for f in linhas if f.Fx < 0) - F_trav
    return Forcas(fase, linhas, Hnet, N, Mres, Movr, Hact, Hres_ext, F_trav, anc)
