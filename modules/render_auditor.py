"""
PRIORIDADE 8 — Auditoria de renderização.

Antes de montar o vídeo final:
- Mede duração real do áudio
- Verifica se a timeline cobre 100% do áudio
- Corrige automaticamente gaps e durações insuficientes
- Garante que o vídeo NUNCA termina antes da narração
"""

import subprocess
from pathlib import Path


def audit_and_fix(timeline: dict, audio_path: str, ffmpeg_exe: str = "ffmpeg") -> tuple:
    """
    Audita e corrige o timeline para garantir cobertura total do áudio.

    Retorna: (timeline_corrigido, audit_report)
    """
    audio_duration = _get_audio_duration(audio_path, ffmpeg_exe)
    scenes         = list(timeline.get("scenes", []))

    if not scenes:
        return timeline, {"error": "timeline vazio"}

    report = {
        "audio_duration":    round(audio_duration, 2),
        "timeline_duration": 0.0,
        "fixes_applied":     [],
        "status":            "ok",
    }

    # ── 1. Recalcula start/end de cada cena a partir do zero ──────────────────
    scenes = _normalize_scene_timing(scenes)

    # ── 2. Mede duração total do timeline ─────────────────────────────────────
    timeline_duration = sum(s.get("duration", 0.0) for s in scenes)
    report["timeline_duration"] = round(timeline_duration, 2)

    # ── 3. Verifica se timeline cobre todo o áudio ────────────────────────────
    gap = audio_duration - timeline_duration

    if gap > 0.5:  # tolerância de 0.5s
        fix_msg = f"timeline {timeline_duration:.1f}s < audio {audio_duration:.1f}s — estendendo {gap:.1f}s"
        report["fixes_applied"].append(fix_msg)
        report["status"] = "fixed"

        # Distribui a diferença: estende a última cena
        scenes[-1] = dict(scenes[-1])
        scenes[-1]["duration"] = scenes[-1].get("duration", 0.0) + gap
        scenes[-1]["end"]      = scenes[-1]["start"] + scenes[-1]["duration"]

    elif gap < -2.0:
        # Timeline muito maior que audio → trim
        report["fixes_applied"].append(
            f"timeline {timeline_duration:.1f}s > audio {audio_duration:.1f}s — sem trim (áudio termina antes)"
        )

    # ── 4. Recalcula start/end após extensão ──────────────────────────────────
    scenes = _normalize_scene_timing(scenes)

    # ── 5. Verifica cenas com duration = 0 ou negativa ────────────────────────
    for i, s in enumerate(scenes):
        if s.get("duration", 0) < 0.5:
            scenes[i] = dict(s)
            scenes[i]["duration"] = 1.0
            scenes[i]["end"] = s["start"] + 1.0
            report["fixes_applied"].append(f"cena {s['scene_id']} duração zerada → 1s")
            report["status"] = "fixed"

    # ── 6. Verifica cobertura visual total ────────────────────────────────────
    # image_file é relativo ao diretório de saída (ex: "assets/image_01.jpg");
    # resolve contra a pasta do áudio, não contra o CWD.
    base_dir = Path(audio_path).parent
    missing_images = [
        s["scene_id"] for s in scenes
        if not (base_dir / str(s.get("image_file", ""))).exists()
        and not s.get("video_file")
    ]
    report["missing_visual_assets"] = missing_images

    timeline_fixed = dict(timeline)
    timeline_fixed["scenes"]         = scenes
    timeline_fixed["total_duration"] = round(sum(s["duration"] for s in scenes), 2)
    timeline_fixed["audio_duration"] = round(audio_duration, 2)

    report["final_duration"] = timeline_fixed["total_duration"]
    report["coverage_pct"]   = round(
        min(timeline_fixed["total_duration"] / max(audio_duration, 0.01), 1.0) * 100, 1
    )

    return timeline_fixed, report


def _normalize_scene_timing(scenes: list) -> list:
    """Reconstrói start/end sequencialmente a partir das durações."""
    result  = []
    current = 0.0
    for s in scenes:
        s = dict(s)
        dur = float(s.get("duration", 4.0))
        dur = max(dur, 0.5)
        s["start"]    = round(current, 3)
        s["end"]      = round(current + dur, 3)
        s["duration"] = round(dur, 3)
        result.append(s)
        current += dur
    return result


def _get_audio_duration(audio_path: str, ffmpeg_exe: str = "ffmpeg") -> float:
    """Obtém duração do áudio em segundos via FFmpeg."""
    try:
        r = subprocess.run(
            [ffmpeg_exe, "-i", str(audio_path)],
            capture_output=True, text=True, timeout=15
        )
        for line in r.stderr.split("\n"):
            if "Duration" in line:
                dur_str = line.split("Duration:")[1].split(",")[0].strip()
                h, m, s = dur_str.split(":")
                return int(h) * 3600 + int(m) * 60 + float(s)
    except Exception as e:
        print(f"[auditor] Erro ao medir duração: {e}")
    return 0.0
