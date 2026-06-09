"""
StoryReplicator v3.5 — Editor AI

Analisa cada cena do storyboard e decide automaticamente:
  - movimento de câmera (9 tipos)
  - intensidade e velocidade do movimento
  - tipo de transição
  - estilo de legenda
  - emoção predominante
  - ritmo da cena
  - necessidade de B-roll

Funciona 100% SEM API — decisões determinísticas baseadas em
emoção, segmento narrativo e duração da cena.

Saída: editing_timeline.json
"""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

try:
    from config import SEGMENT_EMOTIONS
except ImportError:
    SEGMENT_EMOTIONS = {}


# ─── Tipos de movimento de câmera disponíveis ─────────────────────────────────
CAMERA_MOVEMENTS = [
    "slow_push_in",    # Ken Burns suave entrando
    "slow_push_out",   # Ken Burns suave saindo
    "pan_left",        # Pan da direita para esquerda
    "pan_right",       # Pan da esquerda para direita
    "tilt_up",         # Tilt de baixo para cima
    "tilt_down",       # Tilt de cima para baixo
    "parallax",        # Efeito parallax (zoom + lateral)
    "focus_reveal",    # Desfoque → nitidez (reveal dramático)
    "depth_zoom",      # Zoom com leve desfoque de profundidade
    "static",          # Estático (com leve zoom mínimo)
]

# ─── Estilos de legenda ────────────────────────────────────────────────────────
SUBTITLE_STYLES = ["DOCUMENTARY", "CINEMATIC", "MODERN_SHORTS"]

# ─── Tabela de decisão: emoção → parâmetros de edição ─────────────────────────
# Formato: (camera, intensity, speed, trans_in, trans_out, subtitle_style, rhythm, broll_needed)
_EDIT_TABLE = {
    # emoção          câmera            intens  speed  t_in        t_out       subtitles        ritmo     broll
    "mystery":      ("slow_push_in",   0.65,  0.70,  "fade",     "fade",     "CINEMATIC",     "slow",   False),
    "tension":      ("slow_push_in",   0.90,  1.25,  "cut",      "cut",      "MODERN_SHORTS", "fast",   True),
    "revelation":   ("focus_reveal",   0.80,  0.80,  "dissolve", "dissolve", "CINEMATIC",     "medium", False),
    "triumph":      ("slow_push_out",  0.70,  0.75,  "dissolve", "fade",     "DOCUMENTARY",   "slow",   False),
    "pan_right":    ("pan_right",      0.55,  0.65,  "cut",      "cut",      "DOCUMENTARY",   "medium", False),
    "pan_left":     ("pan_left",       0.55,  0.65,  "cut",      "cut",      "DOCUMENTARY",   "medium", False),
    "zoom_in":      ("depth_zoom",     0.75,  0.90,  "cut",      "cut",      "MODERN_SHORTS", "medium", True),
    "contemplation":("tilt_up",        0.40,  0.50,  "fade",     "fade",     "DOCUMENTARY",   "slow",   False),
    "push_in":      ("slow_push_in",   1.00,  1.50,  "cut",      "cut",      "MODERN_SHORTS", "fast",   True),
    "resolution":   ("slow_push_out",  0.50,  0.60,  "dissolve", "fade",     "CINEMATIC",     "slow",   False),
    "curiosity":    ("parallax",       0.60,  0.75,  "cut",      "cut",      "DOCUMENTARY",   "medium", False),
    "static":       ("static",         0.20,  0.50,  "cut",      "fade",     "MODERN_SHORTS", "medium", False),
}
_DEFAULT_EDIT = ("slow_push_in", 0.60, 0.70, "cut", "cut", "DOCUMENTARY", "medium", False)

# ─── Ajuste de movimento por duração da cena ──────────────────────────────────
# Cenas muito curtas (<2s): movimento rápido
# Cenas médias (2-5s): movimento normal
# Cenas longas (>5s): movimento lento + broll
_DURATION_OVERRIDES = {
    "short":  {"speed_mult": 1.3, "intensity_mult": 0.8},   # < 2.5s
    "medium": {"speed_mult": 1.0, "intensity_mult": 1.0},   # 2.5-5s
    "long":   {"speed_mult": 0.7, "intensity_mult": 1.2, "broll": True},  # > 5s
}


# ─── Data class ───────────────────────────────────────────────────────────────

@dataclass
class SceneEditDecision:
    scene_id:          int
    segment:           str
    emotion:           str
    camera:            str
    camera_intensity:  float   # 0.0 – 1.0 (força do movimento)
    camera_speed:      float   # 0.5 – 2.0 (velocidade: 1.0 = normal)
    transition_in:     str     # cut | fade | dissolve
    transition_out:    str
    subtitle_style:    str     # DOCUMENTARY | CINEMATIC | MODERN_SHORTS
    rhythm:            str     # slow | medium | fast
    broll_needed:      bool
    broll_queries:     list    = field(default_factory=list)
    duration:          float   = 0.0
    layers:            list    = field(default_factory=list)  # visual layer types


# ─── Funções principais ────────────────────────────────────────────────────────

def analyze(storyboard: dict, story: dict) -> list[SceneEditDecision]:
    """
    Analisa o storyboard e retorna lista de SceneEditDecision.
    Uma decisão por cena, sem chamada de API.
    """
    decisions = []
    scenes    = storyboard.get("cenas", [])
    # Determina o estilo dominante do vídeo baseado na história
    dominant_style = _infer_dominant_style(story)

    for cena in scenes:
        cid      = cena.get("cena_id", 0)
        segmento = cena.get("segmento", "")
        # Emoção: prefere campo explícito; senão deriva do segmento (garante variedade)
        emotion  = cena.get("emotion") or SEGMENT_EMOTIONS.get(segmento, "mystery")
        duration = float(cena.get("duracao", 4.0))
        desc     = cena.get("descricao_visual", "")
        vtype    = cena.get("tipo_visual", "photograph")

        # Obtém parâmetros base da tabela de emoções
        params = _EDIT_TABLE.get(emotion, _DEFAULT_EDIT)
        cam, intensity, speed, t_in, t_out, sub_style, rhythm, broll = params

        # Ajusta por duração da cena
        dur_class = "short" if duration < 2.5 else ("long" if duration > 5.0 else "medium")
        overrides = _DURATION_OVERRIDES[dur_class]
        intensity = min(1.0, intensity * overrides["intensity_mult"])
        speed     = speed * overrides["speed_mult"]
        if overrides.get("broll"):
            broll = True

        # Força estilo de legenda dominante para consistência visual
        if dominant_style and sub_style != dominant_style:
            # 50% chance de usar o estilo dominante
            if cid % 2 == 0:
                sub_style = dominant_style

        # Gera queries de B-roll
        broll_queries = []
        if broll:
            broll_queries = _build_broll_queries(desc, emotion, story)

        # Define camadas visuais sugeridas
        layers = _suggest_layers(vtype, segmento, duration)

        decisions.append(SceneEditDecision(
            scene_id=cid, segment=segmento, emotion=emotion,
            camera=cam, camera_intensity=round(intensity, 2),
            camera_speed=round(speed, 2), transition_in=t_in,
            transition_out=t_out, subtitle_style=sub_style,
            rhythm=rhythm, broll_needed=broll,
            broll_queries=broll_queries, duration=duration,
            layers=layers,
        ))

    return decisions


def save(decisions: list[SceneEditDecision], output_dir: Path) -> Path:
    """Salva editing_timeline.json na pasta de saída."""
    output_dir = Path(output_dir)
    data = {
        "version": "3.5",
        "total_scenes": len(decisions),
        "decisions": [asdict(d) for d in decisions],
    }
    path = output_dir / "editing_timeline.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def to_dict_map(decisions: list[SceneEditDecision]) -> dict:
    """Retorna {scene_id: decision_dict} para fácil acesso."""
    return {d.scene_id: asdict(d) for d in decisions}


# ─── Helpers internos ─────────────────────────────────────────────────────────

def _infer_dominant_style(story: dict) -> str:
    """Infere o estilo de legenda dominante baseado no tema da história."""
    titulo = (story.get("titulo") or "").lower()
    epoca  = (story.get("epoca_local") or "").lower()

    if any(w in titulo for w in ["golpe", "fraude", "crime", "assassin", "mistério"]):
        return "MODERN_SHORTS"
    if any(w in epoca for w in ["18", "19", "século", "era", "guerra"]):
        return "DOCUMENTARY"
    return "CINEMATIC"


def _build_broll_queries(desc: str, emotion: str, story: dict) -> list:
    """Gera queries de busca para B-roll de sobreposição."""
    epoca   = story.get("epoca_local", "")
    periodo = _extract_decade(epoca)

    # Tipos de B-roll por emoção
    broll_types = {
        "tension":  ["newspaper front page", "official document", "close-up portrait"],
        "push_in":  ["newspaper headline", "telegram", "letter manuscript"],
        "zoom_in":  ["map vintage", "document archival", "newspaper clipping"],
    }.get(emotion, ["historical document", "vintage photograph"])

    queries = []
    for bt in broll_types[:2]:
        q = f"{periodo} {bt}".strip() if periodo else bt
        queries.append(q)

    return queries[:3]


def _extract_decade(epoca: str) -> str:
    import re
    m = re.search(r'\b(1[5-9]\d\d|20[0-2]\d)\b', epoca)
    if m:
        y = int(m.group(0))
        return f"{(y // 10) * 10}s"
    return ""


def _suggest_layers(visual_type: str, segment: str, duration: float) -> list:
    """
    Sugere camadas visuais para o compositor Remotion.
    Cenas mais longas e de conflito/escalada podem ter mais camadas.
    """
    layers = ["main"]   # sempre tem a imagem principal

    if duration > 5.0:
        # Cenas longas: adiciona overlay de documento/mapa quando apropriado
        if visual_type in ("photograph", "portrait"):
            if segment in ("conflito", "escalada", "plot_twist"):
                layers.append("document_overlay")
        if visual_type in ("photograph",) and segment in ("contexto", "personagens"):
            layers.append("portrait_inset")

    if visual_type == "map":
        layers.append("map_highlight")

    return layers
