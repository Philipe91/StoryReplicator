"""
v5.0 — Explainer Generator (modo NotebookLM).

Transforma o conteúdo de um vídeo (transcrição + metadados) em um DECK de
slides narrados, no formato dos "Video Overviews" do NotebookLM:
1 narrador + slides didáticos (título, bullets, dado em destaque, citação),
onde a duração de cada slide = duração do áudio da narração daquele slide.

Uma única chamada Claude produz o deck completo.
"""

import json

from modules.claude_client import ask_json

_DECK_PROMPT = """Você é um roteirista de vídeos educativos no estilo NotebookLM Video Overview:
um narrador único explica um tema com slides limpos e didáticos.

CONTEÚDO A EXPLICAR (vídeo original):
TÍTULO: {title}
DESCRIÇÃO: {description}
TRANSCRIÇÃO: {transcript}

Crie um deck de {min_slides} a {max_slides} slides que EXPLICA esse conteúdo
de forma clara, envolvente e fiel aos fatos do material.

REGRAS:
1. Slide 1 é sempre layout "title" (título forte + subtítulo) e o último é "cta".
2. Varie os layouts: use "stat" quando houver número marcante, "quote" quando
   houver fala/citação forte, "bullets" para listas de ideias (máx 4 bullets,
   máx 8 palavras por bullet).
3. Cada slide tem "narracao": 20-40 palavras em português brasileiro, texto
   corrido pronto para TTS (números por extenso, sem símbolos). A narração
   deve fluir de um slide para o próximo como uma explicação contínua.
4. A narração NÃO deve ler o slide literalmente — o slide resume, a narração explica.
5. Tom: professor curioso e claro, estilo documentário educativo.

Retorne APENAS este JSON (sem explicações):
{{
  "titulo_deck": "...",
  "tema": "...",
  "slides": [
    {{
      "id": 1,
      "layout": "title | bullets | stat | quote | cta",
      "titulo": "Título do slide (máx 8 palavras)",
      "subtitulo": "opcional (máx 12 palavras)",
      "bullets": ["...", "..."],
      "stat": {{"valor": "87%", "rotulo": "descrição curta do número"}},
      "quote": {{"texto": "...", "autor": "..."}},
      "narracao": "Texto da narração deste slide..."
    }}
  ]
}}
Campos não usados pelo layout podem ser omitidos."""


def generate_deck(video_data: dict, min_slides: int = 8, max_slides: int = 14) -> dict:
    """
    Gera o deck de slides a partir dos dados extraídos do vídeo.
    video_data: dict com title/description/transcript (01_video_data.json).
    """
    prompt = _DECK_PROMPT.format(
        title=video_data.get("title", ""),
        description=(video_data.get("description") or "")[:500],
        transcript=(video_data.get("transcript") or "")[:6000],
        min_slides=min_slides,
        max_slides=max_slides,
    )
    deck = ask_json(prompt, max_tokens=6000, fallback={"slides": []})
    deck["slides"] = _sanitize_slides(deck.get("slides", []))
    return deck


def _sanitize_slides(slides: list) -> list:
    """Garante ids sequenciais, layouts válidos e narração não-vazia."""
    valid_layouts = {"title", "bullets", "stat", "quote", "cta"}
    out = []
    for i, s in enumerate(slides, 1):
        if not isinstance(s, dict) or not str(s.get("narracao", "")).strip():
            continue
        s = dict(s)
        s["id"] = i
        if s.get("layout") not in valid_layouts:
            s["layout"] = "bullets" if s.get("bullets") else "title"
        out.append(s)
    return out


def deck_to_narration(deck: dict) -> dict:
    """
    Converte o deck no formato de narração do pipeline (segments por slide),
    pronto para synthesize_narration_directed — cada slide vira um segmento
    com id "slide_NN" e os word boundaries saem etiquetados por slide.
    """
    segments = []
    for s in deck.get("slides", []):
        segments.append({
            "id":   f"slide_{s['id']:02d}",
            "text": str(s.get("narracao", "")).strip(),
        })
    full = " ".join(seg["text"] for seg in segments)
    return {"narration_full": full, "segments": segments}
