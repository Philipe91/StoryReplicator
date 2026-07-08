"""
v5.0 — Slide Renderer (modo NotebookLM).

Renderiza cada slide do deck em PNG usando Pillow — zero dependência nova,
100% local. Layouts: title, bullets, stat, quote, cta. Temas de cor trocáveis
(equivalente aos "estilos" do NotebookLM).
"""

from pathlib import Path

# ─── Temas ─────────────────────────────────────────────────────────────────────
THEMES = {
    "deep": {   # padrão — escuro editorial
        "bg_top":    (15, 17, 21),
        "bg_bottom": (26, 30, 42),
        "text":      (240, 240, 245),
        "muted":     (150, 156, 170),
        "accent":    (255, 209, 102),   # âmbar
    },
    "paper": {  # claro estilo whiteboard
        "bg_top":    (248, 246, 240),
        "bg_bottom": (233, 229, 218),
        "text":      (30, 32, 38),
        "muted":     (110, 112, 120),
        "accent":    (214, 69, 65),     # vermelho tijolo
    },
    "ocean": {
        "bg_top":    (10, 22, 40),
        "bg_bottom": (16, 42, 67),
        "text":      (235, 244, 250),
        "muted":     (135, 165, 190),
        "accent":    (76, 201, 240),    # ciano
    },
}

_FONT_BOLD = [
    r"C:\Windows\Fonts\seguisb.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
_FONT_REG = [
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def render_deck(deck: dict, output_dir, theme: str = "deep",
                size: tuple = (1080, 1920)) -> dict:
    """
    Renderiza todos os slides em assets/slide_NN.png.
    Retorna {slide_id: "assets/slide_NN.png"}.
    """
    output_dir = Path(output_dir)
    assets = output_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    th = THEMES.get(theme, THEMES["deep"])

    total = len(deck.get("slides", []))
    paths = {}
    for i, slide in enumerate(deck.get("slides", [])):
        name = f"slide_{slide['id']:02d}.png"
        _render_slide(slide, assets / name, th, size, index=i + 1, total=total,
                      deck_title=deck.get("titulo_deck", ""))
        paths[slide["id"]] = f"assets/{name}"
    return paths


# ─── Render de um slide ────────────────────────────────────────────────────────

def _render_slide(slide: dict, out: Path, th: dict, size: tuple,
                  index: int, total: int, deck_title: str) -> None:
    from PIL import Image, ImageDraw

    W, H = size
    img  = _gradient(W, H, th["bg_top"], th["bg_bottom"])
    d    = ImageDraw.Draw(img)
    M    = int(W * 0.09)            # margem lateral
    layout = slide.get("layout", "bullets")

    # barra de acento no topo + rodapé com progresso
    d.rectangle([M, int(H * 0.075), M + int(W * 0.14), int(H * 0.075) + 12],
                fill=th["accent"])
    footer = f"{index:02d} / {total:02d}" + (f"  ·  {deck_title[:40]}" if deck_title else "")
    d.text((M, H - int(H * 0.05)), footer, font=_font(_FONT_REG, int(H * 0.016)),
           fill=th["muted"])

    if layout == "title":
        _layout_title(d, slide, th, W, H, M)
    elif layout == "stat":
        _layout_stat(d, slide, th, W, H, M)
    elif layout == "quote":
        _layout_quote(d, slide, th, W, H, M)
    elif layout == "cta":
        _layout_cta(d, slide, th, W, H, M)
    else:
        _layout_bullets(d, slide, th, W, H, M)

    img.save(out, "PNG")


def _layout_title(d, s, th, W, H, M):
    y = int(H * 0.34)
    y = _text_block(d, s.get("titulo", ""), (M, y), W - 2 * M,
                    _font(_FONT_BOLD, int(H * 0.052)), th["text"], line_gap=1.12)
    if s.get("subtitulo"):
        _text_block(d, s["subtitulo"], (M, y + int(H * 0.03)), W - 2 * M,
                    _font(_FONT_REG, int(H * 0.026)), th["muted"])


def _layout_bullets(d, s, th, W, H, M):
    y = int(H * 0.16)
    y = _text_block(d, s.get("titulo", ""), (M, y), W - 2 * M,
                    _font(_FONT_BOLD, int(H * 0.036)), th["text"])
    y += int(H * 0.045)
    f_b = _font(_FONT_REG, int(H * 0.026))
    for b in (s.get("bullets") or [])[:4]:
        d.ellipse([M, y + int(H * 0.011), M + 18, y + int(H * 0.011) + 18],
                  fill=th["accent"])
        y = _text_block(d, str(b), (M + 44, y), W - 2 * M - 44, f_b, th["text"])
        y += int(H * 0.028)


def _layout_stat(d, s, th, W, H, M):
    stat  = s.get("stat") or {}
    valor = str(stat.get("valor", s.get("titulo", "")))
    y = int(H * 0.20)
    y = _text_block(d, s.get("titulo", ""), (M, y), W - 2 * M,
                    _font(_FONT_BOLD, int(H * 0.030)), th["muted"])
    f_big = _font(_FONT_BOLD, int(H * 0.11))
    bbox  = d.textbbox((0, 0), valor, font=f_big)
    d.text(((W - (bbox[2] - bbox[0])) // 2, int(H * 0.38)), valor,
           font=f_big, fill=th["accent"])
    _text_block(d, str(stat.get("rotulo", "")), (M, int(H * 0.55)), W - 2 * M,
                _font(_FONT_REG, int(H * 0.028)), th["text"], align_center=True, draw_w=W - 2 * M)


def _layout_quote(d, s, th, W, H, M):
    q = s.get("quote") or {}
    d.text((M, int(H * 0.22)), "“", font=_font(_FONT_BOLD, int(H * 0.12)),
           fill=th["accent"])
    y = _text_block(d, str(q.get("texto", s.get("titulo", ""))),
                    (M, int(H * 0.34)), W - 2 * M,
                    _font(_FONT_BOLD, int(H * 0.036)), th["text"], line_gap=1.25)
    if q.get("autor"):
        _text_block(d, f"— {q['autor']}", (M, y + int(H * 0.035)), W - 2 * M,
                    _font(_FONT_REG, int(H * 0.024)), th["muted"])


def _layout_cta(d, s, th, W, H, M):
    y = int(H * 0.38)
    y = _text_block(d, s.get("titulo", ""), (M, y), W - 2 * M,
                    _font(_FONT_BOLD, int(H * 0.046)), th["text"])
    if s.get("subtitulo"):
        y += int(H * 0.03)
        _text_block(d, s["subtitulo"], (M, y), W - 2 * M,
                    _font(_FONT_REG, int(H * 0.028)), th["accent"])


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _gradient(W, H, top, bottom):
    from PIL import Image
    img = Image.new("RGB", (1, H))
    for y in range(H):
        t = y / max(H - 1, 1)
        img.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return img.resize((W, H))


def _font(candidates, size):
    from PIL import ImageFont
    for c in candidates:
        try:
            return ImageFont.truetype(c, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _text_block(d, text, pos, max_w, font, fill, line_gap=1.18,
                align_center=False, draw_w=0):
    """Desenha texto com wrap. Retorna o y final."""
    x, y = pos
    if not text:
        return y
    words, line = str(text).split(), ""
    lines = []
    for w in words:
        cand = f"{line} {w}".strip()
        if d.textbbox((0, 0), cand, font=font)[2] > max_w and line:
            lines.append(line)
            line = w
        else:
            line = cand
    if line:
        lines.append(line)

    lh = int(font.size * line_gap)
    for ln in lines:
        lx = x
        if align_center and draw_w:
            tw = d.textbbox((0, 0), ln, font=font)[2]
            lx = x + (draw_w - tw) // 2
        d.text((lx, y), ln, font=font, fill=fill)
        y += lh
    return y
