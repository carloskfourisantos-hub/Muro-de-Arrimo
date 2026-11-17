# -*- mode: python ; coding: utf-8 -*-
"""Receita do PyInstaller para a versão desktop. Gerar com desktop/gerar_executavel.bat."""
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

RAIZ = Path(SPECPATH).parent

datas = [(str(RAIZ / "app.py"), "."), (str(RAIZ / ".streamlit"), ".streamlit")]
for pasta in ("paginas", "core", "ui", "io_"):
    datas.append((str(RAIZ / pasta), pasta))
binaries, hiddenimports = [], []
# o Streamlit carrega as páginas como scripts: o PyInstaller não enxerga o que elas importam
for pacote in ("streamlit", "matplotlib", "pandas", "numpy", "pydantic", "pydantic_core", "openpyxl",
               "reportlab", "pymupdf", "fitz", "altair", "pyarrow"):
    try:
        d, b, h = collect_all(pacote)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass
for pacote in ("streamlit", "pydantic", "numpy", "pandas"):
    datas += copy_metadata(pacote, recursive=True)
hiddenimports += collect_submodules("webview") if __import__("importlib").util.find_spec("webview") else []

a = Analysis(
    [str(RAIZ / "desktop" / "muro_desktop.py")],
    pathex=[str(RAIZ)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["pytest", "hypothesis", "tests"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="MuroDeArrimo",
    console=False,            # sem janela de terminal
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="MuroDeArrimo", upx=False)
