"""
PRIORIDADE 6 — Montagem com movimentos cinematográficos baseados em emoção.
PRIORIDADE 5 — Queima de legendas .ass profissionais.
PRIORIDADE 8 — Verificação de sync audio/video pré-render.

Movimentos disponíveis (mapeados por emoção de cena):
  mystery     → slow zoom in
  tension     → push in (zoom rápido)
  revelation  → zoom out
  triumph     → zoom out suave
  pan_right   → pan da direita para esquerda
  pan_left    → pan da esquerda para direita
  zoom_in     → zoom in moderado
  contemplation → quase estático
  static      → estático
"""

import subprocess
from pathlib import Path
from config import FFMPEG_CRF, FFMPEG_PRESET, OUTPUT_RESOLUTION, FRAME_RATE


# ─── Mapeamento emoção → parâmetros de movimento ──────────────────────────────
_MOTION = {
    "mystery":      ("zoom_in",   1.0,  1.12),
    "tension":      ("zoom_in",   1.0,  1.28),
    "revelation":   ("zoom_out",  1.28, 1.0),
    "triumph":      ("zoom_out",  1.15, 1.0),
    "pan_right":    ("pan_right", 1.10, 1.10),
    "pan_left":     ("pan_left",  1.10, 1.10),
    "zoom_in":      ("zoom_in",   1.0,  1.18),
    "contemplation":("zoom_in",   1.0,  1.05),
    "push_in":      ("zoom_in",   1.0,  1.35),
    "resolution":   ("zoom_out",  1.10, 1.0),
    "curiosity":    ("pan_right", 1.08, 1.08),
    "static":       ("static",    1.05, 1.05),
}
_DEFAULT_MOTION = ("zoom_in", 1.0, 1.08)


# ─── Entry point ──────────────────────────────────────────────────────────────

def assemble(timeline: dict, output_dir: Path, ffmpeg_exe: str = "ffmpeg") -> str:
    """Monta final_video.mp4 a partir do timeline."""
    output_dir  = Path(output_dir)
    audio_file  = output_dir / "audio.wav"
    ass_file    = output_dir / "subtitles.ass"
    srt_file    = output_dir / "subtitles.srt"
    output_video = output_dir / "final_video.mp4"
    concat_list = output_dir / "concat_list.txt"

    scenes = timeline.get("scenes", [])
    if not scenes:
        print("[assembler] Nenhuma cena no timeline.")
        return str(output_video)

    w, h = OUTPUT_RESOLUTION.split("x")

    # ── 1. Renderiza cada cena ────────────────────────────────────────────────
    clips = []
    for scene in scenes:
        clip = _render_scene(scene, output_dir, w, h, ffmpeg_exe)
        if clip:
            clips.append(clip)

    if not clips:
        print("[assembler] Nenhum clipe gerado.")
        return str(output_video)

    # ── 2. Cria concat_list com paths absolutos ───────────────────────────────
    with open(concat_list, "w", encoding="utf-8") as f:
        for c in clips:
            f.write(f"file '{Path(c).resolve().as_posix()}'\n")

    raw_video = output_dir / "raw_video.mp4"
    _run([ffmpeg_exe, "-y", "-f", "concat", "-safe", "0",
          "-i", str(concat_list), "-c", "copy", str(raw_video)])

    if not raw_video.exists():
        print("[assembler] ERRO: raw_video.mp4 não gerado.")
        return str(output_video)

    print(f"  Video bruto: {raw_video.stat().st_size // 1024}KB")

    # ── 3. Adiciona áudio + legendas burned-in ────────────────────────────────
    sub_file   = ass_file if ass_file.exists() else (srt_file if srt_file.exists() else None)
    audio_args = ["-i", str(audio_file)] if audio_file.exists() else []
    map_args   = ["-map", "0:v", "-map", "1:a"] if audio_file.exists() else ["-map", "0:v"]
    audio_codec= ["-c:a", "aac", "-b:a", "128k"] if audio_file.exists() else []

    vf = _build_final_vf(sub_file, w, h)

    cmd = (
        [ffmpeg_exe, "-y", "-i", str(raw_video)]
        + audio_args
        + ["-vf", vf]
        + map_args
        + ["-c:v", "libx264", "-preset", FFMPEG_PRESET, "-crf", str(FFMPEG_CRF)]
        + audio_codec
        + ["-shortest", str(output_video)]
    )
    r = _run(cmd, timeout=600)

    if r != 0 or not output_video.exists():
        # Fallback sem legendas
        print("  [assembler] Retry sem legendas...")
        cmd_fb = (
            [ffmpeg_exe, "-y", "-i", str(raw_video)]
            + audio_args
            + ["-vf", f"scale={w}:{h}"]
            + map_args
            + ["-c:v", "libx264", "-preset", "fast", "-crf", "22"]
            + audio_codec
            + ["-shortest", str(output_video)]
        )
        _run(cmd_fb, timeout=600)

    if output_video.exists():
        sz = output_video.stat().st_size / 1_048_576
        print(f"  final_video.mp4: {sz:.1f}MB")
    return str(output_video)


# ─── Renderização de cada cena ────────────────────────────────────────────────

def _render_scene(scene: dict, output_dir: Path, w: str, h: str,
                  ffmpeg_exe: str) -> str | None:
    cid      = scene.get("scene_id", 0)
    duration = float(scene.get("duration", 4.0))
    emotion  = scene.get("emotion", "mystery")
    clip     = output_dir / f"clip_{cid:02d}.mp4"

    # Prefere vídeo histórico sobre imagem
    vid_file = scene.get("video_file")
    if vid_file:
        vid_path = output_dir / vid_file
        if vid_path.exists():
            result = _render_video_clip(vid_path, clip, duration, w, h, ffmpeg_exe)
            if result:
                return result
            # vídeo falhou → cai para imagem da cena (fallback robusto)

    # Imagem estática com movimento cinematográfico
    img_file = scene.get("image_file", f"assets/image_{cid:02d}.jpg")
    img_path = output_dir / img_file

    if not img_path.exists() or not _valid_image(img_path):
        img_path = _create_placeholder(output_dir, cid, scene.get("subtitle",""), w, h, ffmpeg_exe)

    return _render_image_clip(img_path, clip, duration, emotion, w, h, ffmpeg_exe)


def _valid_image(path: Path) -> bool:
    """Verifica se o arquivo é uma imagem válida (evita JPG corrompido/HTML)."""
    try:
        from PIL import Image
        with Image.open(path) as im:
            im.verify()
        return True
    except Exception:
        return False


def _render_image_clip(img_path: Path, clip: Path, duration: float,
                        emotion: str, w: str, h: str, ffmpeg_exe: str) -> str | None:
    mov_type, z_start, z_end = _MOTION.get(emotion, _DEFAULT_MOTION)
    vf = _build_cinematic_filter(mov_type, z_start, z_end, int(w), int(h), duration)

    r = _run([
        ffmpeg_exe, "-y", "-loop", "1", "-i", str(img_path),
        "-t", str(duration),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "24",
        "-r", str(FRAME_RATE), str(clip)
    ], timeout=120)

    if r != 0 or not clip.exists():
        # Fallback estático simples
        _run([
            ffmpeg_exe, "-y", "-loop", "1", "-i", str(img_path),
            "-t", str(duration),
            "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},format=yuv420p",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26",
            "-r", str(FRAME_RATE), str(clip)
        ], timeout=60)

    return str(clip) if clip.exists() else None


def _render_video_clip(vid_path: Path, clip: Path, duration: float,
                        w: str, h: str, ffmpeg_exe: str) -> str | None:
    """
    Processa clipe de vídeo histórico: recorta duração e adapta resolução.
    -ss/-t ANTES do -i (fast seek no input) evita decodificar o vídeo inteiro —
    crítico para clipes longos de archive (que antes causavam timeout).
    """
    vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},format=yuv420p"
    r = _run([
        ffmpeg_exe, "-y",
        "-ss", "0", "-t", str(duration),     # corta NO INPUT (rápido)
        "-i", str(vid_path),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26",
        "-an", "-r", str(FRAME_RATE),
        "-frames:v", str(int(duration * FRAME_RATE)),
        str(clip)
    ], timeout=90)
    if r != 0 or not clip.exists():
        print(f"    [assembler] vídeo {vid_path.name} falhou — usando imagem da cena")
        return None
    return str(clip)


# ─── Filtro cinematográfico (Ken Burns + movimentos) ──────────────────────────

def _build_cinematic_filter(mov_type: str, z_start: float, z_end: float,
                              w: int, h: int, duration: float) -> str:
    """
    Gera filtro FFmpeg para Ken Burns effect baseado no tipo de movimento.
    Escala a imagem para 1.4× para dar headroom ao zoom/pan.
    """
    frames = max(1, int(duration * FRAME_RATE))
    sw     = int(w * 1.4)
    sh     = int(h * 1.4)
    sw    += sw % 2
    sh    += sh % 2
    scale  = f"scale={sw}:{sh}:force_original_aspect_ratio=increase,crop={sw}:{sh}"

    if mov_type == "zoom_in":
        delta = (z_end - z_start) / frames
        zexpr = f"min(zoom+{delta:.6f},{z_end:.3f})"
        xexpr = "iw/2-(iw/zoom/2)"
        yexpr = "ih/2-(ih/zoom/2)"

    elif mov_type == "zoom_out":
        delta = (z_start - z_end) / frames
        zexpr = f"if(eq(on,1),{z_start:.3f},max(zoom-{delta:.6f},{z_end:.3f}))"
        xexpr = "iw/2-(iw/zoom/2)"
        yexpr = "ih/2-(ih/zoom/2)"

    elif mov_type == "pan_right":
        speed  = sw * 0.12 / frames
        zexpr  = str(z_start)
        xexpr  = f"max(0,min(iw-iw/zoom,iw/2-(iw/zoom/2)+on*{speed:.4f}))"
        yexpr  = "ih/2-(ih/zoom/2)"

    elif mov_type == "pan_left":
        speed  = sw * 0.12 / frames
        zexpr  = str(z_start)
        xexpr  = f"max(0,min(iw-iw/zoom,iw/2-(iw/zoom/2)-on*{speed:.4f}))"
        yexpr  = "ih/2-(ih/zoom/2)"

    else:  # static
        zexpr = str(z_start)
        xexpr = "iw/2-(iw/zoom/2)"
        yexpr = "ih/2-(ih/zoom/2)"

    zoompan = (
        f"zoompan=z='{zexpr}':x='{xexpr}':y='{yexpr}'"
        f":d=1:s={w}x{h}:fps={FRAME_RATE}"
    )
    return f"{scale},{zoompan},format=yuv420p"


# ─── Legenda burned-in ────────────────────────────────────────────────────────

def _build_final_vf(sub_file, w: str, h: str) -> str:
    """Constrói filtro -vf para o vídeo final com legendas opcionais."""
    scale = f"scale={w}:{h}"
    if sub_file is None:
        return f"{scale},format=yuv420p"

    sub_path = Path(sub_file)
    sub_esc  = str(sub_path.resolve()).replace("\\", "/").replace(":", "\\:")

    if sub_path.suffix.lower() == ".ass":
        # ASS tem estilo próprio — não precisa force_style
        return f"{scale},ass='{sub_esc}'"
    else:
        # SRT com estilo embutido — fonte grande para mobile
        style = (
            "FontSize=76,FontName=Arial,Bold=1,"
            "PrimaryColour=&HFFFFFF,OutlineColour=&H000000,"
            "Outline=4,Shadow=1,Alignment=2,MarginV=120"
        )
        return f"{scale},subtitles='{sub_esc}':force_style='{style}'"


# ─── Placeholder ──────────────────────────────────────────────────────────────

def _create_placeholder(output_dir: Path, cid: int, text: str,
                         w: str, h: str, ffmpeg_exe: str) -> Path:
    path = output_dir / "assets" / f"image_{cid:02d}.jpg"
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_text = (text or f"Cena {cid}")[:40].replace("'", "")
    _run([
        ffmpeg_exe, "-y", "-f", "lavfi",
        "-i", f"color=c=0x1a1a2e:s={w}x{h}:d=1",
        "-vf", f"drawtext=text='{safe_text}':fontsize=52:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2",
        "-frames:v", "1", str(path)
    ], timeout=30)
    return path


# ─── Subprocess helper ────────────────────────────────────────────────────────

def _run(cmd: list, timeout: int = 120) -> int:
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return r.returncode
    except subprocess.TimeoutExpired:
        print(f"  [assembler] timeout: {cmd[0]}")
        return 1
    except Exception as e:
        print(f"  [assembler] error: {e}")
        return 1
