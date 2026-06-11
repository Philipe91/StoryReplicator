"""
StoryReplicator v3.7 — Visual Quality Filter

Rejeita ativos visuais de baixa qualidade ANTES da renderização:
  - resolução abaixo do mínimo (imagem 1280px, vídeo 720p)
  - imagens borradas (variância do Laplaciano)
  - imagens excessivamente comprimidas (bytes/pixel baixo)
  - thumbnails / screenshots (heurística por dimensão e nome)

Calcula score de qualidade visual e, quando o ativo é muito relevante mas
pequeno, sinaliza para upscale (Real-ESRGAN / Upscayl).
"""

import subprocess
from pathlib import Path

from config import (
    MIN_IMAGE_WIDTH, PREFERRED_IMAGE_WIDTH, MIN_VIDEO_HEIGHT, PREFERRED_VIDEO_HEIGHT,
    BLUR_VARIANCE_THRESHOLD, MIN_BYTES_PER_PIXEL,
    REALESRGAN_PATH, UPSCAYL_PATH, UPSCALE_RELEVANCE_THRESHOLD,
)


# ─── Avaliação pré-download (por metadados do candidato) ──────────────────────

def passes_metadata_filter(asset, relevance_score: float = 0.0) -> tuple:
    """
    Filtro rápido por metadados (sem baixar). Retorna (ok, motivo).
    Usado para descartar candidatos óbvios antes do download.
    """
    w, h = asset.width or 0, asset.height or 0

    # Heurística de thumbnail por nome
    url_low = (asset.url or "").lower()
    if any(t in url_low for t in ("thumb", "/tn/", "_small", "icon", "/150px", "/120px")):
        # só rejeita se também não tiver dimensão grande declarada
        if not w or w < MIN_IMAGE_WIDTH:
            return False, "thumbnail_url"

    if asset.asset_type == "image":
        # Se a fonte declara dimensão, exige mínimo (upscale pode salvar relevantes)
        if w and w < MIN_IMAGE_WIDTH:
            if relevance_score >= UPSCALE_RELEVANCE_THRESHOLD and upscale_available():
                return True, "below_min_but_upscalable"
            return False, f"width<{MIN_IMAGE_WIDTH}"
    else:  # video
        if h and h < MIN_VIDEO_HEIGHT:
            return False, f"height<{MIN_VIDEO_HEIGHT}"

    return True, "ok"


# ─── Avaliação pós-download (arquivo real) ────────────────────────────────────

def evaluate_image_file(path: Path, relevance_score: float = 0.0) -> dict:
    """
    Analisa o arquivo de imagem baixado.
    Retorna {ok, width, height, sharpness, quality_score, reason, needs_upscale}.
    """
    path = Path(path)
    result = {"ok": False, "width": 0, "height": 0, "sharpness": 0.0,
              "quality_score": 0.0, "reason": "", "needs_upscale": False}

    # PIL ausente → não conseguimos avaliar; aceita para não bloquear pipeline
    try:
        from PIL import Image
        import numpy as np
    except ImportError:
        result["ok"] = True
        result["quality_score"] = 5.0
        result["reason"] = "pil_missing"
        return result

    # Imagem inválida/corrompida (ex: HTML salvo como .jpg) → REJEITA
    try:
        with Image.open(path) as _check:
            _check.verify()
    except Exception as e:
        result["reason"] = f"corrupted:{e}"
        return result   # ok=False → rejeitada

    try:
        with Image.open(path) as im:
            im = im.convert("RGB")
            w, h = im.size
            result["width"], result["height"] = w, h

            # 1. Resolução mínima
            if w < MIN_IMAGE_WIDTH:
                if relevance_score >= UPSCALE_RELEVANCE_THRESHOLD and upscale_available():
                    result["needs_upscale"] = True
                else:
                    result["reason"] = f"width {w}<{MIN_IMAGE_WIDTH}"
                    return result

            # 2. Compressão (bytes por pixel)
            bpp = path.stat().st_size / max(w * h, 1)
            if bpp < MIN_BYTES_PER_PIXEL and not result["needs_upscale"]:
                result["reason"] = f"over_compressed bpp={bpp:.3f}"
                return result

            # 3. Nitidez (variância do Laplaciano)
            sharpness = _laplacian_variance(im, np)
            result["sharpness"] = round(sharpness, 1)
            if sharpness < BLUR_VARIANCE_THRESHOLD and not result["needs_upscale"]:
                result["reason"] = f"blurry var={sharpness:.0f}"
                return result

            # 4. Score de qualidade combinado (0-10)
            result["quality_score"] = _image_quality_score(w, h, sharpness, bpp)
            result["ok"] = True
            result["reason"] = "ok" if not result["needs_upscale"] else "upscale_pending"
            return result

    except Exception as e:
        result["reason"] = f"error:{e}"
        # Sem PIL/numpy: aceita por padrão (não bloqueia o pipeline)
        result["ok"] = True
        result["quality_score"] = 5.0
        return result


def evaluate_video_file(path: Path, ffmpeg_exe: str = "ffmpeg") -> dict:
    """Analisa resolução do vídeo baixado via FFmpeg."""
    result = {"ok": False, "width": 0, "height": 0, "quality_score": 0.0, "reason": ""}
    try:
        r = subprocess.run([ffmpeg_exe, "-i", str(path)],
                           capture_output=True, text=True, timeout=20)
        w, h = _parse_video_resolution(r.stderr)
        result["width"], result["height"] = w, h
        if h and h < MIN_VIDEO_HEIGHT:
            result["reason"] = f"height {h}<{MIN_VIDEO_HEIGHT}"
            return result
        result["quality_score"] = _video_quality_score(h)
        result["ok"] = True
        result["reason"] = "ok"
    except Exception as e:
        result["reason"] = f"error:{e}"
        result["ok"] = True            # não bloqueia se FFprobe falhar
        result["quality_score"] = 6.0
    return result


# ─── Upscale (Real-ESRGAN / Upscayl) ──────────────────────────────────────────

def is_modern_color(path) -> bool:
    """
    True se a imagem é colorida vibrante (foto digital moderna) — indício de
    museu/marco/réplica/foto atual, não do evento histórico (que é P&B/sépia).
    Usado para casos antigos (< ~1970) garantirem material de época.
    """
    try:
        from PIL import Image
        import numpy as np
        with Image.open(path) as im:
            small = im.convert("HSV").resize((128, 128))
            sat = np.asarray(small)[:, :, 1].astype(float) / 255.0
        return float(sat.mean()) > 0.18 or float((sat > 0.35).mean()) > 0.25
    except Exception:
        return False


def upscale_available() -> bool:
    return bool(REALESRGAN_PATH or UPSCAYL_PATH)


def upscale_image(src: Path, dest: Path = None, scale: int = 4) -> bool:
    """
    Faz upscale com Real-ESRGAN ou Upscayl, se configurado.
    Retorna True se gerou imagem ampliada em `dest` (ou sobrescreve src).
    """
    src  = Path(src)
    dest = Path(dest) if dest else src
    if REALESRGAN_PATH:
        cmd = [REALESRGAN_PATH, "-i", str(src), "-o", str(dest), "-s", str(scale)]
    elif UPSCAYL_PATH:
        cmd = [UPSCAYL_PATH, "-i", str(src), "-o", str(dest), "-s", str(scale)]
    else:
        return False
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=120)
        return r.returncode == 0 and dest.exists()
    except Exception:
        return False


# ─── Scoring de qualidade (usado no engine) ───────────────────────────────────

def visual_quality_weight(asset) -> float:
    """
    Peso de qualidade visual (0.0–1.0) para somar ao score do candidato.
    Baseado apenas em metadados (resolução/proporção declaradas).
    """
    w, h = asset.width or 0, asset.height or 0
    if not w or not h:
        return 0.3   # desconhecido — crédito neutro baixo

    if asset.asset_type == "image":
        res_factor = min(w / PREFERRED_IMAGE_WIDTH, 1.0)
    else:
        res_factor = min(h / PREFERRED_VIDEO_HEIGHT, 1.0)

    # Proporção: premia vertical/quadrado (melhor para 9:16)
    ratio = h / max(w, 1)
    ratio_factor = 1.0 if ratio >= 1.2 else (0.7 if ratio >= 0.9 else 0.5)

    return round(res_factor * 0.7 + ratio_factor * 0.3, 3)


# ─── Helpers internos ─────────────────────────────────────────────────────────

def _laplacian_variance(im, np) -> float:
    """Variância do Laplaciano (medida de nitidez). Maior = mais nítido."""
    # Reduz para acelerar
    small = im.convert("L").resize((256, 256))
    arr   = np.asarray(small, dtype=np.float64)
    # Kernel laplaciano 3x3
    lap = (
        -4 * arr
        + np.roll(arr, 1, axis=0) + np.roll(arr, -1, axis=0)
        + np.roll(arr, 1, axis=1) + np.roll(arr, -1, axis=1)
    )
    return float(lap.var())


def _image_quality_score(w: int, h: int, sharpness: float, bpp: float) -> float:
    res_pts   = min(w / PREFERRED_IMAGE_WIDTH, 1.0) * 4
    sharp_pts = min(sharpness / 400.0, 1.0) * 4
    comp_pts  = min(bpp / 0.5, 1.0) * 2
    return round(min(res_pts + sharp_pts + comp_pts, 10.0), 1)


def _video_quality_score(h: int) -> float:
    if h >= PREFERRED_VIDEO_HEIGHT:
        return 10.0
    if h >= MIN_VIDEO_HEIGHT:
        return 7.0
    return 4.0


def _parse_video_resolution(stderr: str) -> tuple:
    import re
    for line in stderr.split("\n"):
        if "Video:" in line:
            m = re.search(r"(\d{2,5})x(\d{2,5})", line)
            if m:
                return int(m.group(1)), int(m.group(2))
    return 0, 0
