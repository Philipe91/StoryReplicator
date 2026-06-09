@echo off
echo ============================================================
echo  StoryReplicator — Instalacao de dependencias
echo ============================================================

REM Verifica Python
python --version >nul 2>&1 || (echo [ERRO] Python nao encontrado. Instale python.org && pause && exit /b 1)

REM Cria venv
echo.
echo [1/5] Criando ambiente virtual...
python -m venv venv
call venv\Scripts\activate.bat

REM Upgrade pip
echo.
echo [2/5] Atualizando pip...
python -m pip install --upgrade pip

REM Instala dependencias
echo.
echo [3/5] Instalando dependencias Python...
pip install anthropic yt-dlp youtube-transcript-api edge-tts numpy soundfile

REM Tenta instalar Kokoro TTS
echo.
echo [4/5] Instalando Kokoro TTS...
pip install kokoro-onnx 2>nul || echo  [AVISO] kokoro-onnx nao disponivel, usando edge-tts como fallback

REM Verifica FFmpeg
echo.
echo [5/5] Verificando FFmpeg...
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
