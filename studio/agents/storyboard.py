"""
Agente Storyboard (Diretor) — divide o roteiro em cenas dirigidas.

Para cada cena define: duração, emoção, ritmo, movimento de câmera,
tipo de mídia necessária (vídeo/imagem/documento/animação) e as decisões
cinematográficas do Editor AI (transições, estilo de legenda, b-roll).

Produz: storyboard + edit_decisions + scene_contexts (para a busca de mídia).
"""

import json
from pathlib import Path

from studio.core import Agent


class StoryboardAgent(Agent):
    name     = "storyboard"
    label    = "Divisão em cenas + direção cinematográfica"
    requires = ("script", "narration", "knowledge_base")
    produces = ("storyboard", "edit_decisions", "scene_contexts", "pseudo_story")

    def run(self, ctx):
        from modules.claude_client import ask_json, story_system
        from modules.editor_ai import analyze as editor_analyze, save as editor_save
        from modules.scene_analyzer import analyze_all_scenes

        kb        = ctx.get("knowledge_base")
        narration = ctx.get("narration")
        duration  = int(ctx.config.get("duration", 180))
        interval  = 4 if duration <= 180 else 5
        ideal     = max(8, duration // interval)

        # pseudo_story: adapta a base de conhecimento ao formato que os motores
        # existentes (editor_ai, scene_analyzer, visual engine) já entendem
        pseudo_story = {
            "titulo":            kb.get("tema", ctx.theme),
            "logline":           kb.get("resumo", "")[:200],
            "epoca_local":       " ".join(kb.get("entidades", {}).get("datas_chave", [])[:2]
                                          + kb.get("entidades", {}).get("locais", [])[:2]),
            "historia_completa": kb.get("resumo", ""),
            "personagem_principal": {
                "nome": (kb.get("entidades", {}).get("personagens") or [""])[0]},
        }

        entidades = kb.get("entidades", {})
        prompt = f"""Você é o diretor de um documentário para YouTube.

NARRAÇÃO FINAL (o vídeo segue este texto):
{json.dumps(narration.get("segments", []), ensure_ascii=False, indent=1)[:7000]}

ENTIDADES DO TEMA (use nas descrições visuais): {json.dumps(entidades, ensure_ascii=False)}

Divida em {ideal} a {ideal + 6} cenas (~{interval}s cada, máx 5s). Para cada cena:
- narracao: trecho EXATO da narração coberto pela cena
- emotion: mystery | tension | revelation | triumph | contemplation | curiosity | static
- ritmo: slow | medium | fast (cortes mais rápidos em momentos de ação/escalada)
- descricao_visual: descrição EM INGLÊS, específica e buscável (nomes próprios,
  local, época, objeto — ex: "Apollo 11 Saturn V launch pad 1969 photograph")
- tipo_visual: video | photograph | document | map | newspaper | illustration
- movimento_camera: zoom in | zoom out | pan left | pan right | static
- precisa_animacao: true apenas se um dado/número merecer destaque animado

Retorne APENAS este JSON:
{{
  "total_cenas": 0,
  "cenas": [
    {{"cena_id": 1, "segmento": "hook", "duracao": 4.0,
      "emotion": "mystery", "ritmo": "medium",
      "narracao": "...", "descricao_visual": "...", "tipo_visual": "photograph",
      "movimento_camera": "zoom in", "legenda": "máx 5 palavras",
      "transicao_entrada": "cut|fade|dissolve", "transicao_saida": "cut|fade|dissolve",
      "precisa_animacao": false}}
  ]
}}"""
        storyboard = ask_json(prompt, max_tokens=8000,
                              system=story_system(pseudo_story),
                              fallback={"cenas": []})
        if not storyboard.get("cenas"):
            print("  Storyboard vazio — tentando de novo (retry 1/1)...")
            storyboard = ask_json(prompt, max_tokens=8000,
                                  fallback={"cenas": []})
        if not storyboard.get("cenas"):
            print("  LLM falhou 2x — usando storyboard heurístico (fallback)")
            storyboard = self._heuristic_storyboard(narration, kb, duration)
        if not storyboard.get("cenas"):
            raise RuntimeError("Storyboard vazio.")
        storyboard["total_cenas"] = len(storyboard["cenas"])
        storyboard["duracao_total"] = duration

        # Decisões cinematográficas (câmera/transição/legenda/b-roll) — motor v3.5
        decisions = editor_analyze(storyboard, pseudo_story)
        editor_save(decisions, ctx.workdir)

        # Contextos estruturados por cena (alimentam a busca profunda de mídia)
        contexts = analyze_all_scenes(storyboard, pseudo_story)

        print(f"  Cenas: {storyboard['total_cenas']} | "
              f"Decisões: {len(decisions)} | Contextos: {len(contexts)}")

        ctx.set("storyboard", storyboard, self.name)
        ctx.set("edit_decisions", decisions, self.name)
        ctx.set("scene_contexts", contexts, self.name)
        ctx.set("pseudo_story", pseudo_story, self.name)
        _save(ctx, "04_storyboard.json", storyboard)


    @staticmethod
    def _heuristic_storyboard(narration: dict, kb: dict, duration: int) -> dict:
        """
        Fallback sem LLM: 1-2 cenas por segmento da narração, dividindo por
        frases. descricao_visual = entidades do tema + frase (o MediaScout
        expande as queries depois; a busca ainda funciona).
        """
        import re
        ents = kb.get("entidades", {})
        base_terms = " ".join((ents.get("locais") or [])[:1]
                              + (ents.get("objetos") or [])[:1]
                              + (ents.get("datas_chave") or [])[:1])
        seg_emotion = {"hook": "mystery", "promessa": "curiosity",
                       "revelacao": "revelation", "cta": "static",
                       "encerramento": "contemplation"}
        cenas, cid = [], 0
        for seg in narration.get("segments", []):
            frases = [f.strip() for f in
                      re.split(r"(?<=[.!?])\s+", seg.get("text", "")) if f.strip()]
            # agrupa em blocos de ~2 frases
            for i in range(0, len(frases), 2):
                cid += 1
                trecho = " ".join(frases[i:i + 2])
                cenas.append({
                    "cena_id": cid,
                    "segmento": seg.get("id", ""),
                    "duracao": 5.0,
                    "emotion": seg_emotion.get(seg.get("id", ""), "tension"),
                    "ritmo": "medium",
                    "narracao": trecho,
                    "descricao_visual": f"{base_terms} {trecho[:60]}".strip(),
                    "tipo_visual": "photograph",
                    "movimento_camera": "zoom in" if cid % 2 else "pan right",
                    "legenda": " ".join(trecho.split()[:5]),
                    "transicao_entrada": "fade",
                    "transicao_saida": "fade",
                    "precisa_animacao": False,
                })
        return {"cenas": cenas, "total_cenas": len(cenas),
                "duracao_total": duration, "fallback": "heuristic"}


def _save(ctx, name: str, data: dict) -> None:
    (Path(ctx.workdir) / name).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
