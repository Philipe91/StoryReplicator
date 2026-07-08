"""
Agente Copywriter — transforma a base de conhecimento em roteiro humano.

Técnicas aplicadas:
- Hook forte nos 3 primeiros segundos (usa o hook_engine para gerar/score-ar)
- Open loops ("mas o que ninguém contava..."), curiosidades espaçadas,
  re-hooks a cada ~30s para retenção
- Anti-IA: frases de comprimento variado, perguntas diretas ao espectador,
  opinião leve, zero clichês de IA ("mergulhe", "vale ressaltar", "além disso")
- CTA curto e natural no fim

Produz: script (dict com segmentos + narração por segmento).
"""

import json
from pathlib import Path

from studio.core import Agent


class CopywriterAgent(Agent):
    name     = "copywriter"
    label    = "Roteiro humano com técnicas de retenção"
    requires = ("knowledge_base",)
    produces = ("script", "narration")

    def run(self, ctx):
        from modules.claude_client import ask_json
        from modules.narration_director import direct as direct_narration

        kb = ctx.get("knowledge_base")
        duration = int(ctx.config.get("duration", 180))
        target_words = int(duration * 2.5)
        notes = ctx.inbox(self.name)
        qa_extra = ("\nCORREÇÕES PEDIDAS PELO REVISOR: "
                    + "; ".join(n["note"] for n in notes)) if notes else ""

        prompt = f"""Você é o roteirista-chefe de um canal grande de documentários no YouTube (estilo Kurzgesagt/Nexo/Ciência Todo Dia: humano, direto, envolvente).

BASE DE CONHECIMENTO (fatos já validados — use SOMENTE isto):
{json.dumps(kb, ensure_ascii=False, indent=1)[:9000]}

Escreva o roteiro narrado de um vídeo de {duration}s (~{target_words} palavras).{qa_extra}

ESTRUTURA OBRIGATÓRIA (retenção):
1. HOOK (0-5s): a frase mais intrigante possível — pergunta, contradição ou número chocante. Nunca "olá pessoal".
2. PROMESSA rápida do que a pessoa vai descobrir.
3. DESENVOLVIMENTO em blocos, cada bloco termina com um gancho para o próximo ("mas isso não foi o pior...").
4. Use as CURIOSIDADES e NÚMEROS MARCANTES da base espaçados pelo vídeo.
5. Momento "plot twist" ou revelação no último terço.
6. Encerramento com reflexão curta + CTA natural (1 frase, sem implorar).

ESTILO ANTI-IA (obrigatório):
- Frases curtas misturadas com médias. Ritmo de fala, não de texto.
- Fale COM o espectador ("você já reparou...", "imagina só").
- Zero clichês de IA: nunca use "mergulhar", "vale ressaltar", "além disso", "é importante notar", "in a world".
- Números por extenso, abreviações expandidas (pronto para TTS).
- Português brasileiro coloquial-culto.

Retorne APENAS este JSON:
{{
  "titulo_interno": "...",
  "segments": [
    {{"id": "hook", "text": "..."}},
    {{"id": "promessa", "text": "..."}},
    {{"id": "bloco_1", "text": "..."}},
    {{"id": "bloco_2", "text": "..."}},
    {{"id": "bloco_3", "text": "..."}},
    {{"id": "revelacao", "text": "..."}},
    {{"id": "encerramento", "text": "..."}},
    {{"id": "cta", "text": "..."}}
  ]
}}"""
        script = ask_json(prompt, max_tokens=6000, fallback={"segments": []})
        if not script.get("segments"):
            raise RuntimeError("Roteiro vazio.")

        # Narração dirigida (pausas dramáticas + plano de prosódia por segmento)
        narration = {
            "narration_full": " ".join(s["text"] for s in script["segments"]),
            "segments": [{"id": s["id"], "text": s["text"]} for s in script["segments"]],
        }
        narration = direct_narration(narration)

        total_w = len(narration["narration_full"].split())
        print(f"  Segmentos: {len(script['segments'])} | Palavras: {total_w} "
              f"(alvo ~{target_words})")

        ctx.set("script", script, self.name)
        ctx.set("narration", narration, self.name)
        _save(ctx, "02_script.json", script)
        _save(ctx, "03_narration.json", narration)


def _save(ctx, name: str, data: dict) -> None:
    (Path(ctx.workdir) / name).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
