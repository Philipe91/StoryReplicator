"""
Agente SEO — pacote completo de publicação para YouTube.

Produz: título, descrição, hashtags, tags, CAPÍTULOS com timestamps reais
(derivados da timeline), palavras-chave, thumbnail renderizada + texto.
"""

import json
from pathlib import Path

from studio.core import Agent


class SEOAgent(Agent):
    name     = "seo"
    label    = "SEO YouTube (título, descrição, capítulos, thumbnail)"
    requires = ("pseudo_story", "timeline")
    produces = ("metadata",)

    def run(self, ctx):
        from modules.publisher_metadata import generate_metadata
        from modules.thumbnail_engine import generate_thumbnails

        workdir  = Path(ctx.workdir)
        story    = ctx.get("pseudo_story")
        timeline = ctx.get("timeline")

        metadata = generate_metadata(story)

        # Capítulos com timestamps REAIS (agrupa cenas por segmento narrativo)
        chapters = self._build_chapters(timeline)
        metadata["capitulos"] = chapters

        # Anexa capítulos à descrição (formato que o YouTube reconhece)
        desc = (metadata.get("descricao") or {}).get("completa", "")
        if chapters and desc:
            cap_txt = "\n".join(f"{c['timestamp']} {c['titulo']}" for c in chapters)
            metadata["descricao"]["completa"] = f"{desc}\n\nCAPÍTULOS:\n{cap_txt}"

        (workdir / "14_metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

        thumbs = generate_thumbnails(timeline, metadata, workdir)
        yt = metadata.get("titulos", {}).get("youtube_shorts", "")
        print(f"  Título: {yt[:60]}")
        print(f"  Capítulos: {len(chapters)} | Thumbnails: {len(thumbs)}")

        ctx.set("metadata", metadata, self.name)

    @staticmethod
    def _build_chapters(timeline: dict) -> list:
        chapters, seen = [], set()
        for sc in timeline.get("scenes", []):
            seg = sc.get("segment", "")
            if seg and seg not in seen:
                seen.add(seg)
                t = int(sc.get("start", 0))
                chapters.append({
                    "timestamp": f"{t//60:d}:{t%60:02d}",
                    "titulo": seg.replace("_", " ").capitalize(),
                })
        return chapters
