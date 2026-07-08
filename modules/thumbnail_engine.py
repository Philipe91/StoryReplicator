"""
v5.0 — Thumbnail Engine.

Renderiza a thumbnail automaticamente (antes o pipeline só gerava o *prompt*
e nenhuma imagem). Composição: melhor imagem do vídeo + gradiente escuro +
texto de impacto do publisher_metadata (texto_sobreposicao).

Saídas:
  thumbnail.jpg        1280x720  (YouTube)
  thumbnail_vertical.jpg 1080x1920 (Shorts/TikTok/Reels cover)

100% local (Pillow). Sem custo.
"""

from pathlib import Path

# Fontes bold comuns no Windows, em ordem de preferência
_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\impact.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\seguisb.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]

_TEXT_COLOR    = (255, 221, 0)     # amarelo de alto contraste
_STROKE_COLOR  = (0, 0, 0)


def generate_thumbnails(timeline: dict, metadata: dict, output_dir) -> list:
    """
    Gera thumbnail.jpg (16:9) e thumbnail_vertical.jpg (9:16).
    Retorna lista de paths gerados (vazia se não houver imagem-fonte/Pillow).
    """
    output_dir = Path(output_dir)
    try:
        from PIL import Image
    except ImportError:
        print("  [thumbnail] Pillow não instalado — pulando")
        return []

    src = _pick_source_image(timeline, output_dir)
    if not src:
        print("  [thumbnail] nenhuma imagem-fonte disponível — pulando")
        return []

    text = ((metadata.get("thumbnail") or {}).get("texto_sobreposicao")
            or metadata.get("titulos", {}).get("youtube_shorts", "")
            or "").strip()

    generated = []
    for name, size in (("thumbnail.jpg", (1280, 720)),
                       ("thumbnail_vertical.jpg", (1080, 1920))):
        out = output_dir / name
        try:
            _compose(src, out, size, text)
            generated.append(str(out))
        except Exception as e:
            print(f"  [thumbnail] erro em {name}: {e}")
    return generated


def _pick_source_image(timeline: dict, output_dir: Path):
    """Melhor imagem: prioriza cenas de hook/plot_twist com arquivo válido."""
    scenes = timeline.get("scenes", [])
    ranked = sorted(scenes, key=lambda s: (
        0 if s.get("segment") in ("hook", "plot_twist") else 1,
        s.get("scene_id", 99),
    ))
    for s in ranked:
        img = s.get("image_file", "")
        if img:
            p = output_dir / img
            if p.exists() and p.stat().st_size > 5000:
                return p
    return None


def _compose(src: Path, out: Path, size: tuple, text: str) -> None:
    from PIL import Image, ImageDraw, ImageFont, ImageEnhance

    W, H = size
    img = Image.open(src).convert("RGB")

    # cover-crop para o aspect alvo
    ratio = max(W / img.width, H / img.height)
    img = img.resize((round(img.width * ratio), round(img.height * ratio)))
    x = (img.width - W) // 2
    y = (img.height - H) // 2
    img = img.crop((x, y, x + W, y + H))

    # leve boost de contraste/saturação (estilo thumbnail)
    img = ImageEnhance.Contrast(img).enhance(1.15)
    img = ImageEnhance.Color(img).enhance(1.2)

    # gradiente escuro na base (área do texto)
    overlay = Image.new("L", (1, H), 0)
    for yy in range(H):
        frac = max(0.0, (yy / H - 0.45)) / 0.55      # começa a escurecer em 45%
        overlay.putpixel((0, yy), int(200 * frac))
    overlay = overlay.resize((W, H))
    black = Image.new("RGB", (W, H), (0, 0, 0))
    img = Image.composite(black, img, overlay)

    if text:
        draw = ImageDraw.Draw(img)
        font_size = int(H * (0.085 if H > W else 0.055))
        font = _load_font(font_size)
        lines = _wrap(text.upper(), 14 if H > W else 18)
        stroke = max(2, font_size // 12)

        line_h  = int(font_size * 1.18)
        total_h = line_h * len(lines)
        ty      = H - total_h - int(H * 0.07)
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font, stroke_width=stroke)
            tw   = bbox[2] - bbox[0]
            draw.text(((W - tw) // 2, ty), line, font=font,
                      fill=_TEXT_COLOR, stroke_width=stroke, stroke_fill=_STROKE_COLOR)
            ty += line_h

    img.save(out, "JPEG", quality=90)


def _load_font(size: int):
    from PIL import ImageFont
    for cand in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(cand, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _wrap(text: str, max_chars: int) -> list:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > max_chars and cur:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines[:3]   # máx 3 linhas
