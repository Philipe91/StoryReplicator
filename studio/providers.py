"""
Studio — ProviderChain: desacoplamento de APIs com fallback automático.

Cada capacidade (busca web, TTS, música, imagem) é uma cadeia de provedores
GRATUITOS em ordem de preferência. Se um falhar (erro, indisponível, sem
resultado), o próximo assume automaticamente. Trocar/adicionar um provedor
não toca no código dos agentes.
"""

from dataclasses import dataclass, field


class AllProvidersFailed(RuntimeError):
    pass


@dataclass
class Provider:
    name: str
    fn: callable                       # fn(*args, **kwargs) -> resultado ou None
    available: callable = None         # () -> bool; None = sempre disponível
    note: str = ""

    def is_available(self) -> bool:
        try:
            return self.available() if self.available else True
        except Exception:
            return False


@dataclass
class ProviderChain:
    kind: str
    providers: list = field(default_factory=list)

    def add(self, provider: Provider) -> "ProviderChain":
        self.providers.append(provider)
        return self

    def call(self, *args, required: bool = False, **kwargs):
        """
        Tenta cada provedor em ordem. Considera falha: exceção ou retorno
        None/vazio. Retorna o primeiro resultado válido.
        """
        errors = []
        for p in self.providers:
            if not p.is_available():
                errors.append(f"{p.name}: indisponível")
                continue
            try:
                result = p.fn(*args, **kwargs)
                if result:
                    return result, p.name
                errors.append(f"{p.name}: vazio")
            except Exception as e:
                errors.append(f"{p.name}: {type(e).__name__}: {e}")
        if required:
            raise AllProvidersFailed(f"[{self.kind}] todos falharam: {errors}")
        return None, None

    def call_all(self, *args, limit: int = None, **kwargs) -> list:
        """
        Chama TODOS os provedores disponíveis e agrega resultados (para
        varredura ampla de mídia — nunca depender de uma única fonte).
        """
        results = []
        for p in self.providers[: limit or len(self.providers)]:
            if not p.is_available():
                continue
            try:
                r = p.fn(*args, **kwargs)
                if r:
                    results.append((p.name, r))
            except Exception:
                continue
        return results
