"""ETAPA 5 — Narração completa pronta para TTS, com modos dinâmicos."""

import json
from config import NARRATION_TONE
from modules.claude_client import ask_json


def write_narration(script: dict, mode_config: dict) -> dict:
    """
    Gera narração otimizada para TTS a partir do roteiro.
    mode_config = get_mode("short" | "reel" | "documentary")
    """
    segments     = mode_config["segments"]
    duration     = mode_config["duration"]
    target_words = mode_config["target_words"]

    seg_schema = json.dumps(
        [
            {
                "id":                 seg_id,
                "start":              v["start"],
                "end":                v["end"],
                "text":               "...",
                "word_count":         0,
                "estimated_duration": 0.0,
            }
            for seg_id, v in segments.items()
        ],
        ensure_ascii=False, indent=2
    )

    prompt = f"""Você é um locutor de documentários cinematográficos.

Baseado no roteiro abaixo, escreva a NARRAÇÃO COMPLETA pronta para síntese de voz (TTS).
Duração alvo: {duration} segundos | ~{target_words} palavras

ROTEIRO:
{json.dumps(script, ensure_ascii=False, indent=2)}

REGRAS CRÍTICAS PARA TTS:
1. Texto corrido, sem símbolos especiais (* # [ ])
2. Números por extenso: "1945" → "mil novecentos e quarenta e cinco"
3. Abreviações por extenso: "Sr." → "Senhor"
4. Use vírgulas para pausas curtas, ponto para pausas longas
5. Tom: {NARRATION_TONE}
6. Português brasileiro claro e envolvente

Retorne APENAS este JSON (sem explicações):
{{
  "narration_full": "Texto completo da narração para TTS...",
  "duracao_alvo": {duration},
  "segments": {seg_schema}
}}"""

    data = ask_json(prompt, max_tokens=3000,
                    fallback={"narration_full": "", "segments": []})
    if not data.get("narration_full") and data.get("raw"):
        data["narration_full"] = data["raw"]
    data.setdefault("segments", [])
    # Calcula word_count e estimated_duration se não preenchidos
    for seg in data["segments"]:
        if not seg.get("word_count"):
            seg["word_count"] = len(seg.get("text", "").split())
        if not seg.get("estimated_duration"):
            seg["estimated_duration"] = round(seg["word_count"] / 2.5, 1)
    return data
