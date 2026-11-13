"""Orquestração: Fase 1 (construtiva) + Fase 2 (muro travado) + dimensionamento.

``calcular(entrada)`` é a única porta de entrada do núcleo: função pura,
resultado imutável.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .avisos import Aviso, calcular_avisos
from .dimensionamento import Dimensionamento, calcular_dimensionamento
from .empuxo import FATIAS_PLANILHA, Empuxo, calcular_empuxo
from .enums import ConvTravamento
from .forcas import Forcas, calcular_forcas
from .geometria import Geometria, calcular_geometria
from .verificacoes import Verificacoes, calcular_verificacoes


@dataclass(frozen=True)
class Fase:
    numero: int
    emp: Empuxo
    forcas: Forcas
    verif: Verificacoes
    avisos: tuple[Aviso, ...]

    @property
    def atende(self) -> bool:
        """``Resumo!C33``: as 4 verificações OK e nenhum aviso de consistência."""
        return self.verif.verificacoes_ok and not self.avisos


@dataclass(frozen=True)
class Travamento:
    """Força mínima no travamento — estimativa da planilha (``Resumo F2!C54:C60``)."""
    TR_T: float
    TR_Mres0: float
    TR_Movr0: float
    TR_Ft: float
    TR_Fd: float
    TR_Freq: float
    TR_Fd_k0: float


@dataclass(frozen=True)
class Resultado:
    entrada: object            # Entrada resolvida
    geo: Geometria
    fase1: Fase
    fase2: Fase                # igual à Fase 1 quando não há travamento
    trav: Travamento
    dim: Dimensionamento

    @property
    def tem_fase2(self) -> bool:
        return bool(self.entrada.trav_usar)

    @property
    def atende_estabilidade(self) -> bool:
        """``Resumo!I37``: todas as fases."""
        return self.fase1.atende and (not self.tem_fase2 or self.fase2.atende)

    @property
    def atende(self) -> bool:
        return self.atende_estabilidade and self.dim.atende


def _fase(e, g: Geometria, n: int, fatias) -> Fase:
    emp = calcular_empuxo(e, g, n, fatias)
    F = calcular_forcas(e, g, emp, n)
    V = calcular_verificacoes(e, g, F)
    return Fase(n, emp, F, V, calcular_avisos(e, g, F, V))


def _travamento(e, f2: Fase) -> Travamento:
    F, V = f2.forcas, f2.verif
    T = F.F_Htrav
    z = e.trav_z
    em_mres = e.trav_conv in (ConvTravamento.SOMAR, ConvTravamento.GEO5)
    Mres0 = F.F_Mres - T * z if em_mres else F.F_Mres
    Movr0 = F.F_Movr if em_mres else F.F_Movr + T * z
    if z <= 0:
        Ft = 0.0
    elif em_mres:
        Ft = max(0.0, (e.FSt_min * Movr0 - Mres0) / z)
    else:
        Ft = max(0.0, (Movr0 - Mres0 / e.FSt_min) / z)
    if e.trav_conv == ConvTravamento.SOMAR:
        Fd = max(0.0, e.FSd_min * V.R_Hact - (V.R_Hres - T))
    else:
        Fd = max(0.0, (V.R_Hact + T) - V.R_Hres / e.FSd_min)
    return Travamento(T, Mres0, Movr0, Ft, Fd, max(Ft, Fd), F.F_Hact)


def calcular(entrada, fatias: tuple[int, int, int] = FATIAS_PLANILHA) -> Resultado:
    e = entrada.resolvida()
    g = calcular_geometria(e)
    f1 = _fase(e, g, 1, fatias)
    f2 = _fase(e, g, 2, fatias)
    return Resultado(e, g, f1, f2, _travamento(e, f2), calcular_dimensionamento(e, g, f1, f2))


# --------------------------------------------------------------------------- extra
@dataclass(frozen=True)
class TravamentoExato:
    """Força mínima no travamento obtida recalculando a Fase 2 a cada tentativa."""
    F_tomb: float            # força mínima para FS tombamento
    F_desl: float            # força mínima para FS deslizamento (exata)
    F_min: float
    resultado: Resultado | None   # Fase 2 recalculada com F_min
    viavel: bool
    obs: str


def travamento_minimo_exato(entrada, tol: float = 1e-3) -> TravamentoExato:
    """Resolve por bisseção a menor força de travamento que atende FSt e FSd.

    A planilha estima a parcela de deslizamento com a excentricidade fixa
    (``Resumo F2!B61``). Aqui a Fase 2 é recalculada a cada iteração, de modo
    que a variação de B' (adesão) entra no resultado.
    """
    base = entrada.com(trav_usar=True)

    def fs(F: float) -> tuple[float, float]:
        v = calcular(base.com(trav_F=F)).fase2.verif
        return v.R_FSt, v.R_FSd

    def menor(indice: int, alvo: float) -> float:
        if fs(0.0)[indice] >= alvo:
            return 0.0
        hi = 10.0
        while fs(hi)[indice] < alvo:
            hi *= 2
            if hi > 1e5:
                return math.inf
        lo = 0.0
        while hi - lo > tol:
            mid = (lo + hi) / 2
            if fs(mid)[indice] >= alvo:
                hi = mid
            else:
                lo = mid
        return hi

    Ft = menor(0, base.FSt_min)
    Fd = menor(1, base.FSd_min)
    Fmin = max(Ft, Fd)
    if math.isinf(Fmin):
        return TravamentoExato(Ft, Fd, Fmin, None, False, "Nenhuma força de travamento atende os FS.")
    res = calcular(base.com(trav_F=Fmin))
    v = res.fase2.verif
    obs = ""
    if not v.ok_exc:
        obs = ("Com essa força a resultante sai do núcleo da base (e/B = %.3f): trave também a base "
               "em vez de aumentar a reação no topo." % v.R_eB)
    elif not v.ok_cap:
        obs = "Com essa força a capacidade de carga da Fase 2 não é atendida."
    return TravamentoExato(Ft, Fd, Fmin, res, v.verificacoes_ok, obs)
