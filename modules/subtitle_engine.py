"""
PRIORIDADE 5 — Sistema de legendas profissionais (.srt + .ass).

Usa edge-tts WordBoundary events para sincronização precisa palavra a palavra.
Gera .ass com estilo profissional para YouTube Shorts / TikTok / Instagram Reels.
"""

import asyncio
import re
from pathlib import Path
from config import EDGE_TTS_VOICE, SUBTITLE_FONT_SIZE, SUBTITLE_MARGIN_V, SUBTITLE_MAX_CHARS, SUBTITLE_MAX_WORDS

# ─── ASS template profissional para 1080×1920 ─────────────────────────────────
_ASS_HEADER = """\
[Script Info]
Title: StoryReplicator Professional Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: 1080
PlayResY: 1920
YCbCr Matrix: None

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0.5,0,1,4,1,2,40,40,{margin_v},1
Style: Highlight,Arial,{font_size},&H0000FFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0.5,0,1,4,1,2,40,40,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

# Palavras que devem ser destacadas (números em PT-BR, termos de alto impacto)
_HIGHLIGHT_PATTERNS = [
    r'\b\d+\b',                           # números arábicos
    r'\b(mil|bilhão|bilhões|milhão|milhões|cem|duzentos|trezentos)\b',
    r'\b(nunca|jamais|sempre|impossível|incrível|absurdo|genial)\b',
]


# ─── TTS com word boundaries ───────────────────────────────────────────────────

async def _stream_tts(text: str, voice: str, mp3_path: str,
                      pitch: str = "+0Hz", rate: str = "+0%") -> list:
    """
    Gera áudio via edge-tts capturando eventos WordBoundary.
    pitch/rate ajustam tom e velocidade da voz.

    IMPORTANTE: desde o edge-tts 7.x o padrão é SentenceBoundary — sem
    boundary="WordBoundary" NENHUM timestamp por palavra é emitido (e as
    legendas viravam estimativa). Com o parâmetro, os timestamps reais
    chegam inclusive com pitch/rate customizados (verificado na prática).

    Retorna lista de {word, start, end} em segundos.
    """
    import edge_tts
    comm = edge_tts.Communicate(
        text, voice=voice,
        pitch=pitch or "+0Hz", rate=rate or "+0%",
        boundary="WordBoundary",
    )
    boundaries = []

    with open(mp3_path, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 10_000_000        # 100ns → s
                dur   = chunk["duration"] / 10_000_000
                boundaries.append({
                    "word":  chunk["text"],
                    "start": round(start, 3),
                    "end":   round(start + dur, 3),
                })
    return boundaries


def synthesize_with_subtitles(
    text: str,
    output_dir: Path,
    voice: str = None,
    ffmpeg_exe: str = "ffmpeg",
    pitch: str = None,
    rate: str = None,
) -> tuple:
    """
    Gera áudio + legendas (.srt e .ass) com sincronização precisa.
    voice/pitch/rate permitem voz nativa por idioma (multi-idioma v3.8).

    Retorna: (audio_wav_path, srt_path, ass_path, word_boundaries)
    """
    from config import EDGE_TTS_PITCH, EDGE_TTS_RATE
    voice     = voice or EDGE_TTS_VOICE
    pitch     = pitch if pitch is not None else EDGE_TTS_PITCH
    rate      = rate  if rate  is not None else EDGE_TTS_RATE
    output_dir = Path(output_dir)
    mp3_path  = output_dir / "audio_tmp.mp3"
    wav_path  = output_dir / "audio.wav"
    srt_path  = output_dir / "subtitles.srt"
    ass_path  = output_dir / "subtitles.ass"

    # Gera áudio e captura word boundaries
    boundaries = asyncio.run(_stream_tts(text, voice, str(mp3_path), pitch, rate))

    # Converte MP3 → WAV
    _mp3_to_wav(str(mp3_path), str(wav_path), ffmpeg_exe)

    # Se não há word boundaries (fallback sem TTS), usa segmentação simples
    real_dur = _get_audio_duration(str(wav_path), ffmpeg_exe)
    if not boundaries:
        boundaries = _estimate_boundaries(text, real_dur)
    else:
        # CORREÇÃO DE SYNC: o edge-tts reporta tempos na escala SEM rate/pitch,
        # mas o áudio final reflete o rate (ex: rate=-5% → fala mais longa).
        # Escala linearmente os timings para casar com a duração real do áudio,
        # eliminando o "adiantamento" progressivo das legendas.
        boundaries = _rescale_boundaries(boundaries, real_dur)
        boundaries = _reattach_punctuation(boundaries, text)

    # Gera legendas
    blocks = _group_into_blocks(boundaries)
    srt_content = _build_srt(blocks)
    ass_content = _build_ass(blocks)

    srt_path.write_text(srt_content, encoding="utf-8")
    ass_path.write_text(ass_content, encoding="utf-8")

    return wav_path, srt_path, ass_path, boundaries


# ─── Reanexar pontuação ───────────────────────────────────────────────────────

def _strip_punct(w: str) -> str:
    return re.sub(r"[^\wÀ-ÿ]", "", w).lower()


def _reattach_punctuation(boundaries: list, text: str) -> list:
    """
    O edge-tts emite WordBoundary SEM a pontuação ("afundar" em vez de
    "afundar."). Realinha os boundaries com os tokens do texto original para
    restaurar pontuação — essencial para o agrupamento de blocos de legenda
    (quebra em fim de frase) e para as pausas dramáticas ("...").
    """
    tokens = text.split()
    out    = []
    ti     = 0
    for b in boundaries:
        word  = b["word"]
        clean = _strip_punct(word)
        replacement = word
        # procura o token correspondente numa janela pequena à frente
        for look in range(ti, min(ti + 3, len(tokens))):
            if _strip_punct(tokens[look]) == clean:
                replacement = tokens[look]
                ti = look + 1
                break
        out.append({**b, "word": replacement})
    return out


# ─── Síntese dirigida por segmento (prosódia aplicada) ────────────────────────

def synthesize_narration_directed(
    narration: dict,
    output_dir: Path,
    voice: str = None,
    ffmpeg_exe: str = "ffmpeg",
    gap_seconds: float = 0.35,
) -> tuple:
    """
    Sintetiza a narração SEGMENTO A SEGMENTO aplicando o prosody_plan do
    Narration Director (rate/pitch por emoção do segmento) — em vez de uma
    voz monótona global. Concatena os áudios com micro-pausa entre segmentos
    e desloca os word boundaries pelo offset real de cada segmento.

    Fallback: sem segments/prosody_plan, usa a síntese de texto corrido.

    Retorna: (audio_wav_path, srt_path, ass_path, word_boundaries)
    """
    from config import EDGE_TTS_PITCH, EDGE_TTS_RATE, EDGE_TTS_VOICE as _DEF_VOICE
    voice    = voice or _DEF_VOICE
    segments = [s for s in (narration.get("segments") or []) if s.get("text", "").strip()]
    prosody  = {p.get("id"): p for p in narration.get("prosody_plan", [])}

    if not segments:
        return synthesize_with_subtitles(
            narration.get("narration_full", ""), output_dir,
            voice=voice, ffmpeg_exe=ffmpeg_exe,
        )

    output_dir = Path(output_dir)
    seg_dir    = output_dir / "tts_segments"
    seg_dir.mkdir(parents=True, exist_ok=True)

    async def _synth_all():
        results = []
        for i, seg in enumerate(segments):
            plan  = prosody.get(seg.get("id"), {})
            pitch = plan.get("pitch", EDGE_TTS_PITCH)
            rate  = plan.get("rate",  EDGE_TTS_RATE)
            mp3   = seg_dir / f"seg_{i:02d}.mp3"
            b     = await _stream_tts(seg["text"], voice, str(mp3), pitch, rate)
            results.append((seg, mp3, b, pitch, rate))
        return results

    results = asyncio.run(_synth_all())

    # Converte cada segmento para WAV padronizado e concatena com pausa
    import wave
    all_frames  = []
    boundaries  = []
    offset      = 0.0
    sr, sw, ch  = 24000, 2, 1
    gap_frames  = b"\x00" * int(sr * gap_seconds) * sw

    for i, (seg, mp3, seg_bounds, pitch, rate) in enumerate(results):
        wav_seg = seg_dir / f"seg_{i:02d}.wav"
        _mp3_to_wav(str(mp3), str(wav_seg), ffmpeg_exe)
        if not wav_seg.exists():
            continue
        with wave.open(str(wav_seg), "rb") as wf:
            sr = wf.getframerate()
            sw = wf.getsampwidth()
            ch = wf.getnchannels()
            frames  = wf.readframes(wf.getnframes())
            seg_dur = wf.getnframes() / float(sr)
        gap_frames = b"\x00" * int(sr * gap_seconds) * sw * ch

        if not seg_bounds:
            seg_bounds = _estimate_boundaries(seg["text"], seg_dur)
        else:
            seg_bounds = _rescale_boundaries(seg_bounds, seg_dur)
            seg_bounds = _reattach_punctuation(seg_bounds, seg["text"])

        for b in seg_bounds:
            boundaries.append({
                "word":    b["word"],
                "start":   round(b["start"] + offset, 3),
                "end":     round(b["end"]   + offset, 3),
                "segment": seg.get("id", ""),
            })

        all_frames.append(frames)
        offset += seg_dur
        if i < len(results) - 1:
            all_frames.append(gap_frames)
            offset += gap_seconds

    if not all_frames:
        raise RuntimeError("Nenhum segmento de áudio foi sintetizado (edge-tts indisponível?)")

    wav_path = output_dir / "audio.wav"
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(ch)
        wf.setsampwidth(sw)
        wf.setframerate(sr)
        wf.writeframes(b"".join(all_frames))

    srt_path = output_dir / "subtitles.srt"
    ass_path = output_dir / "subtitles.ass"
    blocks   = _group_into_blocks(boundaries)
    srt_path.write_text(_build_srt(blocks), encoding="utf-8")
    ass_path.write_text(_build_ass(blocks), encoding="utf-8")

    return wav_path, srt_path, ass_path, boundaries


# ─── Agrupamento em blocos de legenda ─────────────────────────────────────────

def _group_into_blocks(boundaries: list, max_chars: int = None, max_words: int = None) -> list:
    """Agrupa word boundaries em blocos de 2 linhas, máx max_chars por linha."""
    max_chars = max_chars or SUBTITLE_MAX_CHARS
    max_words = max_words or SUBTITLE_MAX_WORDS
    blocks    = []
    current   = []
    line1_len = 0
    line2_len = 0
    on_line2  = False

    def _flush():
        nonlocal current, line1_len, line2_len, on_line2
        if current:
            blocks.append(list(current))
        current   = []
        line1_len = 0
        line2_len = 0
        on_line2  = False

    prev_segment = None
    for wb in boundaries:
        word     = wb["word"]
        wlen     = len(word) + 1   # +1 espaço

        # Nunca deixa um bloco de legenda atravessar segmentos narrativos
        seg = wb.get("segment")
        if seg is not None and prev_segment is not None and seg != prev_segment:
            _flush()
        prev_segment = seg

        if not on_line2:
            if line1_len + wlen > max_chars:
                on_line2  = True
                line2_len = 0

        if on_line2:
            if line2_len + wlen > max_chars:
                _flush()
                on_line2  = False
                line1_len = wlen
                current.append(wb)
                continue
            line2_len += wlen
        else:
            line1_len += wlen

        current.append(wb)

        # Quebra obrigatória em pontuação se bloco não está vazio
        if len(current) >= 3 and word.rstrip("…").endswith((".", "!", "?")):
            _flush()

    _flush()
    return blocks


# ─── Formatação do texto do bloco ─────────────────────────────────────────────

def _format_block_text_srt(words: list, max_chars: int = None) -> str:
    """Formata palavras em texto de 2 linhas para SRT (sem tags ASS)."""
    max_chars = max_chars or SUBTITLE_MAX_CHARS
    text = " ".join(w["word"] for w in words)

    if len(text) <= max_chars:
        return text

    # Divide em 2 linhas pela metade mais próxima de um espaço
    mid = len(text) // 2
    split = text.rfind(" ", 0, mid) or text.find(" ", mid)
    if split <= 0:
        return text
    return text[:split] + "\n" + text[split + 1:]


def _format_block_text_ass(words: list, max_chars: int = None) -> str:
    """Formata palavras com destaque para ASS."""
    max_chars = max_chars or SUBTITLE_MAX_CHARS
    raw_words = [w["word"] for w in words]
    text = " ".join(raw_words)

    # Aplica destaques
    highlighted = _highlight_words(text)

    # Quebra em 2 linhas se necessário
    clean = re.sub(r'\{[^}]+\}', '', highlighted)   # remove tags para medir
    if len(clean) <= max_chars:
        return highlighted

    mid   = len(clean) // 2
    split = clean.rfind(" ", 0, mid) or clean.find(" ", mid)
    if split <= 0:
        return highlighted

    # Rebuild with newline at split
    parts     = clean.split(" ")
    chars     = 0
    line_idx  = 0
    for i, p in enumerate(parts):
        chars += len(p) + 1
        if chars > max_chars:
            line_idx = i
            break
    if line_idx == 0:
        line_idx = len(parts) // 2

    line1 = _highlight_words(" ".join(parts[:line_idx]))
    line2 = _highlight_words(" ".join(parts[line_idx:]))
    return line1 + "\\N" + line2


def _highlight_words(text: str) -> str:
    """Envolve palavras-chave em tags de cor ASS."""
    result = text
    hl_open  = r'{\c&H0000FFFF&}'   # ciano/amarelo
    hl_close = r'{\c&HFFFFFF&}'     # volta ao branco

    for pattern in _HIGHLIGHT_PATTERNS:
        def replacer(m):
            return f"{hl_open}{m.group(0)}{hl_close}"
        result = re.sub(pattern, replacer, result, flags=re.IGNORECASE)
    return result


# ─── Geração SRT ──────────────────────────────────────────────────────────────

def _build_srt(blocks: list) -> str:
    lines = []
    for i, block in enumerate(blocks, 1):
        if not block:
            continue
        start = block[0]["start"]
        end   = block[-1]["end"]
        text  = _format_block_text_srt(block)
        lines += [str(i), f"{_tc(start)} --> {_tc(end)}", text, ""]
    return "\n".join(lines)


# ─── Geração ASS ──────────────────────────────────────────────────────────────

def _build_ass(blocks: list) -> str:
    header = _ASS_HEADER.format(
        font_size=SUBTITLE_FONT_SIZE,
        margin_v=SUBTITLE_MARGIN_V,
    )
    events = []
    for block in blocks:
        if not block:
            continue
        start = block[0]["start"]
        end   = block[-1]["end"]
        text  = _format_block_text_ass(block)
        events.append(
            f"Dialogue: 0,{_ass_tc(start)},{_ass_tc(end)},Default,,0,0,0,,{text}"
        )
    return header + "\n".join(events) + "\n"


# ─── Time code helpers ────────────────────────────────────────────────────────

def _tc(seconds: float) -> str:
    """SRT timecode: HH:MM:SS,mmm"""
    s  = int(seconds)
    ms = int((seconds - s) * 1000)
    return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d},{ms:03d}"


def _ass_tc(seconds: float) -> str:
    """ASS timecode: H:MM:SS.cc"""
    s  = int(seconds)
    cs = int((seconds - s) * 100)
    return f"{s//3600}:{(s%3600)//60:02d}:{s%60:02d}.{cs:02d}"


# ─── Correção de sincronização ─────────────────────────────────────────────────

def _rescale_boundaries(boundaries: list, real_duration: float) -> list:
    """
    Escala linearmente os timings das palavras para casar com a duração real
    do áudio. Corrige o adiantamento causado por rate/pitch no edge-tts.
    """
    if not boundaries or real_duration <= 0:
        return boundaries
    last_end = max(b["end"] for b in boundaries)
    if last_end <= 0:
        return boundaries
    # Fator: alinha a última palavra ao fim da fala (98% do áudio p/ margem)
    factor = (real_duration * 0.98) / last_end
    # Só corrige se o desvio é relevante (>2%)
    if abs(factor - 1.0) < 0.02:
        return boundaries
    return [
        {"word": b["word"],
         "start": round(b["start"] * factor, 3),
         "end":   round(b["end"]   * factor, 3)}
        for b in boundaries
    ]


# ─── Fallbacks ────────────────────────────────────────────────────────────────

def _estimate_boundaries(text: str, total_duration: float) -> list:
    """
    Estima timing das palavras DISTRIBUINDO proporcionalmente ao longo da
    duração REAL do áudio. Usado quando o edge-tts não emite WordBoundary
    (ex: ao usar pitch+rate). Cada palavra recebe um peso (tamanho + pausa
    de pontuação) e o total é escalado para casar exatamente com o áudio.
    """
    words = text.split()
    if not words or total_duration <= 0:
        return []

    # Peso de cada palavra: nº de caracteres + pausa extra após pontuação forte
    weights = []
    for w in words:
        weight = max(len(w), 2)              # base pelo tamanho
        if w.endswith((".", "!", "?")):
            weight += 6                      # pausa longa após frase
        elif w.endswith((",", ";", ":")):
            weight += 3                      # pausa média
        if w.endswith("...") or w == "...":
            weight += 8                      # pausa dramática (reticências)
        weights.append(weight)

    total_weight = sum(weights)
    # Reserva 2% no fim (a última palavra não termina no fim exato do arquivo)
    usable = total_duration * 0.98
    result = []
    current = 0.0
    for w, weight in zip(words, weights):
        dur = usable * (weight / total_weight)
        result.append({"word": w, "start": round(current, 3),
                       "end": round(current + dur, 3)})
        current += dur
    return result


def _get_audio_duration(wav_path: str, ffmpeg_exe: str = "ffmpeg") -> float:
    """Obtém duração do áudio via FFprobe."""
    import subprocess
    try:
        r = subprocess.run(
            [ffmpeg_exe, "-i", wav_path],
            capture_output=True, text=True
        )
        for line in r.stderr.split("\n"):
            if "Duration" in line:
                dur_str = line.split("Duration:")[1].split(",")[0].strip()
                h, m, s = dur_str.split(":")
                return int(h)*3600 + int(m)*60 + float(s)
    except Exception:
        pass
    return 60.0


def _mp3_to_wav(mp3_path: str, wav_path: str, ffmpeg_exe: str = "ffmpeg") -> None:
    import subprocess
    subprocess.run(
        [ffmpeg_exe, "-y", "-i", mp3_path, "-ar", "24000", "-ac", "1", wav_path],
        capture_output=True
    )


# ─── Remotion: subtitles.json com word-level timing ──────────────────────────

def build_subtitles_json(
    boundaries: list,
    subtitle_style: str = "MODERN_SHORTS",
    max_chars: int = None,
) -> dict:
    """
    Gera subtitles.json para o Remotion com word-level timing.

    Retorna dict com:
      entries[]: {start, end, text, style, word_timings[{word, start, end}]}
    """
    blocks  = _group_into_blocks(boundaries, max_chars=max_chars)
    entries = []

    for block in blocks:
        if not block:
            continue
        start = block[0]["start"]
        end   = block[-1]["end"]
        text  = " ".join(w["word"] for w in block)
        entries.append({
            "start":        round(start, 3),
            "end":          round(end, 3),
            "text":         text,
            "style":        subtitle_style,
            "word_timings": [
                {"word": w["word"], "start": round(w["start"], 3), "end": round(w["end"], 3)}
                for w in block
            ],
        })

    return {"version": "3.5", "entries": entries}


def save_subtitles_json(boundaries: list, output_dir, subtitle_style: str = "MODERN_SHORTS") -> str:
    """Salva subtitles.json na pasta de saída. Retorna path."""
    from pathlib import Path
    data = build_subtitles_json(boundaries, subtitle_style)
    path = Path(output_dir) / "subtitles.json"
    path.write_text(__import__("json").dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)
