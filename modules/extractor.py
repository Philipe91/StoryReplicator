"""ETAPA 1 — Extração de dados do YouTube."""

import json
import subprocess
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class VideoData:
    url: str
    title: str = ""
    description: str = ""
    transcript: str = ""
    duration: int = 0
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    upload_date: str = ""
    channel: str = ""
    tags: list = field(default_factory=list)
    top_comments: list = field(default_factory=list)


def extract(url: str, max_comments: int = 20) -> VideoData:
    """Extrai todos os metadados do vídeo usando yt-dlp."""
    data = VideoData(url=url)

    meta = _fetch_metadata(url)
    if meta:
        data.title        = meta.get("title", "")
        data.description  = meta.get("description", "")
        data.duration     = meta.get("duration", 0)
        data.view_count   = meta.get("view_count", 0)
        data.like_count   = meta.get("like_count", 0)
        data.comment_count= meta.get("comment_count", 0)
        data.upload_date  = meta.get("upload_date", "")
        data.channel      = meta.get("channel", "")
        data.tags         = meta.get("tags", [])

    data.transcript   = _fetch_transcript(url)
    data.top_comments = _fetch_comments(url, max_comments)

    return data


def _fetch_metadata(url: str) -> Optional[dict]:
    try:
        result = subprocess.run(
            ["yt-dlp", "--dump-json", "--no-playlist", url],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception as e:
        print(f"[extractor] metadata error: {e}")
    return None


def _fetch_transcript(url: str) -> str:
    """Tenta extrair legenda/transcrição via yt-dlp."""
    try:
        result = subprocess.run(
            [
                "yt-dlp", "--skip-download",
                "--write-auto-subs", "--sub-langs", "pt,en",
                "--sub-format", "vtt",
                "--output", "/tmp/yt_sub_%(id)s",
                url
            ],
            capture_output=True, text=True, timeout=90
        )
        # fallback: tentar extrair do stdout do dump-json
        if result.returncode != 0:
            return _transcript_from_api(url)
    except Exception:
        pass
    return _transcript_from_api(url)


def _transcript_from_api(url: str) -> str:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        video_id = _extract_video_id(url)
        if not video_id:
            return ""
        segments = YouTubeTranscriptApi.get_transcript(video_id, languages=["pt", "en"])
        return " ".join(s["text"] for s in segments)
    except Exception as e:
        print(f"[extractor] transcript error: {e}")
        return ""


def _fetch_comments(url: str, max_comments: int) -> list:
    try:
        result = subprocess.run(
            [
                "yt-dlp", "--skip-download",
                "--write-comments", "--no-playlist",
                "--dump-json", url
            ],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            meta = json.loads(result.stdout)
            comments = meta.get("comments", []) or []
            return [
                {"text": c.get("text", ""), "likes": c.get("like_count", 0)}
                for c in comments[:max_comments]
            ]
    except Exception as e:
        print(f"[extractor] comments error: {e}")
    return []


def _extract_video_id(url: str) -> Optional[str]:
    import re
    patterns = [
        r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})",
        r"(?:shorts/)([A-Za-z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None
