"""
Agente Editor — montagem com ritmo de canal grande.

- Timeline declarativa (JSON) a partir do storyboard + mídia escolhida
- Auditoria de cobertura (vídeo nunca termina antes da voz)
- Zoom/pan por emoção (Ken Burns), transições xfade nos pontos certos,
  legendas modernas queimadas, loudnorm broadcast
- Renderer: Remotion (se instalado) ou FFmpeg — mesma timeline
"""

from pathlib import Path

from studio.core import Agent


class EditorAgent(Agent):
    name     = "editor"
    label    = "Montagem (timeline + transições + legendas + render)"
    requires = ("storyboard", "narration", "image_assignments")
    produces = ("timeline", "video_path")

    def run(self, ctx):
        import json
        from modules.timeline_builder import build_timeline
        from modules.render_auditor import audit_and_fix
        from modules.video_assembler import assemble as ffmpeg_assemble
        import modules.remotion_bridge as remotion_bridge

        workdir  = Path(ctx.workdir)
        ffmpeg   = ctx.config.get("ffmpeg", "ffmpeg")
        renderer = ctx.config.get("renderer", "remotion")
        notes    = ctx.inbox(self.name)
        if notes:
            print(f"  Notas do QA: {[n['note'][:60] for n in notes]}")

        # ── v6.4: voz normalizada + cena cortada NA PALAVRA exata ────────────
        from modules.scene_sync import align_scenes_to_speech, apply_rhythm_transitions
        audio = workdir / "audio.wav"
        boundaries = ctx.get("word_boundaries", [])
        storyboard = dict(ctx.get("storyboard"))

        if boundaries and audio.exists():
            audio_dur = boundaries[-1]["end"] + 0.6
            cenas, n_ok = align_scenes_to_speech(
                storyboard.get("cenas", []), boundaries, audio_dur)
            cenas = apply_rhythm_transitions(cenas, ctx.get("edit_decisions", []))
            storyboard["cenas"] = cenas
            print(f"  Sync fala↔imagem: {n_ok}/{len(cenas)} cenas cortadas "
                  f"na palavra exata (word boundaries)")

        # ── Timeline declarativa ──────────────────────────────────────────────
        mode_like = {"label": f"studio-{ctx.config.get('duration', 180)}s",
                     "duration": int(ctx.config.get("duration", 180))}
        timeline = build_timeline(
            storyboard, ctx.get("narration"),
            {"prompts": []}, mode_like,
            ctx.get("image_assignments"), ctx.get("video_assignments", {}),
        )

        # ── Auditoria: cobertura total do áudio ───────────────────────────────
        audio = workdir / "audio.wav"
        if audio.exists():
            timeline, report = audit_and_fix(timeline, str(audio), ffmpeg)
            print(f"  Áudio {report.get('audio_duration', 0):.1f}s | "
                  f"cobertura {report.get('coverage_pct', 0):.0f}%")
            for fix in report.get("fixes_applied", []):
                print(f"  FIX: {fix}")

        (workdir / "timeline.json").write_text(
            json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")

        if ctx.config.get("skip_video"):
            print("  Render pulado (skip_video).")
            ctx.set("timeline", timeline, self.name)
            ctx.set("video_path", "", self.name)
            return

        # ── Render (Remotion premium → FFmpeg garantido) ──────────────────────
        video_path = ""
        if renderer == "remotion" and remotion_bridge.is_available():
            print("  Renderer: Remotion (React)")
            video_path = remotion_bridge.render(workdir) or ""
            if not video_path:
                print("  Remotion falhou — caindo para FFmpeg")
        if not video_path:
            print("  Renderer: FFmpeg (xfade + Ken Burns + legendas + loudnorm)")
            video_path = ffmpeg_assemble(timeline, workdir, ffmpeg_exe=ffmpeg)

        # ── Motion design (HyperFrames): cards animados sincronizados à voz ──
        if video_path and ctx.config.get("motion_design", True):
            try:
                from modules.motion_design import apply_motion_design
                print("  Motion design (HyperFrames): desenhando cards...")
                enhanced = apply_motion_design(
                    video_path, ctx.get("narration", {}),
                    ctx.get("word_boundaries", []), workdir, ffmpeg=ffmpeg)
                if enhanced:
                    video_path = enhanced
                    print(f"  Overlays aplicados: {Path(enhanced).name} "
                          f"(original em final_video_plain.mp4)")
                else:
                    print("  Motion design falhou — mantendo vídeo sem overlays")
            except Exception as e:
                print(f"  [motion] {e} — mantendo vídeo sem overlays")

        ctx.set("timeline", timeline, self.name)
        ctx.set("video_path", str(video_path), self.name)

