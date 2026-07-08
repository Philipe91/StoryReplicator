"""ETAPA 10 — Geração de metadados de publicação."""

from modules.claude_client import ask_json, story_system


METADATA_PROMPT = """Você é um especialista em SEO e growth hacking para YouTube Shorts, TikTok e Instagram Reels.

Baseado na HISTÓRIA fornecida no contexto do sistema,
crie metadados completos de publicação para maximizar o alcance viral.

TÉCNICA DE CTR (obrigatória):
- Gere 8 variantes de título usando estruturas DIFERENTES: resultado específico,
  pergunta, contraste, número, promessa e curiosidade. Ranqueie da maior para a
  menor chance de clique. A variante nº 1 vira o título principal.
- Título e thumbnail trabalham JUNTOS e nunca repetem a mesma informação:
  um cria a pergunta, o outro amplia a curiosidade.

Retorne um JSON com esta estrutura exata:
{{
  "titulos_variantes_ctr": [
    {{"titulo": "...", "estrutura": "pergunta|numero|contraste|promessa|curiosidade|resultado", "rank": 1}}
  ],
  "titulos": {{
    "youtube_shorts": "A variante rank 1 (máx 70 chars, gancho forte)",
    "tiktok": "Título TikTok (máx 60 chars, trendy)",
    "instagram_reels": "Título Instagram Reels (máx 60 chars)",
    "facebook_reels": "Título Facebook Reels (máx 70 chars)"
  }},
  "descricao": {{
    "completa": "Descrição de 150-200 palavras com keywords...",
    "curta": "Descrição de 50 palavras para mobile...",
    "gancho": "Primeira linha que aparece antes do 'ver mais' (máx 125 chars)"
  }},
  "hashtags": {{
    "principais": ["#hashtag1", "#hashtag2"],
    "nicho": ["#hashtag3", "#hashtag4"],
    "trending": ["#hashtag5", "#hashtag6"],
    "total_recomendado": "Use 15-20 no YouTube, 5-10 no TikTok, 20-30 no Instagram"
  }},
  "thumbnail": {{
    "prompt_principal": "Prompt detalhado em inglês para gerar thumbnail 1280x720...",
    "prompt_negativo": "texto, palavras, cartoon, anime...",
    "elemento_central": "O elemento visual central da imagem",
    "texto_sobreposicao": "Texto de destaque (MÁX 4 palavras, NUNCA repete o título — amplia a curiosidade dele)",
    "cor_dominante": "cor hex sugerida para o texto",
    "paleta": "paleta de cores que se destaca no feed",
    "estilo": "thumbnail estilo YouTube drama"
  }},
  "hooks_variantes": [
    "Versão A do hook para teste A/B",
    "Versão B do hook para teste A/B",
    "Versão C do hook para teste A/B"
  ],
  "horario_publicacao": {{
    "melhor_dia": "...",
    "melhor_hora": "...",
    "justificativa": "..."
  }},
  "tags_youtube": ["tag1", "tag2", "tag3"],
  "categoria_youtube": "...",
  "cta_comentario": "Pergunta para engajar comentários..."
}}

Retorne APENAS o JSON, sem explicações."""


def generate_metadata(story: dict) -> dict:
    """Gera todos os metadados de publicação."""
    # .format() sem args converte as chaves escapadas {{ }} do template em { }
    return ask_json(METADATA_PROMPT.format(), max_tokens=3000,
                    system=story_system(story))
