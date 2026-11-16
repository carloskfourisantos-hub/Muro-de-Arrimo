"""Sobrecargas concentradas, em linha e em faixa no terrapleno — pressões horizontais no muro.

Só existe no aplicativo (a planilha trata apenas a sobrecarga uniforme). Soluções da teoria da
elasticidade (Boussinesq) na forma usada em projeto de contenções (Terzaghi, 1954; NAVFAC DM-7.2;
Bowles), com m = x/H e n = z/H (x = distância ao plano de cálculo, z = profundidade, H = altura):

  faixa  q (kPa):   σh = k·(2q/π)·(β − sen β·cos 2α)
  linha  Q (kN/m):  σh = k·(4Q/(πH))·m²n/(m² + n²)²          (m ≥ 0,4; abaixo disso usa m = 0,4)
  ponto  P (kN):    σh = k·1,77·(P/H²)·m²n²/(m² + n²)³        (idem), reduzida por cos²(1,1θ) em planta

k = 1 para parede rígida: é o dobro da solução elástica (efeito de espelho de uma parede que não se
desloca), que corresponde a ν = 0,5 e é o que os ensaios de Terzaghi confirmaram. k = 0,5 devolve a
solução elástica simples, para parede que se desloca. Nas deformações planas (faixa e linha) a tensão
horizontal não depende do coeficiente de Poisson; na carga pontual depende, e a forma de Terzaghi já
o embute.

As pressões são horizontais (sem atrito) e somam-se ao empuxo de terra.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .enums import ParedeBoussinesq
from .geometria import Geometria

N_INT = 400      # fatias da integração na altura
M_MIN = 0.4      # abaixo de m = 0,4 as expressões de Terzaghi deixam de depender de m


def s_faixa(z, q: float, a: float, b: float, k: float = 1.0):
    """Faixa de largura ``b`` começando a ``a`` do plano; ``z`` = profundidade (> 0)."""
    t1, t2 = np.arctan2(a, z), np.arctan2(a + b, z)
    beta, alfa = t2 - t1, (t1 + t2) / 2
    return k * (2 * q / math.pi) * (beta - np.sin(beta) * np.cos(2 * alfa))


def s_linha(z, Q: float, x: float, H: float, k: float = 1.0):
    m, n = max(x / H, M_MIN), z / H
    return k * (4 * Q / (math.pi * H)) * m**2 * n / (m**2 + n**2) ** 2


def fator_planta(x: float, L: float, n: int = 200) -> float:
    """Média de cos²(1,1θ) num trecho de muro de comprimento ``L`` centrado na carga pontual."""
    y = (np.arange(n) + 0.5) * (L / 2) / n
    ang = np.minimum(1.1 * np.arctan2(y, max(x, 1e-6)), math.pi / 2)
    return float((np.cos(ang) ** 2).mean())


def s_ponto(z, P: float, x: float, H: float, L: float, k: float = 1.0):
    """Pressão média (kPa) num trecho de muro de comprimento ``L`` em frente à carga."""
    m, n = max(x / H, M_MIN), z / H
    return k * 1.77 * (P / H**2) * m**2 * n**2 / (m**2 + n**2) ** 3 * fator_planta(max(x, M_MIN * H), L)


@dataclass(frozen=True)
class Concentradas:
    ativo: bool
    k: float               # 1 = parede rígida (×2); 0,5 = solução elástica
    H_est: float           # altura do plano de cálculo da estabilidade (m)
    Fh: float              # resultante horizontal na estabilidade (kN/m)
    zF: float              # cota da resultante acima do fundo da sapata (m)
    Fh_faixa: float
    Fh_linha: float
    Fh_ponto: float
    W_talao: float         # peso das cargas que ficam sobre o talão (kN/m)
    xW: float              # posição desse peso (x a partir da ponta)
    z_est: np.ndarray      # cotas das fatias do plano de estabilidade
    sh_est: np.ndarray     # pressão em cada fatia (kPa)

    def na_cortina(self, e, g: Geometria, y: np.ndarray) -> np.ndarray:
        """Pressão no tardoz real nas cotas ``y`` (distâncias medidas a partir do tardoz)."""
        if not self.ativo:
            return np.zeros_like(y)
        H = g.z_ter
        z = g.z_ter - y
        ok = z > 0
        zz = np.where(ok, z, 1.0)
        return np.where(ok, _soma(e, zz, H, self.k, 0.0)[0], 0.0)


def _soma(e, z, H: float, k: float, recuo: float):
    """Pressões das três cargas a um plano recuado ``recuo`` do tardoz (0 = o próprio tardoz)."""
    zero = np.zeros_like(z)
    sf = sl = sp = zero
    if e.sc_fx_q > 0:
        ini = max(e.sc_fx_a, recuo)
        larg = e.sc_fx_a + e.sc_fx_b - ini
        if larg > 0:
            sf = s_faixa(z, e.sc_fx_q, ini - recuo, larg, k)
    if e.sc_ln_Q > 0:
        sl = s_linha(z, e.sc_ln_Q, max(0.0, e.sc_ln_x - recuo), H, k)
    if e.sc_pt_P > 0:
        sp = s_ponto(z, e.sc_pt_P, max(0.0, e.sc_pt_x - recuo), H, e.sc_pt_L, k)
    return sf + sl + sp, sf, sl, sp


def calcular_concentradas(e, g: Geometria) -> Concentradas:
    ativo = e.sc_fx_q > 0 or e.sc_ln_Q > 0 or e.sc_pt_P > 0
    k = 1.0 if e.sc_bq == ParedeBoussinesq.RIGIDA else 0.5
    H = max(g.z_dv, 1e-6)                  # terreno no plano vertical pela extremidade do talão
    z = (np.arange(N_INT) + 0.5) * H / N_INT           # profundidade
    cota = H - z
    if not ativo:
        return Concentradas(False, k, H, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, cota, np.zeros_like(z))
    recuo = max(0.0, g.B_base - g.x_bt)    # largura do talão ao nível do terreno
    tot, sf, sl, sp = _soma(e, z, H, k, recuo)
    dz = H / N_INT
    Fh = float(tot.sum() * dz)
    zF = float((tot * cota).sum() * dz) / Fh if Fh > 0 else 0.0
    # parcela das cargas apoiada sobre o talão (peso)
    W = Mw = 0.0
    if e.sc_fx_q > 0 and e.sc_fx_a < recuo:
        fim = min(e.sc_fx_a + e.sc_fx_b, recuo)
        w = e.sc_fx_q * (fim - e.sc_fx_a)
        W, Mw = W + w, Mw + w * (g.x_bt + (e.sc_fx_a + fim) / 2)
    if e.sc_ln_Q > 0 and e.sc_ln_x < recuo:
        W, Mw = W + e.sc_ln_Q, Mw + e.sc_ln_Q * (g.x_bt + e.sc_ln_x)
    if e.sc_pt_P > 0 and e.sc_pt_x < recuo:
        w = e.sc_pt_P / e.sc_pt_L
        W, Mw = W + w, Mw + w * (g.x_bt + e.sc_pt_x)
    return Concentradas(True, k, H, Fh, zF, float(sf.sum() * dz), float(sl.sum() * dz), float(sp.sum() * dz),
                        W, Mw / W if W > 0 else 0.0, cota, tot)
