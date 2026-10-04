@echo off
setlocal EnableDelayedExpansion

:: ── Configuração do terminal ──────────────────────────────────────
:: Codepage UTF-8 para suportar emojis e acentos corretamente
chcp 65001 >nul 2>nul

:: Tamanho da janela: 140 colunas x 40 linhas, buffer de 140x9999
mode con: cols=140 lines=40
powershell -NoProfile -Command "$h = (Get-Host).UI.RawUI; $b = $h.BufferSize; $b.Width = 140; $b.Height = 9999; $h.BufferSize = $b" >nul 2>nul

:: Habilitar Virtual Terminal Processing (cores ANSI no CMD)
reg add HKCU\Console /v VirtualTerminalLevel /t REG_DWORD /d 1 /f >nul 2>nul

:: Título da janela
title Agente Pessoal

:: ── Iniciar o agente ──────────────────────────────────────────────
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" app.py
) else (
    echo.
    echo   Ambiente virtual nao encontrado em .venv.
    echo   Execute este arquivo a partir da pasta agente_pessoal.
    pause
    exit /b 1
)

if errorlevel 1 (
    echo.
    echo   O agente foi encerrado com erro. Veja a mensagem acima.
    pause
)
endlocal
