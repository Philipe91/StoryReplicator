"""
v6.3 — Motion Design Engine (HyperFrames).

Camada automática de motion graphics sobre o vídeo renderizado, no padrão
dos grandes canais: cards de dados, chips, tipografia cinética e CTA,
sincronizados com a narração pelos word boundaries REAIS do TTS.

Fluxo:
  1. O LLM desenha os cards (tipo/tempo/conteúdo) a partir dos segmentos
     da narração com seus tempos reais
  2. Templates HTML/CSS (paleta noir, zona segura p/ legendas) + GSAP
  3. `npx hyperframes render` (Chrome headless local, grátis, Apache 2.0)
  4. Muxa o áudio original de volta (o render sai mudo)

Uso: apply_motion_design(video_path, narration, boundaries, workdir, ffmpeg)
Retorna o path do vídeo final com overlays (ou None se falhar — o vídeo
original permanece intacto).
"""

import json
import shutil
import subprocess
from pathlib import Path

_ACCENTS = ["#4cc9f0", "#f72585", "#4ade80", "#fb923c", "#a78bfa"]
_SKILL_ASSETS = Path(__file__).resolve().parents[1] / ".agents" / "skills" / \
    "talking-head-recut" / "assets"

_VALID_TYPES = {"number", "panel", "chips", "kinetic", "pill"}


def _npx() -> str:
    return shutil.which("npx") or shutil.which("npx.cmd") or "npx"


# ─── 1. Design dos cards via LLM ───────────────────────────────────────────────

def design_cards(narration: dict, boundaries: list, duration: float) -> list:
    from modules.llm_client import ask_json

    spans = _segment_spans(boundaries)
    seg_info = []
    for seg in narration.get("segments", []):
        sid = seg.get("id", "")
        span = spans.get(sid)
        if span:
            seg_info.append({"id": sid, "start": round(span[0], 1),
                             "end": round(span[1], 1),
                             "texto": seg.get("text", "")[:220]})

    prompt = f"""Você é o motion designer de um canal grande do YouTube.
O vídeo abaixo já está pronto (narração + imagens + legendas queimadas na parte
INFERIOR). Desenhe de 4 a 7 CARDS de overlay animado para o TERÇO SUPERIOR da
tela, sincronizados com o que o narrador diz.

SEGMENTOS DA NARRAÇÃO (com tempos reais em segundos):
{json.dumps(seg_info, ensure_ascii=False, indent=1)}

TIPOS DE CARD DISPONÍVEIS:
- "number": número gigante com count-up (use quando houver número marcante).
  campos: kicker, number (só dígitos), label
- "panel":  painel de vidro com dado/curiosidade. campos: kicker, title, detail
- "chips":  lista de 3-8 itens que pipocam em sequência. campos: kicker, items[]
- "kinetic": título letra-a-letra para momento de virada. campos: title, sub
- "pill":   encerramento/CTA. campos: title, pill

REGRAS:
1. O primeiro card cobre o hook (começa entre 0.5 e 1.5s).
2. O último é um "pill" de CTA terminando ~0.5s antes do fim ({duration:.1f}s).
3. Cada card dura 4-10s, DENTRO do segmento que o motiva, sem sobreposição
   entre cards (deixe ≥1s de respiro entre eles).
4. Conteúdo CURTO (títulos ≤5 palavras, detail ≤12 palavras) e fiel à narração.
5. accent: 0-4 (varie entre cards).

Retorne APENAS JSON:
{{"cards": [{{"type": "number", "start": 0.6, "end": 5.5, "accent": 0,
             "kicker": "...", "number": "8", "label": "...",
             "title": "...", "detail": "...", "sub": "...", "pill": "...",
             "items": ["..."]}}]}}
Campos não usados pelo tipo podem ser omitidos."""

    data = ask_json(prompt, max_tokens=3000, fallback={"cards": []})
    cards = _sanitize_cards(data.get("cards", []), duration)
    if not cards:
        cards = _fallback_cards(narration, duration)
    return cards


def _segment_spans(boundaries: list) -> dict:
    spans = {}
    for b in boundaries:
        seg = b.get("segment", "")
        if not seg:
            continue
        if seg not in spans:
            spans[seg] = [b["start"], b["end"]]
        else:
            spans[seg][0] = min(spans[seg][0], b["start"])
            spans[seg][1] = max(spans[seg][1], b["end"])
    return spans


def _sanitize_cards(cards: list, duration: float) -> list:
    out, prev_end = [], 0.0
    for i, c in enumerate(cards):
        if not isinstance(c, dict) or c.get("type") not in _VALID_TYPES:
            continue
        try:
            start = max(float(c.get("start", 0)), prev_end + 1.0 if out else 0.5)
            end   = min(float(c.get("end", start + 6)), duration - 0.4)
        except (TypeError, ValueError):
            continue
        if end - start < 2.5:
            continue
        c = dict(c)
        c["id"] = f"card-{i+1:02d}"
        c["start"], c["end"] = round(start, 2), round(end, 2)
        c["accent"] = int(c.get("accent", i)) % 5
        out.append(c)
        prev_end = end
    return out[:8]


def _fallback_cards(narration: dict, duration: float) -> list:
    """Heurística mínima se o LLM falhar: hook cinético + CTA."""
    segs = narration.get("segments", [])
    hook = (segs[0].get("text", "") if segs else "").split(".")[0][:40]
    return [
        {"id": "card-01", "type": "kinetic", "start": 0.6,
         "end": min(6.0, duration - 1), "accent": 0,
         "title": hook.upper()[:24] or "ASSISTA ATÉ O FIM", "sub": ""},
        {"id": "card-02", "type": "pill",
         "start": max(duration - 8, duration * 0.9), "end": duration - 0.5,
         "accent": 0, "title": "GOSTOU?",
         "pill": "💬 Comente  ·  Inscreva-se"},
    ]


# ─── 2. Geração de HTML + GSAP ─────────────────────────────────────────────────

def _esc(t) -> str:
    return (str(t or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def _card_html(c: dict) -> str:
    cid, acc = c["id"], f"var(--accent-{c['accent']})"
    t = c["type"]
    if t == "number":
        inner = (f'<div class="kicker" style="color:{acc}">{_esc(c.get("kicker"))}</div>'
                 f'<div class="big" id="{cid}-num">{_esc(c.get("number", "0"))}</div>'
                 f'<div class="label">{_esc(c.get("label"))}</div>'
                 f'<div class="rule" id="{cid}-rule" style="background:{acc}"></div>')
        root_cls = "root center"
    elif t == "panel":
        inner = (f'<div class="panel" id="{cid}-panel" style="border-left-color:{acc}">'
                 f'<div class="kicker" style="color:{acc}">{_esc(c.get("kicker"))}</div>'
                 f'<div class="title">{_esc(c.get("title"))}</div>'
                 f'<div class="detail">{_esc(c.get("detail"))}</div></div>')
        root_cls = "root left"
    elif t == "chips":
        chips = "".join(f'<div class="chip" style="background:{acc}">{_esc(i)}</div>'
                        for i in (c.get("items") or [])[:8])
        inner = (f'<div class="kicker boxed" style="color:{acc}">{_esc(c.get("kicker"))}</div>'
                 f'<div class="chips" id="{cid}-chips">{chips}</div>')
        root_cls = "root center"
    elif t == "kinetic":
        chars = "".join(f'<span class="char">{"&nbsp;" if ch == " " else _esc(ch)}</span>'
                        for ch in str(c.get("title", ""))[:26])
        sub = (f'<div class="sub" id="{cid}-sub">{_esc(c.get("sub"))}</div>'
               if c.get("sub") else "")
        inner = f'<div class="ktitle" id="{cid}-title">{chars}</div>{sub}'
        root_cls = "root center"
    else:  # pill
        inner = (f'<div class="ctitle" id="{cid}-title">{_esc(c.get("title"))}</div>'
                 f'<div class="pillbox" id="{cid}-pill" style="background:{acc}">'
                 f'{_esc(c.get("pill"))}</div>')
        root_cls = "root center"

    return (f'<div class="card-host clip" data-card-id="{cid}" '
            f'data-start="{c["start"]}" data-duration="{round(c["end"]-c["start"],3)}" '
            f'data-track-index="2" '
            f'style="left:0;top:0;width:1080px;height:1920px;visibility:hidden;opacity:0;">'
            f'<div class="card" data-card-id="{cid}"><div class="{root_cls}">{inner}'
            f'</div></div></div>')


def _gsap_block(c: dict, fps: int = 30) -> str:
    def q(t):
        return round(round(t * fps) / fps, 4)
    cid = c["id"]
    s, e = c["start"], c["end"]
    host = f'.card-host[data-card-id="{cid}"]'
    lines = [
        f'tl.set(\'{host}\', {{visibility:"visible"}}, {q(s)});',
        f'tl.fromTo(\'{host}\', {{opacity:0}}, {{opacity:1, duration:0.4, ease:"power2.out"}}, {q(s)});',
    ]
    t = c["type"]
    if t == "number":
        try:
            target = int("".join(ch for ch in str(c.get("number", "0")) if ch.isdigit()) or 0)
        except ValueError:
            target = 0
        lines += [
            f'(function(){{const o={{v:0}};tl.to(o,{{v:{target},duration:0.9,ease:"power2.out",'
            f'onUpdate:function(){{const el=document.querySelector(\'.card[data-card-id="{cid}"] #{cid}-num\');'
            f'if(el)el.textContent=String(Math.round(o.v));}}}},{q(s+0.4)});}})();',
            f'tl.fromTo(\'.card[data-card-id="{cid}"] #{cid}-num\', {{opacity:0,scale:0.6}}, '
            f'{{opacity:1,scale:1,duration:0.5,ease:"back.out(1.6)"}}, {q(s+0.4)});',
            f'tl.fromTo(\'.card[data-card-id="{cid}"] #{cid}-rule\', {{width:0}}, '
            f'{{width:320,duration:0.5,ease:"power2.out"}}, {q(s+1.1)});',
        ]
    elif t == "panel":
        lines.append(
            f'tl.fromTo(\'.card[data-card-id="{cid}"] #{cid}-panel\', {{opacity:0,x:-90}}, '
            f'{{opacity:1,x:0,duration:0.55,ease:"power2.out"}}, {q(s+0.2)});')
    elif t == "chips":
        lines.append(
            f'tl.from(\'.card[data-card-id="{cid}"] .chip\', {{opacity:0,y:26,scale:0.7,'
            f'duration:0.4,ease:"back.out(1.5)",stagger:0.12}}, {q(s+0.4)});')
    elif t == "kinetic":
        lines.append(
            f'tl.from(\'.card[data-card-id="{cid}"] #{cid}-title .char\', {{opacity:0,y:40,scale:0.7,'
            f'duration:0.5,ease:"power2.out",stagger:0.05}}, {q(s+0.3)});')
        if c.get("sub"):
            lines.append(
                f'tl.fromTo(\'.card[data-card-id="{cid}"] #{cid}-sub\', {{opacity:0,y:20}}, '
                f'{{opacity:1,y:0,duration:0.5,ease:"power2.out"}}, {q(s+1.2)});')
    else:  # pill
        lines += [
            f'tl.fromTo(\'.card[data-card-id="{cid}"] #{cid}-title\', {{opacity:0,scale:0.7}}, '
            f'{{opacity:1,scale:1,duration:0.5,ease:"back.out(1.6)"}}, {q(s+0.3)});',
            f'tl.fromTo(\'.card[data-card-id="{cid}"] #{cid}-pill\', {{opacity:0,y:40}}, '
            f'{{opacity:1,y:0,duration:0.5,ease:"power2.out"}}, {q(s+1.0)});',
        ]
    lines += [
        f'tl.to(\'{host}\', {{opacity:0,duration:0.35,ease:"power2.in"}}, {q(e-0.37)});',
        f'tl.set(\'{host}\', {{visibility:"hidden"}}, {q(e)});',
    ]
    return "\n          ".join(lines)


_CSS = """
      @font-face { font-family:"Inter"; src:url("fonts/Inter-400-latin.woff2") format("woff2"); font-weight:400; font-display:block; }
      @font-face { font-family:"Inter"; src:url("fonts/Inter-700-latin.woff2") format("woff2"); font-weight:700; font-display:block; }
      :root { --accent-0:#4cc9f0; --accent-1:#f72585; --accent-2:#4ade80;
              --accent-3:#fb923c; --accent-4:#a78bfa; }
      * { box-sizing:border-box; }
      html,body { margin:0; padding:0; width:100%; height:100%; overflow:hidden;
        background:#000; font-family:"Inter", ui-sans-serif, system-ui, sans-serif; }
      #stage { position:relative; width:100%; height:100%; overflow:hidden; }
      .video-wrapper { position:absolute; left:0; top:0; width:1080px; height:1920px; overflow:hidden; }
      .video-wrapper video { width:100%; height:100%; object-fit:cover; }
      .card-host { position:absolute; pointer-events:none; overflow:hidden; }
      .card-host .card { position:relative; width:100%; height:100%; overflow:hidden; }
      .card-host .char { display:inline-block; visibility:visible; }
      .card .root { width:100%; height:100%; background:transparent; display:flex;
        flex-direction:column; color:#f1f1f1; }
      .card .root.center { align-items:center; padding-top:175px; }
      .card .root.left { align-items:flex-start; padding:185px 56px 0; }
      .card .kicker { font-size:28px; font-weight:700; letter-spacing:5px; }
      .card .kicker.boxed { background:rgba(0,0,0,.55); padding:10px 24px;
        border-radius:8px; margin-bottom:26px; }
      .card .big { font-size:290px; font-weight:700; line-height:1; color:#fff;
        margin-top:14px; text-shadow:0 8px 40px rgba(0,0,0,.8); }
      .card .label { font-size:40px; font-weight:700; letter-spacing:2px; color:#fff;
        background:rgba(0,0,0,.55); padding:10px 24px; border-radius:8px; }
      .card .rule { width:0; height:10px; border-radius:5px; margin-top:24px; }
      .card .panel { background:rgba(10,10,14,.78); border-left:12px solid #fff;
        border-radius:14px; padding:32px 38px; max-width:920px;
        box-shadow:0 14px 50px rgba(0,0,0,.5); }
      .card .panel .title { font-size:96px; font-weight:700; line-height:1.04;
        color:#fff; margin-top:8px; }
      .card .panel .detail { font-size:38px; color:#e6e6e6; margin-top:12px; line-height:1.3; }
      .card .chips { display:flex; flex-wrap:wrap; gap:16px; justify-content:center; max-width:920px; }
      .card .chip { font-size:36px; font-weight:700; color:#0c130d; border-radius:999px;
        padding:14px 32px; box-shadow:0 8px 28px rgba(0,0,0,.45); }
      .card .ktitle { font-size:118px; font-weight:700; letter-spacing:3px; color:#fff;
        text-shadow:0 8px 40px rgba(0,0,0,.85); text-align:center; padding:0 30px; }
      .card .sub { font-size:40px; color:#fff; background:rgba(0,0,0,.55);
        padding:10px 26px; border-radius:10px; margin-top:20px; }
      .card .ctitle { font-size:92px; font-weight:700; color:#fff; text-align:center;
        line-height:1.06; max-width:940px; text-shadow:0 8px 40px rgba(0,0,0,.85); }
      .card .pillbox { font-size:38px; font-weight:700; color:#0a1418;
        border-radius:999px; padding:18px 40px; margin-top:30px;
        box-shadow:0 10px 36px rgba(0,0,0,.5); }
"""


def build_composition(cards: list, duration: float, workdir: Path,
                      fps: int = 30) -> Path:
    """Escreve public/index.html com os cards e a timeline GSAP."""
    public = Path(workdir) / "public"
    hosts = "\n      ".join(_card_html(c) for c in cards)
    gsap  = "\n\n          ".join(_gsap_block(c, fps) for c in cards)

    html = f"""<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="utf-8" />
    <style>{_CSS}</style>
  </head>
  <body>
    <div id="stage" data-composition-id="motion-design" data-start="0"
         data-duration="{duration}" data-fps="{fps}" data-width="1080" data-height="1920">
      <div class="video-wrapper" id="video-wrap">
        <video id="bg-video" src="input-video.mp4" muted playsinline
               data-start="0" data-duration="{duration}" data-track-index="1"></video>
      </div>
      {hosts}
      <script src="vendor/gsap.min.js"></script>
      <script>
        (function () {{
          const tl = window.gsap.timeline({{ paused: true }});
          {gsap}
          window.__timelines = window.__timelines || {{}};
          window.__timelines["motion-design"] = tl;
        }})();
      </script>
    </div>
  </body>
</html>
"""
    (public / "index.html").write_text(html, encoding="utf-8")
    return public / "index.html"


# ─── 3/4. Render + mux ─────────────────────────────────────────────────────────

def apply_motion_design(video_path: str, narration: dict, boundaries: list,
                        output_dir, ffmpeg: str = "ffmpeg",
                        fps: int = 30) -> str | None:
    """
    Aplica a camada de motion design ao vídeo. Retorna o path do vídeo final
    (final_video.mp4, com o original preservado em final_video_plain.mp4)
    ou None em falha — sem nunca destruir o vídeo original.
    """
    video_path = Path(video_path)
    output_dir = Path(output_dir)
    if not video_path.exists():
        return None

    workdir = output_dir / "motion_design"
    public  = workdir / "public"
    for sub in ("fonts", "vendor"):
        (public / sub).mkdir(parents=True, exist_ok=True)

    try:
        # assets da skill (fontes + gsap, tudo local)
        for f in (_SKILL_ASSETS / "fonts").glob("*"):
            shutil.copy2(f, public / "fonts" / f.name)
        shutil.copy2(_SKILL_ASSETS / "vendor" / "gsap.min.js", public / "vendor")

        # duração real + vídeo re-encodado com keyframes densos (seek por frame)
        probe = subprocess.run(
            [ffmpeg.replace("ffmpeg", "ffprobe"), "-v", "error", "-show_entries",
             "format=duration", "-of", "csv=p=0", str(video_path)],
            capture_output=True, text=True, timeout=30)
        duration = round(float(probe.stdout.strip()), 3)

        subprocess.run(
            [ffmpeg, "-y", "-i", str(video_path), "-c:v", "libx264", "-crf", "18",
             "-g", str(fps), "-keyint_min", str(fps), "-pix_fmt", "yuv420p",
             "-movflags", "+faststart", "-an", str(public / "input-video.mp4")],
            capture_output=True, timeout=600, check=True)

        # 1. design + 2. composição
        cards = design_cards(narration, boundaries, duration)
        print(f"  Cards de motion design: {len(cards)} "
              f"({', '.join(c['type'] for c in cards)})")
        build_composition(cards, duration, workdir, fps)
        (workdir / "cards.json").write_text(
            json.dumps(cards, ensure_ascii=False, indent=2), encoding="utf-8")

        # 3. render (Chrome headless local)
        r = subprocess.run(
            [_npx(), "hyperframes", "render", "public", "-o", "overlay.mp4",
             "--fps", str(fps)],
            cwd=str(workdir), capture_output=True, text=True, timeout=1800)
        overlay = workdir / "overlay.mp4"
        if not overlay.exists():
            print(f"  [motion] render falhou: {(r.stderr or r.stdout)[-300:]}")
            return None

        # 4. muxa o áudio original de volta e promove o resultado.
        # O áudio vem do BACKUP (plain) — video_path pode SER final_video.mp4,
        # e o ffmpeg não pode ler e escrever o mesmo arquivo.
        plain = output_dir / "final_video_plain.mp4"
        final = output_dir / "final_video.mp4"
        if video_path.resolve() != plain.resolve():
            shutil.copy2(video_path, plain)
        subprocess.run(
            [ffmpeg, "-y", "-i", str(overlay), "-i", str(plain),
             "-map", "0:v", "-map", "1:a", "-c:v", "copy",
             "-c:a", "aac", "-b:a", "192k", "-shortest", str(final)],
            capture_output=True, timeout=300, check=True)
        return str(final)

    except Exception as e:
        print(f"  [motion] erro: {e} — mantendo vídeo sem overlays")
        return None
