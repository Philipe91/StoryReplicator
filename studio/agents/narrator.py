"""
Agente Narrador — voz com prosódia, pausas e emoção.

1. Roda o BENCHMARK automático de motores TTS gratuitos (edge/kokoro/piper):
   naturalidade PT-BR > velocidade > latência. Resultado cacheado.
2. Sintetiza com o vencedor; se falhar, cai para o próximo da cadeia.
3. Com edge: síntese POR SEGMENTO aplicando o prosody_plan (ritmo/tom por
   emoção) + word boundaries REAIS → legendas karaokê exatas.

Produz: audio + word_boundaries + legendas (srt/ass/json).
"""

from pathlib import Path

from studio.core import Agent


class NarratorAgent(Agent):
    name     = "narrador"
    label    = "Narração (benchmark de motores + prosódia)"
    requires = ("narration",)
    produces = ("word_boundaries", "tts_engine")

    def run(self, ctx):
        from studio import tts
        from modules.subtitle_engine import save_subtitles_json

        narration = ctx.get("narration")
        ffmpeg    = ctx.config.get("ffmpeg", "ffmpeg")
        workdir   = Path(ctx.workdir)

        # ── 1. Benchmark automático (cache 7 dias) ────────────────────────────
        bench = tts.benchmark(workdir.parent if workdir.parent.exists() else workdir,
                              ffmpeg=ffmpeg)
        ranking = bench.get("ranking", ["edge"])
        for eng, r in bench.get("results", {}).items():
            if r.get("available"):
                print(f"  [{eng:7s}] RTF={r.get('rtf','?')} "
                      f"naturalidade={r.get('quality_prior','?')} score={r.get('score','?')}")
            else:
                print(f"  [{eng:7s}] indisponível")
        print(f"  Vencedor: {bench.get('winner')} "
              f"(critério: {bench.get('criteria', '')})")

        # ── 2/3. Síntese com fallback em cadeia ──────────────────────────────
        wav, srt, ass, boundaries, used = tts.synthesize(
            narration, workdir, engine_order=ranking or ["edge"], ffmpeg=ffmpeg)

        save_subtitles_json(boundaries, workdir, "MODERN_SHORTS")
        n_segs = len(narration.get("segments", []))
        print(f"  Motor usado: {used} | Segmentos c/ prosódia: {n_segs} | "
              f"Word boundaries: {len(boundaries)}")

        ctx.set("word_boundaries", boundaries, self.name)
        ctx.set("tts_engine", used, self.name)
