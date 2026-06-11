"""
StoryReplicator v4.0 — Asset Acquisition Manager

Resolve o gargalo nº 1 da validação: rate-limit em lote. Em rajada de muitas
buscas, o Wikimedia/Archive limitam e retornam vazio, derrubando a cobertura.

Fornece uma ThrottledSession (drop-in para requests.Session) com:
  - throttling global por domínio (intervalo mínimo entre requests)
  - retry automático com exponential backoff
  - cooldown de domínio ao receber 429/503 (provider rotation natural)
  - tratamento de timeout como falha retentável

Os providers usam apenas session.get(...), então ganham tudo isso de graça —
basta o engine criar uma ThrottledSession em vez de requests.Session.
"""

import random
import threading
import time
from urllib.parse import urlparse

import requests


# Intervalo mínimo entre requests ao MESMO domínio (segundos)
_DOMAIN_MIN_INTERVAL = {
    "commons.wikimedia.org": 1.1,
    "www.loc.gov":           1.5,
    "archive.org":           0.8,
    "api.pexels.com":        0.4,
    "pixabay.com":           0.4,
    "_default":              0.6,
}

# Backoff
_MAX_RETRIES   = 4
_BASE_BACKOFF  = 1.5     # segundos (cresce exponencialmente)
_COOLDOWN_429  = 30.0    # domínio em cooldown após 429/503


class _GlobalThrottle:
    """Throttle por domínio, compartilhado entre todas as sessions (thread-safe)."""
    def __init__(self):
        self._last = {}        # domínio → timestamp do último request
        self._cooldown = {}    # domínio → timestamp até quando está em cooldown
        self._lock = threading.Lock()

    def wait(self, domain: str) -> None:
        interval = _DOMAIN_MIN_INTERVAL.get(domain, _DOMAIN_MIN_INTERVAL["_default"])
        with self._lock:
            now = time.monotonic()
            # Respeita cooldown (após 429)
            cd_until = self._cooldown.get(domain, 0)
            if now < cd_until:
                sleep_for = cd_until - now
            else:
                last = self._last.get(domain, 0)
                sleep_for = max(0, interval - (now - last))
            target = now + sleep_for
            self._last[domain] = target
        if sleep_for > 0:
            time.sleep(sleep_for)

    def cooldown(self, domain: str, seconds: float = _COOLDOWN_429) -> None:
        with self._lock:
            self._cooldown[domain] = time.monotonic() + seconds

    def in_cooldown(self, domain: str) -> bool:
        with self._lock:
            return time.monotonic() < self._cooldown.get(domain, 0)


_THROTTLE = _GlobalThrottle()   # instância global única


class ThrottledSession(requests.Session):
    """requests.Session com throttle + retry + backoff transparentes."""

    def __init__(self, user_agent: str = "StoryReplicator/4.0 (educational)"):
        super().__init__()
        self.headers["User-Agent"] = user_agent

    def get(self, url, **kwargs):    # type: ignore[override]
        domain = urlparse(url).netloc
        kwargs.setdefault("timeout", 15)
        last_exc = None

        for attempt in range(_MAX_RETRIES):
            _THROTTLE.wait(domain)
            try:
                resp = super().get(url, **kwargs)
                # Rate-limit / indisponível → cooldown + retry
                if resp.status_code in (429, 503):
                    _THROTTLE.cooldown(domain)
                    self._backoff(attempt)
                    last_exc = f"HTTP {resp.status_code}"
                    continue
                return resp
            except (requests.Timeout, requests.ConnectionError) as e:
                last_exc = e
                self._backoff(attempt)
                continue
            except Exception as e:
                last_exc = e
                break

        # Esgotou tentativas: devolve um Response sintético com erro (não quebra)
        fake = requests.Response()
        fake.status_code = 599
        fake._content = b""
        fake.url = url
        fake.reason = f"throttled-fail: {last_exc}"
        return fake

    @staticmethod
    def _backoff(attempt: int) -> None:
        # Exponential backoff com jitter
        delay = _BASE_BACKOFF * (2 ** attempt) + random.uniform(0, 0.5)
        time.sleep(min(delay, 20))


def is_domain_limited(url: str) -> bool:
    """Permite ao engine pular um provider em cooldown (provider rotation)."""
    return _THROTTLE.in_cooldown(urlparse(url).netloc)
