"""ETAPA 4 — Roteiro profissional com timecodes dinâmicos por modo."""

import json
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, NARRATION_TONE


def write_script(story: dict, mode_config: dict) -> dict:
    """
    Gera roteiro profissional com timecodes.
    mode_config = get_mode("short" | "reel" | "documentary")
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    segments     = mode_config["segments"]
    duration     = mode_config["duration"]
    target_words = mode_config["target_words"]
    mode_label   = mode_config["label"]

    seg_lines = "\n".join(
        f"- {v['start']}-{v['end']}s: {k.upper().replace('_',' ')} ({v['end']-v['start']}s)"
        for k, v in segments.items()
    )

    # Monta schema JSON esperado dinamicamente
    seg_schema = json.dumps(
        [
            {
                "id": seg_id,
                "start": v["start"],
                "end":   v["end"],
                "titulo": seg_id.upper().replace("_", " "),
                "narration_lines": ["linha1", "linha2"],
                "direcao_visual": "...",
                "musica_sugerida": "...",
            }
            for seg_id, v in segments.items()
        ],
        ensure_ascii=False, indent=2
    )

    prompt = f"""Você é um roteirista profissional de documentários curtos para plataformas de vídeo curto.

Escreva o roteiro completo para um vídeo de {duration} segundos ({mode_label}).

HISTÓRIA:
{json.dumps(story, ensure_ascii=False, indent=2)}

ESTRUTURA DE TEMPO OBRIGATÓRIA:
{seg_lines}

ALVO: ~{target_words} palavras no total
TOM: {NARRATION_TONE}

REGRAS:
- Cada linha de narração máx 12 palavras
- Pausas dramáticas marcadas com [PAUSA]
- Ênfase em palavras-chave com MAIÚSCULAS
- Linguagem acessível mas cinematográfica
- Narre em português brasileiro

Retorne APENAS este JSON (sem explicações):
{{
  "titulo_roteiro": "...",
  "modo": "{mode_label}",
  "duracao_total": {duration},
  "segmentos": {seg_schema}
}}"""

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip().replace("```json","").replace("```","").strip()
    try:
        data = json.loads(raw)
        data["_mode"] = mode_config
        return data
    except json.JSONDecodeError:
        return {"titulo_roteiro": "Roteiro", "segmentos": [], "_mode": mode_config, "raw": raw}
