"""
StoryReplicator v3.8 — Translator

Traduz narração e metadados para múltiplos idiomas usando deep-translator
(Google Translate gratuito, sem chave de API). Cache local por idioma.

Quando a tradução automática falha, retorna o texto original (fallback seguro).
"""

import hashlib
import json
from pathlib import Path


def translate_text(text: str, target: str, source: str = "pt", cache_dir: Path = None) -> str:
    """Traduz um texto. Retorna original se idioma-alvo == origem ou em erro."""
    if not text or not text.strip():
        return text
    if target == source:
        return text

    # Cache
    if cache_dir:
        cache_dir = Path(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        key = hashlib.md5(f"{source}:{target}:{text}".encode()).hexdigest()
        cf  = cache_dir / f"tr_{key}.txt"
        if cf.exists():
            return cf.read_text(encoding="utf-8")

    result = _do_translate(text, target, source)

    if cache_dir and result:
        cf.write_text(result, encoding="utf-8")
    return result or text


def _do_translate(text: str, target: str, source: str) -> str:
    """Tradução via Google Translate (deep-translator). Quebra textos longos."""
    try:
        from deep_translator import GoogleTranslator
    except ImportError:
        print("[translator] deep-translator não instalado — texto não traduzido")
        return text

    tr = GoogleTranslator(source=source, target=target)
    # Google limita ~5000 chars por chamada; quebra por frases se necessário
    if len(text) <= 4500:
        try:
            return tr.translate(text)
        except Exception as e:
            print(f"[translator] erro: {e}")
            return text

    # Texto longo: traduz em blocos por sentença
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text)
    out, buf = [], ""
    for s in sentences:
        if len(buf) + len(s) > 4500:
            try:
                out.append(tr.translate(buf))
            except Exception:
                out.append(buf)
            buf = s
        else:
            buf += (" " + s) if buf else s
    if buf:
        try:
            out.append(tr.translate(buf))
        except Exception:
            out.append(buf)
    return " ".join(out)


def translate_narration(narration: dict, target: str, cache_dir: Path = None) -> dict:
    """Traduz a narração completa e cada segmento."""
    out = dict(narration)
    out["narration_full"] = translate_text(
        narration.get("narration_full", ""), target, cache_dir=cache_dir)
    segs = []
    for s in narration.get("segments", []):
        s2 = dict(s)
        s2["text"] = translate_text(s.get("text", ""), target, cache_dir=cache_dir)
        segs.append(s2)
    out["segments"] = segs
    out["language"] = target
    return out


def translate_storyboard_subtitles(storyboard: dict, target: str, cache_dir: Path = None) -> dict:
    """Traduz apenas as legendas e narração de cada cena (para legendas no idioma)."""
    out = dict(storyboard)
    cenas = []
    for c in storyboard.get("cenas", []):
        c2 = dict(c)
        c2["legenda"]  = translate_text(c.get("legenda", ""), target, cache_dir=cache_dir)
        c2["narracao"] = translate_text(c.get("narracao", ""), target, cache_dir=cache_dir)
        cenas.append(c2)
    out["cenas"] = cenas
    return out


def translate_metadata(metadata: dict, target: str, cache_dir: Path = None) -> dict:
    """Traduz títulos, descrições e CTA dos metadados de publicação."""
    out = dict(metadata)

    if "titulos" in metadata:
        out["titulos"] = {
            k: translate_text(v, target, cache_dir=cache_dir)
            for k, v in metadata["titulos"].items()
        }
    if "descricao" in metadata:
        out["descricao"] = {
            k: translate_text(v, target, cache_dir=cache_dir)
            for k, v in metadata["descricao"].items()
        }
    if "cta_comentario" in metadata:
        out["cta_comentario"] = translate_text(
            metadata["cta_comentario"], target, cache_dir=cache_dir)
    # Hashtags: mantém as principais, traduz termos quando fizer sentido
    out["language"] = target
    return out
