@echo off
echo ============================================================
echo  StoryReplicator — Instalacao de dependencias
echo ============================================================

REM Verifica Python
python --version >nul 2>&1 || (echo [ERRO] Python nao encontrado. Instale python.org && pause && exit /b 1)

REM Cria venv
echo.
echo [1/4] Criando ambiente virtual...
python -m venv venv
call venv\Scripts\activate.bat

REM Upgrade pip
echo.
echo [2/4] Atualizando pip...
python -m pip install --upgrade pip

REM Instala dependencias
echo.
echo [3/4] Instalando dependencias Python...
pip install -r requirements.txt

REM Verifica FFmpeg
echo.
echo [4/4] Verificando FFmpeg...
ffmpeg -version >nul 2>&1 && (echo  [OK] FFmpeg encontrado) || (
    echo  [AVISO] FFmpeg nao encontrado no PATH
    echo  Baixe em: https://ffmpeg.org/download.html
    echo  Adicione ao PATH do sistema
)

echo.
echo ============================================================
echo  Instalacao concluida!
echo  Para usar: python main.py ^<URL_DO_YOUTUBE^>
echo ============================================================
pause
