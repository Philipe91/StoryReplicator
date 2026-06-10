"""
StoryReplicator v4.0 — Narration Director

Humaniza a narração ANTES do TTS, transformando texto plano em uma
narração com ritmo cinematográfico:

  - pausas naturais (após frases de impacto, antes de revelações)
  - respiração (micro-pausas entre orações)
  - suspense (reticências antes do clímax)
  - quebra dramática (isolar a frase de virada)
  - mudança de intensidade (segmentos mais lentos/graves)

Produz:
  - texto "dirigido" com pontuação/pausas que o edge-tts interpreta
  - plano de prosódia por segmento (rate/pitch sugeridos)

100% heurístico, sem API.
"""

import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
import json


# Marcadores de virada que merecem pausa dramática antes
_DRAMATIC_PIVOTS = [
    "mas", "porém", "no entanto", "de repente", "subitamente",
    "até que", "então", "foi quando", "o que ninguém sabia",
]
# Palavras de revelação → suspense antes (reticências)
_REVEAL_TRIGGERS = [
    "descobriu", "revelou", "verdade", "segredo", "na verdade",
    "o que aconteceu", "o final", "ninguém esperava",
]

# Prosódia por segmento narrativo (rate, pitch) — intensidade emocional
_SEGMENT_PROSODY = {
    "hook":       {"rate": "-2%",  "pitch": "-6Hz"},   # firme, pega atenção
    "introducao": {"rate": "-6%",  "pitch": "-8Hz"},
    "contexto":   {"rate": "-4%",  "pitch": "-8Hz"},   # calmo, expositivo
    "personagens":{"rate": "-4%",  "pitch": "-8Hz"},
    "conflito":   {"rate": "-2%",  "pitch": "-6Hz"},   # acelera levemente
    "escalada":   {"rate": "+2%",  "pitch": "-4Hz"},   # tensão crescente
    "plot_twist": {"rate": "-8%",  "pitch": "-10Hz"},  # desacelera, grave, dramático
    "desfecho":   {"rate": "-6%",  "pitch": "-8Hz"},
    "final":      {"rate": "-8%",  "pitch": "-10Hz"},  # solene
    "legado":     {"rate": "-8%",  "pitch": "-10Hz"},
    "cta":        {"rate": "-2%",  "pitch": "-6Hz"},   # convite claro
}


@dataclass
class DirectedNarration:
    narration_full: str = ""
    segments:       list = field(default_factory=list)
    prosody_plan:   list = field(default_factory=list)


def direct(narration: dict) -> dict:
    """
    Recebe a narração e devolve uma versão dirigida (humanizada).
    Mantém a estrutura do dict de narração para uso direto no pipeline.
    """
    out = dict(narration)
    segs = narration.get("segments", [])
    directed_segments = []
    prosody = []
    full_parts = []

    for seg in segs:
        sid  = seg.get("id", "")
        text = seg.get("text", "")
        directed = _humanize_text(text, sid)

        s2 = dict(seg)
        s2["text"] = directed
        directed_segments.append(s2)
        full_parts.append(directed)

        prosody.append({
            "id": sid,
            **_SEGMENT_PROSODY.get(sid, {"rate": "-4%", "pitch": "-8Hz"}),
        })

    if directed_segments:
        out["segments"] = directed_segments
        out["narration_full"] = " ".join(full_parts)
    else:
        # Sem segmentos: humaniza o texto corrido
        out["narration_full"] = _humanize_text(narration.get("narration_full", ""), "")

    out["prosody_plan"] = prosody
    out["directed"] = True
    return out


def save_directed(narration: dict, output_dir: Path) -> None:
    (Path(output_dir) / "narration_directed.json").write_text(
        json.dumps(narration, ensure_ascii=False, indent=2), encoding="utf-8")


# ─── Humanização do texto ──────────────────────────────────────────────────────

def _humanize_text(text: str, segment_id: str) -> str:
    """
    Insere pausas, suspense e quebras dramáticas via pontuação que o
    edge-tts respeita (vírgulas = micro-pausa, reticências = pausa longa).
    """
    if not text.strip():
        return text

    sentences = _split_sentences(text)
    out = []

    for sent in sentences:
        s = sent.strip()
        if not s:
            continue
        low = s.lower()

        # Suspense: reticências antes de revelações
        for trig in _REVEAL_TRIGGERS:
            if trig in low:
                s = re.sub(rf'\b({re.escape(trig)})', r'... \1', s, count=1, flags=re.IGNORECASE)
                break

        # Quebra dramática: isola a oração de virada com pausa antes
        for pivot in _DRAMATIC_PIVOTS:
            # pausa (reticências) antes do pivô quando ele inicia oração
            s = re.sub(rf'(^|, )({pivot})\b', rf'\1... \2', s, count=1, flags=re.IGNORECASE)

        # Respiração: garante vírgula-pausa após conectores longos
        s = re.sub(r'\b(no entanto|porém|além disso|por fim|finalmente)\b',
                   r'\1,', s, flags=re.IGNORECASE)

        out.append(s)

    # Plot twist / final: pausa longa ENTRE frases (mais dramático)
    joiner = " ... " if segment_id in ("plot_twist", "final", "desfecho") else " "
    result = joiner.join(out)

    # Limpa pontuação duplicada
    result = re.sub(r'\.{4,}', '...', result)
    result = re.sub(r'\s+', ' ', result).strip()
    result = re.sub(r'\s+([.,!?])', r'\1', result)
    return result


def _split_sentences(text: str) -> list:
    # Preserva o delimitador final
    parts = re.split(r'(?<=[.!?])\s+', text)
    return [p for p in parts if p.strip()]
