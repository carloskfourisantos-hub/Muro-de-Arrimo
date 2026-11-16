"""Parâmetros de solo recomendados por NSPT — dados de ``Parametros_do_solo_Recomendado.xlsx``.

Faixas (mín, máx) para uso preliminar/anteprojeto. Fontes na própria planilha
(Teixeira & Godoy 1996; Godoy 1983; Bowles 1997; Terzaghi & Peck; Potyondy 1961).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

Faixa = tuple[float, float]


@dataclass(frozen=True)
class Classe:
    nome: str
    nspt: Faixa            # limite superior inf = faixa aberta
    gama: Faixa            # kN/m³
    phi: Faixa             # ° (argila: φ' drenado)
    c: Faixa               # kPa (argila: c' drenado)
    delta_phi: Faixa       # δ/φ
    adesao: Faixa          # ligação limite / adesão (kPa)
    qult: Faixa            # capacidade de carga última indicativa (kPa)
    su: Faixa | None = None  # argila: resistência não drenada (kPa)


INF = math.inf
ARGILA = (
    Classe("Muito mole", (0, 2), (13, 15), (20, 24), (0, 3), (0.5, 0.6), (10, 20), (50, 100), (0, 20)),
    Classe("Mole", (2, 4), (15, 17), (21, 25), (0, 5), (0.5, 0.65), (20, 35), (100, 200), (20, 40)),
    Classe("Média", (4, 8), (17, 18), (22, 27), (3, 10), (0.6, 0.7), (35, 60), (200, 350), (40, 80)),
    Classe("Rija", (8, 15), (18, 19), (24, 29), (8, 15), (0.65, 0.8), (60, 100), (350, 600), (80, 150)),
    Classe("Dura", (15, INF), (19, 20), (26, 32), (15, 25), (0.7, 0.9), (100, 150), (600, 900), (150, 300)),
)
SILTE = (
    Classe("Muito fofo", (0, 3), (14, 16), (24, 28), (0, 5), (0.6, 0.7), (15, 25), (80, 150)),
    Classe("Fofo", (3, 6), (15, 17), (27, 31), (0, 8), (0.65, 0.75), (25, 40), (150, 300)),
    Classe("Medianamente compacto", (6, 12), (16, 18), (29, 34), (0, 12), (0.7, 0.8), (40, 65), (300, 550)),
    Classe("Compacto", (12, 20), (17, 19), (31, 36), (0, 15), (0.75, 0.85), (65, 90), (550, 800)),
    Classe("Muito compacto", (20, INF), (18, 20), (33, 38), (0, 20), (0.8, 0.9), (90, 150), (800, 1100)),
)
AREIA = (
    Classe("Muito fofa", (0, 4), (15, 17), (26, 30), (0, 0), (0.6, 0.7), (20, 30), (100, 200)),
    Classe("Fofa", (4, 10), (16, 18), (29, 33), (0, 0), (0.65, 0.75), (30, 50), (200, 450)),
    Classe("Medianamente compacta", (10, 20), (17, 19), (32, 36), (0, 0), (0.7, 0.8), (50, 70), (450, 900)),
    Classe("Compacta", (20, 30), (18, 20), (35, 40), (0, 0), (0.75, 0.85), (70, 90), (900, 1500)),
    Classe("Muito compacta", (30, INF), (19, 21), (38, 45), (0, 0), (0.8, 0.9), (90, 130), (1500, 2500)),
)
TABELAS = {"Argila": ARGILA, "Silte": SILTE, "Areia": AREIA}

# solo misto -> (solo base, Δφ, operação na coesão, Δδ)
MISTOS = {
    "Argila siltosa": ("Argila", 2.0, ("x", 0.88), 1.0),
    "Argila arenosa": ("Argila", 4.0, ("x", 0.6), 2.0),
    "Silte arenoso": ("Silte", -2.0, ("x", 0.45), -1.0),
    "Silte argiloso": ("Silte", 0.0, ("+", 5.0), 0.0),
    "Areia argilosa": ("Areia", -2.0, ("=", 10.0), -1.0),
    "Areia siltosa": ("Areia", -4.0, ("=", 5.0), -2.0),
}
TIPOS = list(TABELAS) + list(MISTOS)

# ------------------------------------------------------------------ adesão base-solo: a = α·c
# Nenhuma norma brasileira fixa α (a NBR 11682 e a NBR 6122 não tratam do assunto). Critério adotado:
#  · Das (Principles of Foundation Engineering): atrito e adesão na base como k1·φ e k2·c, com k1 e k2
#    usualmente entre 1/2 e 2/3;
#  · NAVFAC DM-7.2 (tabela de atrito e adesão entre materiais diferentes): a razão adesão/coesão cai com a
#    consistência — ≈ 1,0 até c = 24 kPa; 1,0 → 0,75 até 48; 0,75 → 0,47 até 96; 0,47 → 0,32 até 192 kPa;
#  · EN 1997-1 (6.5.3): em condição drenada despreza c'; em condição não drenada usa cu na área comprimida.
# Coesão de areias e siltes sem argila é aparente (sucção/cimentação) e se perde com a saturação: α = 0.
ALFA_SEM_ARGILA = 0.0
ALFA_ARGILOSO = 0.5            # limite inferior de Das: solos mistos com argila e argilas rijas a duras
ALFA_ARGILA_PLASTICA = 2 / 3   # limite superior de Das: argila muito mole a média (molda-se à base)
_ALFA_MISTO = {"Argila siltosa": None, "Argila arenosa": ALFA_ARGILOSO, "Silte arenoso": ALFA_SEM_ARGILA,
               "Silte argiloso": ALFA_ARGILOSO, "Areia argilosa": ALFA_ARGILOSO, "Areia siltosa": ALFA_SEM_ARGILA}
_NAVFAC = ((0.0, 1.0), (24.0, 1.0), (48.0, 0.75), (96.0, 0.47), (192.0, 0.32))   # (c em kPa, adesão/c)


def alfa_nao_drenado(su: float) -> float:
    """Razão adesão/Su pela tabela do NAVFAC DM-7.2 (interpolação linear entre as faixas de consistência)."""
    for (c0, a0), (c1, a1) in zip(_NAVFAC, _NAVFAC[1:]):
        if su <= c1:
            return a0 + (a1 - a0) * (su - c0) / (c1 - c0)
    return _NAVFAC[-1][1]


def alfa_adesao(tipo: str, nspt: float, nao_drenado: bool = False, su: float = 0.0) -> float:
    """α da adesão base-solo (a = α·c) para o tipo de solo e a consistência."""
    base = MISTOS[tipo][0] if tipo in MISTOS else tipo
    if base == "Argila" and nao_drenado:
        return alfa_nao_drenado(su)
    if tipo in MISTOS and _ALFA_MISTO[tipo] is not None:
        return _ALFA_MISTO[tipo]
    if base != "Argila":
        return ALFA_SEM_ARGILA
    return ALFA_ARGILA_PLASTICA if classificar(tipo, nspt).nome in ("Muito mole", "Mole", "Média") else ALFA_ARGILOSO

NOTAS = {
    "Argila": "Su = 10 × NSPT (Teixeira & Godoy, 1996). φ' não é função direta do NSPT: confirme com ensaio "
              "triaxial quando a obra justificar. Para escavações e contenções provisórias em argila mole, "
              "priorize a análise não drenada (φu = 0, c = Su).",
    "Silte": "Silte puro/não plástico tem coesão real próxima de 0; os valores de coesão são aparentes (sucção) "
             "e não devem ser usados como resistência permanente em análise de longo prazo ou solo submerso.",
    "Areia": "Faixas de φ conferidas contra Bowles (1997), Godoy (1983) [φ = 28 + 0,4·NSPT] e Teixeira (1996) "
             "[φ = √(20·NSPT) + 15].",
    "misto": "Correção de solo misto: convenção de escritório, sem fonte acadêmica específica — trate como "
             "ajuste de engenharia e compare com sondagem/ensaio sempre que possível.",
}
FONTES = [
    "TEIXEIRA, A.T.; GODOY, N.S. Análise, projeto e execução de fundações rasas. In: HACHICH et al., Fundações: "
    "teoria e prática. PINI, 1996/1998.",
    "GODOY, N.S. (1972, 1983), apud HACHICH et al. (1998) — pesos específicos e φ = 28 + 0,4·NSPT.",
    "TEIXEIRA, A.T. (1996) — φ = √(20·NSPT) + 15 para areias.",
    "TERZAGHI, K.; PECK, R.B. Soil Mechanics in Engineering Practice. Wiley, 1948/1967.",
    "BOWLES, J.E. Foundation Analysis and Design. 5ª ed. McGraw-Hill, 1997.",
    "SIMONS, N.E.; MENZIES, B.K. — classificação de consistência de argilas por Su.",
    "POTYONDY, J.G. Skin friction between various soils and construction materials. Géotechnique, 1961.",
    "ABNT NBR 6484, NBR 6122 e NBR 11682.",
]


def classificar(tipo: str, nspt: float) -> Classe:
    base = MISTOS[tipo][0] if tipo in MISTOS else tipo
    for cl in TABELAS[base]:
        if nspt <= cl.nspt[1]:
            return cl
    return TABELAS[base][-1]


@dataclass(frozen=True)
class Sugestao:
    tipo: str
    classe: Classe
    gama: float
    phi: float
    c: float
    delta: float          # atrito solo-estrutura (°)
    adesao: float
    qult: float
    obs: tuple[str, ...]
    alfa: float = 0.0     # adesão base-solo: a = α·c


def sugerir(tipo: str, nspt: float, postura: float = 0.0, nao_drenado: bool = False) -> Sugestao:
    """Parâmetros sugeridos. ``postura`` 0 = mínimo da faixa (conservador) … 1 = máximo."""
    cl = classificar(tipo, nspt)
    base = MISTOS[tipo][0] if tipo in MISTOS else tipo
    t = min(1.0, max(0.0, postura))
    val = lambda f: f[0] + t * (f[1] - f[0])  # noqa: E731
    obs = [NOTAS[base]]
    gama, phi, c = val(cl.gama), val(cl.phi), val(cl.c)
    if base == "Argila" and nao_drenado:
        phi, c = 0.0, min(10.0 * nspt, cl.su[1]) if nspt > 0 else 0.0
        obs.append("Condição não drenada: φu = 0 e c = Su = 10·NSPT.")
    dphi = val(cl.delta_phi)
    delta = dphi * phi
    if tipo in MISTOS and not (base == "Argila" and nao_drenado):
        _, d_phi, (op, k), d_delta = MISTOS[tipo]
        phi += d_phi
        c = c * k if op == "x" else (c + k if op == "+" else k)
        delta = dphi * phi + d_delta
        obs.append(NOTAS["misto"])
    return Sugestao(tipo, cl, gama, phi, c, max(0.0, delta), val(cl.adesao), val(cl.qult), tuple(obs),
                    alfa_adesao(tipo, nspt, nao_drenado, c))


def correlacoes(nspt: float) -> dict[str, float]:
    """Correlações rápidas (uso preliminar)."""
    return {
        "Argila — Su = 10·NSPT (kPa)": 10 * nspt,
        "Argila — γ = 15 + 0,33·NSPT (kN/m³)": 15 + 0.33 * nspt,
        "Silte — φ = 20 + 0,5·NSPT (°)": 20 + 0.5 * nspt,
        "Silte — γ = 15 + 0,25·NSPT (kN/m³)": 15 + 0.25 * nspt,
        "Areia — φ = 28 + 0,4·NSPT (°) [Godoy]": 28 + 0.4 * nspt,
        "Areia — φ = √(20·NSPT) + 15 (°) [Teixeira]": math.sqrt(20 * nspt) + 15,
        "Areia — γ = 15 + 0,2·NSPT (kN/m³)": 15 + 0.2 * nspt,
    }
