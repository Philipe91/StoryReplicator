"""
ETAPA 6 — Storyboard com cenas granulares (P3) e campo emotion (P6).

Mudanças vs v1:
- Cenas de ~4s cada (era ~7s) → mais variedade visual
- Campo `emotion` por cena → usado pelo video_assembler para movimentos
- Máx 5s por cena (regra de cobertura visual — P3)
"""

import json
from config import IMAGE_STYLE, SEGMENT_EMOTIONS
from modules.claude_client import ask_json, story_system


def generate_storyboard(narration: dict, story: dict, mode_config: dict) -> dict:
    """
    Gera storyboard completo com cenas curtas (4s média) e emoção por cena.
    mode_config = get_mode(...)
    """
    duration = mode_config["duration"]
    segments = mode_config["segments"]

    # P3: 1 cena a cada 4s → mais variedade visual
    interval     = mode_config.get("scene_interval", 4)
    ideal_scenes = max(8, duration // interval)
    seg_list     = ", ".join(f"{k}({v['start']}-{v['end']}s)" for k, v in segments.items())

    # Mapeamento segmento → emoção para orientar os prompts
    seg_emotions = {k: SEGMENT_EMOTIONS.get(k, "mystery") for k in segments}

    prompt = f"""Você é um diretor de arte de documentários cinematográficos profissionais.

Crie o storyboard completo para um vídeo de {duration} segundos,
baseado na HISTÓRIA fornecida no contexto do sistema e na NARRAÇÃO abaixo.

NARRAÇÃO:
{json.dumps(narration, ensure_ascii=False, indent=2)}

REGRAS OBRIGATÓRIAS:
1. Total de cenas: {ideal_scenes} a {ideal_scenes + 6} (1 cena a cada ~{interval}s)
2. Cada cena máx 5 segundos (regra de variedade visual)
3. Segmentos: {seg_list}
4. Emoções por segmento: {json.dumps(seg_emotions)}
5. Estilo visual: {IMAGE_STYLE}
6. Formato vertical 9:16 (Shorts/Reels)
7. Cada cena deve ter uma descrição visual ÚNICA e ESPECÍFICA
8. Priorize imagens reais histórias (documentos, retratos, mapas, jornais)

Para cada cena defina:
- emotion: mystery | tension | revelation | triumph | pan_right | pan_left | zoom_in | contemplation | static
- descricao_visual: O QUE BUSCAR — específico para encontrar na Wikimedia/Library of Congress
  (ex: "crowd of European immigrants Ellis Island 1890 photograph" NÃO "pessoas chegando")
- tipo_visual: photograph | newspaper | document | map | portrait | engraving | advertisement

Retorne APENAS este JSON (sem explicações):
{{
  "total_cenas": 0,
  "duracao_total": {duration},
  "cenas": [
    {{
      "cena_id": 1,
      "start": 0.0,
      "end": 4.0,
      "duracao": 4.0,
      "segmento": "hook",
      "emotion": "mystery",
      "narracao": "Texto exato da narração nesta cena",
      "descricao_visual": "Descrição ESPECÍFICA em inglês para busca de imagem",
      "tipo_visual": "photograph",
      "angulo_camera": "close-up | plano aberto | aéreo | médio",
      "movimento_camera": "zoom in | zoom out | pan left | pan right | static",
      "legenda": "Legenda curta (máx 5 palavras)",
      "transicao_entrada": "cut | fade | dissolve",
      "transicao_saida": "cut | fade | dissolve",
      "nota_direcao": "instrução técnica"
    }}
  ]
}}"""

    data = ask_json(prompt, max_tokens=8000, system=story_system(story),
                    fallback={"total_cenas": 0, "cenas": []})
    if "cenas" not in data:
        data["cenas"] = []
    data["total_cenas"]   = len(data["cenas"])
    data["duracao_total"] = duration
    # Garante campo emotion em todas as cenas
    for cena in data["cenas"]:
        if "emotion" not in cena:
            cena["emotion"] = SEGMENT_EMOTIONS.get(cena.get("segmento", ""), "mystery")
    return data
