"""ETAPA 9a — Síntese de voz com Kokoro TTS."""

import os
import struct
import wave
from pathlib import Path
from config import KOKORO_VOICE, KOKORO_SPEED, KOKORO_LANG


def synthesize(text: str, output_path: str) -> bool:
    """
    Sintetiza texto em áudio WAV usando Kokoro TTS.
    Tenta múltiplos backends em ordem de preferência.
    """
    output_path = str(output_path)

    if _try_kokoro_onnx(text, output_path):
        return True

    if _try_kokoro_package(text, output_path):
        return True

    if _try_edge_tts(text, output_path):
        return True

    print("[tts] AVISO: Todos os backends TTS falharam. Gerando áudio de placeholder.")
    _generate_silence(output_path, duration=120)
    return False


def _try_kokoro_onnx(text: str, output_path: str) -> bool:
    """Backend: kokoro-onnx (mais leve, recomendado)."""
    try:
        from kokoro_onnx import Kokoro
        kokoro = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")
        samples, sample_rate = kokoro.create(
            text,
            voice=KOKORO_VOICE,
            speed=KOKORO_SPEED,
            lang=KOKORO_LANG,
        )
        _save_wav(samples, sample_rate, output_path)
        print(f"[tts] kokoro-onnx: {output_path}")
        return True
    except ImportError:
        return False
    except Exception as e:
        print(f"[tts] kokoro-onnx error: {e}")
        return False


def _try_kokoro_package(text: str, output_path: str) -> bool:
    """Backend: kokoro package (PyPI)."""
    try:
        from kokoro import KPipeline
        pipeline = KPipeline(lang_code=KOKORO_LANG)
        generator = pipeline(text, voice=KOKORO_VOICE, speed=KOKORO_SPEED)

        all_audio = []
        for _, _, audio in generator:
            all_audio.extend(audio.tolist())

        if all_audio:
            _save_wav(all_audio, 24000, output_path)
            print(f"[tts] kokoro package: {output_path}")
            return True
    except ImportError:
        return False
    except Exception as e:
        print(f"[tts] kokoro package error: {e}")
    return False


def _try_edge_tts(text: str, output_path: str) -> bool:
    """Fallback: edge-tts (Microsoft TTS via edge)."""
    try:
        import asyncio
        import edge_tts

        async def _run():
            communicate = edge_tts.Communicate(text, voice="pt-BR-FranciscaNeural")
            tmp = output_path.replace(".wav", "_tmp.mp3")
            await communicate.save(tmp)
            return tmp

        tmp_mp3 = asyncio.run(_run())
        _mp3_to_wav(tmp_mp3, output_path)
        print(f"[tts] edge-tts: {output_path}")
        return True
    except ImportError:
        return False
    except Exception as e:
        print(f"[tts] edge-tts error: {e}")
    return False


def _save_wav(samples, sample_rate: int, output_path: str) -> None:
    import array
    data = array.array("h", [int(max(-32768, min(32767, s * 32767))) for s in samples])
    with wave.open(output_path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(data.tobytes())


def _mp3_to_wav(mp3_path: str, wav_path: str) -> None:
    import subprocess
    subprocess.run(
        ["ffmpeg", "-y", "-i", mp3_path, wav_path],
        capture_output=True
    )
    try:
        os.remove(mp3_path)
    except Exception:
        pass


def _generate_silence(output_path: str, duration: int = 120, sample_rate: int = 24000) -> None:
    """Gera arquivo WAV de silêncio como placeholder."""
    num_frames = sample_rate * duration
    with wave.open(output_path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * num_frames)
