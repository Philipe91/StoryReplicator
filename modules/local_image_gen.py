"""
v6.4 — Geração de imagem LOCAL na GPU (SDXL-Lightning).

Escolhido para a RTX 3060 12GB sem forçá-la: SDXL-Lightning 4-step
(ByteDance, licença aberta) — ~7GB de VRAM em fp16, 2-4s por imagem.

DETECÇÃO EM RUNTIME: o mesmo repositório roda no PC do trabalho (sem GPU);
available() decide. Sem CUDA, a cadeia de geração pula direto para as
opções de API (Pollinations FLUX → Stable Horde).

Cadeia completa de imagem gerada (media_scout):
  mídia REAL (sempre 1º) → Pollinations FLUX (API grátis)
  → SDXL-Lightning local (GPU) → Stable Horde (fila grátis)
"""

from pathlib import Path

_CKPT_REPO = "ByteDance/SDXL-Lightning"
_CKPT_FILE = "sdxl_lightning_4step.safetensors"

_pipeline = None


def available() -> bool:
    try:
        import torch
        if not torch.cuda.is_available():
            return False
        import diffusers  # noqa: F401
        return True
    except ImportError:
        return False


def _get_pipeline():
    """Carrega o pipeline 1x por processo (download ~7GB na primeira vez)."""
    global _pipeline
    if _pipeline is not None:
        return _pipeline

    import torch
    from diffusers import StableDiffusionXLPipeline, EulerDiscreteScheduler
    from huggingface_hub import hf_hub_download

    ckpt = hf_hub_download(_CKPT_REPO, _CKPT_FILE)
    pipe = StableDiffusionXLPipeline.from_single_file(
        ckpt, torch_dtype=torch.float16, variant="fp16")
    # Receita oficial do Lightning: trailing timesteps + guidance 0
    pipe.scheduler = EulerDiscreteScheduler.from_config(
        pipe.scheduler.config, timestep_spacing="trailing")
    pipe.to("cuda")
    pipe.enable_vae_slicing()
    _pipeline = pipe
    return pipe


def generate(prompt: str, out_path, width: int = 1080, height: int = 1920,
             negative: str = "text, watermark, low quality, deformed") -> bool:
    """
    Gera uma imagem e salva em out_path (JPEG). Retorna True em sucesso.
    SDXL nasce em ~1024px; gera em 768x1344 (9:16 nativo) e amplia para o
    tamanho final com Pillow (mais rápido e estável que gerar 1080x1920).
    """
    if not available():
        return False
    try:
        import torch
        pipe = _get_pipeline()
        gw, gh = (768, 1344) if height > width else (1344, 768)
        with torch.inference_mode():
            img = pipe(prompt[:300], negative_prompt=negative,
                       num_inference_steps=4, guidance_scale=0,
                       width=gw, height=gh).images[0]
        if (gw, gh) != (width, height):
            img = img.resize((width, height))
        img.convert("RGB").save(str(out_path), "JPEG", quality=92)
        return Path(out_path).exists()
    except Exception as e:
        print(f"  [sdxl-local] erro: {e}")
        return False
