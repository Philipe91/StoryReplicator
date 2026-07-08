"""
Studio — camada de TTS com múltiplos motores gratuitos e BENCHMARK automático.

Motores (todos grátis):
  edge     → edge-tts (Azure Neural pt-BR-AntonioNeural). Melhor naturalidade
             PT-BR gratuita + word boundaries reais + prosódia por segmento.
  kokoro   → kokoro-onnx local (vozes pt: pf_dora/pm_alex). Rápido em CPU,
             prosódia PT inferior. Fallback offline.
  piper    → piper-tts local (pt_BR-faber). Muito rápido, timbre datado.
             Fallback de emergência.

O benchmark roda cada motor disponível numa frase de teste PT-BR e mede
RTF (tempo de síntese / duração do áudio). A escolha pondera:
naturalidade PT-BR (prior de qualidade) > velocidade > latência.
Resultado fica em cache (tts_benchmark.json) e o sistema passa a usar o
vencedor — se ele quebrar em produção, a cadeia cai para o próximo.
"""

import json
import time
import wave
from pathlib import Path

# Prior de naturalidade PT-BR (0-10) — pesquisa jul/2026:
# Qwen3-TTS (local, Apache 2.0, emoção por instrução — ESCOLHA DO USUÁRIO
# como principal) > Google Chirp 3 HD (API grátis) > edge/Azure Neural >
# Chatterbox pt-BR (local MIT) >> Kokoro pt > Piper pt
_QUALITY_PRIOR = {"qwen3": 10.0, "google": 9.5, "edge": 9.0,
                  "chatterbox": 8.5, "kokoro": 5.5, "piper": 4.5}

_TEST_SENTENCE = ("Em mil novecentos e sessenta e nove, o mundo parou "
                  "para assistir um homem pisar na lua.")


# ─── Disponibilidade ───────────────────────────────────────────────────────────

def edge_available() -> bool:
    try:
        import edge_tts  # noqa: F401
        return True
    except ImportError:
        return False


def kokoro_available() -> bool:
    try:
        from kokoro_onnx import Kokoro  # noqa: F401
        return (Path("kokoro-v1.0.onnx").exists() and Path("voices-v1.0.bin").exists())
    except ImportError:
        return False


def piper_available() -> bool:
    try:
        from piper import PiperVoice  # noqa: F401
        return True
    except ImportError:
        import shutil
        return bool(shutil.which("piper"))


def qwen3_available() -> bool:
    """Qwen3-TTS local (Apache 2.0, PT entre 10 idiomas, emoção por instrução)."""
    try:
        from qwen_tts import Qwen3TTSModel  # noqa: F401
        return True
    except ImportError:
        return False


def google_available() -> bool:
    """Google Cloud TTS Chirp 3 HD — 1M chars/mês grátis (exige credencial)."""
    import os
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        return False
    try:
        from google.cloud import texttospeech  # noqa: F401
        return True
    except ImportError:
        return False


def chatterbox_available() -> bool:
    """Chatterbox Multilingual pt-BR — local, MIT, lento em CPU (lote)."""
    try:
        from chatterbox.tts import ChatterboxMultilingualTTS  # noqa: F401
        return True
    except ImportError:
        return False


AVAILABILITY = {"qwen3": qwen3_available, "google": google_available,
                "edge": edge_available, "chatterbox": chatterbox_available,
                "kokoro": kokoro_available, "piper": piper_available}


# ─── Síntese por motor (frase única, para benchmark) ──────────────────────────

def _synth_edge(text: str, out_wav: Path, ffmpeg: str = "ffmpeg") -> None:
    import asyncio
    from modules.subtitle_engine import _stream_tts, _mp3_to_wav
    mp3 = out_wav.with_suffix(".mp3")
    asyncio.run(_stream_tts(text, "pt-BR-AntonioNeural", str(mp3), "-8Hz", "-5%"))
    _mp3_to_wav(str(mp3), str(out_wav), ffmpeg)
    mp3.unlink(missing_ok=True)


def _synth_kokoro(text: str, out_wav: Path, ffmpeg: str = "ffmpeg") -> None:
    import soundfile as sf
    from kokoro_onnx import Kokoro
    k = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")
    samples, sr = k.create(text, voice="pm_alex", speed=1.0, lang="pt-br")
    sf.write(str(out_wav), samples, sr)


def _synth_piper(text: str, out_wav: Path, ffmpeg: str = "ffmpeg") -> None:
    from piper import PiperVoice
    voice = PiperVoice.load("pt_BR-faber-medium.onnx")
    with wave.open(str(out_wav), "wb") as wf:
        voice.synthesize(text, wf)


_qwen3_model = None    # cache: carregar o modelo 1x por processo


def _synth_qwen3(text: str, out_wav: Path, ffmpeg: str = "ffmpeg") -> None:
    global _qwen3_model
    import torch
    import soundfile as sf
    from qwen_tts import Qwen3TTSModel
    if _qwen3_model is None:
        _qwen3_model = Qwen3TTSModel.from_pretrained(
            "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
            device_map="cpu", dtype=torch.float32)
    wavs, sr = _qwen3_model.generate_custom_voice(
        text=text,
        language="Portuguese",
        speaker=__import__("os").getenv("QWEN3_TTS_SPEAKER", "Ryan"),
        instruct="Narre como um documentário brasileiro: tom grave, "
                 "pausado e envolvente.",
    )
    sf.write(str(out_wav), wavs[0], sr)


def _synth_google(text: str, out_wav: Path, ffmpeg: str = "ffmpeg") -> None:
    from google.cloud import texttospeech
    client = texttospeech.TextToSpeechClient()
    resp = client.synthesize_speech(
        input=texttospeech.SynthesisInput(text=text),
        voice=texttospeech.VoiceSelectionParams(
            language_code="pt-BR", name="pt-BR-Chirp3-HD-Charon"),
        audio_config=texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16,
            sample_rate_hertz=24000),
    )
    out_wav.write_bytes(resp.audio_content)


def _synth_chatterbox(text: str, out_wav: Path, ffmpeg: str = "ffmpeg") -> None:
    import torchaudio
    from chatterbox.tts import ChatterboxMultilingualTTS
    model = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
    wav = model.generate(text, language_id="pt", exaggeration=0.55)
    torchaudio.save(str(out_wav), wav, model.sr)


_SYNTH = {"qwen3": _synth_qwen3, "google": _synth_google,
          "edge": _synth_edge, "chatterbox": _synth_chatterbox,
          "kokoro": _synth_kokoro, "piper": _synth_piper}


# ─── Benchmark automático ──────────────────────────────────────────────────────

def benchmark(workdir: Path, ffmpeg: str = "ffmpeg",
              force: bool = False) -> dict:
    """
    Compara os motores disponíveis e escolhe o melhor.
    Cache em <workdir>/tts_benchmark.json (revalida a cada 7 dias).
    """
    cache = Path(workdir) / "tts_benchmark.json"
    if cache.exists() and not force:
        age = time.time() - cache.stat().st_mtime
        if age < 7 * 24 * 3600:
            data = json.loads(cache.read_text(encoding="utf-8"))
            if AVAILABILITY.get(data.get("winner"), lambda: False)():
                return data

    results = {}
    tmp = Path(workdir) / "_tts_bench"
    tmp.mkdir(parents=True, exist_ok=True)

    for engine, avail in AVAILABILITY.items():
        if not avail():
            results[engine] = {"available": False}
            continue
        out = tmp / f"bench_{engine}.wav"
        t0 = time.time()
        try:
            _SYNTH[engine](_TEST_SENTENCE, out, ffmpeg)
            synth_time = time.time() - t0
            with wave.open(str(out), "rb") as wf:
                audio_dur = wf.getnframes() / float(wf.getframerate())
            rtf = synth_time / max(audio_dur, 0.1)
            results[engine] = {
                "available":  True,
                "synth_time": round(synth_time, 2),
                "audio_dur":  round(audio_dur, 2),
                "rtf":        round(rtf, 3),
                "quality_prior": _QUALITY_PRIOR[engine],
                # naturalidade pesa 10x mais que velocidade
                "score": round(_QUALITY_PRIOR[engine] * 10 - min(rtf, 5) * 2, 1),
            }
        except Exception as e:
            results[engine] = {"available": False, "error": str(e)[:120]}

    ranked = sorted((e for e, r in results.items() if r.get("available")),
                    key=lambda e: results[e]["score"], reverse=True)
    data = {
        "test_sentence": _TEST_SENTENCE,
        "results":       results,
        "ranking":       ranked,
        "winner":        ranked[0] if ranked else None,
        "criteria":      "naturalidade PT-BR (peso 10) > velocidade RTF (peso 2)",
    }
    cache.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


# ─── Síntese de narração completa (com fallback em cadeia) ─────────────────────

def synthesize(narration: dict, output_dir: Path, engine_order: list,
               ffmpeg: str = "ffmpeg") -> tuple:
    """
    Sintetiza a narração completa com o 1º motor da ordem que funcionar.
    edge → prosódia por segmento + word boundaries reais.
    kokoro/piper → síntese direta + boundaries estimados por peso.
    Retorna (wav, srt, ass, boundaries, engine_usado).
    """
    from modules.subtitle_engine import (
        synthesize_narration_directed, _estimate_boundaries,
        _group_into_blocks, _build_srt, _build_ass, _get_audio_duration)

    last_err = None
    for engine in engine_order:
        if not AVAILABILITY.get(engine, lambda: False)():
            continue
        try:
            if engine == "edge":
                wav, srt, ass, bounds = synthesize_narration_directed(
                    narration, output_dir, ffmpeg_exe=ffmpeg)
                return wav, srt, ass, bounds, "edge"

            # Motores locais: síntese POR SEGMENTO + concatenação com pausa.
            # Boundaries estimados por segmento (muito mais precisos que
            # estimar o texto inteiro de uma vez).
            out  = Path(output_dir)
            segs = [s for s in narration.get("segments", [])
                    if s.get("text", "").strip()] \
                or [{"id": "full", "text": narration.get("narration_full", "")}]

            seg_dir = out / "tts_segments"
            seg_dir.mkdir(parents=True, exist_ok=True)
            gap = 0.35
            all_frames, bounds = [], []
            offset = 0.0
            sr = sw = ch = None
            for i, seg in enumerate(segs):
                wav_seg = seg_dir / f"seg_{i:02d}.wav"
                _SYNTH[engine](seg["text"], wav_seg, ffmpeg)
                with wave.open(str(wav_seg), "rb") as wf:
                    sr, sw, ch = (wf.getframerate(), wf.getsampwidth(),
                                  wf.getnchannels())
                    frames  = wf.readframes(wf.getnframes())
                    seg_dur = wf.getnframes() / float(sr)
                for b in _estimate_boundaries(seg["text"], seg_dur):
                    bounds.append({**b, "start": round(b["start"] + offset, 3),
                                   "end": round(b["end"] + offset, 3),
                                   "segment": seg.get("id", "")})
                all_frames.append(frames)
                offset += seg_dur
                if i < len(segs) - 1:
                    all_frames.append(b"\x00" * int(sr * gap) * sw * ch)
                    offset += gap

            wav = out / "audio.wav"
            with wave.open(str(wav), "wb") as wf:
                wf.setnchannels(ch)
                wf.setsampwidth(sw)
                wf.setframerate(sr)
                wf.writeframes(b"".join(all_frames))

            blocks = _group_into_blocks(bounds)
            srt = out / "subtitles.srt"
            ass = out / "subtitles.ass"
            srt.write_text(_build_srt(blocks), encoding="utf-8")
            ass.write_text(_build_ass(blocks), encoding="utf-8")
            return wav, srt, ass, bounds, engine
        except Exception as e:
            last_err = e
            print(f"  [{engine}] falhou: {e} — tentando próximo motor")

    raise RuntimeError(f"Todos os motores de TTS falharam. Último erro: {last_err}")
