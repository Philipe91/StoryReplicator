@echo off
echo ============================================================
echo  StoryReplicator v3.5 — Instalando dependencias Remotion
echo ============================================================
echo.

node --version >nul 2>&1 || (echo [ERRO] Node.js nao encontrado. Instale em nodejs.org && pause && exit /b 1)

echo [1/2] Instalando pacotes npm (pode demorar 1-2 minutos)...
npm install

if %errorlevel% neq 0 (
    echo [ERRO] npm install falhou.
    pause
    exit /b 1
)

echo.
echo [2/2] Verificando instalacao...
npx remotion --version

echo.
echo ============================================================
echo  Remotion instalado com sucesso!
echo  Use: python main.py ^<URL^> --renderer remotion
echo ============================================================
pause
