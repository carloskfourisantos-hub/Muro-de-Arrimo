"""Monta o aplicativo Android/PWA em ``android/www`` (pasta pronta para publicar ou empacotar).

    cd android
    npm install            # baixa o Pyodide (Python em WebAssembly)
    python montar.py       # copia a interface, empacota o núcleo e baixa numpy e pydantic

O que entra em ``www``:
  * a interface (``src/``);
  * ``programa.zip`` — ``core/`` e ``ponte.py``, o mesmo código do aplicativo de computador;
  * ``pyodide/`` — o interpretador Python e os pacotes numpy e pydantic para WebAssembly;
  * ícones e a lista de arquivos guardados no aparelho para uso sem internet (``sw.js``).
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
SRC, WWW = AQUI / "src", AQUI / "www"
PYODIDE = AQUI / "node_modules" / "pyodide"
PACOTES = ("numpy", "pydantic")
NUCLEO = ("pyodide.mjs", "pyodide.asm.mjs", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json")
CACHE = AQUI / ".cache"       # rodas já baixadas (não vai para o repositório)


def _dependencias(trava: dict) -> dict[str, str]:
    pacotes, vistos = trava["packages"], {}

    def visita(nome: str) -> None:
        n = nome.lower().replace("_", "-")
        if n in vistos or n not in pacotes:
            return
        vistos[n] = pacotes[n]["file_name"]
        for d in pacotes[n].get("depends", []):
            visita(d)
    for p in PACOTES:
        visita(p)
    return vistos


def _icone(tamanho: int, destino: Path) -> None:
    """Ícone desenhado com o matplotlib: perfil do muro sobre fundo azul."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon

    fig = plt.figure(figsize=(1, 1), dpi=tamanho)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    fig.patch.set_facecolor("#1f5fae")
    ax.add_patch(Polygon([(5.3, 3.2), (8.2, 3.2), (8.2, 7.4), (5.3, 7.4)], color="#d9c7a0"))          # aterro
    ax.add_patch(Polygon([(2.2, 2.2), (8.2, 2.2), (8.2, 3.2), (5.3, 3.2), (5.0, 7.8), (4.3, 7.8), (4.0, 3.2),
                          (2.2, 3.2)], color="#ffffff"))                                             # muro
    fig.savefig(destino, facecolor=fig.get_facecolor())
    plt.close(fig)


def icones_android(res: Path) -> None:
    """Troca o ícone padrão do Capacitor pelo do aplicativo (rodar depois de ``npx cap add android``)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon

    def desenho(tamanho: int, destino: Path, margem: float, fundo: bool) -> None:
        fig = plt.figure(figsize=(1, 1), dpi=tamanho)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(-margem, 10 + margem)        # margem > 0 encolhe o desenho (zona segura do ícone adaptável)
        ax.set_ylim(-margem, 10 + margem)
        ax.axis("off")
        ax.add_patch(Polygon([(5.3, 3.2), (8.2, 3.2), (8.2, 7.4), (5.3, 7.4)], color="#d9c7a0"))
        ax.add_patch(Polygon([(2.2, 2.2), (8.2, 2.2), (8.2, 3.2), (5.3, 3.2), (5.0, 7.8), (4.3, 7.8), (4.0, 3.2),
                              (2.2, 3.2)], color="#ffffff"))
        fig.savefig(destino, facecolor="#1f5fae" if fundo else "none", transparent=not fundo)
        plt.close(fig)

    for dens, lado in (("mdpi", 48), ("hdpi", 72), ("xhdpi", 96), ("xxhdpi", 144), ("xxxhdpi", 192)):
        pasta = res / f"mipmap-{dens}"
        pasta.mkdir(parents=True, exist_ok=True)
        desenho(lado, pasta / "ic_launcher.png", 0.0, True)
        desenho(lado, pasta / "ic_launcher_round.png", 1.2, True)
        desenho(round(lado * 108 / 48), pasta / "ic_launcher_foreground.png", 4.0, False)
    (res / "values").mkdir(parents=True, exist_ok=True)
    (res / "values" / "ic_launcher_background.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n    <color name="ic_launcher_background">#1F5FAE</color>\n'
        "</resources>\n", encoding="utf-8")
    print(f"ícones gravados em {res}")


def montar() -> Path:
    if not (PYODIDE / "pyodide.mjs").exists():
        sys.exit("Falta o Pyodide: rode 'npm install' dentro da pasta android antes de montar.")
    versao_pyodide = json.loads((PYODIDE / "package.json").read_text(encoding="utf-8"))["version"]
    trava = json.loads((PYODIDE / "pyodide-lock.json").read_text(encoding="utf-8"))
    if WWW.exists():
        shutil.rmtree(WWW)
    shutil.copytree(SRC, WWW)
    (WWW / "pyodide").mkdir()
    for nome in NUCLEO:
        shutil.copy2(PYODIDE / nome, WWW / "pyodide" / nome)

    CACHE.mkdir(exist_ok=True)
    base = f"https://cdn.jsdelivr.net/pyodide/v{versao_pyodide}/full/"
    for pacote, arquivo in _dependencias(trava).items():
        guardado = CACHE / arquivo
        if not guardado.exists():
            print(f"baixando {arquivo}")
            with urllib.request.urlopen(base + arquivo, timeout=120) as r:
                dados = r.read()
            esperado = trava["packages"][pacote]["sha256"]
            if hashlib.sha256(dados).hexdigest() != esperado:
                sys.exit(f"{arquivo}: o arquivo baixado não confere com o esperado (sha256).")
            guardado.write_bytes(dados)
        shutil.copy2(guardado, WWW / "pyodide" / arquivo)

    # o programa: o mesmo núcleo do aplicativo de computador + a ponte
    with zipfile.ZipFile(WWW / "programa.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.write(AQUI / "ponte.py", "ponte.py")
        for f in sorted((RAIZ / "core").glob("*.py")):
            z.write(f, f"core/{f.name}")

    _icone(192, WWW / "icone-192.png")
    _icone(512, WWW / "icone-512.png")

    arquivos = sorted(p.relative_to(WWW).as_posix() for p in WWW.rglob("*") if p.is_file() and p.name != "sw.js")
    resumo = hashlib.sha256()
    for a in arquivos:
        if a not in ("app.js",):                       # app.js recebe a versão abaixo
            resumo.update((WWW / a).read_bytes())
    resumo.update((SRC / "app.js").read_bytes())
    versao = f"{date.today():%Y.%m.%d}-{resumo.hexdigest()[:7]}"
    app = WWW / "app.js"
    app.write_text(app.read_text(encoding="utf-8").replace("__VERSAO__", versao), encoding="utf-8")
    sw = WWW / "sw.js"
    sw.write_text(sw.read_text(encoding="utf-8").replace("__VERSAO__", versao)
                  .replace("__ARQUIVOS__", json.dumps(["./"] + arquivos, ensure_ascii=False)), encoding="utf-8")
    tamanho = sum(p.stat().st_size for p in WWW.rglob("*") if p.is_file()) / 1e6
    print(f"pronto: {WWW} — versão {versao}, {len(arquivos) + 1} arquivos, {tamanho:.1f} MB")
    return WWW


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--icones":
        icones_android(Path(sys.argv[2]))
    else:
        montar()
