"""
StoryReplicator v3.8 — Multi-idioma

Gera uma versão do documentário em um idioma específico, REUSANDO os assets
visuais (imagens/vídeos) e a música já baixados — só traduz narração/legendas,
gera voz nativa do idioma e remonta.

Estrutura de saída:
    output/<slug>/
        assets/                  (compartilhado entre idiomas)
        music.mp3                (compartilhado)
        pt/  en/  es/            (uma subpasta por idioma)
            audio.wav, subtitles.{srt,ass,json}, final_video.mp4,
            narration.json, metadata.json, quality_report.json
"""

import json
import shutil
from pathlib import Path

from config import LANG_CONFIG
from modules import translator
from modules.subtitle_engine  import synthesize_with_subtitles, save_subtitles_json
from modules.timeline_builder import build_timeline
from modules.render_auditor   import audit_and_fix
from modules.music_engine     import mix_audio
from modules.video_assembler  import assemble


def generate_language_version(
    lang: str,
    base_dir: Path,
    storyboard: dict,
    narration: dict,
    metadata: dict,
    mode_config: dict,
    image_assignments: dict,
    video_assignments: dict,
    music_path: Path = None,
    ffmpeg_exe: str = "ffmpeg",
    subtitle_style: str = "CINEMATIC",
    skip_video: bool = False,
) -> dict:
    """
    Gera a versão de um idioma. Retorna info do resultado.
    Assets visuais são lidos de base_dir/assets (compartilhados).
    """
    cfg = LANG_CONFIG.get(lang)
    if not cfg:
        return {"lang": lang, "status": "unknown_language"}

    base_dir = Path(base_dir)
    lang_dir = base_dir / lang
    lang_dir.mkdir(parents=True, exist_ok=True)

    # Assets ficam em base_dir/assets (compartilhados). Em vez de copiar/symlink,
    # reescrevemos os paths para "../assets/..." — o assembler resolve relativo
    # à pasta do idioma (en/../assets = assets). Zero duplicação de arquivos.
    image_assignments = {k: _parent_path(v) for k, v in (image_assignments or {}).items()}
    video_assignments = {k: _parent_path(v) for k, v in (video_assignments or {}).items()}

    tr_cache = base_dir / "cache" / "translations"

    print(f"\n  ── Idioma: {cfg['name']} ({lang}) ──")

    # 1. Traduz narração (pt = original)
    if lang == "pt":
        narr_lang = narration
        sb_lang   = storyboard
    else:
        print(f"    Traduzindo narração → {lang}...")
        narr_lang = translator.translate_narration(narration, cfg["translate_code"], tr_cache)
        sb_lang   = translator.translate_storyboard_subtitles(storyboard, cfg["translate_code"], tr_cache)

    (lang_dir / "narration.json").write_text(
        json.dumps(narr_lang, ensure_ascii=False, indent=2), encoding="utf-8")

    # 2. TTS com voz NATIVA do idioma + pitch/rate
    print(f"    Gerando voz [{cfg['tts_voice']}]...")
    text = narr_lang.get("narration_full", "")
    _, _, _, boundaries = synthesize_with_subtitles(
        text, lang_dir, voice=cfg["tts_voice"],
        ffmpeg_exe=ffmpeg_exe, pitch=cfg["pitch"], rate=cfg["rate"],
    )
    save_subtitles_json(boundaries, lang_dir, subtitle_style)
    shutil.copy2(lang_dir / "audio.wav", lang_dir / "narration_only.wav")

    # 3. Mixa música (mesma trilha para todos os idiomas)
    if music_path and Path(music_path).exists():
        print(f"    Mixando trilha sonora...")
        mix_audio(lang_dir / "narration_only.wav", Path(music_path),
                  lang_dir / "audio.wav", ffmpeg_exe=ffmpeg_exe, duck=True)

    # 4. Timeline (mesmos assets visuais) + auditoria
    timeline = build_timeline(sb_lang, narr_lang, {}, mode_config,
                               image_assignments, video_assignments)
    timeline, audit = audit_and_fix(timeline, str(lang_dir / "audio.wav"), ffmpeg_exe)
    (lang_dir / "timeline.json").write_text(
        json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")

    # 5. Metadados traduzidos
    if metadata:
        meta_lang = (metadata if lang == "pt"
                     else translator.translate_metadata(metadata, cfg["translate_code"], tr_cache))
        (lang_dir / "metadata.json").write_text(
            json.dumps(meta_lang, ensure_ascii=False, indent=2), encoding="utf-8")

    # 6. Montagem
    video_path = ""
    if not skip_video:
        print(f"    Montando vídeo {lang}...")
        video_path = assemble(timeline, lang_dir, ffmpeg_exe=ffmpeg_exe)

    return {
        "lang":        lang,
        "name":        cfg["name"],
        "status":      "done",
        "voice":       cfg["tts_voice"],
        "audio_duration": audit.get("audio_duration", 0),
        "video_path":  video_path,
        "dir":         str(lang_dir),
    }


def _parent_path(rel: str) -> str:
    """Converte 'assets/x.jpg' → '../assets/x.jpg' (aponta para a pasta-mãe)."""
    if not rel:
        return rel
    rel = str(rel).lstrip("/")
    return rel if rel.startswith("../") else f"../{rel}"


def generate_all_languages(langs: list, base_dir: Path, **kwargs) -> list:
    """Gera várias versões de idioma em sequência. Retorna lista de resultados."""
    results = []
    for lang in langs:
        try:
            results.append(generate_language_version(lang, base_dir, **kwargs))
        except Exception as e:
            print(f"  [multilang] erro em {lang}: {e}")
            results.append({"lang": lang, "status": "error", "error": str(e)})
    return results
