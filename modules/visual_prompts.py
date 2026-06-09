"""ETAPA 7 — Geração de prompts visuais para geração de imagens."""

import json
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, IMAGE_STYLE


VISUAL_PROMPT_TEMPLATE = """Você é um diretor de arte especializado em documentários históricos cinematográficos.

Baseado no storyboard abaixo, crie prompts detalhados para geração de imagens com IA.

STORYBOARD:
{storyboard}

ESTILO BASE: {style}

PARA CADA CENA, crie um prompt otimizado para geração de imagem (Midjourney / DALL-E / Flux).

REGRAS DOS PROMPTS:
1. Sempre em inglês
2. Incluir: sujeito + ação + cenário + iluminação + câmera + estilo
3. Formato: [sujeito], [ação/estado], [cenário], [iluminação], [câmera], [estilo técnico]
4. Negativo sempre: "cartoon, anime, illustration, painting, drawing, watercolor, sketch"
5. Máx 120 palavras por prompt

Retorne um JSON com esta estrutura:
{{
  "prompts": [
    {{
      "image_id": "IMAGE_01",
      "cena_id": 1,
      "segmento": "hook",
      "titulo": "Título descritivo da imagem",
      "prompt_positivo": "Detailed English prompt for image generation...",
      "prompt_negativo": "cartoon, anime, illustration, painting, drawing, watercolor, sketch, blurry, low quality",
      "aspect_ratio": "9:16",
      "resolucao": "1080x1920",
      "estilo_especifico": "cinematic, documentary photography",
      "referencia_cor": "muted browns and sepia tones",
      "mood": "tense, mysterious, historical"
    }}
  ]
}}

Retorne APENAS o JSON, sem explicações."""


def generate_visual_prompts(storyboard: dict) -> dict:
    """Gera prompts visuais detalhados para cada cena do storyboard."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = VISUAL_PROMPT_TEMPLATE.format(
        storyboard=json.dumps(storyboard, ensure_ascii=False, indent=2),
        style=IMAGE_STYLE,
    )

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=6000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(raw)
        # Renumerar IDs de imagem sequencialmente
        for i, p in enumerate(data.get("prompts", []), 1):
            p["image_id"] = f"IMAGE_{i:02d}"
        return data
    except json.JSONDecodeError:
        return {"prompts": [], "raw": raw}


def export_prompts_txt(visual_prompts: dict, output_path: str) -> None:
    """Exporta prompts em formato .txt legível para uso manual."""
    lines = []
    for p in visual_prompts.get("prompts", []):
        lines.append(f"{'='*60}")
        lines.append(f"{p['image_id']} — {p.get('titulo', '')}")
        lines.append(f"Segmento: {p.get('segmento', '')}")
        lines.append(f"")
        lines.append(f"POSITIVO:")
        lines.append(p.get("prompt_positivo", ""))
        lines.append(f"")
        lines.append(f"NEGATIVO:")
        lines.append(p.get("prompt_negativo", ""))
        lines.append(f"")
        lines.append(f"Aspect Ratio: {p.get('aspect_ratio', '9:16')}")
        lines.append(f"Mood: {p.get('mood', '')}")
        lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
