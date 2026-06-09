"""
ETAPA 9 — Timeline JSON + SRT.

PRIORIDADE 3 — Cobertura visual: nenhuma imagem por mais de 5s.
PRIORIDADE 4 — Suporte a vídeos históricos (type: image | video).
"""

from config import SEGMENT_EMOTIONS


def build_timeline(
    storyboard: dict,
    narration: dict,   # kept for API compat — not used directly
    visual_prompts: dict,
    mode_config: dict,
    image_assignments: dict = None,
    video_assignments: dict = None,
) -> dict:
    """
    Constrói timeline JSON.

    image_assignments: {cena_id: "assets/image_XX.jpg"}
    video_assignments: {cena_id: "assets/video_XX.mp4"}
    """
    prompts_by_cena: dict = {}
    for p in visual_prompts.get("prompts", []):
        cid = p.get("cena_id")
        if cid is not None:
            prompts_by_cena[cid] = p

    image_assignments = image_assignments or {}
    video_assignments = video_assignments or {}

    scenes = []
    for cena in storyboard.get("cenas", []):
        cena_id  = cena.get("cena_id", 0)
        segmento = cena.get("segmento", "")
        duration = float(cena.get("duracao", 4.0))
        emotion  = cena.get("emotion", SEGMENT_EMOTIONS.get(segmento, "mystery"))
        img_data = prompts_by_cena.get(cena_id, {})

        # P4: prefere vídeo sobre imagem quando disponível
        video_file = video_assignments.get(cena_id)
        image_file = image_assignments.get(cena_id, f"assets/image_{cena_id:02d}.jpg")

        asset_type = "video" if video_file else "image"

        scene_entry = {
            "scene_id":      cena_id,
            "start":         cena.get("start", 0.0),
            "end":           cena.get("end",   0.0),
            "duration":      duration,
            "segment":       segmento,
            "emotion":       emotion,          # P6
            "asset_type":    asset_type,       # P4
            "voice":         cena.get("narracao", ""),
            "subtitle":      cena.get("legenda", ""),
            "image_file":    image_file,
            "video_file":    video_file or "",
            "image_prompt":  img_data.get("prompt_positivo", ""),
            "visual_type":   cena.get("tipo_visual", "photograph"),
            "zoom":          _resolve_zoom(cena.get("movimento_camera", ""), emotion),
            "transition_in": cena.get("transicao_entrada", "cut"),
            "transition_out":cena.get("transicao_saida",   "cut"),
            "camera_angle":  cena.get("angulo_camera", ""),
            "fx":            cena.get("efeito_especial", "none"),
        }
        scenes.append(scene_entry)

    # P3 — Garante cobertura visual: cenas > 5s são marcadas para o assembler
    scenes = _flag_long_scenes(scenes)

    return {
        "version":        "2.0",
        "mode":           mode_config.get("label", ""),
        "total_duration": mode_config.get("duration", 180),
        "resolution":     "1080x1920",
        "fps":            30,
        "audio_file":     "audio.wav",
        "subtitles_file": "subtitles.ass",
        "scenes":         scenes,
        "post_processing": {
            "color_grade":       "cinematic_warm",
            "film_grain":        True,
            "grain_intensity":   0.12,
            "vignette":          True,
            "vignette_intensity": 0.25,
            "contrast_boost":    1.08,
        },
    }


def build_srt(storyboard: dict) -> str:
    """Gera SRT básico a partir do storyboard (backup — substitui subtitle_engine)."""
    lines = []
    index = 1
    for cena in storyboard.get("cenas", []):
        subtitle = cena.get("legenda", "").strip()
        if not subtitle:
            subtitle = " ".join(cena.get("narracao", "").split()[:6])
        if not subtitle:
            continue
        lines += [
            str(index),
            f"{_sec_to_srt(cena.get('start', 0))} --> {_sec_to_srt(cena.get('end', 0))}",
            subtitle, "",
        ]
        index += 1
    return "\n".join(lines)


# ─── P3: Cobertura visual ─────────────────────────────────────────────────────

def _flag_long_scenes(scenes: list, max_sec: float = 5.0) -> list:
    """
    Marca cenas com duração > max_sec com needs_visual_variety=True.
    O video_assembler pode usar isso para aplicar movimentos de câmera
    mais dramáticos e compensar a falta de troca de imagem.
    """
    result = []
    for s in scenes:
        s = dict(s)
        if float(s.get("duration", 0)) > max_sec:
            s["needs_visual_variety"] = True
            # Usa o movimento mais dinâmico disponível para a emoção
            emotion = s.get("emotion", "mystery")
            dynamic = {
                "mystery":      "tension",
                "contemplation": "mystery",
                "static":       "zoom_in",
            }.get(emotion, emotion)
            s["emotion"] = dynamic
        else:
            s["needs_visual_variety"] = False
        result.append(s)
    return result


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _resolve_zoom(movimento: str, emotion: str = "") -> str:
    """Resolve tipo de zoom do campo movimento_camera do storyboard."""
    m = (movimento or "").lower()
    if "zoom in"  in m: return "zoom_in"
    if "zoom out" in m: return "zoom_out"
    if "pan"      in m: return "pan"
    # Fallback: usa emoção
    if emotion in ("tension", "push_in", "mystery"): return "zoom_in"
    if emotion in ("revelation", "triumph"):          return "zoom_out"
    return "static"


def _sec_to_srt(seconds: float) -> str:
    s  = int(seconds)
    ms = int((seconds - s) * 1000)
    return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d},{ms:03d}"
