@echo off
REM StoryReplicator — Atalho de execucao
REM Uso: run.bat <URL> [--skip-video]

if "%~1"=="" (
    echo Uso: run.bat ^<URL_YOUTUBE^> [--skip-video]
    echo Exemplo: run.bat https://youtube.com/watch?v=xxxxx
    pause
    exit /b 1
)

call venv\Scripts\activate.bat 2>nul || echo [AVISO] venv nao encontrado, usando Python global

set ANTHROPIC_API_KEY=%ANTHROPIC_API_KEY%

if "%ANTHROPIC_API_KEY%"=="" (
    echo [ERRO] ANTHROPIC_API_KEY nao definida
    echo Defina com: set ANTHROPIC_API_KEY=sua_chave
    pause
    exit /b 1
)

python main.py %*
pause
