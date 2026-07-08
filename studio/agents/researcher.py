"""
Agente Pesquisador — pesquisa profunda do tema na web (100% gratuito).

Fontes em cadeia de fallback:
  1. Wikipedia (API REST pt + en — sem chave, sem limite abusivo)
  2. DuckDuckGo (lib `ddgs`, opcional — busca web como um humano)
  3. Leitura das páginas top (requests + extração de texto)

Depois, o Claude:
  - cruza as fontes e VALIDA fatos (descarta o que só aparece em 1 fonte fraca)
  - extrai curiosidades e números marcantes
  - gera a base de conhecimento com REFERÊNCIAS (URL por fato)

Produz: knowledge_base (dict) + 01_research.json
"""

import json
import re

import requests

from studio.core import Agent
from studio.providers import Provider, ProviderChain

_UA = {"User-Agent": "StoryReplicatorStudio/1.0 (pesquisa educacional)"}


class ResearcherAgent(Agent):
    name     = "pesquisador"
    label    = "Pesquisa profunda do tema (Wikipedia + web + validação)"
    requires = ()
    produces = ("knowledge_base",)

    def run(self, ctx):
        theme = ctx.theme
        notes = ctx.inbox(self.name)
        if notes:
            print(f"  Notas do QA: {[n['note'][:60] for n in notes]}")

        sources = []

        # ── 1. Wikipedia PT + EN ─────────────────────────────────────────────
        for lang in ("pt", "en"):
            for page in _wikipedia_search(theme, lang=lang, limit=3):
                extract = _wikipedia_extract(page["title"], lang=lang)
                if extract and len(extract) > 400:
                    sources.append({
                        "source": f"wikipedia-{lang}",
                        "title":  page["title"],
                        "url":    f"https://{lang}.wikipedia.org/wiki/{page['title'].replace(' ', '_')}",
                        "text":   extract[:6000],
                    })
        print(f"  Wikipedia: {len(sources)} artigos")

        # ── 2. Busca web (DuckDuckGo, se disponível) + leitura das páginas ──
        web_chain = ProviderChain("websearch", [
            Provider("duckduckgo", _ddg_search, available=_ddg_available),
        ])
        hits, provider = web_chain.call(theme, max_results=6)
        n_web = 0
        for hit in (hits or []):
            text = _fetch_page_text(hit.get("href", ""))
            if text and len(text) > 500:
                sources.append({
                    "source": provider,
                    "title":  hit.get("title", ""),
                    "url":    hit.get("href", ""),
                    "text":   text[:5000],
                })
                n_web += 1
            if n_web >= 4:
                break
        print(f"  Web ({provider or 'indisponível'}): {n_web} páginas lidas")

        if not sources:
            raise RuntimeError("Nenhuma fonte encontrada para o tema.")

        # ── 3. Claude: valida, cruza e estrutura ─────────────────────────────
        kb = self._build_knowledge_base(theme, sources, notes)
        kb["sources_consulted"] = [
            {"source": s["source"], "title": s["title"], "url": s["url"]}
            for s in sources
        ]
        ctx.set("knowledge_base", kb, self.name)
        _save(ctx, "01_research.json", kb)
        print(f"  Fatos validados: {len(kb.get('fatos', []))} | "
              f"Curiosidades: {len(kb.get('curiosidades', []))} | "
              f"Fontes: {len(sources)}")

    def _build_knowledge_base(self, theme, sources, qa_notes) -> dict:
        from modules.claude_client import ask_json

        src_block = "\n\n".join(
            f"[FONTE {i+1}] {s['source']} — {s['title']} ({s['url']})\n{s['text'][:3500]}"
            for i, s in enumerate(sources)
        )
        extra = ""
        if qa_notes:
            extra = "\nATENÇÃO DO REVISOR: " + "; ".join(n["note"] for n in qa_notes)

        prompt = f"""Você é um pesquisador rigoroso preparando a base de um vídeo documental.

TEMA: {theme}
{extra}
FONTES COLETADAS:
{src_block}

TAREFA — validação cruzada:
1. Um fato só entra se for consistente entre as fontes (ou vier de fonte forte como Wikipedia). Elimine contradições, boatos e imprecisões.
2. Marque a confiança de cada fato: alta (2+ fontes) | media (1 fonte forte).
3. Extraia curiosidades pouco conhecidas e números marcantes (ótimos para retenção).
4. Aponte personagens, locais, datas e objetos centrais (serão usados para buscar imagens/vídeos).

Retorne APENAS este JSON:
{{
  "tema": "{theme}",
  "resumo": "Resumo denso do tema em 150-250 palavras...",
  "fatos": [
    {{"fato": "...", "confianca": "alta|media", "fonte_url": "..."}}
  ],
  "curiosidades": [
    {{"curiosidade": "...", "fonte_url": "..."}}
  ],
  "numeros_marcantes": [
    {{"valor": "...", "contexto": "...", "fonte_url": "..."}}
  ],
  "entidades": {{
    "personagens": ["..."],
    "locais": ["..."],
    "datas_chave": ["..."],
    "objetos": ["..."]
  }},
  "angulos_narrativos": ["ângulo 1 para o vídeo", "ângulo 2"],
  "descartado": ["informação eliminada por inconsistência e por quê"]
}}"""
        return ask_json(prompt, max_tokens=6000, fallback={"tema": theme, "fatos": []})


# ─── Providers de busca ────────────────────────────────────────────────────────

def _wikipedia_search(query: str, lang: str = "pt", limit: int = 3) -> list:
    try:
        r = requests.get(
            f"https://{lang}.wikipedia.org/w/api.php",
            params={"action": "query", "list": "search", "srsearch": query,
                    "srlimit": limit, "format": "json"},
            headers=_UA, timeout=15,
        )
        return [{"title": i["title"]} for i in
                r.json().get("query", {}).get("search", [])]
    except Exception:
        return []


def _wikipedia_extract(title: str, lang: str = "pt") -> str:
    try:
        r = requests.get(
            f"https://{lang}.wikipedia.org/w/api.php",
            params={"action": "query", "prop": "extracts", "explaintext": "1",
                    "titles": title, "format": "json", "exsectionformat": "plain"},
            headers=_UA, timeout=15,
        )
        pages = r.json().get("query", {}).get("pages", {})
        return next(iter(pages.values()), {}).get("extract", "")
    except Exception:
        return ""


def _ddg_available() -> bool:
    try:
        import ddgs        # noqa: F401  (pacote `ddgs`, sucessor do duckduckgo-search)
        return True
    except ImportError:
        try:
            import duckduckgo_search   # noqa: F401
            return True
        except ImportError:
            return False


def _ddg_search(query: str, max_results: int = 6) -> list:
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS
    with DDGS() as ddg:
        return list(ddg.text(query, max_results=max_results))


def _fetch_page_text(url: str) -> str:
    """Extração simples de texto de página (sem dependências extras)."""
    if not url:
        return ""
    try:
        r = requests.get(url, headers=_UA, timeout=15)
        if r.status_code != 200:
            return ""
        html = r.text
        html = re.sub(r"(?is)<(script|style|nav|header|footer|aside)[^>]*>.*?</\1>", " ", html)
        text = re.sub(r"(?s)<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        return text
    except Exception:
        return ""


def _save(ctx, name: str, data: dict) -> None:
    from pathlib import Path
    p = Path(ctx.workdir) / name
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
