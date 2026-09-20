@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" app.py
) else (
    echo Ambiente virtual nao encontrado em .venv.
    echo Execute este arquivo a partir da pasta agente_pessoal.
    pause
    exit /b 1
)

if errorlevel 1 (
    echo.
    echo O agente foi encerrado com erro. Veja a mensagem acima.
    pause
)
endlocal
