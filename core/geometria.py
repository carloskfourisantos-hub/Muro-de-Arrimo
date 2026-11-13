"""Geometria — port da aba ``Geometria``.

Origem na aresta inferior da ponta; x positivo para o aterro, z para cima.
Os nomes dos atributos são os nomes definidos na planilha.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .enums import FaceInclinada, ModoCunha, PosicaoContraforte

TOL = 1e-4          # "existe talão/ponta?" (planilha: > 0,0001)
EPS = 1e-9
SEM_LIMITE = 1e9    # sentinela da planilha (u_w quando o plano não encontra o tardoz)

Ponto = tuple[float, float]


@dataclass(frozen=True)
class Poligono:
    nome: str
    vertices: tuple[Ponto, ...]
    A: float
    x: float
    z: float


def poligono(nome: str, vertices: list[Ponto]) -> Poligono:
    """Área e centroide pela fórmula do laço (mesma soma da planilha)."""
    n = len(vertices)
    s = sx = sz = 0.0
    for i in range(n):
        x0, z0 = vertices[i]
        x1, z1 = vertices[(i + 1) % n]
        e = x0 * z1 - x1 * z0
        s += e
        sx += (x0 + x1) * e
        sz += (z0 + z1) * e
    if abs(s) < EPS:
        return Poligono(nome, tuple(vertices), abs(s) / 2, 0.0, 0.0)
    return Poligono(nome, tuple(vertices), abs(s) / 2, sx / (3 * s), sz / (3 * s))


@dataclass(frozen=True)
class Geometria:
    h_cort: float
    B_base: float
    x_fb: float
    x_tb: float
    x_ft: float
    x_tt: float
    z_ter: float
    x_bt: float
    z_dv: float
    cv: int
    eps_r: float
    th_c: float
    a_t: float
    u_w: float
    u_t: float
    hit_t: int
    z_P: float
    x_P: float
    z_top_pl: float
    z_na: float
    z_naw: float
    z_cf: float
    z_D: float
    cortina: Poligono
    sapata: Poligono
    solo: Poligono
    solo_na: Poligono
    contraforte: Poligono
    solo_ponta: Poligono
    croqui: dict[str, list[Ponto]] = field(default_factory=dict)

    def x_frontal(self, z: float, h_sap: float) -> float:
        return self.x_fb + (self.x_ft - self.x_fb) * (z - h_sap) / self.h_cort

    def x_tardoz(self, z: float, h_sap: float) -> float:
        return self.x_tb + (self.x_tt - self.x_tb) * (z - h_sap) / self.h_cort


def calcular_geometria(e) -> Geometria:
    """``e`` = Entrada já resolvida."""
    hs, H = e.h_sap, e.H_muro
    beta = math.radians(e.beta_t)
    h_cort = H - hs
    B = e.b_ponta + e.t_base + e.b_talao
    x_fb = e.b_ponta
    x_tb = e.b_ponta + e.t_base
    frontal = e.face_inc == FaceInclinada.FRONTAL
    x_ft = x_tb - e.t_topo if frontal else e.b_ponta
    x_tt = x_tb if frontal else e.b_ponta + e.t_topo
    z_ter = max(hs, H - e.h_reb)
    x_bt = x_tb + (x_tt - x_tb) * (z_ter - hs) / h_cort
    z_dv = z_ter + (B - x_bt) * math.tan(beta)
    cv = 1 if (e.modo_cunha == ModoCunha.VERTICAL and e.b_talao > TOL) else 0
    eps_r = math.asin(min(1.0, math.sin(beta) / math.sin(math.radians(e.phi_at))))
    th_c = max(0.0, math.radians(45 - e.phi_at / 2) - (eps_r - beta) / 2)
    a_t = math.atan((x_tb - x_tt) / h_cort)
    den = math.tan(th_c) + (x_tt - x_tb) / h_cort
    u_w = SEM_LIMITE if den <= EPS else (B - x_tb) / den
    u_t = (z_ter - hs + (B - x_bt) * math.tan(beta)) / (1 + math.tan(th_c) * math.tan(beta))
    hit_t = 1 if u_w > z_ter - hs else 0
    z_P = hs + (u_t if hit_t == 1 else u_w)
    x_P = B - (z_P - hs) * math.tan(th_c)
    if cv == 1:
        z_top_pl = z_dv
    elif hit_t == 1 and e.b_talao > TOL:
        z_top_pl = z_P
    else:
        z_top_pl = z_ter
    z_na = max(hs, min(e.hw_at, z_ter))
    z_naw = z_na if cv == 1 else max(hs, min(z_na, z_P))
    z_cf = hs + min(e.cf_h, h_cort)
    z_D = max(hs, min(e.D_frente, H))

    def xf(z: float) -> float:
        return x_fb + (x_ft - x_fb) * (z - hs) / h_cort

    def xt(z: float) -> float:
        return x_tb + (x_tt - x_tb) * (z - hs) / h_cort

    cortina = poligono("Cortina", [(x_fb, hs), (x_tb, hs), (x_tt, H), (x_ft, H)])
    sapata = poligono("Sapata", [(0.0, 0.0), (B, 0.0), (B, hs), (0.0, hs)])
    p3 = (B, z_dv) if cv == 1 else (x_P, z_P)
    p4 = (x_bt, z_ter) if (cv == 1 or hit_t == 1) else (x_P, z_P)
    solo = poligono("Cunha de terra sobre o talão", [(x_tb, hs), (B, hs), p3, p4])
    solo_na = poligono("Solo sobre o talão abaixo do NA", [
        (x_tb, hs), (B, hs),
        (B if cv == 1 else B - (z_naw - hs) * math.tan(th_c), z_naw),
        (xt(z_naw), z_naw)])
    frente = e.cf_tipo == PosicaoContraforte.FRENTE
    if frente:
        cf_v = [(x_fb - min(e.cf_Lb, e.b_ponta), hs), (x_fb, hs),
                (xf(z_cf), z_cf), (xf(z_cf) - min(e.cf_Lt, xf(z_cf)), z_cf)]
    else:
        cf_v = [(x_tb, hs), (x_tb + min(e.cf_Lb, e.b_talao), hs),
                (xt(z_cf) + min(e.cf_Lt, B - xt(z_cf)), z_cf), (xt(z_cf), z_cf)]
    contraforte = poligono("Contraforte (perfil lateral)", cf_v)
    solo_ponta = poligono("Solo sobre a ponta", [(0.0, hs), (x_fb, hs), (xf(z_D), z_D), (0.0, z_D)])

    # ---- dados do croqui (Geometria!B96:D129)
    croqui: dict[str, list[Ponto]] = {
        "muro": [(0, 0), (B, 0), (B, hs), (x_tb, hs), (x_tt, H), (x_ft, H), (x_fb, hs), (0, hs), (0, 0)],
        "terreno": [(x_bt, z_ter), (B + 1.5, z_ter + (B + 1.5 - x_bt) * math.tan(beta))],
        "terreno_frente": [(-1.0, e.D_frente),
                           (0.0 if e.D_frente <= hs else xf(min(e.D_frente, H)), e.D_frente)],
        "plano": [((B, z_dv) if cv == 1 else ((x_P, z_P) if hit_t == 1 else (x_bt, z_ter))),
                  ((B, z_dv) if cv == 1 else (x_P, z_P)), (B, hs), (B, 0.0)],
    }
    if e.cf_usar:
        croqui["contraforte"] = list(cf_v) + [cf_v[0]]
    if e.hw_at > 0:
        croqui["na_atras"] = [(xt(min(e.hw_at, H)) if e.hw_at > hs else B, min(e.hw_at, z_dv)),
                              (B + 1.5, min(e.hw_at, z_dv))]
    if e.hw_fr > 0:
        croqui["na_frente"] = [(-1.0, e.hw_fr), (0.0 if e.hw_fr <= hs else xf(min(e.hw_fr, H)), e.hw_fr)]

    return Geometria(h_cort, B, x_fb, x_tb, x_ft, x_tt, z_ter, x_bt, z_dv, cv, eps_r, th_c, a_t,
                     u_w, u_t, hit_t, z_P, x_P, z_top_pl, z_na, z_naw, z_cf, z_D,
                     cortina, sapata, solo, solo_na, contraforte, solo_ponta, croqui)
