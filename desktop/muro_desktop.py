"""Muro de arrimo — versão para desktop.

Abre o aplicativo numa janela própria, sem terminal e sem digitar comandos: o servidor do
Streamlit roda escondido neste computador (só em 127.0.0.1) e a janela mostra a interface.
É o MESMO aplicativo (mesmo núcleo de cálculo e mesmas páginas); não há segunda versão do código.

Uso:
    python desktop/muro_desktop.py              janela própria (pywebview) ou, sem ela, o navegador
    python desktop/muro_desktop.py --navegador  força abrir no navegador padrão
    python desktop/muro_desktop.py --teste      sobe o servidor, confere a resposta e encerra

Como executável (.exe) é gerado por desktop/gerar_executavel.bat (PyInstaller).
"""
from __future__ import annotations

import multiprocessing
import socket
import sys
import time
import urllib.request
from pathlib import Path

TITULO = "Muro de arrimo — NBR 11682 / NBR 6118"
CONGELADO = getattr(sys, "frozen", False)
# no executável os arquivos do aplicativo ficam na pasta de dados do PyInstaller
RAIZ = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _servidor(porta: int) -> None:
    """Processo filho: roda o Streamlit (precisa da thread principal do próprio processo)."""
    import os

    os.chdir(RAIZ)
    sys.path.insert(0, str(RAIZ))
    from streamlit.web import bootstrap

    opcoes = {
        "server.port": porta, "server.address": "127.0.0.1", "server.headless": True,
        "server.fileWatcherType": "none", "browser.gatherUsageStats": False,
        "global.developmentMode": False, "client.toolbarMode": "minimal",
    }
    bootstrap.load_config_options(flag_options=opcoes)
    bootstrap.run(str(RAIZ / "app.py"), False, [], opcoes)


def _esperar(url: str, proc: multiprocessing.Process, limite: float = 90.0) -> bool:
    fim = time.time() + limite
    while time.time() < fim:
        if not proc.is_alive():
            return False
        try:
            with urllib.request.urlopen(url + "/_stcore/health", timeout=2) as r:
                if r.status == 200:
                    return True
        except OSError:
            time.sleep(0.4)
    return False


def _aviso(texto: str) -> None:
    """Mensagem de erro visível mesmo sem terminal (executável sem console)."""
    try:
        import tkinter
        from tkinter import messagebox

        raiz = tkinter.Tk()
        raiz.withdraw()
        messagebox.showerror(TITULO, texto)
        raiz.destroy()
    except Exception:       # sem tkinter ou sem tela: vai para o terminal
        print(texto, file=sys.stderr)


def main(args: list[str]) -> int:
    porta = _porta_livre()
    url = f"http://127.0.0.1:{porta}"
    proc = multiprocessing.Process(target=_servidor, args=(porta,), daemon=True)
    proc.start()
    try:
        if not _esperar(url, proc):
            _aviso("O aplicativo não conseguiu iniciar. Feche outras cópias abertas e tente de novo.")
            return 1
        if "--teste" in args:
            with urllib.request.urlopen(url, timeout=10) as r:
                print(f"servidor OK em {url} (HTTP {r.status})")
            return 0
        janela = None
        if "--navegador" not in args:
            try:
                import webview            # pywebview: janela nativa (WebView2 no Windows)

                janela = webview
            except ImportError:
                janela = None
        if janela is not None:
            janela.create_window(TITULO, url, width=1400, height=900, min_size=(900, 600))
            janela.start()                # bloqueia até a janela ser fechada
        else:
            import webbrowser

            webbrowser.open(url)
            print(f"{TITULO}\nAberto no navegador: {url}\nFeche esta janela (ou Ctrl+C) para encerrar.")
            while proc.is_alive():
                time.sleep(1)
        return 0
    except KeyboardInterrupt:
        return 0
    finally:
        if proc.is_alive():
            proc.terminate()
            proc.join(5)


if __name__ == "__main__":
    multiprocessing.freeze_support()      # obrigatório no executável do Windows
    sys.exit(main(sys.argv[1:]))
