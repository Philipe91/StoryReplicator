"""
StoryReplicator v4.0 — Retention Engine

Analisa o roteiro/narração ANTES da renderização e atribui um
retention_score (0-100), detectando os fatores que mais fazem o
espectador abandonar vídeos curtos:

  - trechos lentos (segmentos longos demais sem troca de assunto)
  - excesso de contexto (muita exposição antes da ação)
  - baixa tensão (segmentos de conflito/clímax sem palavras de tensão)
  - excesso de exposição (frases longas, densas, sem gancho)

Gera sugestões automáticas de melhoria. 100% heurístico, sem API.
"""

import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
import json


# Palavras que sinalizam tensão/ação (esperadas em conflito/escalada/twist)
_TENSION_WORDS = {
    "mas", "porém", "de repente", "subitamente", "então", "quando",
    "nunca", "jamais", "perigo", "medo", "fugiu", "preso", "morte", "morreu",
    "descobriu", "revelou", "segredo", "chocante", "impossível", "última",
    "tarde demais", "ninguém", "sozinho", "escapou", "tensão", "ameaça",
}
# Palavras de exposição/contexto (excesso = lento)
_EXPOSITION_WORDS = {
    "nasceu", "cresceu", "durante", "na época", "naquele tempo", "história",
    "começou", "anos", "família", "infância", "estudou", "trabalhava",
}
# Segmentos onde se espera ALTA tensão
_HIGH_TENSION_SEGMENTS = {"conflito", "escalada", "plot_twist", "clímax", "climax"}


@dataclass
class RetentionReport:
    score:        int = 0           # 0-100
    pace_score:   float = 0.0
    tension_score: float = 0.0
    exposition_score: float = 0.0
    hook_score:   float = 0.0
    slow_segments: list = field(default_factory=list)
    issues:       list = field(default_factory=list)
    suggestions:  list = field(default_factory=list)
    per_segment:  list = field(default_factory=list)


def analyze(narration: dict, storyboard: dict = None, hook_score: float = None) -> RetentionReport:
    """
    Analisa narração + storyboard e retorna RetentionReport (score 0-100).
    """
    rep = RetentionReport()
    segments = narration.get("segments", [])
    if not segments:
        # Sem segmentação: analisa texto corrido
        segments = [{"id": "full", "text": narration.get("narration_full", ""),
                     "start": 0, "end": 60}]

    total_words = 0
    slow = []
    seg_details = []

    for seg in segments:
        sid   = seg.get("id", "")
        text  = seg.get("text", "")
        words = text.split()
        wc    = len(words)
        total_words += wc
        dur   = max(seg.get("end", 0) - seg.get("start", 0), 1)
        wps   = wc / dur   # palavras por segundo

        text_low = text.lower()
        tension_hits    = sum(1 for w in _TENSION_WORDS if w in text_low)
        exposition_hits = sum(1 for w in _EXPOSITION_WORDS if w in text_low)

        # Frases longas = exposição pesada
        sentences = [s for s in re.split(r'[.!?]+', text) if s.strip()]
        avg_sentence_len = (wc / len(sentences)) if sentences else wc

        # Detecta trecho lento: muita duração com pouca tensão
        is_slow = False
        if sid in _HIGH_TENSION_SEGMENTS and tension_hits == 0:
            is_slow = True
            slow.append(sid)
        if dur > 8 and tension_hits == 0 and wc > 0:
            is_slow = True
            if sid not in slow:
                slow.append(sid)

        seg_details.append({
            "id": sid, "words": wc, "duration": round(dur, 1),
            "tension_hits": tension_hits, "exposition_hits": exposition_hits,
            "avg_sentence_len": round(avg_sentence_len, 1), "slow": is_slow,
        })

    rep.per_segment   = seg_details
    rep.slow_segments = slow

    # ── Sub-scores ────────────────────────────────────────────────────────────
    # Ritmo (0-10): penaliza segmentos lentos
    pace = 10.0 - (len(slow) / max(len(segments), 1)) * 10
    rep.pace_score = round(max(0, pace), 1)

    # Tensão (0-10): segmentos de clímax devem ter palavras de tensão
    high_segs = [s for s in seg_details if s["id"] in _HIGH_TENSION_SEGMENTS]
    if high_segs:
        with_tension = sum(1 for s in high_segs if s["tension_hits"] > 0)
        rep.tension_score = round(with_tension / len(high_segs) * 10, 1)
    else:
        total_tension = sum(s["tension_hits"] for s in seg_details)
        rep.tension_score = round(min(total_tension / 3, 10), 1)

    # Exposição (0-10): menos exposição = melhor (10 = ideal)
    total_expo = sum(s["exposition_hits"] for s in seg_details)
    expo_ratio = total_expo / max(len(segments), 1)
    rep.exposition_score = round(max(0, 10 - expo_ratio * 3), 1)

    # Hook (0-10): vem do hook_engine se fornecido
    rep.hook_score = hook_score if hook_score is not None else 6.0

    # ── Score final 0-100 ─────────────────────────────────────────────────────
    rep.score = int(round(
        rep.hook_score      * 0.30 +    # hook é o fator #1
        rep.pace_score      * 0.25 +
        rep.tension_score   * 0.25 +
        rep.exposition_score* 0.20
    ) * 10)

    # ── Issues + sugestões ────────────────────────────────────────────────────
    if slow:
        rep.issues.append(f"{len(slow)} trecho(s) lento(s): {', '.join(slow)}")
        rep.suggestions.append(
            f"Encurte ou adicione tensão aos segmentos: {', '.join(slow)}")
    if rep.tension_score < 6:
        rep.issues.append("Baixa tensão nos momentos de clímax")
        rep.suggestions.append(
            "Adicione palavras de virada ('mas', 'de repente', 'então') no conflito/escalada")
    if rep.exposition_score < 6:
        rep.issues.append("Excesso de exposição/contexto")
        rep.suggestions.append(
            "Corte detalhes de fundo; vá direto ao gancho e à ação")
    if rep.hook_score < 7:
        rep.issues.append("Hook fraco — risco de abandono nos 3s iniciais")
        rep.suggestions.append(
            "Use o melhor hook do hook_engine (pergunta ou afirmação chocante)")
    long_segs = [s for s in seg_details if s["avg_sentence_len"] > 18]
    if long_segs:
        rep.suggestions.append(
            f"Frases muito longas em {len(long_segs)} segmento(s) — quebre em frases curtas")

    return rep


def save_report(rep: RetentionReport, output_dir: Path) -> None:
    (Path(output_dir) / "retention_report.json").write_text(
        json.dumps(asdict(rep), ensure_ascii=False, indent=2), encoding="utf-8")
