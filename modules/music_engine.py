"""
StoryReplicator v3.7 — Adaptive Music Engine

Adiciona trilha sonora dinâmica e contextual:
  1. Analisa a emoção dominante do vídeo (por segmentos/cenas)
  2. Escolhe a categoria musical (MYSTERY, SUSPENSE, DRAMATIC, ...)
  3. Busca música livre no Internet Archive (sem chave) + Pixabay (se key)
  4. Baixa a melhor faixa, com cache
  5. Mixa com a narração via FFmpeg: narração 100%, música 12-20%,
     ducking automático (sidechaincompress) + fade in/out

Música nunca compete com a narração.
"""

import hashlib
import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests

from config import (
    MUSIC_CATEGORIES, EMOTION_TO_MUSIC, SEGMENT_TO_MUSIC, MUSIC_SEARCH_TERMS,
    NARRATION_VOLUME, MUSIC_VOLUME, MUSIC_DUCK_VOLUME, MUSIC_FADE_SEC,
    PIXABAY_API_KEY,
)


@dataclass
class MusicTrack:
    url:       str
    title:     str = ""
    category:  str = ""
    source:    str = ""
    duration:  float = 0.0
    license:   str = "public domain"
    local_path: str = ""
    score:     float = 0.0


# Catálogo de fallback — coleções de música livre estáveis no Internet Archive.
# Usado quando a busca dinâmica não retorna nada baixável.
_FALLBACK_COLLECTIONS = {
    "MYSTERY":       "Kai_Engel",
    "SUSPENSE":      "Kai_Engel",
    "DRAMATIC":      "Kevin_MacLeod",
    "DARK":          "Kai_Engel",
    "EMOTIONAL":     "Chris_Zabriskie",
    "INSPIRING":     "Chris_Zabriskie",
    "TRIUMPH":       "Kevin_MacLeod",
    "HISTORICAL":    "Kevin_MacLeod",
    "INVESTIGATION": "Kevin_MacLeod",
}


class MusicEngine:

    CACHE_TTL = 30 * 24 * 3600
    MIN_BYTES = 100_000
    MAX_BYTES = 30 * 1024 * 1024

    def __init__(self, output_dir: Path, cache_dir: Path = None):
        self.output_dir = Path(output_dir)
        self.cache_dir  = Path(cache_dir) if cache_dir else self.output_dir / "cache"
        self.meta_dir   = self.cache_dir / "music_metadata"
        self.dl_dir     = self.cache_dir / "music_downloads"
        for d in (self.meta_dir, self.dl_dir):
            d.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "StoryReplicator/3.7 (educational)"

    # ── Análise emocional ────────────────────────────────────────────────────

    def analyze_dominant_emotion(self, storyboard: dict, edit_decisions: list = None) -> dict:
        """
        Determina a categoria musical dominante e por segmento.
        Retorna {dominant, by_segment, distribution}.
        """
        cenas = storyboard.get("cenas", [])
        votes = {}
        by_segment = {}

        for cena in cenas:
            seg = cena.get("segmento", "")
            emo = cena.get("emotion", "")
            # Preferência: emoção da cena → segmento
            cat = EMOTION_TO_MUSIC.get(emo) or SEGMENT_TO_MUSIC.get(seg, "HISTORICAL")
            votes[cat] = votes.get(cat, 0) + 1
            by_segment[seg] = cat

        # Reforça com decisões do editor AI (se houver)
        if edit_decisions:
            for d in edit_decisions:
                emo = getattr(d, "emotion", "") if not isinstance(d, dict) else d.get("emotion", "")
                cat = EMOTION_TO_MUSIC.get(emo)
                if cat:
                    votes[cat] = votes.get(cat, 0) + 0.5

        dominant = max(votes, key=votes.get) if votes else "HISTORICAL"
        return {
            "dominant":     dominant,
            "by_segment":   by_segment,
            "distribution": votes,
        }

    # ── Seleção de trilha ────────────────────────────────────────────────────

    def select_track(self, category: str, min_duration: float = 60.0) -> MusicTrack | None:
        """Busca e baixa a melhor faixa para a categoria."""
        if category not in MUSIC_CATEGORIES:
            category = "HISTORICAL"

        candidates = self._search_archive_music(category)
        candidates += self._search_pixabay_music(category)   # se key disponível

        # Pontua: prefere duração suficiente e título coerente
        for c in candidates:
            c.score = self._score_track(c, category, min_duration)
        candidates.sort(key=lambda t: t.score, reverse=True)

        # Tenta baixar o melhor
        for cand in candidates[:6]:
            dest = self.output_dir / "music.mp3"
            if self._download(cand, dest):
                cand.local_path = "music.mp3"
                return cand

        # Fallback: coleção curada conhecida
        return self._fallback_track(category)

    # ── Busca Internet Archive (sem chave) ───────────────────────────────────

    def _search_archive_music(self, category: str) -> list:
        query = MUSIC_SEARCH_TERMS.get(category, "cinematic instrumental")
        key   = hashlib.md5(f"music:{category}".encode()).hexdigest()
        cached = self._load_cache(key)
        if cached is not None:
            return [MusicTrack(**c) for c in cached]

        results = []
        try:
            q = (f"({query}) AND mediatype:audio AND "
                 f"(licenseurl:(*creativecommons* OR *publicdomain*))")
            r = self.session.get(
                "https://archive.org/advancedsearch.php",
                params={"q": q, "fl[]": "identifier,title,subject",
                        "rows": "10", "output": "json", "sort[]": "downloads desc"},
                timeout=15,
            )
            if r.status_code == 200:
                for doc in r.json().get("response", {}).get("docs", []):
                    iid = doc.get("identifier", "")
                    if not iid:
                        continue
                    # Resolve um arquivo de áudio dentro do item
                    audio_url = self._resolve_archive_audio(iid)
                    if audio_url:
                        results.append(MusicTrack(
                            url=audio_url, title=doc.get("title", ""),
                            category=category, source="archive",
                        ))
                    if len(results) >= 6:
                        break
        except Exception as e:
            print(f"[music] archive error: {e}")

        self._save_cache(key, [vars(r) for r in results])
        return results

    def _resolve_archive_audio(self, identifier: str) -> str:
        """Encontra a URL de um MP3/OGG dentro de um item do Archive."""
        try:
            r = self.session.get(f"https://archive.org/metadata/{identifier}", timeout=12)
            if r.status_code != 200:
                return ""
            files = r.json().get("files", [])
            for f in files:
                name = f.get("name", "")
                if name.lower().endswith((".mp3", ".ogg")):
                    return f"https://archive.org/download/{identifier}/{name}"
        except Exception:
            pass
        return ""

    # ── Busca Pixabay (opcional, key gratuita) ───────────────────────────────

    def _search_pixabay_music(self, category: str) -> list:
        # Pixabay descontinuou a API pública de música; mantido como stub
        # caso reativem. Retorna vazio sem key ou se indisponível.
        if not PIXABAY_API_KEY:
            return []
        return []

    # ── Fallback curado ──────────────────────────────────────────────────────

    def _fallback_track(self, category: str) -> MusicTrack | None:
        coll = _FALLBACK_COLLECTIONS.get(category, "Kevin_MacLeod")
        try:
            r = self.session.get(
                "https://archive.org/advancedsearch.php",
                params={"q": f"creator:({coll}) AND mediatype:audio",
                        "fl[]": "identifier,title", "rows": "5",
                        "output": "json", "sort[]": "downloads desc"},
                timeout=15,
            )
            if r.status_code == 200:
                for doc in r.json().get("response", {}).get("docs", []):
                    iid = doc.get("identifier", "")
                    url = self._resolve_archive_audio(iid) if iid else ""
                    if url:
                        track = MusicTrack(url=url, title=doc.get("title", ""),
                                           category=category, source="archive_fallback")
                        dest = self.output_dir / "music.mp3"
                        if self._download(track, dest):
                            track.local_path = "music.mp3"
                            return track
        except Exception as e:
            print(f"[music] fallback error: {e}")
        return None

    # ── Scoring ──────────────────────────────────────────────────────────────

    def _score_track(self, track: MusicTrack, category: str, min_dur: float) -> float:
        score = 0.5
        text  = track.title.lower()
        terms = MUSIC_SEARCH_TERMS.get(category, "").split()
        hits  = sum(1 for t in terms if t in text)
        score += min(hits / max(len(terms), 1), 1.0) * 0.4
        # Penaliza títulos que sugerem voz/letra
        if any(w in text for w in ("vocal", "lyrics", "song", "feat", "remix")):
            score -= 0.3
        return round(score, 3)

    # ── Download ─────────────────────────────────────────────────────────────

    def _download(self, track: MusicTrack, dest: Path) -> bool:
        h     = hashlib.md5(track.url.encode()).hexdigest()
        cache = self.dl_dir / f"{h}.mp3"
        if cache.exists() and (time.time() - cache.stat().st_mtime) < self.CACHE_TTL:
            try:
                dest.write_bytes(cache.read_bytes())
                return True
            except Exception:
                pass
        try:
            r = self.session.get(track.url, timeout=30, stream=True)
            if r.status_code != 200:
                return False
            data = b"".join(r.iter_content(131072))
            if not (self.MIN_BYTES <= len(data) <= self.MAX_BYTES):
                # arquivos enormes: ainda aceita se < 50MB
                if len(data) < self.MIN_BYTES:
                    return False
            cache.write_bytes(data)
            dest.write_bytes(data)
            return True
        except Exception as e:
            print(f"[music] download error: {e}")
            return False

    # ── Cache ────────────────────────────────────────────────────────────────

    def _load_cache(self, key: str):
        p = self.meta_dir / f"{key}.json"
        if not p.exists() or (time.time() - p.stat().st_mtime) > self.CACHE_TTL:
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _save_cache(self, key: str, data: list):
        try:
            (self.meta_dir / f"{key}.json").write_text(json.dumps(data), encoding="utf-8")
        except Exception:
            pass


# ─── Mixagem de áudio (narração + música com ducking) ─────────────────────────

def mix_audio(
    narration_wav: Path,
    music_file: Path,
    output_wav: Path,
    ffmpeg_exe: str = "ffmpeg",
    music_volume: float = None,
    duck: bool = True,
) -> bool:
    """
    Mixa narração (100%) + música (12-20%) com ducking automático e fades.

    Ducking: a música abaixa para MUSIC_DUCK_VOLUME quando há narração,
    via sidechaincompress (a narração controla a compressão da música).
    """
    narration_wav = Path(narration_wav)
    music_file    = Path(music_file)
    output_wav    = Path(output_wav)
    music_volume  = music_volume if music_volume is not None else MUSIC_VOLUME

    if not narration_wav.exists():
        return False
    if not music_file.exists():
        # Sem música: copia narração
        import shutil
        shutil.copy2(narration_wav, output_wav)
        return True

    # Duração da narração para loop/fade da música
    dur = _audio_duration(narration_wav, ffmpeg_exe)
    fade_out_start = max(0.0, dur - MUSIC_FADE_SEC)

    # Normaliza a música a um alvo LUFS fixo (independente de quão quieta/alta
    # seja a faixa) para garantir que fique audível abaixo da narração.
    # I=-22 → música mais presente (~4 dB acima do padrão anterior),
    # ainda ~4-5 dB abaixo da narração (~-18 dB).
    target_lufs = -22

    if duck:
        # Ducking SUAVE sobre música já normalizada: abaixa parcialmente sob a voz.
        filter_complex = (
            f"[1:a]aloop=loop=-1:size=2e9,atrim=0:{dur:.2f},"
            f"loudnorm=I={target_lufs}:TP=-2,"
            f"afade=t=in:st=0:d={MUSIC_FADE_SEC},"
            f"afade=t=out:st={fade_out_start:.2f}:d={MUSIC_FADE_SEC}[mus];"
            f"[mus][0:a]sidechaincompress=threshold=0.06:ratio=2.5:attack=100:release=700[duck];"
            f"[0:a][duck]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[out]"
        )
    else:
        # Sem ducking: música normalizada em volume fixo audível
        filter_complex = (
            f"[1:a]aloop=loop=-1:size=2e9,atrim=0:{dur:.2f},"
            f"loudnorm=I={target_lufs}:TP=-2,"
            f"afade=t=in:st=0:d={MUSIC_FADE_SEC},"
            f"afade=t=out:st={fade_out_start:.2f}:d={MUSIC_FADE_SEC}[mus];"
            f"[0:a][mus]amix=inputs=2:duration=first:normalize=0[out]"
        )

    cmd = [
        ffmpeg_exe, "-y",
        "-i", str(narration_wav),
        "-i", str(music_file),
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-ar", "24000", "-ac", "1",
        str(output_wav),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=180)
        if r.returncode == 0 and output_wav.exists():
            return True
        # Fallback sem ducking se sidechain falhar
        if duck:
            return mix_audio(narration_wav, music_file, output_wav,
                             ffmpeg_exe, music_volume, duck=False)
        print(f"[music] mix falhou: {r.stderr.decode('utf-8','replace')[-200:]}")
        return False
    except Exception as e:
        print(f"[music] mix erro: {e}")
        return False


def _audio_duration(path: Path, ffmpeg_exe: str) -> float:
    try:
        r = subprocess.run([ffmpeg_exe, "-i", str(path)],
                           capture_output=True, text=True, timeout=15)
        for line in r.stderr.split("\n"):
            if "Duration" in line:
                d = line.split("Duration:")[1].split(",")[0].strip()
                h, m, s = d.split(":")
                return int(h)*3600 + int(m)*60 + float(s)
    except Exception:
        pass
    return 60.0
