@echo off
rem Gera o executavel em dist\MuroDeArrimo\MuroDeArrimo.exe (rodar no Windows).
cd /d "%~dp0\.."
if not exist .venv\Scripts\python.exe python -m venv .venv || goto :erro
.venv\Scripts\python -m pip install -r requirements.txt -r desktop\requirements-desktop.txt || goto :erro
.venv\Scripts\python -m PyInstaller --noconfirm --clean desktop\muro_desktop.spec || goto :erro
echo.
echo Pronto: dist\MuroDeArrimo\MuroDeArrimo.exe
echo Para levar a outro computador, copie a pasta dist\MuroDeArrimo inteira.
pause
exit /b 0
:erro
echo.
echo A geracao falhou. Veja a mensagem acima.
pause
