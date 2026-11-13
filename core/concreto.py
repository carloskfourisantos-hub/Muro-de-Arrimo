"""Concreto armado — ABNT NBR 6118: materiais, flexão simples e cisalhamento.

Para fck ≤ 40 MPa as expressões são idênticas às da planilha (diagrama
retangular 0,85·fcd·0,8x). Fora dessa faixa a planilha deixa de seguir a norma
e o aplicativo aplica a NBR 6118:
  * fck > 40 MPa: ηc = (40/fck)^(1/3) na tensão do bloco (NBR 6118:2023, 17.2.2);
  * fck > 50 MPa: λ, αc, fctm, ρmin (Tab. 17.3) e x/d ≤ 0,35 do grupo II.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# NBR 6118, Tabela 17.3 — taxa mínima de armadura de flexão (seção retangular)
_RHO_MIN = ((30, 0.0015), (35, 0.00164), (40, 0.00179), (45, 0.00194), (50, 0.00208),
            (55, 0.00211), (60, 0.00219), (65, 0.00226), (70, 0.00233), (75, 0.00239),
            (80, 0.00245), (85, 0.00251), (90, 0.00256))


def area_barras(phi_mm: float, s_cm: float) -> float:
    """Área de aço por metro (cm²/m) para barras ϕ a cada s."""
    return math.pi * (phi_mm / 10) ** 2 / 4 * 100 / s_cm


@dataclass(frozen=True)
class Concreto:
    fck: float
    fcd: float      # MPa
    fyd: float      # MPa
    fctm: float     # MPa
    fctd: float     # MPa
    rho_min: float
    k_bloco: float  # αc·ηc·λ   (0,68 na planilha)
    k_meio: float   # αc·ηc/2   (0,425 na planilha)
    lam: float      # λ         (0,8 na planilha)
    xd_lim_nbr: float
    desvio_planilha: bool   # True quando a NBR 6118 difere do que a planilha calcula

    # ------------------------------------------------------------- flexão simples
    def as_nec(self, M: float, d: float, b: float = 1.0) -> float:
        """As necessária (cm²) para o momento de cálculo M (kN·m). −1 = seção insuficiente."""
        if M <= 0:
            return 0.0
        t = M / (self.k_meio * self.fcd * 1000 * b)
        if d**2 <= t:
            return -1.0
        x = (d - math.sqrt(d**2 - t)) / self.lam
        return self.k_bloco * self.fcd * 1000 * b * x / (self.fyd * 1000) * 10000

    def linha_neutra(self, As: float, b: float = 1.0) -> float:
        """x (m) com a armadura efetiva As (cm²) escoando."""
        return As * self.fyd / 10 / (self.k_bloco * self.fcd * 1000 * b)

    def mrd(self, As: float, d: float, b: float = 1.0) -> float:
        """Momento resistente (kN·m) da armadura efetiva As (cm²)."""
        return As * self.fyd / 10 * (d - self.lam / 2 * self.linha_neutra(As, b))

    def xd(self, As: float, d: float, b: float = 1.0) -> float:
        return self.linha_neutra(As, b) / d

    # ---------------------------------------------- cisalhamento sem estribos
    def vrd1(self, As: float, d: float, b: float = 1.0) -> float:
        """NBR 6118 19.4.1 — lajes sem armadura transversal (kN)."""
        k = max(1.0, 1.6 - d)
        rho1 = min(0.02, As / 10000 / (b * d))
        return 0.25 * self.fctd * k * (1.2 + 40 * rho1) * b * d * 1000

    def vrd_geo5(self, d: float, b: float = 1.0) -> float:
        """0,6·fctd·b·d — critério do GEO5 (legado)."""
        return 0.6 * self.fctd * b * d * 1000


def criar_concreto(fck: float, fyk: float, gc: float, gs: float) -> Concreto:
    fcd, fyd = fck / gc, fyk / gs
    if fck <= 50:
        fctm, lam, alfa = 0.3 * fck ** (2 / 3), 0.8, 0.85
    else:
        fctm = 2.12 * math.log(1 + 0.11 * fck)
        lam = 0.8 - (fck - 50) / 400
        alfa = 0.85 * (1 - (fck - 50) / 200)
    eta = 1.0 if fck <= 40 else (40 / fck) ** (1 / 3)
    rho = next((r for lim, r in _RHO_MIN if fck <= lim), _RHO_MIN[-1][1])
    if fck <= 40:   # constantes literais da planilha (evita ruído de arredondamento)
        k_bloco, k_meio = 0.68, 0.425
    else:
        k_bloco, k_meio = alfa * eta * lam, alfa * eta / 2
    return Concreto(fck, fcd, fyd, fctm, 0.7 * fctm / gc, rho, k_bloco, k_meio, lam,
                    0.45 if fck <= 50 else 0.35, fck > 40)
