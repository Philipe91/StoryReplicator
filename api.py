"""
StoryReplicator v4.0 — Camada de API (pronta para interface)

Ponto de entrada ÚNICO e estável para qualquer cliente (CLI atual, futura UI
web, ou serviço SaaS). Encapsula toda a geração atrás de um objeto de
requisição e um objeto de resposta — separando backend (lógica) de interface.

Exemplo:
    from api import GenerationRequest, generate
    req = GenerationRequest(
        url="https://youtu.be/XXXX",
        format="micro_story",        # micro_story|short_documentary|documentary|long_documentary|custom
        language="pt",               # pt|en|es|fr
        renderer="remotion",         # remotion|ffmpeg
        target_duration=45,          # opcional (sobrepõe o default do formato)
        langs=["pt","en"],           # versões multi-idioma
    )
    result = generate(req)
    print(result.status, result.video_path, result.quality_report)
"""

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


# ─── Objeto de requisição (o "contrato" da interface) ─────────────────────────

@dataclass
class GenerationRequest:
    url:             str
    format:          str = "micro_story"
    language:        str = "pt"
    renderer:        str = "remotion"
    target_duration: Optional[int] = None      # None → usa default do formato
    langs:           list = field(default_factory=lambda: ["pt"])
    skip_video:      bool = False
    skip_images:     bool = False
    skip_video_search: bool = False
    output_dir:      Optional[str] = None

    @staticmethod
    def from_dict(d: dict) -> "GenerationRequest":
        """Cria a requisição a partir de um JSON/dict (o que a UI enviará)."""
        return GenerationRequest(
            url=d["url"],
            format=d.get("format", "micro_story"),
            language=d.get("language", "pt"),
            renderer=d.get("renderer", "remotion"),
            target_duration=d.get("target_duration"),
            langs=d.get("langs") or [d.get("language", "pt")],
            skip_video=d.get("skip_video", False),
            skip_images=d.get("skip_images", False),
            skip_video_search=d.get("skip_video_search", False),
            output_dir=d.get("output_dir"),
        )


@dataclass
class GenerationResult:
    status:         str                      # "done" | "error"
    output_dir:     str = ""
    video_path:     str = ""
    quality_report: dict = field(default_factory=dict)
    languages:      list = field(default_factory=list)   # versões geradas
    error:          str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ─── Entrada única de geração ─────────────────────────────────────────────────

def generate(request: GenerationRequest) -> GenerationResult:
    """
    Executa o pipeline completo a partir do objeto de requisição.
    Esta é a fronteira backend↔interface: a UI só monta o GenerationRequest
    e lê o GenerationResult, sem conhecer detalhes internos.
    """
    from config import resolve_format
    import main as pipeline

    try:
        mode = resolve_format(request.format, request.target_duration)
        out = pipeline.run(
            url=request.url,
            mode_name=None,                  # usa mode explícito abaixo
            renderer=request.renderer,
            skip_video=request.skip_video,
            skip_images=request.skip_images,
            skip_video_search=request.skip_video_search,
            output_dir=Path(request.output_dir) if request.output_dir else None,
            langs=request.langs,
            mode_override=mode,              # Format Manager resolvido
        )
        out = Path(out)
        # Carrega o quality report gerado
        qr_path = out / "quality_report.json"
        qr = {}
        if qr_path.exists():
            import json
            qr = json.loads(qr_path.read_text(encoding="utf-8"))

        return GenerationResult(
            status="done",
            output_dir=str(out),
            video_path=str(out / "final_video.mp4"),
            quality_report=qr,
            languages=request.langs,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return GenerationResult(status="error", error=str(e))


def generate_from_dict(payload: dict) -> dict:
    """Atalho JSON→JSON para a futura API web."""
    return generate(GenerationRequest.from_dict(payload)).to_dict()
