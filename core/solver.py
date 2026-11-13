"""Recursos que a planilha não tem: dimensionamento automático e estudo paramétrico.

Tudo aqui apenas chama ``calcular`` repetidas vezes — nenhuma fórmula nova.
"""
from __future__ import annotations

from dataclasses import dataclass

from .dimensionamento import NAO_OK
from .fases import Resultado, calcular

BITOLAS = (6.3, 8.0, 10.0, 12.5, 16.0, 20.0, 25.0)
ESPACAMENTOS = (20.0, 17.5, 15.0, 12.5, 10.0, 7.5)


def estabilidade_ok(r: Resultado) -> bool:
    """As 4 verificações da NBR 11682 em todas as fases (sem considerar avisos)."""
    return r.fase1.verif.verificacoes_ok and (not r.tem_fase2 or r.fase2.verif.verificacoes_ok)


# ----------------------------------------------------------------- geometria
@dataclass(frozen=True)
class BaseMinima:
    encontrado: bool
    b_ponta: float
    b_talao: float
    B: float
    resultado: Resultado | None
    tentativas: int


def menor_valor(entrada, campo: str, maximo: float, passo: float = 0.05) -> tuple[float | None, Resultado | None]:
    """Menor valor de ``campo`` (a partir do atual, de ``passo`` em ``passo``) que atende a estabilidade."""
    v = getattr(entrada, campo)
    while v <= maximo + 1e-9:
        try:
            r = calcular(entrada.com(**{campo: round(v, 4)}))
        except ValueError:
            r = None
        if r is not None and estabilidade_ok(r):
            return round(v, 4), r
        v += passo
    return None, None


def base_minima(entrada, passo: float = 0.10) -> BaseMinima:
    """Combinação ponta × talão de menor largura B que atende a estabilidade.

    Varre ponta de 0 a 0,6·H e talão de 0 a 1,2·H; entre soluções de mesma B
    prefere a de maior FS ao deslizamento.
    """
    H = entrada.H_muro
    n_p = int(round(0.6 * H / passo))
    n_t = int(round(1.2 * H / passo))
    melhor = None
    n = 0
    for soma in range(0, n_p + n_t + 1):          # B crescente
        candidatos = []
        for ip in range(0, min(n_p, soma) + 1):
            it = soma - ip
            if it > n_t:
                continue
            n += 1
            try:
                r = calcular(entrada.com(b_ponta=round(ip * passo, 4), b_talao=round(it * passo, 4)))
            except ValueError:
                continue
            if estabilidade_ok(r):
                candidatos.append((min(r.fase1.verif.R_FSd, r.fase2.verif.R_FSd), ip, it, r))
        if candidatos:
            _, ip, it, r = max(candidatos, key=lambda c: c[0])
            melhor = BaseMinima(True, round(ip * passo, 4), round(it * passo, 4), r.geo.B_base, r, n)
            break
    return melhor or BaseMinima(False, entrada.b_ponta, entrada.b_talao, 0.0, None, n)


# -------------------------------------------------------------- paramétrico
def estudo_parametrico(entrada, campo: str, valores) -> list[dict]:
    """FS e excentricidade para cada valor de ``campo`` (linhas inválidas são puladas)."""
    linhas = []
    for val in valores:
        try:
            r = calcular(entrada.com(**{campo: val}))
        except ValueError:
            continue
        for f in (r.fase1, r.fase2) if r.tem_fase2 else (r.fase1,):
            v = f.verif
            linhas.append(dict(valor=val, fase=f.numero, FSt=v.R_FSt, FSd=v.R_FSd, eB=v.R_eB, FScc=v.R_FScc,
                               sig_max=v.sig_max, ok=v.verificacoes_ok, dim_ok=r.dim.atende))
    return linhas


# ---------------------------------------------------------------- armaduras
# posição -> (campo do diâmetro, campo do espaçamento, índices das verificações ligadas, usa a extra do talão)
_POSICOES = {
    "Cortina — face do tardoz": ("ar_tz_phi", "ar_tz_s", (0, 1, 2, 3, 6), False, False),
    "Cortina — face frontal": ("ar_fr_phi", "ar_fr_s", (4, 5), False, False),
    "Base — face inferior (ponta)": ("ar_bi_phi", "ar_bi_s", (10, 11, 12, 13), False, False),
    "Base — face superior (talão)": ("ar_bs_phi", "ar_bs_s", (14, 15, 16), True, False),
    "Cortina — horizontal face do tardoz": ("ar_hz_tz_phi", "ar_hz_tz_s", (7,), False, True),
    "Cortina — horizontal face frontal": ("ar_hz_fr_phi", "ar_hz_fr_s", (8, 9), False, True),
    "Base entre contrafortes — inferior": ("ar_bl_i_phi", "ar_bl_i_s", (17, 19, 20), False, True),
    "Base entre contrafortes — superior": ("ar_bl_s_phi", "ar_bl_s_s", (18, 19), False, True),
}


@dataclass(frozen=True)
class Sugestao:
    posicao: str
    campo_phi: str
    campo_s: str
    phi: float
    s: float
    As: float
    atende: bool


def sugerir_armaduras(entrada) -> tuple[object, list[Sugestao]]:
    """Menor área de aço (ϕ comercial × espaçamento) que atende as verificações de cada posição.

    Devolve a entrada com as armaduras sugeridas e a lista de sugestões.
    ``atende = False`` indica que nem a combinação mais pesada resolve
    (seção insuficiente: aumente a espessura).
    """
    import math

    opcoes = sorted(((math.pi * (p / 10) ** 2 / 4 * 100 / s, p, s) for p in BITOLAS for s in ESPACAMENTOS),
                    key=lambda o: (o[0], -o[2]))
    e = entrada
    saida = []
    for pos, (cphi, cs, idx, extra_talao, so_cf) in _POSICOES.items():
        if so_cf and not e.cf_usar:
            continue
        escolhido = None
        for As, p, s in opcoes:
            tent = e.com(**{cphi: p, cs: s})
            d = calcular(tent).dim
            ok = all(d.checks[i].situacao != NAO_OK for i in idx)
            if extra_talao:
                ok = ok and d.extras[0].situacao != NAO_OK
            if ok:
                escolhido = (tent, Sugestao(pos, cphi, cs, p, s, As, True))
                break
        if escolhido is None:
            As, p, s = opcoes[-1]
            escolhido = (e.com(**{cphi: p, cs: s}), Sugestao(pos, cphi, cs, p, s, As, False))
        e = escolhido[0]
        saida.append(escolhido[1])
    return e, saida
