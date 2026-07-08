"""ETAPA 4 — Roteiro profissional com timecodes dinâmicos por modo."""

import json
from config import NARRATION_TONE
from modules.claude_client import ask_json, story_system


def write_script(story: dict, mode_config: dict) -> dict:
    """
    Gera roteiro profissional com timecodes.
    mode_config = get_mode("short" | "reel" | "documentary")
    """
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

Escreva o roteiro completo para um vídeo de {duration} segundos ({mode_label}),
baseado na HISTÓRIA fornecida no contexto do sistema.

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

    data = ask_json(prompt, max_tokens=3000, system=story_system(story),
                    fallback={"titulo_roteiro": "Roteiro", "segmentos": []})
    data.setdefault("segmentos", [])
    data["_mode"] = mode_config
    return data
