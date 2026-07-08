"""
Agente de Música — trilha adaptativa + efeitos sonoros + ambiência.

- Emoção dominante do storyboard → categoria musical (motor v3.7)
- Fontes gratuitas: biblioteca local (music_library/), Jamendo API (se houver
  JAMENDO_CLIENT_ID grátis) e Internet Archive
- Mixagem com DUCKING (música abaixa quando há voz — nunca compete)
- SFX contextuais (Freesound/Archive) sobrepostos nos momentos certos
"""

import os
from pathlib import Path

from studio.core import Agent


class MusicAgent(Agent):
    name     = "musica"
    label    = "Trilha sonora adaptativa + SFX + ducking"
    requires = ("storyboard", "edit_decisions")
    produces = ("music_info",)

    def run(self, ctx):
        import shutil
        from modules.music_engine import MusicEngine, mix_audio
        from modules.sound_design_engine import SoundDesignEngine

        workdir    = Path(ctx.workdir)
        ffmpeg     = ctx.config.get("ffmpeg", "ffmpeg")
        audio_path = workdir / "audio.wav"
        music_info = {"applied": False}

        if not audio_path.exists():
            print("  Sem narração — pulando música.")
            ctx.set("music_info", music_info, self.name)
            return

        storyboard     = ctx.get("storyboard")
        edit_decisions = ctx.get("edit_decisions")

        # ── Trilha ────────────────────────────────────────────────────────────
        try:
            mengine  = MusicEngine(output_dir=workdir)
            emo      = mengine.analyze_dominant_emotion(storyboard, edit_decisions)
            category = emo["dominant"]
            print(f"  Emoção dominante: {category} ({emo['distribution']})")

            track = self._local_library_track(category) \
                or mengine.select_track(category, min_duration=30.0)
            if track:
                narration_only = workdir / "narration_only.wav"
                if not narration_only.exists():
                    shutil.copy2(audio_path, narration_only)
                local = track if isinstance(track, Path) else workdir / track.local_path
                ok = mix_audio(narration_only, local, audio_path,
                               ffmpeg_exe=ffmpeg, duck=True)
                title = track.name if isinstance(track, Path) else track.title
                music_info = {"applied": ok, "category": category,
                              "title": str(title)[:60], "ducking": True}
                print(f"  Trilha: {str(title)[:50]} | ducking: "
                      f"{'ok' if ok else 'falhou'}")
            else:
                print("  Nenhuma trilha encontrada — só narração.")
        except Exception as e:
            print(f"  [música] {e} — seguindo sem trilha")

        # ── SFX contextuais ───────────────────────────────────────────────────
        try:
            sde  = SoundDesignEngine(output_dir=workdir)
            cues = sde.detect_cues(storyboard)
            if cues:
                cues = sde.acquire(cues)
                if cues:
                    mixed = workdir / "audio_sfx.wav"
                    if sde.mix_into_audio(audio_path, cues, mixed, ffmpeg_exe=ffmpeg):
                        shutil.copy2(mixed, audio_path)
                        music_info["sfx"] = len(cues)
                sde.save_report(cues)
            print(f"  SFX aplicados: {music_info.get('sfx', 0)}")
        except Exception as e:
            print(f"  [sfx] {e} — sem efeitos")

        ctx.set("music_info", music_info, self.name)

    def _local_library_track(self, category: str):
        """
        Biblioteca local royalty-free (music_library/<CATEGORIA>/*.mp3).
        Mais confiável que APIs: o usuário baixa 1x lotes do Pixabay Music /
        YouTube Audio Library / Incompetech e organiza por categoria.
        """
        lib = Path(__file__).resolve().parents[2] / "music_library" / category.upper()
        if lib.exists():
            tracks = sorted(lib.glob("*.mp3")) + sorted(lib.glob("*.wav"))
            if tracks:
                import random
                return random.choice(tracks)
        return None
