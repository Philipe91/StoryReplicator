"""ETAPA 2 — Análise da estrutura narrativa."""

from modules.claude_client import ask_json
from modules.extractor import VideoData


ANALYSIS_PROMPT = """Você é um especialista em narrativa audiovisual e psicologia do storytelling.

Analise o vídeo abaixo e extraia a estrutura narrativa completa.

TÍTULO: {title}
DESCRIÇÃO: {description}
TRANSCRIÇÃO: {transcript}
DURAÇÃO: {duration}s
VISUALIZAÇÕES: {views}

Retorne um JSON com esta estrutura exata:
{{
  "tema_central": "...",
  "gancho_emocional": "...",
  "elementos_virais": ["...", "..."],
  "estrutura": {{
    "hook": {{
      "conteudo": "...",
      "tecnica": "...",
      "duracao_estimada": 0
    }},
    "contexto": {{
      "conteudo": "...",
      "personagens": ["..."],
      "cenario": "...",
      "duracao_estimada": 0
    }},
    "conflito": {{
      "conteudo": "...",
      "tensao_principal": "...",
      "duracao_estimada": 0
    }},
    "escalada": {{
      "conteudo": "...",
      "viradas": ["...", "..."],
      "duracao_estimada": 0
    }},
    "plot_twist": {{
      "conteudo": "...",
      "surpresa": "...",
      "duracao_estimada": 0
    }},
    "encerramento": {{
      "conteudo": "...",
      "licao": "...",
      "duracao_estimada": 0
    }}
  }},
  "tom": "...",
  "publico_alvo": "...",
  "por_que_viral": "...",
  "formula_replicavel": "..."
}}

Retorne APENAS o JSON, sem explicações."""


def analyze(video: VideoData) -> dict:
    """Analisa estrutura narrativa e retorna relatório completo."""
    transcript_excerpt = (video.transcript or "")[:3000]

    prompt = ANALYSIS_PROMPT.format(
        title=video.title,
        description=(video.description or "")[:500],
        transcript=transcript_excerpt,
        duration=video.duration,
        views=video.view_count,
    )

    return ask_json(prompt, max_tokens=2000,
                    fallback={"formula_replicavel": video.title})
