#!/usr/bin/env python3
"""
StoryReplicator v3.5 — Remotion + Editor AI + Documentários profissionais.

Uso:
  python main.py <url> [--mode micro|short|documentary|epic]
                        [--renderer remotion|ffmpeg]
                        [--skip-video] [--skip-images]

Modos:
  micro        60s   — TikTok / Shorts rápido
  short       120s   — YouTube Shorts / Reels
  documentary 180s   — Documentário (PADRÃO)
  epic        360s   — Narrativa épica completa

Renderizadores:
  remotion    Remotion (React) — qualidade premium, requer Node.js (PADRÃO)
  ffmpeg      FFmpeg — compatibilidade máxima, fallback automático
"""

import argparse
import json
import os
import time
from pathlib import Path

if not os.getenv("ANTHROPIC_API_KEY"):
    print("[AVISO] ANTHROPIC_API_KEY não definida.")
    print("  Etapas de IA (análise, roteiro, narração) serão ignoradas.")
    print("  Para uso completo: set ANTHROPIC_API_KEY=sk-ant-...")
    print()

from config import OUTPUT_DIR, get_mode
from modules.extractor              import extract
from modules.analyzer               import analyze
from modules.story_generator        import generate_story
from modules.script_writer          import write_script
from modules.narration_writer       import write_narration
from modules.storyboard_generator   import generate_storyboard
from modules.scene_analyzer         import analyze_all_scenes
from modules.editor_ai              import analyze as editor_ai_analyze, save as editor_ai_save   # v3.5
from modules.hook_engine            import generate_hooks, select_best, save_hooks                # v4.0
from modules.retention_engine       import analyze as retention_analyze, save_report as save_retention  # v4.0
from modules.narration_director     import direct as direct_narration, save_directed              # v4.0
import modules.character_engine      as character_engine                                          # v4.0
import modules.map_engine            as map_engine                                                # v4.0
import modules.newspaper_engine      as newspaper_engine                                          # v4.0
from modules.sound_design_engine    import SoundDesignEngine                                      # v4.0
from modules.visual_asset_engine    import UniversalVisualEngine, save_reports, extract_assignments  # v3.6
from modules.music_engine            import MusicEngine, mix_audio                                    # v3.7
from modules.visual_prompts         import generate_visual_prompts, export_prompts_txt
from modules.timeline_builder       import build_timeline
from modules.subtitle_engine        import synthesize_with_subtitles, save_subtitles_json         # v3.5
from modules.render_auditor         import audit_and_fix
from modules.video_assembler        import assemble as ffmpeg_assemble
from modules.publisher_metadata     import generate_metadata
from modules.quality_reporter       import generate as generate_quality_report
import modules.remotion_bridge      as remotion_bridge                                            # v3.5


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _banner(mode_config: dict):
    print("\n" + "="*64)
    print("  StoryReplicator v3.0  —  Histórias Reais Inacreditáveis")
    print(f"  Modo: {mode_config['label']} | {mode_config['target_words']} palavras-alvo")
    print("="*64 + "\n")


def _step(n: int, label: str):
    print(f"\n[ETAPA {n:02d}] {label}")
    print("-" * 54)


def _save(data: dict, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Salvo: {path.name}")


def _slug(url: str) -> str:
    import re
    return re.sub(r"[^a-zA-Z0-9]", "_", url)[:40] + f"_{int(time.time())}"


def _fmt(n: int) -> str:
    if n > 1_048_576: return f"{n/1_048_576:.1f}MB"
    if n > 1024:      return f"{n/1024:.0f}KB"
    return f"{n}B"


def _get_ffmpeg() -> str:
    """Retorna caminho do FFmpeg (PATH ou imageio_ffmpeg)."""
    import shutil
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


# ─── Pipeline principal ───────────────────────────────────────────────────────

def run(
    url: str,
    mode_name: str = "documentary",
    renderer: str = "remotion",
    skip_video: bool = False,
    skip_images: bool = False,
    skip_video_search: bool = False,
    output_dir: Path = None,
    langs: list = None,
    mode_override: dict = None,
) -> Path:

    langs   = langs or ["pt"]
    # mode_override (Format Manager via API) tem prioridade sobre mode_name
    mode    = mode_override if mode_override else get_mode(mode_name)
    ffmpeg  = _get_ffmpeg()
    _banner(mode)
    t0 = time.time()

    out    = Path(output_dir) if output_dir else OUTPUT_DIR / _slug(url)
    assets = out / "assets"
    out.mkdir(parents=True, exist_ok=True)
    assets.mkdir(parents=True, exist_ok=True)

    print(f"  URL:    {url}")
    print(f"  Output: {out}")
    print(f"  FFmpeg: {ffmpeg}")

    # ── ETAPA 01: Extração ────────────────────────────────────────────────────
    _step(1, "Extração de dados do YouTube")
    video = extract(url)
    print(f"  Título:     {video.title}")
    print(f"  Duração:    {video.duration}s  |  Views: {video.view_count:,}")
    _save(vars(video), out / "01_video_data.json")

    # ── ETAPA 02: Análise narrativa ───────────────────────────────────────────
    _step(2, "Análise da estrutura narrativa")
    analysis = analyze(video)
    print(f"  Tema:  {analysis.get('tema_central','?')[:60]}")
    _save(analysis, out / "02_analysis.json")

    # ── ETAPA 03: Nova história ───────────────────────────────────────────────
    _step(3, "Nova história original")
    story = generate_story(analysis)
    print(f"  Título:  {story.get('titulo','?')}")
    print(f"  Logline: {str(story.get('logline','?'))[:70]}")
    _save(story, out / "03_story.json")

    # ── ETAPA 03b: Hook Intelligence — v4.0 ───────────────────────────────────
    _step(3, "Hook Intelligence — 3 hooks + score (v4.0)")
    hooks     = generate_hooks(story, analysis, n=3)
    best_hook = select_best(hooks)
    save_hooks(hooks, best_hook, out)
    for h in hooks:
        mark = "★" if h.text == best_hook.text else " "
        print(f"  {mark} [{h.style:9s}] score={h.total:.1f} (cur={h.curiosity} imp={h.impact} ret={h.retention}) {h.text[:45]}")
    # Injeta o melhor hook na história
    if best_hook.text:
        story.setdefault("estrutura", {})["hook"] = best_hook.text
        _save(story, out / "03_story.json")

    # ── ETAPA 04: Roteiro ─────────────────────────────────────────────────────
    _step(4, f"Roteiro profissional — {mode['label']}")
    script = write_script(story, mode)
    print(f"  Segmentos: {len(script.get('segmentos',[]))}")
    _save(script, out / "04_script.json")

    # ── ETAPA 05: Narração ────────────────────────────────────────────────────
    _step(5, f"Narração TTS — alvo {mode['target_words']} palavras")
    narration = write_narration(script, mode)
    total_w   = sum(s.get("word_count", 0) for s in narration.get("segments", []))
    print(f"  Palavras: {total_w}  |  Preview: {narration.get('narration_full','')[:80]}...")
    _save(narration, out / "05_narration.json")

    # ── ETAPA 05b: Narration Director — humaniza a narração (v4.0) ────────────
    _step(5, "Narration Director — pausas, ritmo, suspense (v4.0)")
    narration = direct_narration(narration)
    save_directed(narration, out)
    _save(narration, out / "05_narration.json")
    print(f"  Narração dirigida (pausas/ritmo aplicados)")
    print(f"  Preview: {narration.get('narration_full','')[:90]}...")

    # ── ETAPA 06: Storyboard granular ─────────────────────────────────────────
    _step(6, "Storyboard (cenas ~4s + emoção)")
    storyboard = generate_storyboard(narration, story, mode)
    print(f"  Cenas: {storyboard.get('total_cenas', 0)}  "
          f"(intervalo alvo: {mode.get('scene_interval',4)}s)")
    _save(storyboard, out / "06_storyboard.json")

    # ── ETAPA 06b: Retention Engine — análise pré-render (v4.0) ───────────────
    _step(6, "Retention Engine — score 0-100 + sugestões (v4.0)")
    retention = retention_analyze(narration, storyboard, hook_score=best_hook.total)
    save_retention(retention, out)
    print(f"  RETENTION SCORE: {retention.score}/100")
    print(f"  (ritmo={retention.pace_score} tensão={retention.tension_score} "
          f"exposição={retention.exposition_score} hook={retention.hook_score})")
    for s in retention.suggestions[:3]:
        print(f"  → {s}")

    # ── ETAPA 07: Scene Analyzer — P1 ─────────────────────────────────────────
    _step(7, "Análise estruturada de cenas (P1)")
    scene_contexts = analyze_all_scenes(storyboard, story)
    print(f"  Contextos extraídos: {len(scene_contexts)}")
    ctx_data = {cid: vars(ctx) for cid, ctx in scene_contexts.items()}
    _save(ctx_data, out / "07_scene_contexts.json")

    # ── ETAPA 07a: Inteligência Visual — Character / Map / Newspaper (v4.0) ────
    _step(7, "Inteligência Visual: personagens, mapas, jornais")
    characters = character_engine.analyze(story, storyboard)
    character_engine.save(characters, out)
    map_cues = map_engine.analyze(storyboard, story)
    map_engine.save(map_cues, out)
    news_cues = newspaper_engine.analyze(storyboard, story)
    newspaper_engine.save(news_cues, out)
    # Injeta queries de mapa/jornal como prioridade nas cenas certas —
    # alimenta o visual engine (characters.json fica salvo p/ a interface).
    for c in map_cues:
        if c.scene_id in scene_contexts and c.search_terms:
            scene_contexts[c.scene_id].search_queries.insert(0, c.search_terms[0])
    for c in news_cues:
        if c.scene_id in scene_contexts and c.search_terms:
            scene_contexts[c.scene_id].search_queries.insert(0, c.search_terms[0])
    print(f"  Personagens: {len(characters)} | Mapas: {len(map_cues)} | Jornais: {len(news_cues)}")

    # ── ETAPA 07b: Editor AI — v3.5 ───────────────────────────────────────────
    _step(7, "Editor AI — decisões cinematográficas por cena (v3.5)")
    edit_decisions = editor_ai_analyze(storyboard, story)
    editor_ai_save(edit_decisions, out)
    broll_needed = sum(1 for d in edit_decisions if d.broll_needed)
    styles_used  = sorted({d.subtitle_style for d in edit_decisions})
    print(f"  Decisões:      {len(edit_decisions)} cenas")
    print(f"  B-roll marcado:{broll_needed} cenas")
    print(f"  Estilos legenda:{', '.join(styles_used)}")

    # ── ETAPA 08: Universal Visual Asset Engine — v3.6 ────────────────────────
    image_assignments, video_assignments = {}, {}
    if not skip_images:
        _step(8, "Universal Visual Asset Engine (vídeo + imagem + documento)")
        uengine    = UniversalVisualEngine(output_dir=out, prefer_video=not skip_video_search,
                                           ffmpeg_exe=ffmpeg)
        va_result  = uengine.run(storyboard, story, scene_contexts)
        save_reports(va_result, out)
        image_assignments, video_assignments = extract_assignments(va_result)
        print(f"\n  {va_result['found']}/{va_result['total_scenes']} ativos "
              f"({va_result['success_rate']}%)")
        print(f"  Vídeos: {va_result['video_count']} | Imagens: {va_result['image_count']} "
              f"| Históricos: {va_result['historical_assets_count']} "
              f"| Docs: {va_result['document_count']}")
        print(f"  Mix: {va_result.get('mix_pct', {})}  (alvo {va_result.get('mix_target', {})})")
        print(f"  Fontes: {', '.join(va_result.get('sources_used', []))}")
    else:
        print("\n[ETAPA 08] Aquisição de ativos ignorada (--skip-images)")
        va_result = {"found": 0, "total_scenes": 0, "missing": 0, "success_rate": 0,
                     "video_count": 0, "image_count": 0, "historical_assets_count": 0,
                     "document_count": 0, "sources_used": [], "assignments": {}}

    # ── ETAPA 10: Visual Prompts (fallback manual) ────────────────────────────
    _step(10, "Prompts visuais para imagens faltantes")
    visual_prompts = generate_visual_prompts(storyboard)
    print(f"  Prompts: {len(visual_prompts.get('prompts', []))}")
    _save(visual_prompts, out / "10_visual_prompts.json")
    export_prompts_txt(visual_prompts, str(out / "10_image_prompts.txt"))

    # ── ETAPA 11: Timeline JSON ───────────────────────────────────────────────
    _step(11, "Timeline JSON")
    timeline = build_timeline(
        storyboard, narration, visual_prompts, mode,
        image_assignments, video_assignments,
    )
    print(f"  Cenas: {len(timeline.get('scenes', []))}  |  "
          f"Duração: {timeline['total_duration']}s")
    _save(timeline, out / "timeline.json")

    # ── ETAPA 12: TTS com word boundaries — P5 ────────────────────────────────
    _step(12, "Síntese de voz + legendas profissionais (P5)")
    narration_text = narration.get("narration_full", "")
    word_boundaries = []
    if narration_text:
        try:
            wav_path, srt_path, ass_path, word_boundaries = synthesize_with_subtitles(
                narration_text, out, ffmpeg_exe=ffmpeg
            )
            print(f"  Audio:     {wav_path.name}  ({wav_path.stat().st_size // 1024}KB)")
            print(f"  Legendas:  {srt_path.name} + {ass_path.name}  "
                  f"({len(word_boundaries)} word boundaries)")
            # subtitles.json para Remotion (word-level timing)
            dominant_style = styles_used[0] if styles_used else "CINEMATIC"
            sub_json_path  = save_subtitles_json(word_boundaries, out, dominant_style)
            print(f"  subtitles.json: {Path(sub_json_path).name}")
        except Exception as e:
            print(f"  [TTS] Erro: {e} — gerando silêncio placeholder")
            _generate_silence_wav(out / "audio.wav")
    else:
        print("  Narração vazia, ignorando TTS.")

    # ── ETAPA 12b: Adaptive Music Engine — v3.7 ───────────────────────────────
    music_info = {"applied": False}
    audio_path = out / "audio.wav"
    if audio_path.exists() and not skip_video:
        _step(12, "Adaptive Music Engine — trilha sonora contextual (v3.7)")
        try:
            mengine   = MusicEngine(output_dir=out)
            emo       = mengine.analyze_dominant_emotion(storyboard, edit_decisions)
            category  = emo["dominant"]
            print(f"  Emoção dominante: {category}  (distribuição: {emo['distribution']})")
            track = mengine.select_track(category, min_duration=30.0)
            if track:
                # Backup da narração pura e mixagem com música + ducking
                narration_only = out / "narration_only.wav"
                if not narration_only.exists():
                    import shutil; shutil.copy2(audio_path, narration_only)
                ok = mix_audio(narration_only, out / track.local_path, audio_path,
                               ffmpeg_exe=ffmpeg, duck=True)
                music_info = {
                    "applied":      ok,
                    "category":     category,
                    "source":       track.source,
                    "title":        track.title,
                    "ducking":      True,
                    "music_volume": 0.16,
                }
                print(f"  Trilha: [{track.source}] {track.title[:50]}")
                print(f"  Mixagem: {'OK (ducking)' if ok else 'falhou — narração pura'}")
            else:
                print("  Nenhuma trilha encontrada — seguindo só com narração")
        except Exception as e:
            print(f"  [música] erro: {e} — seguindo só com narração")

    # ── ETAPA 12c: Sound Design Engine — SFX contextuais (v4.0) ───────────────
    sfx_info = {"applied": False, "cues": 0}
    if audio_path.exists() and not skip_video:
        _step(12, "Sound Design — efeitos sonoros contextuais (v4.0)")
        try:
            sde  = SoundDesignEngine(output_dir=out)
            cues = sde.detect_cues(storyboard)
            if cues:
                cues = sde.acquire(cues)
                if cues:
                    mixed = out / "audio_sfx.wav"
                    if sde.mix_into_audio(audio_path, cues, mixed, ffmpeg_exe=ffmpeg):
                        import shutil; shutil.copy2(mixed, audio_path)
                        sfx_info = {"applied": True, "cues": len(cues),
                                    "categories": sorted({c.category for c in cues})}
                sde.save_report(cues)
            print(f"  SFX aplicados: {sfx_info['cues']} "
                  f"({', '.join(sfx_info.get('categories', [])) or 'nenhum'})")
        except Exception as e:
            print(f"  [sfx] erro: {e} — seguindo sem efeitos")

    # ── ETAPA 13: Auditoria de renderização — P8 ──────────────────────────────
    _step(13, "Auditoria de renderização (P8)")
    audio_path = out / "audio.wav"
    if audio_path.exists():
        timeline, audit_report = audit_and_fix(timeline, str(audio_path), ffmpeg)
        _save(timeline, out / "timeline.json")  # salva versão corrigida
        _save(audit_report, out / "13_audit_report.json")
        print(f"  Áudio:    {audit_report.get('audio_duration', 0):.1f}s")
        print(f"  Timeline: {audit_report.get('timeline_duration', 0):.1f}s")
        print(f"  Cobertura: {audit_report.get('coverage_pct', 0):.0f}%")
        if audit_report.get("fixes_applied"):
            for fix in audit_report["fixes_applied"]:
                print(f"  FIX: {fix}")
    else:
        print("  Sem áudio — auditoria ignorada.")
        audit_report = {}

    # ── ETAPA 14: Metadados de publicação ─────────────────────────────────────
    _step(14, "Metadados de publicação")
    metadata = generate_metadata(story)
    _save(metadata, out / "14_metadata.json")
    yt    = metadata.get("titulos", {}).get("youtube_shorts", story.get("titulo", ""))
    tags  = metadata.get("hashtags", {}).get("principais", [])
    print(f"  YouTube: {yt}")
    print(f"  Tags:    {' '.join(tags[:5])}")
    _export_metadata_txt(metadata, out / "14_metadata.txt")

    # ── ETAPA 15: Montagem ────────────────────────────────────────────────────
    final_path = out / "final_video.mp4"
    if not skip_video:
        use_remotion = (renderer == "remotion") and remotion_bridge.is_available()
        if use_remotion:
            _step(15, "Montagem — Remotion (React renderer) [v3.5]")
            video_path = remotion_bridge.render(out) or ""
            if not video_path:
                print("  Remotion falhou — usando FFmpeg como fallback")
                use_remotion = False
        if not use_remotion:
            _step(15, "Montagem — FFmpeg + movimentos cinematográficos")
            video_path = ffmpeg_assemble(timeline, out, ffmpeg_exe=ffmpeg)
        print(f"  Vídeo final: {Path(video_path).name if video_path else 'não gerado'}")
    else:
        print("\n[ETAPA 15] Montagem ignorada (--skip-video)")
        video_path = str(final_path)

    # ── ETAPA 16: Relatório de qualidade — P9 ────────────────────────────────
    _step(16, "Relatório de qualidade (P9)")
    audio_dur = audit_report.get("audio_duration", 0.0)
    q_report  = generate_quality_report(
        timeline, audio_dur, va_result, video_path, out, ffmpeg,
        edit_decisions=edit_decisions, scene_contexts=scene_contexts,
        visual_assets_result=va_result, music_info=music_info,
        hook_score=best_hook.total, retention_score_100=retention.score,
    )
    _print_quality_summary(q_report)

    # ── ETAPA 17: Versões multi-idioma — v3.8 (sob demanda) ───────────────────
    extra_langs = [l for l in (langs or ["pt"]) if l != "pt"]
    if extra_langs and not skip_video:
        _step(17, f"Versões adicionais de idioma: {', '.join(extra_langs)}")
        from modules.multilang import generate_all_languages
        music_path = out / "music.mp3"
        results = generate_all_languages(
            extra_langs, out,
            storyboard=storyboard, narration=narration, metadata=metadata,
            mode_config=mode, image_assignments=image_assignments,
            video_assignments=video_assignments,
            music_path=music_path if music_path.exists() else None,
            ffmpeg_exe=ffmpeg, skip_video=skip_video,
        )
        for r in results:
            print(f"  [{r['lang']}] {r.get('status')}: {r.get('video_path','')}")

    # ── Sumário final ─────────────────────────────────────────────────────────
    elapsed = time.time() - t0
    print("\n" + "="*64)
    print(f"  CONCLUÍDO em {elapsed:.1f}s  |  Modo: {mode['label']}")
    print(f"  Score geral: {q_report['scores']['overall']}/10")
    print(f"  Pasta: {out}")
    for f in sorted(out.glob("*")):
        if f.is_file() and not f.name.startswith("clip_") and f.name not in ("concat_list.txt", "raw_video.mp4", "audio_tmp.mp3"):
            print(f"    {f.name:<40} {_fmt(f.stat().st_size)}")
    print("="*64 + "\n")

    return out


# ─── Utilitários ──────────────────────────────────────────────────────────────

def _generate_silence_wav(path: Path, duration: int = 180, sr: int = 24000):
    import wave
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(b"\x00\x00" * sr * duration)


def _export_metadata_txt(metadata: dict, path: Path):
    lines = []
    for plat, titulo in (metadata.get("titulos") or {}).items():
        lines += [f"[{plat.upper()}]", titulo, ""]
    desc = metadata.get("descricao") or {}
    lines += ["[DESCRIÇÃO]", desc.get("completa", ""), ""]
    all_tags = (
        (metadata.get("hashtags") or {}).get("principais", [])
        + (metadata.get("hashtags") or {}).get("nicho", [])
        + (metadata.get("hashtags") or {}).get("trending", [])
    )
    lines += ["[HASHTAGS]", " ".join(all_tags), ""]
    thumb = metadata.get("thumbnail") or {}
    lines += ["[THUMBNAIL]", thumb.get("prompt_principal", ""), "", f"Texto: {thumb.get('texto_sobreposicao','')}"]
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Metadados TXT: {path.name}")


def _print_quality_summary(report: dict):
    scores = report.get("scores", {})
    status = report.get("status", "?")
    symbols = {"excellent": "EXCELENTE", "good": "BOM", "needs_work": "MELHORAR"}
    print(f"  Status:     {symbols.get(status, status)}")
    print(f"  Visual:        {scores.get('visual', 0)}/10")
    print(f"  Sync:          {scores.get('sync', 0)}/10")
    print(f"  Narrativa:     {scores.get('narrative', 0)}/10")
    print(f"  Variedade:     {scores.get('visual_variety_score', 0)}/10")
    print(f"  Câmera:        {scores.get('camera_movement_score', 0)}/10")
    print(f"  Legendas:      {scores.get('subtitle_quality_score', 0)}/10")
    print(f"  Hist. acc.:    {scores.get('historical_accuracy_score', 0)}/10")
    print(f"  Retenção:      {scores.get('retention_estimate', 0)}/10")
    print(f"  GERAL:         {scores.get('overall', 0)}/10")
    print(f"  --- Ativos (v3.6) ---")
    print(f"  Vídeos: {report.get('video_count',0)} | Imagens: {report.get('image_count',0)} "
          f"| Históricos: {report.get('historical_assets_count',0)} "
          f"| Docs: {report.get('document_count',0)} | B-roll: {report.get('broll_count',0)}")
    print(f"  Cobertura: {report.get('coverage_score',0)}/10  Mix: {report.get('asset_mix_pct',{})}")
    print(f"  --- Qualidade Visual (v3.7) ---")
    print(f"  Qualidade: {scores.get('visual_quality_score',0)}/10  "
          f"Rejeitados: {report.get('low_resolution_rejected',0)}  "
          f"Upscaled: {report.get('upscaled_assets',0)}  "
          f"Res.média: {report.get('average_resolution','?')}")
    print(f"  --- Trilha Sonora (v3.7) ---")
    print(f"  Música: {report.get('music_category','none')} [{report.get('music_source','none')}] "
          f"score={scores.get('music_score',0)}/10  balanço={scores.get('audio_balance_score',0)}/10")
    print(f"  --- Retenção (v4.0) ---")
    print(f"  RETENTION SCORE: {report.get('retention_score','?')}/100  "
          f"Hook: {report.get('hook_score','?')}/10  CTR estimado: {report.get('estimated_ctr','?')}")
    if report.get("issues"):
        for issue in report["issues"]:
            print(f"  [!] {issue}")


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="StoryReplicator v3.5 — Remotion + Editor AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemplos:\n"
            "  python main.py https://youtu.be/XXXXX\n"
            "  python main.py https://youtu.be/XXXXX --renderer remotion\n"
            "  python main.py https://youtu.be/XXXXX --renderer ffmpeg --mode short\n"
            "  python main.py https://youtu.be/XXXXX --mode epic --skip-video\n"
            "  python main.py https://youtu.be/XXXXX --skip-images\n"
        ),
    )
    parser.add_argument("url")
    parser.add_argument("--format", default=None,
                        choices=["micro_story","short_documentary","documentary",
                                 "long_documentary","custom"],
                        help="Formato (Format Manager v4.0). Padrão: micro_story")
    parser.add_argument("--duration", type=int, default=None,
                        help="Duração-alvo em segundos (30-300). Sobrepõe o padrão do formato")
    parser.add_argument("--mode", default=None,
                        choices=["micro","short","documentary","epic"],
                        help="(legado) modo fixo; prefira --format")
    parser.add_argument("--renderer", default="remotion",
                        choices=["remotion","ffmpeg"],
                        help="remotion=premium (padrão) | ffmpeg=compatibilidade")
    parser.add_argument("--skip-video",        action="store_true")
    parser.add_argument("--skip-images",       action="store_true")
    parser.add_argument("--skip-video-search", action="store_true",
                        help="Pular busca de vídeos históricos")
    parser.add_argument("--output-dir",        default=None)
    parser.add_argument("--langs", default="pt",
                        help="Idiomas separados por vírgula (ex: pt,en,es). Padrão: pt")
    args = parser.parse_args()

    # Format Manager: se --format ou --duration, resolve um mode dinâmico
    mode_override = None
    if args.format or args.duration:
        from config import resolve_format
        mode_override = resolve_format(args.format, args.duration)

    run(
        url=args.url,
        renderer=args.renderer,
        mode_name=args.mode or "documentary",
        skip_video=args.skip_video,
        skip_images=args.skip_images,
        skip_video_search=args.skip_video_search,
        output_dir=args.output_dir,
        langs=[l.strip() for l in args.langs.split(",") if l.strip()],
        mode_override=mode_override,
    )
