"""Leitura de relatório de sondagem SPT em PDF (com camada de texto).

Os boletins não têm formato padronizado; o leitor usa só o que eles têm em comum:

* ensaio SPT: três contagens de golpes seguidas de duas somas, com
  ``1ª+2ª = g1+g2`` e ``2ª+3ª = g2+g3`` — a aritmética identifica a linha;
* descrições das camadas alinhadas numa mesma coluna, começando por um nome de solo;
* profundidades de mudança de camada (``0,40`` ``2,85`` …) logo à esquerda das descrições;
* leituras do nível d'água acompanhadas de "N.A." ou "nível d'água".

PDF escaneado (só imagem) não tem texto para ler. O resultado é sempre revisável
pelo usuário na tabela de camadas.
"""
from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass

import pymupdf

from core.perfil import Camada, Furo, _sem_acento, completar

_ID = re.compile(r"\b(S[PMTR]|SPT|ST|F)\s?[-–.]?\s?0*(\d{1,3})\b")
_SOLO = re.compile(r"^(argila|areia|silte|aterro|pedregulho|solo|camada|entulho|turfa|cascalho|rocha|concre|"
                   r"alteracao|saprolito|materia|matac|bloco|gnaisse|granito|piso|asfalto)", re.I)
_PROF = re.compile(r"^\d{1,2},\d{2}$")
_INT = re.compile(r"^(\d{1,3})(?:/\d{1,3})?$")
_CONECTIVO = {"de", "e", "a", "cor", "cores", "com", "pouco", "muito", "da", "do"}


@dataclass
class _Palavra:
    x0: float
    y: float
    x1: float
    t: str
    linha: tuple[int, int]


def _palavras(pagina) -> list[_Palavra]:
    vistas, saida = set(), []
    for x0, y0, x1, y1, t, bloco, linha, _ in pagina.get_text("words"):
        chave = (t, round(x0), round(y0))
        if chave in vistas:                      # texto duplicado sobreposto
            continue
        vistas.add(chave)
        saida.append(_Palavra(x0, (y0 + y1) / 2, x1, t, (bloco, linha)))
    return saida


def _linhas(palavras: list[_Palavra]) -> list[tuple[float, float, str, int]]:
    """Linhas de texto do PDF: (x0, y, texto, bloco), sem duplicatas."""
    grupos = defaultdict(list)
    for p in palavras:
        grupos[p.linha].append(p)
    vistas, saida = set(), []
    for ps in grupos.values():
        ps.sort(key=lambda p: p.x0)
        txt = " ".join(p.t for p in ps)
        chave = (txt, round(ps[0].x0), round(ps[0].y))
        if chave not in vistas:
            vistas.add(chave)
            saida.append((ps[0].x0, ps[0].y, txt, ps[0].linha[0]))
    return saida


# ------------------------------------------------------------------------- SPT
def _linhas_spt(palavras: list[_Palavra]) -> list[tuple[float, int, float | None]]:
    """Linhas de ensaio: (y, NSPT, profundidade rotulada ou None)."""
    ints = [(p, int(_INT.match(p.t).group(1))) for p in palavras if _INT.match(p.t)]
    ints.sort(key=lambda a: (a[0].y, a[0].x0))
    achadas = []
    for i, (a, g1) in enumerate(ints):
        mesma = [(p, v) for p, v in ints if abs(p.y - a.y) < 1.5 and p.x0 > a.x0]
        mesma.sort(key=lambda b: b[0].x0)
        if len(mesma) < 2:
            continue
        (b, g2), (c, g3) = mesma[0], mesma[1]
        if not (5 < b.x0 - a.x0 < 32 and 5 < c.x0 - b.x0 < 32):
            continue
        somas = [(p, v) for p, v in ints if c.x0 < p.x0 < c.x0 + 75 and abs(p.y - a.y) < 6 and p is not c]
        somas.sort(key=lambda b: b[0].x0)
        par = None
        for j in range(len(somas) - 1):
            if somas[j][1] == g1 + g2 and somas[j + 1][1] == g2 + g3 and abs(somas[j][0].y - somas[j + 1][0].y) < 6:
                par = (somas[j][0], somas[j + 1][0])
                break
        if par is None:
            continue
        rotulo = None
        for p in palavras:                       # "7,00" à esquerda da linha
            if abs(p.y - a.y) < 2 and p.x0 < a.x0 and re.fullmatch(r"\d{1,2},00", p.t):
                rotulo = float(p.t.replace(",", "."))
        if rotulo is None:                       # inteiro isolado à direita (eixo do gráfico)
            dir_ = [(p.x0, v) for p, v in ints if abs(p.y - a.y) < 2 and p.x0 > par[1].x0 + 40]
            if dir_:
                rotulo = float(min(dir_)[1])
        achadas.append((a.y, g2 + g3, rotulo))
    achadas.sort()
    unicas: list[tuple[float, int, float | None]] = []
    for r in achadas:
        if not unicas or r[0] - unicas[-1][0] > 10:
            unicas.append(r)
    return unicas


def _profundidades(linhas, ultima: float) -> list[tuple[float, float, int]]:
    """Atribui a profundidade de cada ensaio: (profundidade, y, NSPT)."""
    if not linhas:
        return []
    ys = [r[0] for r in linhas]
    passos = [b - a for a, b in zip(ys, ys[1:]) if 15 < b - a < 60]
    ppm = statistics.median(passos) if passos else 28.35            # pontos por metro (1:100)
    rel = [round((y - ys[0]) / ppm) for y in ys]
    votos = Counter(int(r[2]) - k for r, k in zip(linhas, rel) if r[2] is not None)
    d0 = votos.most_common(1)[0][0] if votos else int(ultima) + 1
    return [(float(d0 + k), y, r[1]) for (y, r), k in zip(zip(ys, linhas), rel)]


# -------------------------------------------------------------------- camadas
def _descricoes(linhas, x_desc: float, y_min: float, y_max: float) -> list[tuple[float, float, str]]:
    """Parágrafos da coluna de descrição dentro do corpo do boletim: (y inicial, y final, texto).

    Cada bloco de texto do PDF é tratado à parte (alguns boletins trazem a mesma
    descrição duas vezes, em posições ligeiramente diferentes).
    """
    col = [(b, y, t) for x, y, t, b in linhas if abs(x - x_desc) < 3.5]
    ys = sorted(y for _, y, _ in col)
    passos = [b - a for a, b in zip(ys, ys[1:]) if 4 < b - a < 14]
    passo = statistics.median(passos) if passos else 9.0
    paragrafos: list[list] = []
    for bloco in sorted({b for b, _, _ in col}):
        ant = None
        for y, t in sorted((y, t) for b, y, t in col if b == bloco):
            nova = ant is None
            if ant is not None:
                fim = ant[2].rstrip()
                ult = _sem_acento(fim.split()[-1]) if fim.split() else ""
                nova = (y - ant[1] > 1.35 * passo or fim.endswith(".")
                        or (bool(_SOLO.match(_sem_acento(t))) and not fim.endswith((",", "-"))
                            and ult not in _CONECTIVO))
            if nova:
                ant = [y, y, t]
                paragrafos.append(ant)
            else:
                ant[1] = y
                ant[2] += " " + t
    saida: list[tuple[float, float, str]] = []
    for a, b, t in sorted(paragrafos):
        t = " ".join(t.split())
        s = _sem_acento(t)
        if not (y_min <= a <= y_max) or not (_SOLO.match(s) or s.startswith("limite")):
            continue
        copia = False
        for k, (a2, b2, u) in enumerate(saida):                  # cópia sobreposta (inteira ou truncada)
            v = _sem_acento(u)
            if abs(a - a2) < 45 and (v.startswith(s) or s.startswith(v)):
                if len(s) > len(v):
                    saida[k] = (a2, max(b, b2), t)
                copia = True
                break
        if not copia:
            saida.append((a, b, t))
    return saida


def _coluna_das_descricoes(linhas) -> float | None:
    xs = Counter(round(x) for x, _, t, _ in linhas if _SOLO.match(_sem_acento(t)) and len(t) > 8)
    return float(xs.most_common(1)[0][0]) if xs else None


def _nivel_dagua(palavras: list[_Palavra], linhas, y_corpo: float) -> tuple[float | None, bool]:
    """(profundidade do NA mais raso, True se o boletim fala em NA)."""
    leituras, citado = [], False
    for x, y, t, _ in linhas:
        s = _sem_acento(t)
        if "n.a" in s or "nivel d" in s or "nivel de agua" in s:
            citado = True
        for m in re.finditer(r"(\d{1,2},\d{1,2})\s?m\b", t):         # "8,22m em 05/12/2024"
            if re.search(r"\d\)\s*$", t[:m.start()]) or "em " in t[m.end():m.end() + 5]:
                leituras.append(float(m.group(1).replace(",", ".")))
    for p in palavras:                                               # "inicial: 17,70 m" no cabeçalho
        if _sem_acento(p.t) in ("inicial:", "final:") and p.y < y_corpo:
            dir_ = sorted((q.x0, q.t) for q in palavras if abs(q.y - p.y) < 2 and q.x0 > p.x0)
            if dir_ and re.fullmatch(r"\d{1,2},\d{1,2}", dir_[0][1]):
                leituras.append(float(dir_[0][1].replace(",", ".")))
    return (min(leituras) if leituras else None), citado


# --------------------------------------------------------------------- páginas
@dataclass
class _Pagina:
    numero: int
    furo: str
    spt: list            # (y, NSPT, rótulo)
    rotulos: list        # profundidades de mudança de camada
    descr: list          # (y0, y1, texto)
    aterro: list         # (y, profundidade rotulada na mesma linha ou None)
    na: float | None
    cota: float | None
    fim: float | None    # "LIMITE DE SONDAGEM: 35,45 m"


def _ler_pagina(pagina, numero: int) -> _Pagina | None:
    palavras = _palavras(pagina)
    if not palavras:
        return None
    linhas = _linhas(palavras)
    spt = _linhas_spt(palavras)
    x_desc = _coluna_das_descricoes(linhas)
    if len(spt) < 2 and x_desc is None:
        return None
    topo = " ".join(t for _, y, t, _ in sorted(linhas, key=lambda a: (a[1], a[0])) if y < 130)
    m = _ID.search(topo)
    if not m and len(spt) < 2:
        return None
    furo = f"{m.group(1)}-{int(m.group(2)):02d}" if m else "Furo"
    rotulos, descr, aterro, fim = [], [], [], None
    if x_desc is not None:
        rot = [p for p in palavras if _PROF.match(p.t) and x_desc - 48 <= p.x0 <= x_desc - 6]
        ancoras = [p.y for p in rot] + [r[0] for r in spt]
        if ancoras:
            ya, yb = min(ancoras) - 15, max(ancoras) + 25
            for y0, y1, t in _descricoes(linhas, x_desc, ya, yb):
                if _sem_acento(t).startswith("limite"):
                    mm = re.search(r"(\d{1,2},\d{2})", t)
                    fim = float(mm.group(1).replace(",", ".")) if mm else fim
                else:
                    descr.append((y0, y1, t))
            rotulos = sorted({float(p.t.replace(",", ".")) for p in rot if ya <= p.y <= yb + 10})
            largura = max((p.x1 for p in palavras if x_desc - 3 <= p.x0 and ya <= p.y <= yb
                           and p.linha[0] in {q.linha[0] for q in palavras if abs(q.x0 - x_desc) < 3.5}),
                          default=x_desc + 150)
            for p in palavras:
                if p.t == "AT" and ya <= p.y <= yb and (x_desc - 110 <= p.x0 < x_desc
                                                         or largura - 20 <= p.x0 <= largura + 45):
                    junto = [float(q.t.replace(",", ".")) for q in rot if abs(q.y - p.y) < 3]
                    aterro.append((p.y, junto[0] if junto else None))
    y_corpo = min([r[0] for r in spt] + [d[0] for d in descr] + [1e9])
    na, _ = _nivel_dagua(palavras, linhas, y_corpo)
    texto = " ".join(t for _, _, t, _ in linhas)
    mc = re.search(r"[Cc]ota[^:\d]{0,25}:\s*(\d{1,4}[.,]\d{1,3})\s*m", texto)
    cota = float(mc.group(1).replace(",", ".")) if mc else None
    return _Pagina(numero, furo, spt, rotulos, descr, aterro, na, cota, fim)


def _montar(nome: str, paginas: list[_Pagina]) -> Furo:
    avisos: list[str] = []
    # ---- SPT
    spt: list[tuple[float, int]] = []
    for pg in paginas:
        for prof, _, n in _profundidades(pg.spt, spt[-1][0] if spt else 0.0):
            if not spt or prof > spt[-1][0]:
                spt.append((prof, n))
    if spt and [p for p, _ in spt] != [spt[0][0] + i for i in range(len(spt))]:
        avisos.append("Há metros sem NSPT lido (ensaio com penetração parcial, impenetrável ou trecho em rocha).")
    # ---- camadas
    todos = sorted({r for pg in paginas for r in pg.rotulos})
    por_topo = bool(todos) and todos[0] < 0.005
    descr: list[tuple[str, bool]] = []
    limites = set(todos)
    at_rotulo = {r for pg in paginas for _, r in pg.aterro if r is not None}
    for i, pg in enumerate(paginas):
        soltos = [y for y, r in pg.aterro if r is None]
        itens = [(t, any(y0 - 8 <= ya <= y1 + 8 for ya in soltos)) for y0, y1, t in pg.descr]
        if i > 0 and itens and descr and _sem_acento(itens[0][0])[:40] == _sem_acento(descr[-1][0])[:40]:
            itens = itens[1:]                              # continuação da camada da folha anterior
            ant = paginas[i - 1].rotulos
            if not por_topo and ant:
                limites.discard(max(ant))                  # quebra de folha, não de camada
        descr += itens
    fim = max([pg.fim for pg in paginas if pg.fim] + ([spt[-1][0] + 0.45] if spt else []) + sorted(limites)[-1:]
              + [0.0])
    limites |= {0.0, fim}
    lim = sorted(limites)
    intervalos = list(zip(lim, lim[1:]))
    if len(descr) != len(intervalos):
        avisos.append(f"Foram lidas {len(descr)} descrições para {len(intervalos)} intervalos de profundidade: "
                      "confira topo e base de cada camada na tabela.")
    camadas = []
    for k, (t, at) in enumerate(descr):
        if k < len(intervalos):
            a, b = intervalos[k]
        else:
            a = b = intervalos[-1][1] if intervalos else 0.0
        camadas.append(Camada(a, b, t, aterro=at or (a if por_topo else b) in at_rotulo))
    if len(intervalos) > len(descr) and camadas:           # sobra de intervalos: estende a última camada
        ult = camadas[-1]
        camadas[-1] = Camada(ult.topo, intervalos[-1][1], ult.descricao, aterro=ult.aterro)
    nas = [pg.na for pg in paginas if pg.na is not None]
    cotas = [pg.cota for pg in paginas if pg.cota is not None]
    if not nas:
        avisos.append("Nível d'água não identificado no boletim: confira e informe-o se existir.")
    if not spt:
        avisos.append("Nenhum ensaio SPT reconhecido: informe o NSPT de cada camada na tabela.")
    return completar(Furo(nome, tuple(camadas), tuple(spt), min(nas) if nas else None,
                          cotas[0] if cotas else None, tuple(avisos)))


@dataclass
class Leitura:
    furos: list[Furo]
    avisos: list[str]
    paginas: int


def ler_pdf(dados: bytes) -> Leitura:
    """Lê os boletins de sondagem de um relatório em PDF."""
    try:
        doc = pymupdf.open(stream=dados, filetype="pdf")
    except Exception as ex:
        raise ValueError(f"Não foi possível abrir o PDF: {ex}") from ex
    por_furo: dict[str, list[_Pagina]] = defaultdict(list)
    com_texto = 0
    for i, pagina in enumerate(doc):
        if len(pagina.get_text().strip()) > 40:
            com_texto += 1
        pg = _ler_pagina(pagina, i + 1)
        if pg is not None and (len(pg.spt) >= 2 or (pg.descr and pg.rotulos)):
            por_furo[pg.furo].append(pg)
    avisos = []
    if com_texto == 0:
        avisos.append("O PDF não tem texto (parece escaneado): não é possível ler os boletins automaticamente. "
                      "Preencha o perfil manualmente.")
    elif not por_furo:
        avisos.append("Nenhum boletim de sondagem SPT foi reconhecido neste PDF. Preencha o perfil manualmente.")
    furos = [_montar(nome, pgs) for nome, pgs in por_furo.items()]
    return Leitura(furos, avisos, len(doc))
