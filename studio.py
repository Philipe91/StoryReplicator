#!/usr/bin/env python3
"""
StoryReplicator STUDIO — plataforma multi-agentes de vídeo automático.

Entrada por TEMA (pesquisa na web) em vez de URL:

  python studio.py "história do farol de Alexandria"
  python studio.py "por que o Concorde foi aposentado" --duration 240
  python studio.py "buracos negros" --skip-video          (só assets/roteiro)
  python studio.py --tts-bench                            (só benchmark de vozes)

Pipeline de agentes:
  Pesquisador → Copywriter → Storyboard → MediaScout → Narrador
  → Música → Editor → SEO → Revisor (com loop de retrabalho automático)
"""

import argparse
import os
import re
import time
from pathlib import Path


def _slug(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text.lower()).strip("_")[:40]
    return f"{s}_{int(time.time())}"


def main():
    parser = argparse.ArgumentParser(
        description="StoryReplicator Studio — vídeo automático por tema (multi-agentes)")
    parser.add_argument("theme", nargs="?", help="Tema do vídeo (pesquisado na web)")
    parser.add_argument("--duration", type=int, default=180,
                        help="Duração-alvo em segundos (padrão: 180)")
    parser.add_argument("--renderer", default="remotion",
                        choices=["remotion", "ffmpeg"])
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--skip-video", action="store_true",
                        help="Gerar tudo menos o render final")
    parser.add_argument("--skip-video-search", action="store_true",
                        help="Só imagens (sem busca de vídeo)")
    parser.add_argument("--no-motion", action="store_true",
                        help="Desliga a camada de motion design (HyperFrames)")
    parser.add_argument("--tts-bench", action="store_true",
                        help="Rodar apenas o benchmark de motores TTS e sair")
    parser.add_argument("--qa-rounds", type=int, default=2,
                        help="Máx. de rodadas de retrabalho do QA (padrão: 2)")
    args = parser.parse_args()

    from main import _get_ffmpeg
    ffmpeg = _get_ffmpeg()

    if args.tts_bench:
        from studio import tts
        data = tts.benchmark(Path("."), ffmpeg=ffmpeg, force=True)
        print("\nRanking:", " > ".join(data["ranking"]) or "nenhum motor disponível")
        print("Vencedor:", data["winner"])
        return

    if not args.theme:
        parser.error("informe o tema do vídeo (ou use --tts-bench)")
    from modules.llm_client import any_available, available_providers
    if not any_available():
        raise SystemExit(
            "Nenhum provider de IA configurado. Configure UMA opção GRATUITA:\n"
            "  set GROQ_API_KEY=...        (console.groq.com — grátis, sem cartão)\n"
            "  set GEMINI_API_KEY=...      (aistudio.google.com — grátis, sem cartão)\n"
            "  set OPENROUTER_API_KEY=...  (openrouter.ai — modelos :free)\n"
            "  ou instale o Ollama (ollama.com) para rodar 100% local, sem cadastro.")
    print(f"IA disponível: {', '.join(available_providers())}")

    from config import OUTPUT_DIR
    from studio.core import JobContext, Orchestrator
    from studio.agents.researcher import ResearcherAgent
    from studio.agents.copywriter import CopywriterAgent
    from studio.agents.storyboard import StoryboardAgent
    from studio.agents.media_scout import MediaScoutAgent
    from studio.agents.narrator import NarratorAgent
    from studio.agents.music_agent import MusicAgent
    from studio.agents.editor import EditorAgent
    from studio.agents.seo import SEOAgent
    from studio.agents.reviewer import ReviewerAgent

    workdir = Path(args.output_dir) if args.output_dir else OUTPUT_DIR / _slug(args.theme)
    workdir.mkdir(parents=True, exist_ok=True)

    print("=" * 64)
    print("  StoryReplicator STUDIO — multi-agentes")
    print(f"  Tema: {args.theme}")
    print(f"  Duração-alvo: {args.duration}s | Saída: {workdir}")
    print("=" * 64)

    ctx = JobContext(
        theme=args.theme,
        workdir=workdir,
        config={
            "duration":          args.duration,
            "renderer":          args.renderer,
            "ffmpeg":            ffmpeg,
            "skip_video":        args.skip_video,
            "skip_video_search": args.skip_video_search,
            "motion_design":     not args.no_motion,
        },
    )

    orchestrator = Orchestrator(
        agents=[
            ResearcherAgent(),
            CopywriterAgent(),
            StoryboardAgent(),
            MediaScoutAgent(),
            NarratorAgent(),
            MusicAgent(),
            EditorAgent(),
            SEOAgent(),
        ],
        qa_agent=ReviewerAgent(),
        max_qa_rounds=args.qa_rounds,
        critical=("pesquisador", "copywriter", "storyboard", "narrador"),
    )

    t0 = time.time()
    ctx = orchestrator.run(ctx)

    print("\n" + "=" * 64)
    video = ctx.get("video_path", "")
    qa    = ctx.get("qa_report", {})
    print(f"  CONCLUÍDO em {time.time() - t0:.0f}s | QA: {qa.get('status', '?')}")
    if video:
        print(f"  Vídeo: {video}")
    print(f"  Pasta: {workdir}")
    print("=" * 64)


if __name__ == "__main__":
    main()
