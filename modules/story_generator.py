"""ETAPA 3 — Geração de nova história original com mesma estrutura."""

import json
from modules.claude_client import ask_json


STORY_PROMPT = """Você é um roteirista especializado em histórias reais inacreditáveis para vídeos virais.

Baseado na análise abaixo, crie uma NOVA HISTÓRIA COMPLETAMENTE ORIGINAL.
NÃO copie o vídeo original. Use a mesma fórmula narrativa mas com personagens, época e evento diferentes.

ANÁLISE DO VÍDEO ORIGINAL:
{analysis}

REGRAS:
1. História 100% original — personagens e eventos diferentes
2. Mantenha a mesma fórmula de gancho e estrutura
3. Mesma intensidade dramática
4. Nicho: Histórias Reais Inacreditáveis
5. Baseada em fatos históricos reais (adapte se necessário)
6. Tom: documental, misterioso, cinematográfico

Retorne um JSON com esta estrutura exata:
{{
  "titulo": "...",
  "subtitulo": "...",
  "logline": "Uma frase que resume a história com gancho",
  "personagem_principal": {{
    "nome": "...",
    "descricao": "...",
    "motivacao": "..."
  }},
  "epoca_local": "...",
  "historia_completa": "Narrativa detalhada em 300-400 palavras...",
  "estrutura": {{
    "hook": "Frase de abertura impactante (máx 15 palavras)",
    "contexto": "Apresentação do personagem e cenário (50-70 palavras)",
    "conflito": "O problema central que desencadeia a história (80-100 palavras)",
    "escalada": "Como a situação se agrava e intensifica (80-100 palavras)",
    "plot_twist": "A reviravolta inesperada (40-60 palavras)",
    "encerramento": "Resolução e impacto final (40-60 palavras)",
    "cta": "Chamada para ação envolvente (20-30 palavras)"
  }},
  "palavras_chave_seo": ["...", "...", "..."],
  "angulo_viral": "..."
}}

Retorne APENAS o JSON, sem explicações."""


def generate_story(analysis: dict) -> dict:
    """Gera nova história original baseada na análise do vídeo original."""
    prompt = STORY_PROMPT.format(analysis=json.dumps(analysis, ensure_ascii=False, indent=2))
    return ask_json(prompt, max_tokens=3000, fallback={"titulo": "Nova História"})
