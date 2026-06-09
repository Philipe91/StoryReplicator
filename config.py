import os
from pathlib import Path

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL      = "claude-sonnet-4-6"

PROJECT_ROOT = Path(__file__).parent
OUTPUT_DIR   = PROJECT_ROOT / "output"
ASSETS_DIR   = OUTPUT_DIR / "assets"

# ─── Modos de vídeo — P7 ──────────────────────────────────────────────────────
# micro       →  60s  (antigo "short")
# short       → 120s  (antigo "documentary")
# documentary → 180s  NOVO PADRÃO
# epic        → 360s  NOVO

VIDEO_MODES = {
    "micro": {
        "label":        "Micro (60s)",
        "duration":     60,
        "target_words": 150,
        "scene_interval": 4,   # segundos por cena — P3
        "segments": {
            "hook":       {"start": 0,  "end": 3},
            "contexto":   {"start": 3,  "end": 10},
            "conflito":   {"start": 10, "end": 28},
            "escalada":   {"start": 28, "end": 48},
            "plot_twist": {"start": 48, "end": 55},
            "cta":        {"start": 55, "end": 60},
        },
    },
    "short": {
        "label":        "Short (120s)",
        "duration":     120,
        "target_words": 300,
        "scene_interval": 4,
        "segments": {
            "hook":       {"start": 0,   "end": 3},
            "contexto":   {"start": 3,   "end": 15},
            "conflito":   {"start": 15,  "end": 45},
            "escalada":   {"start": 45,  "end": 70},
            "plot_twist": {"start": 70,  "end": 90},
            "final":      {"start": 90,  "end": 110},
            "cta":        {"start": 110, "end": 120},
        },
    },
    "documentary": {
        "label":        "Documentary (180s)",
        "duration":     180,
        "target_words": 450,
        "scene_interval": 4,
        "segments": {
            "hook":       {"start": 0,   "end": 4},
            "contexto":   {"start": 4,   "end": 20},
            "conflito":   {"start": 20,  "end": 60},
            "escalada":   {"start": 60,  "end": 100},
            "plot_twist": {"start": 100, "end": 130},
            "final":      {"start": 130, "end": 165},
            "cta":        {"start": 165, "end": 180},
        },
    },
    "epic": {
        "label":        "Epic (360s)",
        "duration":     360,
        "target_words": 900,
        "scene_interval": 5,
        "segments": {
            "hook":        {"start": 0,   "end": 5},
            "introducao":  {"start": 5,   "end": 30},
            "contexto":    {"start": 30,  "end": 70},
            "personagens": {"start": 70,  "end": 110},
            "conflito":    {"start": 110, "end": 170},
            "escalada":    {"start": 170, "end": 240},
            "plot_twist":  {"start": 240, "end": 290},
            "desfecho":    {"start": 290, "end": 335},
            "legado":      {"start": 335, "end": 350},
            "cta":         {"start": 350, "end": 360},
        },
    },
}

DEFAULT_MODE = "documentary"   # P7: novo padrão


def get_mode(name: str = None) -> dict:
    """Retorna configuração do modo. Padrão: 'documentary'."""
    name = (name or DEFAULT_MODE).lower().strip()
    if name not in VIDEO_MODES:
        # Aliases retrocompatíveis
        _aliases = {"reel": "short", "short60": "micro"}
        name = _aliases.get(name, DEFAULT_MODE)
    return VIDEO_MODES[name]


# ─── Emoções → movimentos cinematográficos — P6 ───────────────────────────────
# (segmento → tipo de movimento para o video_assembler)
SEGMENT_EMOTIONS = {
    "hook":       "mystery",
    "introducao": "contemplation",
    "contexto":   "pan_right",
    "personagens":"zoom_in",
    "conflito":   "tension",
    "escalada":   "push_in",
    "plot_twist": "revelation",
    "desfecho":   "triumph",
    "final":      "resolution",
    "legado":     "contemplation",
    "cta":        "static",
}

# ─── Visuais ───────────────────────────────────────────────────────────────────
IMAGE_STYLE = (
    "Historical Documentary, Cinematic, Photorealistic, 8K resolution, "
    "Realistic Lighting, Film Grain, National Geographic Quality, "
    "dramatic shadows, muted color palette, aged texture"
)

# ─── TTS ───────────────────────────────────────────────────────────────────────
KOKORO_VOICE   = "af_bella"
KOKORO_SPEED   = 1.0
KOKORO_LANG    = "pt"
EDGE_TTS_VOICE = "pt-BR-FranciscaNeural"

# ─── FFmpeg ────────────────────────────────────────────────────────────────────
FFMPEG_CRF        = 20
FFMPEG_PRESET     = "medium"
OUTPUT_RESOLUTION = "1080x1920"
FRAME_RATE        = 30

# ─── Legendas profissionais — P5 ──────────────────────────────────────────────
SUBTITLE_FONT_SIZE   = 78
SUBTITLE_MARGIN_V    = 120    # px da borda inferior (safe zone para Shorts/Reels)
SUBTITLE_MAX_CHARS   = 34     # chars máx por linha
SUBTITLE_MAX_WORDS   = 6      # palavras por bloco

# ─── Narração ─────────────────────────────────────────────────────────────────
NARRATION_TONE = (
    "documental, cinematográfico, misterioso e altamente envolvente. "
    "Use frases curtas e impactantes. Crie suspense. Narre como um documentário da Netflix."
)
