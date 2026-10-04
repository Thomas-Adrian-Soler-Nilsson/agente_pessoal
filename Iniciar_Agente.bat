@echo off
setlocal EnableDelayedExpansion

rem --- Configuracao do terminal ---
rem Codepage UTF-8 para o Python imprimir emojis e acentos corretamente.
rem ATENCAO: este arquivo e mantido 100 por cento em ASCII de proposito.
rem O cmd.exe perde o alinhamento de leitura do proprio .bat depois de um
rem "chcp 65001" quando o arquivo tem caracteres multibyte (barras de
rem desenho, acentos), e passa a executar pedacos das linhas, gerando
rem "nao e reconhecido como um comando interno ou externo".
chcp 65001 >nul 2>nul

rem Tamanho da janela: 140 colunas x 40 linhas, buffer de 140x9999
mode con: cols=140 lines=40
powershell -NoProfile -Command "$h = (Get-Host).UI.RawUI; $b = $h.BufferSize; $b.Width = 140; $b.Height = 9999; $h.BufferSize = $b" >nul 2>nul

rem Habilitar Virtual Terminal Processing (cores ANSI no CMD)
reg add HKCU\Console /v VirtualTerminalLevel /t REG_DWORD /d 1 /f >nul 2>nul

rem Titulo da janela
title Agente Pessoal

rem --- Iniciar o agente ---
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
