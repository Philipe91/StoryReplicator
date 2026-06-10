"""
PRIORIDADE 9 — Relatório de qualidade pós-renderização.

Gera quality_report.json com métricas objetivas e recomendações.
"""

import json
from pathlib import Path


def generate(
    timeline: dict,
    audio_duration: float,
    acquisition_result: dict,
    video_path: str,
    output_dir: Path,
    ffmpeg_exe: str = "ffmpeg",
    edit_decisions: list = None,
    scene_contexts: dict = None,
    visual_assets_result: dict = None,
    music_info: dict = None,
    hook_score: float = None,
    retention_score_100: int = None,
) -> dict:
    """Gera quality_report.json após a renderização."""
    visual_assets_result = visual_assets_result or {}
    music_info           = music_info or {}

    scenes          = timeline.get("scenes", [])
    total_scenes    = len(scenes)
    target_duration = timeline.get("total_duration", 0.0)
    edit_decisions  = edit_decisions or []
    scene_contexts  = scene_contexts or {}

    # ── Duração final do vídeo gerado ─────────────────────────────────────────
    final_duration = _get_video_duration(str(video_path), ffmpeg_exe)

    # ── Assets visuais ────────────────────────────────────────────────────────
    images_used = [s for s in scenes if s.get("image_file") and not s.get("video_file")]
    videos_used = [s for s in scenes if s.get("video_file")]

    # Conta ativos encontrados vs placeholders
    found_assets = acquisition_result.get("found", 0)
    total_acq    = acquisition_result.get("total_scenes", total_scenes)
    missing_img  = acquisition_result.get("missing", 0)

    # ── Cobertura visual (% de duração com ativo próprio) ─────────────────────
    covered_duration = sum(
        float(s.get("duration", 0))
        for s in scenes
        if s.get("image_file") and "placeholder" not in str(s.get("image_file", ""))
    )
    coverage_pct = round(covered_duration / max(audio_duration, 0.01) * 100, 1)

    # ── Scores base ───────────────────────────────────────────────────────────
    visual_score    = _score_visual(found_assets, total_acq, coverage_pct)
    sync_score      = _score_sync(final_duration, audio_duration)
    narrative_score = _score_narrative(scenes)
    retention_score = _score_retention(visual_score, sync_score, total_scenes, audio_duration)

    # ── Scores v3.5 (P9) ──────────────────────────────────────────────────────
    visual_variety_score   = _score_visual_variety(scenes, audio_duration)
    camera_movement_score  = _score_camera_movement(edit_decisions)
    subtitle_quality_score = _score_subtitle_quality(edit_decisions, output_dir)
    historical_acc_score   = _score_historical_accuracy(acquisition_result, scene_contexts)

    # ── Problemas detectados ──────────────────────────────────────────────────
    issues = []
    recommendations = []

    if missing_img > 0:
        issues.append(f"{missing_img} cenas sem imagem própria (usando placeholder)")
        recommendations.append(f"Adicionar manualmente imagens para cenas: "
                                f"{[a['cena_id'] for a in acquisition_result.get('assignments',{}).values() if a.get('status')=='missing']}")

    if sync_score < 8:
        issues.append(f"Dessincronia: vídeo={final_duration:.1f}s vs áudio={audio_duration:.1f}s")
        recommendations.append("Verifique render_auditor — extend última cena")

    if coverage_pct < 80:
        issues.append(f"Cobertura visual baixa: {coverage_pct}%")
        recommendations.append("Aumente o número de cenas no storyboard ou melhore buscas de imagem")

    long_scenes = [s for s in scenes if float(s.get("duration", 0)) > 7]
    if long_scenes:
        issues.append(f"{len(long_scenes)} cenas com duração > 7s (parecem slideshow)")
        recommendations.append("Use modo documentary com cenas de 4s — edita config DEFAULT_MODE")

    # ── Métricas v3.6 (Universal Visual Asset Engine) ─────────────────────────
    va           = visual_assets_result
    video_count  = va.get("video_count", len(videos_used))
    image_count  = va.get("image_count", len(images_used))
    hist_count   = va.get("historical_assets_count", 0)
    doc_count    = va.get("document_count", 0)
    broll_count  = sum(1 for d in edit_decisions if getattr(d, "broll_needed", False)) if edit_decisions else 0
    coverage_score = round(min(coverage_pct / 100 * 10, 10.0), 1)
    asset_mix    = va.get("mix_pct", {})

    # v3.7 — Visual Quality Filter
    visual_quality_score = va.get("visual_quality_score", 0.0)
    low_res_rejected     = va.get("low_resolution_rejected", 0)
    upscaled             = va.get("upscaled_assets", 0)
    avg_resolution       = va.get("average_resolution", "0x0")

    # v3.7 — Adaptive Music Engine
    music_category    = music_info.get("category", "none")
    music_source      = music_info.get("source", "none")
    has_music         = music_info.get("applied", False)
    music_score       = _score_music(music_info)
    audio_balance     = _score_audio_balance(music_info)

    # ── Relatório final ───────────────────────────────────────────────────────
    report = {
        "version":          "3.7",
        "final_duration":   round(final_duration, 2),
        "target_duration":  round(target_duration, 2),
        "audio_duration":   round(audio_duration, 2),
        "sync_delta":       round(abs(final_duration - audio_duration), 2),
        "total_scenes":     total_scenes,
        "images_used":      len(images_used),
        "videos_used":      len(videos_used),
        "found_assets":     found_assets,
        "missing_assets":   missing_img,
        "visual_coverage_pct": coverage_pct,
        "video_count":      video_count,
        "image_count":      image_count,
        "historical_assets_count": hist_count,
        "document_count":   doc_count,
        "broll_count":      broll_count,
        "coverage_score":   coverage_score,
        "asset_mix_pct":    asset_mix,
        # v3.7 — Visual Quality Filter
        "low_resolution_rejected": low_res_rejected,
        "upscaled_assets":         upscaled,
        "average_resolution":      avg_resolution,
        # v3.7 — Adaptive Music Engine
        "music_category":   music_category,
        "music_source":     music_source,
        "music_applied":    has_music,
        # v4.0 — Núcleo de Retenção
        "retention_score":  retention_score_100 if retention_score_100 is not None else int(retention_score * 10),
        "hook_score":       round(hook_score, 1) if hook_score is not None else None,
        "estimated_ctr":    _estimate_ctr(hook_score, retention_score_100),
        "scores": {
            "visual":               visual_score,
            "sync":                 sync_score,
            "narrative":            narrative_score,
            "retention_estimate":   retention_score,
            "hook_score":           round(hook_score, 1) if hook_score is not None else 6.0,
            "visual_variety_score": visual_variety_score,
            "camera_movement_score":camera_movement_score,
            "subtitle_quality_score":subtitle_quality_score,
            "historical_accuracy_score": historical_acc_score,
            "visual_quality_score": visual_quality_score,
            "music_score":          music_score,
            "audio_balance_score":  audio_balance,
            "overall": round((
                visual_score + sync_score + narrative_score + retention_score
                + visual_variety_score + camera_movement_score
                + subtitle_quality_score + historical_acc_score
                + visual_quality_score + music_score + audio_balance
            ) / 11, 1),
        },
        "issues":           issues,
        "recommendations":  recommendations,
        "status":           "excellent" if retention_score >= 8 else "good" if retention_score >= 6 else "needs_work",
    }

    report_path = Path(output_dir) / "quality_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


# ─── Estimativa de CTR (v4.0) ──────────────────────────────────────────────────

def _estimate_ctr(hook_score: float, retention_100: int) -> str:
    """Estima faixa de CTR com base no hook e retenção (heurístico)."""
    h = hook_score if hook_score is not None else 6.0
    r = (retention_100 if retention_100 is not None else 60) / 10.0
    combined = h * 0.6 + r * 0.4   # 0-10
    if combined >= 8.5:
        return "alto (8-12%)"
    if combined >= 7:
        return "bom (5-8%)"
    if combined >= 5:
        return "médio (3-5%)"
    return "baixo (<3%)"


# ─── Scores v3.7 (música) ──────────────────────────────────────────────────────

def _score_music(music_info: dict) -> float:
    """Score da trilha sonora: presença, fonte e coerência de categoria."""
    if not music_info.get("applied"):
        return 5.0   # neutro: vídeo sem música ainda é válido
    score = 7.0
    if music_info.get("category") and music_info.get("category") != "none":
        score += 1.5
    if music_info.get("source") and "fallback" not in str(music_info.get("source", "")):
        score += 1.5
    return round(min(score, 10.0), 1)


def _score_audio_balance(music_info: dict) -> float:
    """Equilíbrio áudio: narração nunca abafada pela música."""
    if not music_info.get("applied"):
        return 8.0   # só narração = sempre inteligível
    if music_info.get("ducking"):
        return 10.0  # ducking garante narração clara
    vol = music_info.get("music_volume", 0.16)
    # Volume na faixa 12-20% é ideal
    if 0.10 <= vol <= 0.22:
        return 8.5
    return 6.0


# ─── Scores individuais ───────────────────────────────────────────────────────

def _score_visual(found: int, total: int, coverage_pct: float) -> float:
    if total == 0:
        return 0.0
    asset_ratio = found / total        # 0-1
    cov_ratio   = coverage_pct / 100   # 0-1
    return round(min(10.0, (asset_ratio * 5) + (cov_ratio * 5)), 1)


# ─── Scores v3.5 (P9) ──────────────────────────────────────────────────────────

def _score_visual_variety(scenes: list, duration: float) -> float:
    """
    Variedade visual: penaliza cenas longas (slideshow), recompensa
    troca frequente de imagem e diversidade de tipos visuais.
    """
    if not scenes or duration <= 0:
        return 0.0
    # Densidade de cenas (ideal: 1 cena a cada 4s)
    density   = min((len(scenes) / (duration / 4.0)), 1.0)
    # Diversidade de tipos visuais (foto, jornal, mapa, documento, retrato)
    vtypes    = {s.get("visual_type", "photograph") for s in scenes}
    diversity = min(len(vtypes) / 4.0, 1.0)
    # Penalidade por cenas longas (> 5s)
    long_n    = sum(1 for s in scenes if float(s.get("duration", 0)) > 5.0)
    penalty   = min(long_n / max(len(scenes), 1), 0.5)
    score     = (density * 5) + (diversity * 5) - (penalty * 4)
    return round(max(0.0, min(10.0, score)), 1)


def _score_camera_movement(edit_decisions: list) -> float:
    """
    Movimento de câmera: recompensa diversidade de movimentos e
    penaliza excesso de cenas estáticas.
    """
    if not edit_decisions:
        return 5.0   # neutro quando não há editor AI (provável FFmpeg)
    movements = [d.camera if hasattr(d, "camera") else d.get("camera", "static")
                 for d in edit_decisions]
    unique    = len(set(movements))
    static_n  = sum(1 for m in movements if m == "static")
    diversity = min(unique / 6.0, 1.0)          # 6+ tipos distintos = ótimo
    static_pen= min(static_n / max(len(movements), 1), 1.0)
    score     = (diversity * 8) + 2 - (static_pen * 4)
    return round(max(0.0, min(10.0, score)), 1)


def _score_subtitle_quality(edit_decisions: list, output_dir) -> float:
    """
    Qualidade de legenda: verifica presença de subtitles.json/.ass
    e consistência de estilo.
    """
    score = 4.0
    od    = Path(output_dir)
    if (od / "subtitles.ass").exists():
        score += 2.0
    if (od / "subtitles.json").exists():
        score += 2.0    # word-level timing premium
    if (od / "subtitles.srt").exists():
        score += 1.0
    # Consistência de estilo (poucos estilos diferentes = mais profissional)
    if edit_decisions:
        styles = {d.subtitle_style if hasattr(d, "subtitle_style") else d.get("subtitle_style","")
                  for d in edit_decisions}
        if len(styles) <= 2:
            score += 1.0
    return round(min(10.0, score), 1)


def _score_historical_accuracy(acquisition_result: dict, scene_contexts: dict) -> float:
    """
    Acurácia histórica: combina score médio de aderência das imagens
    encontradas com a presença de período/local identificados.
    """
    assignments = acquisition_result.get("assignments", {})
    if not assignments:
        return 5.0
    found     = [a for a in assignments.values() if a.get("status") == "found"]
    if not found:
        return 0.0
    # Score médio de aderência das imagens (0-1) × 6
    avg_score = sum(a.get("score", 0.0) for a in found) / len(found)
    img_pts   = min(avg_score, 1.0) * 6
    # Cobertura de contexto histórico (período + local identificados)
    ctx_pts   = 0.0
    if scene_contexts:
        with_period = sum(1 for c in scene_contexts.values()
                          if getattr(c, "period", "") or (isinstance(c, dict) and c.get("period")))
        ctx_pts = min(with_period / max(len(scene_contexts), 1), 1.0) * 4
    else:
        ctx_pts = 2.0
    return round(min(10.0, img_pts + ctx_pts), 1)


def _score_sync(final_dur: float, audio_dur: float) -> float:
    if audio_dur <= 0:
        return 10.0
    delta_pct = abs(final_dur - audio_dur) / audio_dur
    if delta_pct < 0.02:
        return 10.0
    if delta_pct < 0.05:
        return 8.0
    if delta_pct < 0.10:
        return 6.0
    if delta_pct < 0.20:
        return 4.0
    return 2.0


def _score_narrative(scenes: list) -> float:
    """Score simplificado baseado em variedade de segmentos e coberturas."""
    if not scenes:
        return 0.0
    segments = {s.get("segment", "") for s in scenes}
    variety  = len(segments) / 7.0    # máx 7 segmentos típicos
    count_ok = min(len(scenes) / 12.0, 1.0)   # ideal 12+ cenas
    return round(min(10.0, (variety + count_ok) * 5), 1)


def _score_retention(visual: float, sync: float, total_scenes: int, duration: float) -> float:
    """Estima score de retenção combinando todos os fatores."""
    scene_density = min(total_scenes / max(duration / 4, 1), 1.0)   # ideal: 1 cena/4s
    base = (visual * 0.4) + (sync * 0.3) + (scene_density * 10 * 0.3)
    return round(min(10.0, base), 1)


# ─── Utilitário ───────────────────────────────────────────────────────────────

def _get_video_duration(video_path: str, ffmpeg_exe: str) -> float:
    import subprocess
    try:
        r = subprocess.run([ffmpeg_exe, "-i", video_path],
                           capture_output=True, text=True, timeout=15)
        for line in r.stderr.split("\n"):
            if "Duration" in line:
                dur_str = line.split("Duration:")[1].split(",")[0].strip()
                h, m, s = dur_str.split(":")
                return int(h) * 3600 + int(m) * 60 + float(s)
    except Exception:
        pass
    return 0.0
