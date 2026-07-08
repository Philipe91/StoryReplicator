"""
v5.0 — Explainer Pipeline (modo NotebookLM).

Fluxo "Video Overview": URL do YouTube → transcrição → deck de slides
didáticos (Claude) → narração por slide (edge-tts com prosódia/timestamps
reais) → slides PNG (Pillow) → montagem FFmpeg com xfade + legendas + música.

A duração de cada slide é ditada pela duração REAL do áudio da sua narração
(mesma sincronização do NotebookLM). Reusa todo o motor existente do pipeline.

Uso: python main.py <url> --style explainer [--theme deep|paper|ocean]
"""

import json
import time
from pathlib import Path

from config import OUTPUT_DIR


def run_explainer(
    url: str,
    output_dir: Path = None,
    theme: str = "deep",
    skip_video: bool = False,
    with_music: bool = True,
) -> Path:
    from main import _get_ffmpeg, _save, _slug, _step
    from modules.extractor import extract
    from modules.explainer_generator import generate_deck, deck_to_narration
    from modules.slide_renderer import render_deck
    from modules.subtitle_engine import synthesize_narration_directed, save_subtitles_json
    from modules.publisher_metadata import generate_metadata
    from modules.thumbnail_engine import generate_thumbnails
    from modules.video_assembler import assemble as ffmpeg_assemble

    ffmpeg = _get_ffmpeg()
    out    = Path(output_dir) if output_dir else OUTPUT_DIR / _slug(url)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    print("\n" + "=" * 64)
    print("  StoryReplicator v5.0 — MODO EXPLAINER (estilo NotebookLM)")
    print(f"  Tema visual: {theme}")
    print("=" * 64)

    # ── 1. Extração ───────────────────────────────────────────────────────────
    _step(1, "Extração de dados do YouTube")
    video = extract(url)
    print(f"  Título: {video.title}")
    _save(vars(video), out / "01_video_data.json")

    # ── 2. Deck de slides ─────────────────────────────────────────────────────
    _step(2, "Deck de slides didáticos (Claude)")
    deck = generate_deck(vars(video))
    if not deck.get("slides"):
        raise RuntimeError("Deck vazio — verifique a transcrição/chave de API.")
    print(f"  Deck: {deck.get('titulo_deck', '?')}  |  {len(deck['slides'])} slides")
    for s in deck["slides"]:
        print(f"    {s['id']:02d} [{s['layout']:7s}] {s.get('titulo', '')[:50]}")
    _save(deck, out / "02_deck.json")

    # ── 3. Narração por slide (prosódia + word boundaries reais) ─────────────
    _step(3, "Narração por slide (edge-tts + timestamps reais)")
    narration = deck_to_narration(deck)
    wav_path, srt_path, ass_path, boundaries = synthesize_narration_directed(
        narration, out, ffmpeg_exe=ffmpeg
    )
    save_subtitles_json(boundaries, out, "DOCUMENTARY")
    audio_dur = _wav_duration(wav_path)
    print(f"  Áudio: {audio_dur:.1f}s  |  {len(boundaries)} word boundaries")

    # ── 4. Slides PNG ─────────────────────────────────────────────────────────
    _step(4, f"Renderização dos slides (Pillow, tema '{theme}')")
    slide_paths = render_deck(deck, out, theme=theme)
    print(f"  Slides renderizados: {len(slide_paths)}")

    # ── 5. Timeline sincronizada pelo áudio ───────────────────────────────────
    _step(5, "Timeline (duração do slide = duração da narração)")
    timeline = _build_slide_timeline(deck, slide_paths, boundaries, audio_dur)
    _save(timeline, out / "timeline.json")
    for sc in timeline["scenes"]:
        print(f"    slide {sc['scene_id']:02d}: {sc['start']:6.2f}s → {sc['end']:6.2f}s")

    # ── 6. Trilha sonora discreta (opcional) ──────────────────────────────────
    if with_music and not skip_video:
        _step(6, "Trilha sonora discreta")
        try:
            from modules.music_engine import MusicEngine, mix_audio
            import shutil
            mengine = MusicEngine(output_dir=out)
            track   = mengine.select_track("INSPIRING", min_duration=30.0)
            if track:
                narration_only = out / "narration_only.wav"
                if not narration_only.exists():
                    shutil.copy2(wav_path, narration_only)
                ok = mix_audio(narration_only, out / track.local_path, wav_path,
                               ffmpeg_exe=ffmpeg, duck=True)
                print(f"  Trilha: {track.title[:50]}  ({'ok' if ok else 'falhou'})")
            else:
                print("  Nenhuma trilha encontrada — só narração")
        except Exception as e:
            print(f"  [música] erro: {e} — só narração")

    # ── 7. Montagem ───────────────────────────────────────────────────────────
    if not skip_video:
        _step(7, "Montagem FFmpeg (xfade + legendas + loudnorm)")
        video_path = ffmpeg_assemble(timeline, out, ffmpeg_exe=ffmpeg)
        print(f"  Vídeo: {Path(video_path).name}")

    # ── 8. Metadados + thumbnail ──────────────────────────────────────────────
    _step(8, "Metadados + thumbnail")
    try:
        pseudo_story = {
            "titulo":  deck.get("titulo_deck", video.title),
            "logline": deck.get("tema", ""),
            "historia_completa": narration["narration_full"][:1500],
        }
        metadata = generate_metadata(pseudo_story)
        _save(metadata, out / "14_metadata.json")
        thumbs = generate_thumbnails(timeline, metadata, out)
        for t in thumbs:
            print(f"  Thumbnail: {Path(t).name}")
    except Exception as e:
        print(f"  [metadata] erro: {e}")

    print("\n" + "=" * 64)
    print(f"  EXPLAINER CONCLUÍDO em {time.time() - t0:.1f}s")
    print(f"  Pasta: {out}")
    print("=" * 64 + "\n")
    return out


# ─── Timeline a partir dos boundaries ─────────────────────────────────────────

def _build_slide_timeline(deck: dict, slide_paths: dict,
                          boundaries: list, audio_dur: float) -> dict:
    """
    Constrói timeline com 1 cena por slide. A fronteira entre slides fica no
    ponto médio entre o fim da última palavra de um slide e o início da
    primeira palavra do próximo (a troca acontece na micro-pausa).
    """
    slides = deck.get("slides", [])
    spans  = {}
    for b in boundaries:
        seg = b.get("segment", "")
        if seg not in spans:
            spans[seg] = [b["start"], b["end"]]
        else:
            spans[seg][0] = min(spans[seg][0], b["start"])
            spans[seg][1] = max(spans[seg][1], b["end"])

    scenes = []
    prev_end_cut = 0.0
    for i, s in enumerate(slides):
        seg_id = f"slide_{s['id']:02d}"
        span   = spans.get(seg_id)
        start  = prev_end_cut
        if i + 1 < len(slides):
            nxt = spans.get(f"slide_{slides[i+1]['id']:02d}")
            end = ((span[1] + nxt[0]) / 2) if (span and nxt) else start + 5.0
        else:
            end = max(audio_dur, span[1] if span else start + 5.0)
        end = max(end, start + 1.5)     # cena nunca menor que 1.5s

        scenes.append({
            "scene_id":      s["id"],
            "start":         round(start, 3),
            "end":           round(end, 3),
            "duration":      round(end - start, 3),
            "segment":       seg_id,
            "emotion":       "contemplation",     # zoom sutil no slide
            "asset_type":    "image",
            "voice":         s.get("narracao", ""),
            "subtitle":      s.get("titulo", ""),
            "image_file":    slide_paths.get(s["id"], ""),
            "video_file":    "",
            "visual_type":   "slide",
            "zoom":          "zoom_in",
            "transition_in": "fade",
            "transition_out": "fade",
        })
        prev_end_cut = end

    return {
        "version":        "5.0-explainer",
        "mode":           "Explainer (NotebookLM style)",
        "total_duration": round(scenes[-1]["end"], 2) if scenes else 0,
        "audio_duration": round(audio_dur, 2),
        "resolution":     "1080x1920",
        "fps":            30,
        "audio_file":     "audio.wav",
        "subtitles_file": "subtitles.ass",
        "scenes":         scenes,
    }


def _wav_duration(path) -> float:
    import wave
    with wave.open(str(path), "rb") as wf:
        return wf.getnframes() / float(wf.getframerate())
