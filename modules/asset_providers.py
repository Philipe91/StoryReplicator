"""
StoryReplicator v3.6 — Universal Visual Asset Providers

Cada provider busca em uma fonte e retorna List[VisualAsset] normalizado.

Fontes SEM chave (funcionam sempre, zero custo, zero cadastro):
  - Wikimedia Commons (imagens + vídeos)
  - Internet Archive   (imagens + vídeos)
  - Library of Congress (imagens)

Fontes com chave GRATUITA (opcionais, ativadas por env var):
  - Pexels   (vídeos + imagens)  — PEXELS_API_KEY
  - Pixabay  (vídeos + imagens)  — PIXABAY_API_KEY

Cada função recebe uma `requests.Session` para reuso de conexão e respeito a rate-limit.
"""

import time
from dataclasses import dataclass, field

from config import PEXELS_API_KEY, PIXABAY_API_KEY


# ─── Asset normalizado ─────────────────────────────────────────────────────────

@dataclass
class VisualAsset:
    url:          str
    title:        str   = ""
    description:  str    = ""
    asset_type:   str    = "image"   # "video" | "image"
    category:     str    = "image_complement"  # chave de ASSET_PRIORITY
    width:        int     = 0
    height:       int     = 0
    duration:     float   = 0.0      # segundos (vídeos)
    source:       str     = ""       # provider name
    license:      str     = "unknown"
    score:        float   = 0.0
    local_path:   str     = ""
    extra:        dict    = field(default_factory=dict)


# ─── Wikimedia Commons ─────────────────────────────────────────────────────────

def wikimedia_search(session, query: str, want_video: bool = False) -> list:
    """Busca imagens ou vídeos no Wikimedia Commons."""
    results = []
    try:
        r = session.get(
            "https://commons.wikimedia.org/w/api.php",
            params={"action": "query", "list": "search", "srnamespace": "6",
                    "srsearch": query, "srlimit": "8", "format": "json"},
            timeout=15,
        )
        if r.status_code != 200 or not r.text.strip():
            return results
        items = r.json().get("query", {}).get("search", [])
        if not items:
            return results

        titles = "|".join(i["title"] for i in items[:6])
        time.sleep(0.3)
        r2 = session.get(
            "https://commons.wikimedia.org/w/api.php",
            params={"action": "query", "titles": titles, "prop": "imageinfo",
                    "iiprop": "url|size|mime|extmetadata", "format": "json"},
            timeout=15,
        )
        if not r2.text.strip():
            return results

        for page in r2.json().get("query", {}).get("pages", {}).values():
            ii   = (page.get("imageinfo") or [{}])[0]
            url  = ii.get("url", "")
            mime = ii.get("mime", "")
            if not url:
                continue
            is_video = mime.startswith("video/") or url.lower().endswith((".webm", ".ogv", ".mp4"))
            if want_video and not is_video:
                continue
            if not want_video and (is_video or url.lower().endswith(".svg")):
                continue
            meta = ii.get("extmetadata", {})
            results.append(VisualAsset(
                url=url, title=page.get("title", ""),
                description=(meta.get("ImageDescription", {}).get("value", "") or "")[:200],
                asset_type="video" if is_video else "image",
                width=ii.get("width", 0), height=ii.get("height", 0),
                source="wikimedia",
                license=meta.get("LicenseShortName", {}).get("value", "unknown"),
            ))
    except Exception:
        pass
    return results


# ─── Internet Archive ──────────────────────────────────────────────────────────

def archive_search(session, query: str, want_video: bool = False) -> list:
    """Busca no Internet Archive (mediatype movies para vídeo, image para imagem)."""
    results = []
    mediatype = "movies" if want_video else "image"
    try:
        q = f"({query}) AND mediatype:{mediatype}"
        if want_video:
            q += " AND (licenseurl:(*creativecommons* OR *publicdomain*) OR collection:prelinger)"
        r = session.get(
            "https://archive.org/advancedsearch.php",
            params={"q": q, "fl[]": "identifier,title,description,runtime",
                    "rows": "8", "output": "json", "sort[]": "downloads desc"},
            timeout=15,
        )
        if r.status_code != 200:
            return results
        for doc in r.json().get("response", {}).get("docs", []):
            iid = doc.get("identifier", "")
            if not iid:
                continue
            desc = doc.get("description", "") or ""
            if isinstance(desc, list):
                desc = desc[0] if desc else ""
            if want_video:
                url = f"https://archive.org/download/{iid}/{iid}.mp4"
                results.append(VisualAsset(
                    url=url, title=doc.get("title", ""), description=str(desc)[:200],
                    asset_type="video", duration=_runtime_secs(doc.get("runtime", "")),
                    source="archive", license="public domain",
                    extra={"identifier": iid},
                ))
            else:
                url = f"https://archive.org/services/img/{iid}"
                results.append(VisualAsset(
                    url=url, title=doc.get("title", ""), description=str(desc)[:200],
                    asset_type="image", source="archive", license="public domain",
                ))
    except Exception:
        pass
    return results


# ─── Library of Congress (apenas imagens) ──────────────────────────────────────

def loc_search(session, query: str) -> list:
    results = []
    try:
        r = session.get(
            "https://www.loc.gov/search/",
            params={"q": query, "fo": "json", "c": "6", "at": "results",
                    "fa": "online-format:image"},
            timeout=15,
        )
        if r.status_code != 200 or not r.text.strip():
            return results
        for item in r.json().get("results", []):
            img = None
            for u in (item.get("image_url") or []):
                if isinstance(u, str) and u.startswith("http"):
                    img = u
                    break
            if not img:
                continue
            desc = item.get("description") or []
            results.append(VisualAsset(
                url=img, title=item.get("title", ""),
                description=str(desc[0] if desc else "")[:200],
                asset_type="image", source="loc", license="public domain",
            ))
    except Exception:
        pass
    return results


# ─── Pexels (chave gratuita opcional) ──────────────────────────────────────────

def pexels_search(session, query: str, want_video: bool = False) -> list:
    if not PEXELS_API_KEY:
        return []
    results = []
    headers = {"Authorization": PEXELS_API_KEY}
    try:
        if want_video:
            r = session.get("https://api.pexels.com/videos/search",
                            params={"query": query, "per_page": "6", "orientation": "portrait"},
                            headers=headers, timeout=15)
            if r.status_code != 200:
                return results
            for v in r.json().get("videos", []):
                files = sorted(v.get("video_files", []),
                               key=lambda f: (f.get("height") or 0), reverse=True)
                hd = next((f for f in files if (f.get("height") or 0) <= 1920), files[0] if files else None)
                if not hd:
                    continue
                results.append(VisualAsset(
                    url=hd["link"], title=f"Pexels {v.get('id')}",
                    asset_type="video", duration=float(v.get("duration", 0)),
                    width=hd.get("width", 0), height=hd.get("height", 0),
                    source="pexels", license="Pexels License",
                ))
        else:
            r = session.get("https://api.pexels.com/v1/search",
                            params={"query": query, "per_page": "6", "orientation": "portrait"},
                            headers=headers, timeout=15)
            if r.status_code != 200:
                return results
            for p in r.json().get("photos", []):
                src = p.get("src", {})
                results.append(VisualAsset(
                    url=src.get("large2x") or src.get("large") or src.get("original", ""),
                    title=p.get("alt", "") or f"Pexels {p.get('id')}",
                    asset_type="image", width=p.get("width", 0), height=p.get("height", 0),
                    source="pexels", license="Pexels License",
                ))
    except Exception:
        pass
    return results


# ─── Pixabay (chave gratuita opcional) ─────────────────────────────────────────

def pixabay_search(session, query: str, want_video: bool = False) -> list:
    if not PIXABAY_API_KEY:
        return []
    results = []
    try:
        if want_video:
            r = session.get("https://pixabay.com/api/videos/",
                            params={"key": PIXABAY_API_KEY, "q": query, "per_page": "6"},
                            timeout=15)
            if r.status_code != 200:
                return results
            for v in r.json().get("hits", []):
                vids = v.get("videos", {})
                stream = vids.get("large") or vids.get("medium") or {}
                if not stream.get("url"):
                    continue
                results.append(VisualAsset(
                    url=stream["url"], title=v.get("tags", ""),
                    asset_type="video", duration=float(v.get("duration", 0)),
                    width=stream.get("width", 0), height=stream.get("height", 0),
                    source="pixabay", license="Pixabay License",
                ))
        else:
            r = session.get("https://pixabay.com/api/",
                            params={"key": PIXABAY_API_KEY, "q": query,
                                    "per_page": "6", "image_type": "photo"},
                            timeout=15)
            if r.status_code != 200:
                return results
            for p in r.json().get("hits", []):
                results.append(VisualAsset(
                    url=p.get("largeImageURL", "") or p.get("webformatURL", ""),
                    title=p.get("tags", ""), asset_type="image",
                    width=p.get("imageWidth", 0), height=p.get("imageHeight", 0),
                    source="pixabay", license="Pixabay License",
                ))
    except Exception:
        pass
    return results


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _runtime_secs(runtime: str) -> float:
    if not runtime:
        return 0.0
    parts = str(runtime).split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        return float(parts[0])
    except Exception:
        return 0.0


def active_providers() -> dict:
    """Retorna quais providers estão ativos (para logging)."""
    return {
        "wikimedia": True,
        "archive":   True,
        "loc":       True,
        "pexels":    bool(PEXELS_API_KEY),
        "pixabay":   bool(PIXABAY_API_KEY),
    }
