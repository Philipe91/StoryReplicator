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

# ─── Multi-idioma (v3.8) ──────────────────────────────────────────────────────
# Cada idioma usa uma voz NATIVA daquele idioma — evita o "escorregão" de
# vozes multilíngues para outro idioma. pitch/rate ajustam tom e ritmo.
LANG_CONFIG = {
    "pt": {
        "name":      "Português (BR)",
        "tts_voice": "pt-BR-AntonioNeural",     # masculina nativa BR
        "pitch":     "-8Hz",                    # levemente grave (opção A escolhida)
        "rate":      "-5%",
        "translate_code": "pt",
    },
    "en": {
        "name":      "English (US)",
        "tts_voice": "en-US-AndrewNeural",      # masculina nativa EN (não-multilíngue)
        "pitch":     "-5Hz",
        "rate":      "-3%",
        "translate_code": "en",
    },
    "es": {
        "name":      "Español (ES)",
        "tts_voice": "es-ES-AlvaroNeural",      # masculina nativa ES
        "pitch":     "-5Hz",
        "rate":      "-3%",
        "translate_code": "es",
    },
}

DEFAULT_LANG = "pt"

# Voz/idioma padrão usados quando não se especifica idioma
EDGE_TTS_VOICE = LANG_CONFIG[DEFAULT_LANG]["tts_voice"]
EDGE_TTS_PITCH = LANG_CONFIG[DEFAULT_LANG]["pitch"]
EDGE_TTS_RATE  = LANG_CONFIG[DEFAULT_LANG]["rate"]

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

# ─── v3.6 — Universal Visual Asset Engine ─────────────────────────────────────

# Chaves de API GRATUITAS (opcionais). Sem elas, o engine usa apenas
# Wikimedia + Internet Archive + Library of Congress (zero custo, zero cadastro).
# Para ativar Pexels/Pixabay, registre-se grátis e exporte as variáveis:
#   set PEXELS_API_KEY=...    (https://www.pexels.com/api/  — gratuito)
#   set PIXABAY_API_KEY=...   (https://pixabay.com/api/docs/ — gratuito)
PEXELS_API_KEY  = os.getenv("PEXELS_API_KEY", "")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")

# Ordem de prioridade dos tipos de ativo (1 = melhor). Usada no scoring.
ASSET_PRIORITY = {
    "video_relevant":   1,   # vídeo altamente relevante para a cena
    "video_context":    2,   # vídeo relacionado ao contexto
    "video_historical": 3,   # vídeo histórico
    "photo_historical": 4,   # fotografia histórica
    "document":         5,   # documento histórico
    "newspaper":        6,   # jornal histórico
    "map":              7,   # mapa
    "engraving":        8,   # gravura
    "image_complement": 9,   # imagem complementar
}

# Duração útil de cada ativo na timeline (segundos)
ASSET_DURATION_MIN = 2.0
ASSET_DURATION_MAX = 6.0

# Mistura-alvo da timeline (proporções). O engine tenta se aproximar.
ASSET_MIX_TARGET = {
    "video":      0.50,   # 40–60%
    "image":      0.30,   # 20–40%
    "document":   0.20,   # 10–20% (documentos, mapas, jornais)
}

# B-roll: categorias genéricas para ilustrar contexto quando faltar material
BROLL_CATEGORIES = [
    "corridor", "city street", "crowd", "vehicle",
    "building exterior", "document close up", "landscape",
]

# ─── v3.7 — Adaptive Music Engine ─────────────────────────────────────────────

# Categorias de trilha sonora
MUSIC_CATEGORIES = [
    "MYSTERY", "INVESTIGATION", "DRAMATIC", "HISTORICAL", "SUSPENSE",
    "EMOTIONAL", "TRIUMPH", "DARK", "INSPIRING",
]

# Emoção da cena → categoria musical
EMOTION_TO_MUSIC = {
    "mystery":      "MYSTERY",
    "curiosity":    "INVESTIGATION",
    "tension":      "SUSPENSE",
    "revelation":   "DRAMATIC",
    "triumph":      "TRIUMPH",
    "resolution":   "EMOTIONAL",
    "contemplation":"EMOTIONAL",
    "push_in":      "DRAMATIC",
    "pan_right":    "HISTORICAL",
    "pan_left":     "HISTORICAL",
    "zoom_in":      "INVESTIGATION",
    "static":       "EMOTIONAL",
}

# Segmento narrativo → categoria musical (usado para emoção dominante)
SEGMENT_TO_MUSIC = {
    "hook":       "MYSTERY",
    "introducao": "HISTORICAL",
    "contexto":   "INVESTIGATION",
    "personagens":"HISTORICAL",
    "conflito":   "SUSPENSE",
    "escalada":   "DRAMATIC",
    "plot_twist": "DRAMATIC",
    "desfecho":   "TRIUMPH",
    "final":      "EMOTIONAL",
    "legado":     "INSPIRING",
    "cta":        "EMOTIONAL",
}

# Termos de busca de música por categoria (Internet Archive, sem chave)
MUSIC_SEARCH_TERMS = {
    "MYSTERY":       "mysterious ambient instrumental cinematic",
    "INVESTIGATION": "investigation detective instrumental suspense",
    "DRAMATIC":      "dramatic orchestral cinematic instrumental",
    "HISTORICAL":    "historical orchestral classical instrumental",
    "SUSPENSE":      "suspense tension dark instrumental",
    "EMOTIONAL":     "emotional piano cinematic instrumental",
    "TRIUMPH":       "triumphant epic orchestral instrumental",
    "DARK":          "dark ambient drone instrumental",
    "INSPIRING":     "inspiring uplifting cinematic instrumental",
}

# Volumes de mixagem
NARRATION_VOLUME = 1.0     # 100%
MUSIC_VOLUME     = 0.16    # 16% (faixa 12–20%)
MUSIC_DUCK_VOLUME = 0.08   # volume da música quando há narração (ducking)
MUSIC_FADE_SEC   = 1.5     # duração de fade in/out

# ─── v3.7 — Visual Quality Filter ─────────────────────────────────────────────

# Resolução mínima aceitável
MIN_IMAGE_WIDTH      = 1280
PREFERRED_IMAGE_WIDTH = 1920
MIN_VIDEO_HEIGHT     = 720
PREFERRED_VIDEO_HEIGHT = 1080

# Limiar de detecção de borrão (variância do Laplaciano). Abaixo = borrada.
# Baixo (25) para tolerar fotos históricas/scans antigos, que são naturalmente
# menos nítidos mas legítimos. Rejeita apenas borrão severo.
BLUR_VARIANCE_THRESHOLD = 22.0

# Razão bytes/pixel mínima (abaixo = excessivamente comprimida)
MIN_BYTES_PER_PIXEL = 0.05

# Upscale: caminho para Real-ESRGAN ou Upscayl (opcional). Vazio = desativado.
REALESRGAN_PATH = os.getenv("REALESRGAN_PATH", "")
UPSCAYL_PATH    = os.getenv("UPSCAYL_PATH", "")
# Score de relevância acima do qual vale a pena fazer upscale de ativo pequeno
UPSCALE_RELEVANCE_THRESHOLD = 0.55
