@echo off
rem Abre o aplicativo numa janela propria. Na primeira vez cria o ambiente e instala as dependencias.
cd /d "%~dp0\.."
if not exist .venv\Scripts\python.exe (
  echo Preparando o ambiente pela primeira vez. Isso leva alguns minutos...
  python -m venv .venv || goto :erro
  .venv\Scripts\python -m pip install -r requirements.txt pywebview || goto :erro
)
start "" .venv\Scripts\pythonw.exe desktop\muro_desktop.py
exit /b 0
:erro
echo.
echo Nao foi possivel preparar o ambiente. Confira se o Python esta instalado e no PATH.
pause
