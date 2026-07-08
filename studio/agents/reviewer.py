"""
Agente Revisor (QA) — inspeção antes da exportação + pedido de retrabalho.

Verificações objetivas (medidas, não opinião):
  - narração desalinhada: cobertura da timeline vs duração do áudio
  - mídia repetida: mesmo arquivo/URL em cenas diferentes
  - cortes ruins: cenas < 1,5s ou > 8s
  - volume: loudness da voz vs música (ffmpeg volumedetect)
  - legendas: blocos vazios, sobreposição de tempos, chars por linha
  - português: ortografia/gramática da narração (checagem via Claude)
  - vídeo final existe e tem duração coerente

Se houver problema grave, preenche qa_report.rework com o AGENTE que deve
re-executar e a nota — o orquestrador cuida do loop.
"""

import json
import re
import subprocess
from pathlib import Path

from studio.core import Agent


class ReviewerAgent(Agent):
    name     = "revisor"
    label    = "Revisão de qualidade + retrabalho automático"
    requires = ("timeline",)
    produces = ("qa_report",)

    def run(self, ctx):
        workdir  = Path(ctx.workdir)
        ffmpeg   = ctx.config.get("ffmpeg", "ffmpeg")
        timeline = ctx.get("timeline")
        issues, rework = [], []

        # ── 1. Sincronização voz ↔ timeline ───────────────────────────────────
        audio_dur = _media_duration(workdir / "audio.wav", ffmpeg)
        tl_dur    = float(timeline.get("total_duration", 0))
        if audio_dur and abs(tl_dur - audio_dur) > 1.5:
            issues.append(f"timeline {tl_dur:.1f}s vs áudio {audio_dur:.1f}s "
                          f"(desvio {abs(tl_dur-audio_dur):.1f}s)")
            rework.append({"agent": "editor",
                           "note": "Timeline não cobre o áudio — re-auditar durações."})

        # ── 2. Mídia repetida ─────────────────────────────────────────────────
        files = [s.get("video_file") or s.get("image_file", "")
                 for s in timeline.get("scenes", [])]
        dupes = {f for f in files if f and files.count(f) > 1}
        if dupes:
            issues.append(f"mídia repetida em cenas: {sorted(dupes)[:3]}")
            if len(dupes) > 2:
                rework.append({"agent": "media_scout",
                               "note": f"Repetição excessiva ({len(dupes)} arquivos "
                                       f"duplicados) — buscar mídias alternativas."})

        # ── 3. Cortes ruins ───────────────────────────────────────────────────
        bad_cuts = [s["scene_id"] for s in timeline.get("scenes", [])
                    if s.get("duration", 4) < 1.5 or s.get("duration", 4) > 8]
        if bad_cuts:
            issues.append(f"cenas com duração ruim (<1.5s ou >8s): {bad_cuts[:5]}")

        # ── 4. Volumes (voz vs música) ────────────────────────────────────────
        vol_narr  = _mean_volume(workdir / "narration_only.wav", ffmpeg)
        vol_final = _mean_volume(workdir / "audio.wav", ffmpeg)
        if vol_narr is not None and vol_final is not None:
            if vol_final > vol_narr + 3:
                issues.append(f"música alta demais (mix {vol_final:.1f}dB vs "
                              f"voz {vol_narr:.1f}dB)")
                rework.append({"agent": "musica",
                               "note": "Música competindo com a voz — reduzir volume/ducking."})

        # ── 5. Legendas ───────────────────────────────────────────────────────
        srt = workdir / "subtitles.srt"
        if srt.exists():
            problems = _check_srt(srt.read_text(encoding="utf-8"))
            issues.extend(problems)
        else:
            issues.append("subtitles.srt ausente")

        # ── 6. Ortografia/gramática (Claude) ──────────────────────────────────
        narration = ctx.get("narration", {})
        text = narration.get("narration_full", "")[:4000]
        if text:
            try:
                from modules.claude_client import ask_json
                check = ask_json(
                    "Revise APENAS erros objetivos de português (ortografia, "
                    "concordância) no texto abaixo. Ignore estilo. Retorne JSON "
                    '{"erros": [{"trecho": "...", "correcao": "..."}]} '
                    "(lista vazia se não houver).\n\nTEXTO:\n" + text,
                    max_tokens=1000, fallback={"erros": []})
                for e in check.get("erros", [])[:5]:
                    issues.append(f"português: '{e.get('trecho','')[:40]}' → "
                                  f"'{e.get('correcao','')[:40]}'")
                if len(check.get("erros", [])) > 2:
                    rework.append({"agent": "copywriter",
                                   "note": "Corrigir erros de português apontados: "
                                           + json.dumps(check["erros"][:5],
                                                        ensure_ascii=False)})
            except Exception:
                pass

        # ── 7. Vídeo final ────────────────────────────────────────────────────
        video = ctx.get("video_path", "")
        if video and Path(video).exists():
            vdur = _media_duration(Path(video), ffmpeg)
            if vdur and audio_dur and abs(vdur - audio_dur) > 2.0:
                issues.append(f"vídeo {vdur:.1f}s vs áudio {audio_dur:.1f}s")
        elif not ctx.config.get("skip_video"):
            issues.append("vídeo final não foi gerado")
            rework.append({"agent": "editor", "note": "Render falhou — repetir montagem."})

        # Dedup de retrabalho (1 pedido por agente por rodada)
        seen = set()
        rework = [r for r in rework
                  if not (r["agent"] in seen or seen.add(r["agent"]))]

        status = "aprovado" if not rework else "retrabalho"
        report = {"status": status, "issues": issues, "rework": rework,
                  "audio_duration": audio_dur, "timeline_duration": tl_dur}
        (workdir / "qa_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"  Status: {status.upper()} | Problemas: {len(issues)} | "
              f"Retrabalho: {[r['agent'] for r in rework] or 'nenhum'}")
        for i in issues[:8]:
            print(f"  [!] {i}")

        ctx.set("qa_report", report, self.name)


# ─── Medições ──────────────────────────────────────────────────────────────────

def _media_duration(path: Path, ffmpeg: str) -> float | None:
    if not path.exists():
        return None
    try:
        r = subprocess.run([ffmpeg, "-i", str(path)], capture_output=True,
                           text=True, timeout=20)
        m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", r.stderr)
        if m:
            h, mn, s = m.groups()
            return int(h) * 3600 + int(mn) * 60 + float(s)
    except Exception:
        pass
    return None


def _mean_volume(path: Path, ffmpeg: str) -> float | None:
    if not path.exists():
        return None
    try:
        r = subprocess.run(
            [ffmpeg, "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, text=True, timeout=60)
        m = re.search(r"mean_volume:\s*(-?[\d.]+)\s*dB", r.stderr)
        return float(m.group(1)) if m else None
    except Exception:
        return None


def _check_srt(content: str) -> list:
    problems = []
    blocks = [b for b in content.split("\n\n") if b.strip()]
    prev_end = 0.0
    overlaps = empty = long_lines = 0
    for b in blocks:
        lines = b.strip().split("\n")
        if len(lines) < 3 or not lines[2].strip():
            empty += 1
            continue
        m = re.search(r"(\d+):(\d+):(\d+),(\d+)\s*-->\s*(\d+):(\d+):(\d+),(\d+)",
                      b)
        if m:
            start = int(m.group(1))*3600 + int(m.group(2))*60 + int(m.group(3)) \
                    + int(m.group(4))/1000
            end   = int(m.group(5))*3600 + int(m.group(6))*60 + int(m.group(7)) \
                    + int(m.group(8))/1000
            if start < prev_end - 0.05:
                overlaps += 1
            prev_end = end
        if any(len(l) > 42 for l in lines[2:]):
            long_lines += 1
    if empty:
        problems.append(f"legendas: {empty} bloco(s) vazio(s)")
    if overlaps:
        problems.append(f"legendas: {overlaps} sobreposição(ões) de tempo")
    if long_lines > len(blocks) * 0.2:
        problems.append(f"legendas: {long_lines} bloco(s) com linhas longas")
    return problems
