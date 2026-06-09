"""
StoryReplicator v3.5 — Remotion Bridge

Conecta o pipeline Python ao renderizador Remotion (Node.js/React).

Responsabilidades:
1. Verifica se Node.js e o projeto Remotion estão disponíveis
2. Copia todos os assets (imagens, áudio, JSONs) para remotion_renderer/public/
3. Invoca `npx remotion render` com os parâmetros corretos
4. Move final_video_remotion.mp4 para a pasta de saída
5. Fallback automático para FFmpeg se Remotion falhar
"""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path


REMOTION_DIR = Path(__file__).parent.parent / "remotion_renderer"


def _npx() -> str:
    """Resolve o executável npx (npx.cmd no Windows)."""
    return shutil.which("npx") or shutil.which("npx.cmd") or "npx"


def _npm() -> str:
    return shutil.which("npm") or shutil.which("npm.cmd") or "npm"


# ─── Verificação de disponibilidade ───────────────────────────────────────────

def is_available() -> bool:
    """Verifica se Node.js e o projeto Remotion estão prontos para uso."""
    if not shutil.which("node") and not shutil.which("node.exe"):
        return False
    if not REMOTION_DIR.exists():
        return False
    if not (REMOTION_DIR / "package.json").exists():
        return False
    if not (REMOTION_DIR / "node_modules").exists():
        print("[remotion] node_modules não encontrado — rode: install.bat em remotion_renderer/")
        return False
    return True


def install(verbose: bool = True) -> bool:
    """Instala dependências do projeto Remotion (npm install)."""
    if not REMOTION_DIR.exists():
        print(f"[remotion] Diretório não encontrado: {REMOTION_DIR}")
        return False
    print("[remotion] Instalando dependências npm...")
    r = subprocess.run(
        [_npm(), "install"],
        cwd=str(REMOTION_DIR),
        capture_output=not verbose,
        timeout=300,
    )
    return r.returncode == 0


# ─── Preparação do ambiente Remotion ──────────────────────────────────────────

def prepare_assets(output_dir: Path) -> Path:
    """
    Copia todos os assets do pipeline para remotion_renderer/public/.
    Retorna o diretório public.
    """
    output_dir = Path(output_dir)
    public_dir = REMOTION_DIR / "public"
    public_dir.mkdir(exist_ok=True)

    # Limpa run anterior
    for f in public_dir.glob("*.json"):
        f.unlink(missing_ok=True)
    for f in public_dir.glob("*.wav"):
        f.unlink(missing_ok=True)
    for f in public_dir.glob("*.srt"):
        f.unlink(missing_ok=True)
    for f in public_dir.glob("*.ass"):
        f.unlink(missing_ok=True)

    # Copia arquivos de dados
    _copy_if_exists(output_dir / "timeline.json",          public_dir / "timeline.json")
    _copy_if_exists(output_dir / "editing_timeline.json",  public_dir / "editing_timeline.json")
    _copy_if_exists(output_dir / "subtitles.json",         public_dir / "subtitles.json")
    _copy_if_exists(output_dir / "subtitles.srt",          public_dir / "subtitles.srt")
    _copy_if_exists(output_dir / "subtitles.ass",          public_dir / "subtitles.ass")
    _copy_if_exists(output_dir / "audio.wav",              public_dir / "audio.wav")
    _copy_if_exists(output_dir / "03_story.json",          public_dir / "story.json")

    # Copia assets de imagem e vídeo
    assets_src  = output_dir / "assets"
    assets_dest = public_dir / "assets"
    if assets_src.exists():
        if assets_dest.exists():
            shutil.rmtree(assets_dest)
        shutil.copytree(assets_src, assets_dest)

    # Copia broll se existir
    broll_src  = output_dir / "broll"
    broll_dest = public_dir / "broll"
    if broll_src.exists():
        if broll_dest.exists():
            shutil.rmtree(broll_dest)
        shutil.copytree(broll_src, broll_dest)

    print(f"  Assets copiados para: {public_dir}")
    return public_dir


# ─── Renderização Remotion ────────────────────────────────────────────────────

def render(
    output_dir: Path,
    output_filename: str = "final_video_remotion.mp4",
    fps: int = 30,
    width: int = 1080,
    height: int = 1920,
    concurrency: int = 4,
) -> str | None:
    """
    Renderiza o vídeo com Remotion.
    Retorna path do vídeo gerado ou None se falhar.
    """
    output_dir  = Path(output_dir)
    output_path = output_dir / output_filename

    # Prepara assets
    public_dir = prepare_assets(output_dir)

    # Calcula total de frames a partir do timeline
    total_frames = _get_total_frames(public_dir / "timeline.json", fps)
    if total_frames <= 0:
        print("[remotion] Não foi possível determinar total de frames.")
        return None

    print(f"  Remotion: {total_frames} frames @ {fps}fps = {total_frames/fps:.1f}s")

    # Destino temporário dentro do remotion_renderer
    tmp_output = REMOTION_DIR / "out" / output_filename
    tmp_output.parent.mkdir(exist_ok=True)

    # Props passadas como JSON inline
    props = json.dumps({
        "fps":           fps,
        "width":         width,
        "height":        height,
        "totalFrames":   total_frames,
        "subtitleStyle": _get_dominant_subtitle_style(public_dir / "editing_timeline.json"),
    })

    # Formato: npx remotion render [composition-id] [output]
    # O entry point vem do package.json (src/index.ts → registerRoot)
    cmd = [
        _npx(), "remotion", "render",
        "DocumentaryVideo",
        str(tmp_output),
        "--props", props,
        "--concurrency", str(concurrency),
        "--log", "verbose" if os.environ.get("REMOTION_VERBOSE") else "info",
    ]

    print(f"  Renderizando com Remotion ({concurrency} threads)...")
    t0 = time.time()
    r  = subprocess.run(
        cmd,
        cwd=str(REMOTION_DIR),
        capture_output=False,
        timeout=1800,   # 30 min max
    )

    if r.returncode != 0 or not tmp_output.exists():
        print(f"  [remotion] Renderização falhou (code {r.returncode})")
        return None

    # Move para pasta de saída
    shutil.move(str(tmp_output), str(output_path))
    elapsed = time.time() - t0
    sz_mb   = output_path.stat().st_size / 1_048_576
    print(f"  final_video_remotion.mp4: {sz_mb:.1f}MB em {elapsed:.0f}s")
    return str(output_path)


# ─── Utilidades ───────────────────────────────────────────────────────────────

def _copy_if_exists(src: Path, dest: Path) -> None:
    if src.exists():
        shutil.copy2(src, dest)


def _get_total_frames(timeline_path: Path, fps: int) -> int:
    """Lê total_duration do timeline.json e converte para frames."""
    try:
        data = json.loads(timeline_path.read_text(encoding="utf-8"))
        duration = float(data.get("total_duration", 0) or data.get("audio_duration", 0))
        # Adiciona 1s de buffer para garantir cobertura total
        return int((duration + 1.0) * fps)
    except Exception as e:
        print(f"[remotion] Erro ao ler timeline: {e}")
        return 0


def _get_dominant_subtitle_style(editing_path: Path) -> str:
    """Extrai o estilo de legenda mais comum do editing_timeline.json."""
    try:
        data     = json.loads(editing_path.read_text(encoding="utf-8"))
        styles   = [d.get("subtitle_style", "CINEMATIC") for d in data.get("decisions", [])]
        dominant = max(set(styles), key=styles.count) if styles else "CINEMATIC"
        return dominant
    except Exception:
        return "CINEMATIC"
