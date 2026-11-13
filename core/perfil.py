"""Perfil de sondagem (SPT) → parâmetros do muro e esforço lateral por camadas.

Um ``Furo`` é a leitura de um boletim de sondagem: camadas (topo, base,
descrição), NSPT por metro e nível d'água. A partir dele e do trecho de
profundidade ocupado pelo muro (início e fim) saem:

* os parâmetros de cada camada (faixas de ``core.solos`` por tipo de solo e NSPT);
* o solo arrimado equivalente (o núcleo do muro trabalha com uma camada só);
* o solo de fundação (abaixo do fundo da sapata);
* o diagrama de esforço lateral por camadas (Rankine ativo, repouso e água).

Tudo aqui é estimativa de anteprojeto: correlação com NSPT não substitui ensaio.
"""
from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field, replace

import numpy as np

from . import solos

GAMA_SAT_MAIS = 1.0     # γsat ≈ γ + 1 kN/m³ (a planilha de solos não traz γsat)
SEM_SOLO = "Não considerar"
TIPOS = solos.TIPOS + [SEM_SOLO]


@dataclass(frozen=True)
class Camada:
    topo: float
    base: float
    descricao: str
    tipo: str = SEM_SOLO        # um de ``TIPOS``
    nspt: float | None = None   # NSPT médio da camada
    aterro: bool = False

    @property
    def espessura(self) -> float:
        return self.base - self.topo


@dataclass(frozen=True)
class Furo:
    nome: str
    camadas: tuple[Camada, ...]
    spt: tuple[tuple[float, int], ...] = ()   # (profundidade do ensaio em m, NSPT)
    na: float | None = None                   # profundidade do nível d'água (m); None = não encontrado
    cota: float | None = None                 # cota da boca do furo
    avisos: tuple[str, ...] = field(default_factory=tuple)

    @property
    def profundidade(self) -> float:
        fim = max((c.base for c in self.camadas), default=0.0)
        return max(fim, max((p for p, _ in self.spt), default=0.0))


# --------------------------------------------------------------- classificação
def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


_NAO_SOLO = ("concreto", "piso", "rocha", "concrec", "gnaisse", "granito", "matac", "asfalto", "basalto",
             "impenetravel", "limite d")
_QUALIF = {"argila": (("silt", "Argila siltosa"), ("aren", "Argila arenosa")),
           "silte": (("aren", "Silte arenoso"), ("argil", "Silte argiloso")),
           "areia": (("argil", "Areia argilosa"), ("silt", "Areia siltosa"))}


def classificar_descricao(descricao: str) -> tuple[str, bool]:
    """Tipo de solo (``solos.TIPOS``) e indicação de aterro a partir da descrição táctil-visual."""
    t = _sem_acento(descricao)
    aterro = "aterro" in t or "entulho" in t
    pos = {k: t.find(k) for k in ("argila", "silte", "areia")}
    achados = {k: p for k, p in pos.items() if p >= 0}
    if not achados:
        return SEM_SOLO, aterro
    if any(n in t for n in _NAO_SOLO) and min(achados.values()) > 25:
        return SEM_SOLO, aterro
    base = min(achados, key=achados.get)
    resto = t[achados[base] + len(base):]
    melhor = None
    for raiz, tipo in _QUALIF[base]:
        for m in re.finditer(raiz + r"[a-z\-]*", resto):
            antes = resto[max(0, m.start() - 8):m.start()]
            if "pouco" in antes or "pouca" in antes:     # "pouco arenosa" não muda o tipo
                continue
            if melhor is None or m.start() < melhor[0]:
                melhor = (m.start(), tipo)
            break
    return (melhor[1] if melhor else base.capitalize()), aterro


def nspt_medio(spt, topo: float, base: float) -> float | None:
    """Média dos NSPT cujo ensaio (trecho de 45 cm) cai dentro da camada."""
    dentro = [n for p, n in spt if topo <= p + 0.225 < base]
    if dentro:
        return sum(dentro) / len(dentro)
    perto = [(abs(p + 0.225 - (topo + base) / 2), n) for p, n in spt
             if abs(p + 0.225 - (topo + base) / 2) <= 1.5]      # camada fina sem ensaio: o mais próximo
    return min(perto)[1] if perto else None


def completar(furo: Furo) -> Furo:
    """Preenche tipo de solo e NSPT médio das camadas que ainda não os têm."""
    novas = []
    for c in furo.camadas:
        tipo, aterro = classificar_descricao(c.descricao)
        novas.append(replace(c, tipo=tipo if c.tipo == SEM_SOLO else c.tipo, aterro=c.aterro or aterro,
                             nspt=c.nspt if c.nspt is not None else nspt_medio(furo.spt, c.topo, c.base)))
    return replace(furo, camadas=tuple(novas))


# ---------------------------------------------------------------- parâmetros
@dataclass(frozen=True)
class Estrato:
    """Camada com parâmetros de cálculo, já recortada ao trecho de interesse."""
    topo: float
    base: float
    tipo: str
    nspt: float
    gama: float
    gsat: float
    phi: float       # °
    c: float         # kPa
    delta: float     # ° (atrito solo-estrutura)
    aterro: bool = False

    @property
    def espessura(self) -> float:
        return self.base - self.topo


def estratos(furo: Furo, z_ini: float, z_fim: float, postura: float = 0.0, sem_coesao: bool = False,
             nao_drenado: bool = False) -> tuple[tuple[Estrato, ...], tuple[str, ...]]:
    """Camadas com parâmetros entre ``z_ini`` e ``z_fim`` (m abaixo da boca do furo)."""
    saida, avisos = [], []
    for c in furo.camadas:
        topo, base = max(c.topo, z_ini), min(c.base, z_fim)
        if base - topo <= 1e-6:
            continue
        if c.tipo == SEM_SOLO:
            avisos.append(f"{c.topo:.2f}–{c.base:.2f} m: '{c.descricao[:50]}' não tem tipo de solo e foi ignorada.")
            continue
        if c.nspt is None:
            avisos.append(f"{c.topo:.2f}–{c.base:.2f} m: sem NSPT — informe-o na tabela de camadas.")
            continue
        s = solos.sugerir(c.tipo, c.nspt, postura, nao_drenado)
        saida.append(Estrato(topo, base, c.tipo, c.nspt, s.gama, s.gama + GAMA_SAT_MAIS, s.phi,
                             0.0 if (sem_coesao and not nao_drenado) else s.c, s.delta, c.aterro))
        if c.aterro:
            avisos.append(f"{c.topo:.2f}–{c.base:.2f} m é ATERRO: correlações com NSPT são pouco confiáveis nele.")
    coberto = sum(e.espessura for e in saida)
    if z_fim - z_ini - coberto > 0.05:
        avisos.append(f"Só {coberto:.2f} m dos {z_fim - z_ini:.2f} m do trecho têm camada com parâmetros.")
    return tuple(saida), tuple(dict.fromkeys(avisos))


MEDIA, DESFAVORAVEL = "Média ponderada pela espessura", "Camada mais desfavorável"


def equivalente(est: tuple[Estrato, ...], criterio: str = MEDIA) -> Estrato | None:
    """Solo homogêneo equivalente a um conjunto de estratos."""
    if not est:
        return None
    h = sum(e.espessura for e in est)
    topo, base = est[0].topo, est[-1].base
    if criterio == DESFAVORAVEL:
        return Estrato(topo, base, min(est, key=lambda e: e.phi).tipo, min(e.nspt for e in est),
                       max(e.gama for e in est), max(e.gsat for e in est), min(e.phi for e in est),
                       min(e.c for e in est), min(e.delta for e in est), any(e.aterro for e in est))
    m = lambda f: sum(f(e) * e.espessura for e in est) / h   # noqa: E731
    phi = math.degrees(math.atan(m(lambda e: math.tan(math.radians(e.phi)))))
    return Estrato(topo, base, max(est, key=lambda e: e.espessura).tipo, m(lambda e: e.nspt), m(lambda e: e.gama),
                   m(lambda e: e.gsat), phi, m(lambda e: e.c), m(lambda e: e.delta), any(e.aterro for e in est))


# ------------------------------------------------------------ esforço lateral
@dataclass(frozen=True)
class EsforcoLateral:
    z: np.ndarray          # profundidade (m abaixo da boca do furo)
    sv: np.ndarray         # tensão vertical efetiva (kPa)
    ativo: np.ndarray      # pressão ativa de Rankine (kPa)
    repouso: np.ndarray    # pressão em repouso K0 (kPa)
    agua: np.ndarray       # pressão hidrostática (kPa)
    E_ativo: float         # resultantes (kN/m)
    E_repouso: float
    E_agua: float
    z_ativo: float         # altura da resultante acima do fundo (m)
    z_repouso: float
    z_agua: float


def esforco_lateral(est: tuple[Estrato, ...], z_ini: float, z_fim: float, q: float = 0.0,
                    na: float | None = None, gam_w: float = 10.0, n: int = 400) -> EsforcoLateral:
    """Diagrama de pressão lateral em paramento vertical, terreno horizontal, por camadas.

    Ativo: σa = Ka·σ'v − 2c·√Ka ≥ 0 (Rankine, Ka = tan²(45° − φ/2)); repouso:
    σ0 = (1 − sen φ)·σ'v (Jaky). Abaixo do NA usa γ' = γsat − γw e soma a água à parte.
    O terreno arrimado começa em ``z_ini`` (o solo acima foi removido) com a sobrecarga ``q``.
    """
    dz = (z_fim - z_ini) / n
    z = z_ini + (np.arange(n) + 0.5) * dz
    gama = np.zeros(n)
    ka, k0, c = np.zeros(n), np.zeros(n), np.zeros(n)
    for e in est:
        m = (z >= e.topo) & (z < e.base)
        sub = (z > na) if na is not None else np.zeros(n, bool)
        gama[m] = np.where(sub[m], e.gsat - gam_w, e.gama)
        phi = math.radians(e.phi)
        ka[m] = math.tan(math.pi / 4 - phi / 2) ** 2
        k0[m] = 1 - math.sin(phi)
        c[m] = e.c
    sem = gama == 0                      # trechos sem camada: usa a vizinha mais próxima
    if sem.any() and (~sem).any():
        idx = np.where(~sem)[0]
        prox = idx[np.abs(np.where(sem)[0][:, None] - idx[None, :]).argmin(axis=1)]
        for arr in (gama, ka, k0, c):
            arr[sem] = arr[prox]
    sv = q + np.cumsum(gama * dz) - gama * dz / 2
    ativo = np.maximum(0.0, ka * sv - 2 * c * np.sqrt(ka))
    repouso = k0 * sv
    agua = gam_w * np.maximum(0.0, z - na) if na is not None else np.zeros(n)

    def res(p):
        E = float(p.sum() * dz)
        return E, (float((p * (z_fim - z)).sum() * dz) / E if E > 0 else 0.0)
    (Ea, za), (E0, z0), (Ew, zw) = res(ativo), res(repouso), res(agua)
    return EsforcoLateral(z, sv, ativo, repouso, agua, Ea, E0, Ew, za, z0, zw)


# --------------------------------------------------------- do perfil para o muro
@dataclass(frozen=True)
class Proposta:
    """Dados do muro derivados do estudo de solo."""
    campos: dict                       # nome do campo da Entrada → valor
    arrimado: tuple[Estrato, ...]
    arrimado_eq: Estrato | None
    fundacao: tuple[Estrato, ...]
    fundacao_eq: Estrato | None
    por_camadas: EsforcoLateral | None
    homogeneo: EsforcoLateral | None
    avisos: tuple[str, ...]


def propor(furo: Furo, z_ini: float, z_fim: float, largura_base: float = 3.0, q: float = 0.0,
           postura: float = 0.0, criterio: str = MEDIA, sem_coesao: bool = True,
           fundacao_nao_drenada: bool = False, gam_w: float = 10.0) -> Proposta:
    """Monta os dados do muro para o trecho ``z_ini``–``z_fim`` do furo."""
    avisos: list[str] = []
    arr, av = estratos(furo, z_ini, z_fim, postura, sem_coesao)
    avisos += av
    z_inf = z_fim + max(1.0, 1.5 * largura_base)          # bulbo de tensões ~ 1,5·B
    fun, av = estratos(furo, z_fim, min(z_inf, max(furo.profundidade, z_fim + 0.1)), postura, False,
                       fundacao_nao_drenada)
    avisos += [a for a in av if a not in avisos]
    arr_eq, fun_eq = equivalente(arr, criterio), equivalente(fun, criterio)
    H = z_fim - z_ini
    campos: dict = {"H_muro": round(H, 2), "h_reb": 0.0}
    na = furo.na
    if arr_eq:
        phi = max(5.0, round(arr_eq.phi, 1))
        campos.update(gam_at=round(arr_eq.gama, 1), gsat_at=round(arr_eq.gsat, 1), phi_at=phi,
                      c_at=round(arr_eq.c, 1), delta_est=round(min(arr_eq.delta, phi), 1))
    else:
        avisos.append("Nenhuma camada com parâmetros no trecho do muro: o solo arrimado não foi alterado.")
    if fun_eq:
        campos.update(gam_f=round(fun_eq.gama, 1), gsat_f=round(fun_eq.gsat, 1), phi_f=round(fun_eq.phi, 1),
                      c_f=round(fun_eq.c, 1))
    else:
        avisos.append("Nenhuma camada com parâmetros abaixo do fundo da sapata: o solo de fundação não foi "
                      "alterado.")
    hw = 0.0 if na is None else max(0.0, min(H, z_fim - na))
    campos["hw_at"] = round(hw, 2)
    if hw > 0:
        avisos.append(f"NA a {na:.2f} m: {hw:.2f} m de água acima do fundo da sapata entram no cálculo. Com "
                      "drenagem eficiente atrás do muro, reduza esse valor na verificação.")
    elif na is not None and na - z_fim < 1.5 * largura_base:
        avisos.append(f"NA a {na:.2f} m, {na - z_fim:.2f} m abaixo do fundo da sapata: reduz a capacidade de "
                      "carga (não considerado automaticamente).")
    cam = esforco_lateral(arr, z_ini, z_fim, q, na, gam_w) if arr else None
    hom = esforco_lateral((arr_eq,), z_ini, z_fim, q, na, gam_w) if arr_eq else None
    if cam and hom and hom.E_ativo < 0.95 * cam.E_ativo:
        avisos.append(f"O solo homogêneo equivalente dá empuxo ativo {100 * (1 - hom.E_ativo / cam.E_ativo):.0f} % "
                      "menor que o perfil por camadas: prefira o critério 'Camada mais desfavorável'.")
    return Proposta(campos, arr, arr_eq, fun, fun_eq, cam, hom, tuple(avisos))
