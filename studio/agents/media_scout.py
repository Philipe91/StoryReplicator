"""
Agente de Busca de Mídia (MediaScout) — pesquisa como um editor humano.

Estratégia profunda por cena:
1. EXPANSÃO DE QUERIES (1 chamada Claude em lote): para cada cena gera
   variações em inglês E português, sinônimos, termos técnicos, personagens,
   locais e eventos relacionados — nunca uma busca única.
2. VARREDURA em todas as fontes gratuitas (Wikimedia, Internet Archive,
   Library of Congress, Openverse, Pexels*, Pixabay* — *se houver chave grátis),
   com dezenas de candidatos comparados por cena.
3. SCORE multi-critério + dedup (nunca repete mídia semelhante) + filtro de
   qualidade (resolução, borrão, compressão).
4. PROVENIÊNCIA: media_report.json registra, por cena, queries usadas,
   candidatos ranqueados (URL, autor, licença, fonte, score 0-100), escolhido
   e justificativa — exigência de auditoria.

Produz: media_result + image/video_assignments.
"""

import json
from pathlib import Path

from studio.core import Agent


class MediaScoutAgent(Agent):
    name     = "media_scout"
    label    = "Busca profunda de mídia (multi-fonte, multi-idioma)"
    requires = ("storyboard", "scene_contexts", "pseudo_story")
    produces = ("media_result", "image_assignments", "video_assignments")

    def run(self, ctx):
        from modules.visual_asset_engine import (
            UniversalVisualEngine, save_reports, extract_assignments)

        storyboard   = ctx.get("storyboard")
        contexts     = ctx.get("scene_contexts")
        pseudo_story = ctx.get("pseudo_story")
        ffmpeg       = ctx.config.get("ffmpeg", "ffmpeg")
        notes        = ctx.inbox(self.name)

        # ── 1. Expansão profunda de queries (PT + EN + sinônimos + entidades) ──
        expansions = self._expand_queries(storyboard, ctx)
        n_added = 0
        for cid, extra_queries in expansions.items():
            sctx = contexts.get(cid)
            if not sctx:
                continue
            for q in extra_queries:
                if q and q not in sctx.search_queries:
                    sctx.search_queries.append(q)
                    n_added += 1
        print(f"  Queries expandidas: +{n_added} "
              f"(PT/EN/sinônimos/entidades relacionadas)")

        # QA pediu retrabalho? Reforça variedade limpando o cache de decisão
        if notes:
            print(f"  Notas do QA: {[n['note'][:60] for n in notes]}")

        # ── 2-4. Varredura multi-fonte com score, dedup, qualidade e ledger ────
        engine = UniversalVisualEngine(
            output_dir=Path(ctx.workdir),
            prefer_video=not ctx.config.get("skip_video_search", False),
            ffmpeg_exe=ffmpeg,
        )
        result = engine.run(storyboard, pseudo_story, contexts)
        save_reports(result, Path(ctx.workdir))
        image_assign, video_assign = extract_assignments(result)

        print(f"  {result['found']}/{result['total_scenes']} cenas com mídia "
              f"({result['success_rate']}%) | vídeos: {result['video_count']} "
              f"| imagens: {result['image_count']}")
        print(f"  Fontes usadas: {', '.join(result.get('sources_used', []))}")

        # ── 5. Último recurso: gerar imagem por IA (Pollinations, grátis) ──────
        missing = [a for a in result["assignments"].values()
                   if a.get("status") == "missing"]
        if missing:
            n_gen = self._generate_missing(missing, storyboard, image_assign,
                                           result, ctx)
            print(f"  Imagens geradas por IA (fallback): {n_gen}/{len(missing)}")

        ctx.set("media_result", result, self.name)
        ctx.set("image_assignments", image_assign, self.name)
        ctx.set("video_assignments", video_assign, self.name)

    def _generate_missing(self, missing: list, storyboard: dict,
                          image_assign: dict, result: dict, ctx) -> int:
        """Gera imagem via Pollinations.ai só para cenas sem NENHUMA mídia real."""
        import datetime
        import requests as _rq
        from config import IMAGE_STYLE

        cenas = {c["cena_id"]: c for c in storyboard.get("cenas", [])}
        assets_dir = Path(ctx.workdir) / "assets"
        assets_dir.mkdir(exist_ok=True)
        created = 0
        for a in missing[:6]:                      # limite de cortesia da API
            cid  = a.get("cena_id")
            cena = cenas.get(cid, {})
            desc = cena.get("descricao_visual", "") or cena.get("narracao", "")
            if not desc:
                continue
            prompt = f"{desc}, {IMAGE_STYLE}"
            import urllib.parse
            url = ("https://image.pollinations.ai/prompt/"
                   + urllib.parse.quote(prompt[:300])
                   + "?width=1080&height=1920&nologo=true")
            try:
                r = _rq.get(url, timeout=90)
                if r.status_code == 200 and len(r.content) > 20_000:
                    dest = assets_dir / f"image_{cid:02d}.jpg"
                    dest.write_bytes(r.content)
                    image_assign[cid] = f"assets/image_{cid:02d}.jpg"
                    result["assignments"][cid] = {
                        "cena_id": cid, "status": "found", "asset_type": "image",
                        "category": "ai_generated", "source": "pollinations-ai",
                        "url": url, "local_path": f"assets/image_{cid:02d}.jpg",
                        "score": 0.4, "license": "AI generated",
                    }
                    result.setdefault("provenance", {})[cid] = {
                        "scene_id": cid, "queries": [desc[:80]],
                        "accessed_at": datetime.datetime.now().isoformat(timespec="seconds"),
                        "ranked": [], "chosen": {
                            "url": url, "source": "pollinations-ai",
                            "license": "AI generated", "score_100": 40,
                            "justificativa": "Nenhuma mídia real encontrada após "
                                             "varredura multi-fonte e expansão de "
                                             "queries — imagem gerada por IA.",
                        },
                    }
                    created += 1
            except Exception:
                continue
        return created

    def _expand_queries(self, storyboard: dict, ctx) -> dict:
        """1 chamada em lote: variações de busca por cena (editor humano)."""
        from modules.claude_client import ask_json

        cenas_min = [
            {"cena_id": c["cena_id"],
             "descricao_visual": c.get("descricao_visual", ""),
             "narracao": c.get("narracao", "")[:120]}
            for c in storyboard.get("cenas", [])
        ]
        kb = ctx.get("knowledge_base", {})
        prompt = f"""Você é o pesquisador de imagens de um grande canal do YouTube.
Para CADA cena abaixo, gere 4 queries de busca ADICIONAIS e diversas:
- 2 em inglês (sinônimos, termos técnicos, nome do evento/pessoa/local exato)
- 1 em português
- 1 lateral (acontecimento/objeto/local RELACIONADO que ilustre a cena)
Queries curtas (2-5 palavras), específicas, buscáveis em bancos de imagem.

ENTIDADES DO TEMA: {json.dumps(kb.get("entidades", {}), ensure_ascii=False)}

CENAS:
{json.dumps(cenas_min, ensure_ascii=False, indent=1)[:6000]}

Retorne APENAS JSON: {{"expansions": [{{"cena_id": 1, "queries": ["...", "...", "...", "..."]}}]}}"""
        data = ask_json(prompt, max_tokens=4000, fallback={"expansions": []})
        return {e["cena_id"]: e.get("queries", [])
                for e in data.get("expansions", []) if "cena_id" in e}
