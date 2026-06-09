"""
PRIORIDADE 4 — Busca automática de vídeos históricos de domínio público.

Fontes:
- Internet Archive (Prelinger Archives, public domain footage)
- Wikimedia Commons (vídeos históricos)

Quando disponível, vídeo histórico real tem prioridade sobre imagem.
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests


@dataclass
class VideoAsset:
    identifier: str
    url: str
    title: str
    description: str = ""
    duration: float = 0.0    # segundos
    source: str = ""
    format: str = "mp4"
    score: float = 0.0
    local_path: str = ""


class VideoAcquisitionEngine:
    """Busca e baixa clipes de vídeo histórico de domínio público."""

    CACHE_TTL  = 7 * 24 * 3600
    REQ_DELAY  = 0.5
    MAX_DL_SIZE = 50 * 1024 * 1024   # 50MB máximo por clipe
    MIN_BYTES   = 50_000              # mínimo 50KB

    def __init__(self, output_dir: Path, cache_dir: Path = None):
        self.output_dir   = Path(output_dir)
        self.assets_dir   = self.output_dir / "assets"
        self.cache_dir    = Path(cache_dir) if cache_dir else self.output_dir / "cache"
        self.meta_dir     = self.cache_dir / "video_metadata"
        self.vid_cache    = self.cache_dir / "video_downloads"

        for d in [self.assets_dir, self.meta_dir, self.vid_cache]:
            d.mkdir(parents=True, exist_ok=True)

        self.session = requests.Session()
        self.session.headers["User-Agent"] = "StoryReplicator/2.0 (educational research)"

    def search_for_scene(self, keywords: dict, cena_id: int,
                          max_duration: float = 15.0) -> Optional[VideoAsset]:
        """
        Busca um clipe de vídeo relevante para a cena.
        Retorna VideoAsset ou None se não encontrado.
        """
        queries = keywords.get("search_queries", [])[:3]
        period  = keywords.get("period", "")

        candidates: list[VideoAsset] = []

        for q in queries:
            found = self._search_archive(q, period, max_duration)
            candidates.extend(found)
            if len(candidates) >= 10:
                break
            time.sleep(self.REQ_DELAY)

        if not candidates:
            return None

        # Pontua e seleciona o melhor
        candidates = self._score(candidates, keywords)
        for cand in candidates[:5]:
            dest = self.assets_dir / f"video_{cena_id:02d}.mp4"
            if self._download_clip(cand, dest):
                cand.local_path = str(dest.relative_to(self.output_dir))
                print(f"    VIDEO [{cand.source}] {cand.title[:55]} ({cand.duration:.0f}s)")
                return cand

        return None

    # ── Internet Archive ──────────────────────────────────────────────────────

    def _search_archive(self, query: str, period: str, max_duration: float) -> list:
        """Busca no Internet Archive por vídeos históricos de domínio público."""
        cache_key = hashlib.md5(f"video:{query}".encode()).hexdigest()
        cached    = self._load_cache(cache_key)
        if cached is not None:
            return [VideoAsset(**c) for c in cached]

        results = []
        try:
            q_full = (
                f"({query}) AND mediatype:movies AND "
                f"licenseurl:(*creativecommons* OR *publicdomain*) "
                f"AND subject:(historic OR vintage OR archive OR documentary)"
            )
            r = self.session.get(
                "https://archive.org/advancedsearch.php",
                params={
                    "q":      q_full,
                    "fl[]":   "identifier,title,description,runtime,mediatype",
                    "rows":   "8",
                    "output": "json",
                    "sort[]": "downloads desc",
                },
                timeout=15,
            )
            if r.status_code != 200:
                return results

            for doc in r.json().get("response", {}).get("docs", []):
                iid = doc.get("identifier", "")
                if not iid:
                    continue
                runtime = _parse_runtime(doc.get("runtime", ""))
                if runtime > max_duration * 2 and runtime > 0:
                    continue  # clipe muito longo
                results.append(VideoAsset(
                    identifier=iid,
                    url=f"https://archive.org/download/{iid}/{iid}.mp4",
                    title=doc.get("title", ""),
                    description=str(doc.get("description", "") or "")[:200],
                    duration=runtime,
                    source="archive",
                ))

            self._save_cache(cache_key, [_va_to_dict(v) for v in results])
        except Exception as e:
            print(f"[video_acq] archive error: {e}")

        return results

    # ── Scoring ───────────────────────────────────────────────────────────────

    def _score(self, candidates: list, keywords: dict) -> list:
        queries  = [q.lower() for q in keywords.get("search_queries", [])]
        subjects = [s.lower() for s in keywords.get("subjects", [])]
        period   = keywords.get("period", "").lower()

        for c in candidates:
            text  = f"{c.title} {c.description}".lower()
            score = 0.0

            # Keyword match (50%)
            if queries:
                hits = sum(1 for q in queries if any(w in text for w in q.split() if len(w) > 3))
                score += min(hits / len(queries), 1.0) * 0.50

            # Subject match (25%)
            if subjects:
                hits = sum(1 for s in subjects if s in text)
                score += min(hits / len(subjects), 1.0) * 0.25

            # Period match (25%)
            if period and period[:4] in text:
                score += 0.25

            c.score = round(score, 3)

        return sorted(candidates, key=lambda x: x.score, reverse=True)

    # ── Download ──────────────────────────────────────────────────────────────

    def _download_clip(self, asset: VideoAsset, dest: Path) -> bool:
        """Baixa clipe de vídeo com verificação de tamanho."""
        vid_hash = hashlib.md5(asset.url.encode()).hexdigest()
        cached   = self.vid_cache / f"{vid_hash}.mp4"

        if cached.exists() and (time.time() - cached.stat().st_mtime) < self.CACHE_TTL:
            try:
                import shutil
                shutil.copy2(cached, dest)
                return True
            except Exception:
                pass

        try:
            r = self.session.get(asset.url, timeout=30, stream=True)
            if r.status_code != 200:
                # Tenta URL alternativa no Archive
                alt_url = f"https://archive.org/download/{asset.identifier}"
                r = self.session.get(alt_url, timeout=15)
                if r.status_code != 200:
                    return False

            ct = r.headers.get("content-type", "")
            if "video" not in ct and "octet-stream" not in ct:
                return False

            total = int(r.headers.get("content-length", 0))
            if total > self.MAX_DL_SIZE:
                return False

            data = b"".join(r.iter_content(65536))
            if len(data) < self.MIN_BYTES:
                return False

            cached.write_bytes(data)
            dest.write_bytes(data)
            return True

        except Exception as e:
            print(f"[video_acq] download error {asset.url}: {e}")
            return False

    # ── Cache ─────────────────────────────────────────────────────────────────

    def _load_cache(self, key: str) -> Optional[list]:
        path = self.meta_dir / f"{key}.json"
        if not path.exists() or (time.time() - path.stat().st_mtime) > self.CACHE_TTL:
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _save_cache(self, key: str, data: list) -> None:
        try:
            (self.meta_dir / f"{key}.json").write_text(
                json.dumps(data), encoding="utf-8"
            )
        except Exception:
            pass


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _parse_runtime(runtime_str: str) -> float:
    """Converte string de runtime (MM:SS ou HH:MM:SS) para segundos."""
    if not runtime_str:
        return 0.0
    parts = str(runtime_str).split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        return float(parts[0])
    except Exception:
        return 0.0


def _va_to_dict(v: VideoAsset) -> dict:
    return {
        "identifier":  v.identifier,
        "url":         v.url,
        "title":       v.title,
        "description": v.description,
        "duration":    v.duration,
        "source":      v.source,
        "format":      v.format,
        "score":       v.score,
        "local_path":  v.local_path,
    }
