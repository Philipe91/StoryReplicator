"""
v5.0 — B-roll Engine.

O Editor AI marca cenas com layer "document_overlay" e gera broll_queries,
e o Remotion (BrollOverlay) espera arquivos broll/broll_XX_doc.jpg — mas
nenhuma etapa criava esses arquivos (feature órfã desde a v3.5).

Este módulo fecha o circuito: para cada cena marcada, busca uma imagem
documental (Wikimedia/Internet Archive, gratuitos) e salva no caminho
que o renderer espera.
"""

from pathlib import Path

from modules.asset_providers import wikimedia_search, archive_search
from modules.request_manager import ThrottledSession


def acquire_broll(edit_decisions: list, output_dir, max_scenes: int = 6) -> int:
    """
    Baixa b-roll documental para cenas com layer "document_overlay".
    Limita a max_scenes para não estourar o tempo de pipeline.
    Retorna quantos arquivos foram criados.
    """
    output_dir = Path(output_dir)
    targets = [
        d for d in edit_decisions
        if "document_overlay" in getattr(d, "layers", [])
        and getattr(d, "broll_queries", [])
    ][:max_scenes]
    if not targets:
        return 0

    broll_dir = output_dir / "broll"
    broll_dir.mkdir(parents=True, exist_ok=True)
    session = ThrottledSession()
    created = 0

    for d in targets:
        dest = broll_dir / f"broll_{d.scene_id:02d}_doc.jpg"
        if dest.exists():
            created += 1
            continue
        for query in d.broll_queries[:2]:
            asset = _best_image(session, query)
            if asset and _download_jpeg(session, asset.url, dest):
                created += 1
                break
    return created


def _best_image(session, query: str):
    """Primeira imagem razoável (≥600px de largura) para a query."""
    for provider in (wikimedia_search, archive_search):
        try:
            for a in provider(session, query):
                if a.asset_type == "image" and (a.width or 601) > 600:
                    return a
        except Exception:
            continue
    return None


def _download_jpeg(session, url: str, dest: Path) -> bool:
    try:
        r = session.get(url, timeout=20)
        if r.status_code != 200 or len(r.content) < 5000:
            return False
        tmp = dest.with_suffix(".tmp")
        tmp.write_bytes(r.content)
        try:
            from PIL import Image
            with Image.open(tmp) as im:
                im.convert("RGB").save(dest, "JPEG", quality=88)
            tmp.unlink(missing_ok=True)
        except Exception:
            tmp.rename(dest)   # já pode ser JPEG válido
        return dest.exists()
    except Exception:
        return False
