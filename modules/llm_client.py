"""
v6.1 — Cliente LLM multi-provider com fallback automático (cérebro do sistema).

O sistema NÃO depende mais da API da Anthropic. Qualquer provider gratuito
serve; o primeiro disponível (com chave/servidor ativo) é usado e, se falhar,
o próximo assume:

  1. anthropic   → ANTHROPIC_API_KEY        (opcional, pago)
  2. groq        → GROQ_API_KEY             (GRÁTIS, sem cartão — console.groq.com)
  3. gemini      → GEMINI_API_KEY           (GRÁTIS, sem cartão — aistudio.google.com)
  4. openrouter  → OPENROUTER_API_KEY       (modelos :free — openrouter.ai)
  5. ollama      → servidor local :11434    (100% local, sem cadastro — ollama.com)

Modelos padrão (sobrescreva por env var):
  GROQ_MODEL       = llama-3.3-70b-versatile
  GEMINI_MODEL     = gemini-2.5-flash
  OPENROUTER_MODEL = meta-llama/llama-3.3-70b-instruct:free
  OLLAMA_MODEL     = qwen2.5:7b

Interface idêntica ao antigo claude_client: ask() / ask_json() / story_system().
Retry com backoff dentro de cada provider; troca de provider em falha dura.
"""

import json
import os
import random
import re
import time

import requests

_RETRYABLE = {429, 500, 502, 503, 504, 529}
_TIMEOUT   = 120


# ─── Providers ─────────────────────────────────────────────────────────────────

def _anthropic_available() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def _anthropic_ask(prompt, max_tokens, system):
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    kwargs = {}
    if system:
        kwargs["system"] = [{"type": "text", "text": system,
                             "cache_control": {"type": "ephemeral"}}]
    msg = client.messages.create(
        model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6"),
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}], **kwargs)
    return msg.content[0].text.strip()


def _openai_compat_ask(base_url, api_key, model, prompt, max_tokens, system,
                       timeout=_TIMEOUT):
    """Groq, OpenRouter e Ollama falam o mesmo dialeto (OpenAI chat)."""
    messages = ([{"role": "system", "content": system}] if system else []) \
        + [{"role": "user", "content": prompt}]
    r = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
        json={"model": model, "messages": messages,
              "max_tokens": max_tokens, "temperature": 0.7},
        timeout=timeout,
    )
    if r.status_code in _RETRYABLE:
        raise _Retryable(f"HTTP {r.status_code}")
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def _groq_available() -> bool:
    return bool(os.getenv("GROQ_API_KEY"))


def _groq_ask(prompt, max_tokens, system):
    return _openai_compat_ask(
        "https://api.groq.com/openai/v1", os.getenv("GROQ_API_KEY"),
        os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        prompt, max_tokens, system)


def _gemini_available() -> bool:
    return bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_AI_API_KEY"))


def _gemini_ask(prompt, max_tokens, system):
    key   = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_AI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.7},
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        params={"key": key}, json=body, timeout=_TIMEOUT)
    if r.status_code in _RETRYABLE:
        raise _Retryable(f"HTTP {r.status_code}")
    r.raise_for_status()
    cands = r.json().get("candidates", [])
    parts = (cands[0].get("content", {}).get("parts", [])) if cands else []
    text  = "".join(p.get("text", "") for p in parts).strip()
    if not text:
        raise RuntimeError("Gemini retornou vazio (bloqueio de conteúdo?)")
    return text


def _openrouter_available() -> bool:
    return bool(os.getenv("OPENROUTER_API_KEY"))


def _openrouter_ask(prompt, max_tokens, system):
    return _openai_compat_ask(
        "https://openrouter.ai/api/v1", os.getenv("OPENROUTER_API_KEY"),
        os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free"),
        prompt, max_tokens, system)


def _ollama_available() -> bool:
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def _ollama_ask(prompt, max_tokens, system):
    # LLM local em CPU: carregar o modelo (9GB+) e gerar milhares de tokens
    # leva vários minutos — timeout generoso, configurável por env var
    timeout = int(os.getenv("OLLAMA_TIMEOUT", "1800"))
    return _openai_compat_ask(
        "http://localhost:11434/v1", "ollama",
        os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
        prompt, max_tokens, system, timeout=timeout)


class _Retryable(RuntimeError):
    pass


PROVIDERS = [
    ("anthropic",  _anthropic_available,  _anthropic_ask),
    ("groq",       _groq_available,       _groq_ask),
    ("gemini",     _gemini_available,     _gemini_ask),
    ("openrouter", _openrouter_available, _openrouter_ask),
    ("ollama",     _ollama_available,     _ollama_ask),
]


def available_providers() -> list:
    return [name for name, avail, _ in PROVIDERS if avail()]


def any_available() -> bool:
    return bool(available_providers())


# ─── Interface pública (mesma do antigo claude_client) ─────────────────────────

_active = {"name": None}   # provider que funcionou por último (sticky)


def ask(prompt: str, max_tokens: int = 2000, system: str = None,
        max_retries: int = 2) -> str:
    """
    Tenta o provider ativo (ou o 1º disponível); em falha persistente, passa
    ao próximo da cadeia. Retry exponencial dentro de cada provider.
    """
    order = sorted(PROVIDERS,
                   key=lambda p: 0 if p[0] == _active["name"] else 1)
    errors = []
    for name, avail, fn in order:
        if not avail():
            continue
        delay = 2.0
        for attempt in range(max_retries + 1):
            try:
                result = fn(prompt, max_tokens, system)
                if _active["name"] != name:
                    print(f"  [llm] provider: {name}")
                    _active["name"] = name
                return result
            except _Retryable as e:
                if attempt >= max_retries:
                    errors.append(f"{name}: {e}")
                    break
                time.sleep(delay + random.uniform(0, 1))
                delay = min(delay * 2, 20)
            except Exception as e:
                status = getattr(getattr(e, "response", None), "status_code", None)
                if status in _RETRYABLE and attempt < max_retries:
                    time.sleep(delay + random.uniform(0, 1))
                    delay = min(delay * 2, 20)
                    continue
                errors.append(f"{name}: {type(e).__name__}: {e}")
                break
    raise RuntimeError(
        "Nenhum provider de LLM disponível/funcional. "
        f"Erros: {errors or 'nenhuma chave configurada'}. "
        "Configure UMA opção gratuita: GROQ_API_KEY (console.groq.com), "
        "GEMINI_API_KEY (aistudio.google.com), OPENROUTER_API_KEY "
        "(openrouter.ai) ou instale o Ollama (ollama.com).")


def ask_json(prompt: str, max_tokens: int = 2000, system: str = None,
             fallback: dict = None) -> dict:
    """ask() + parse tolerante de JSON (remove cercas, extrai objeto externo)."""
    raw = ask(prompt, max_tokens=max_tokens, system=system)
    cleaned = raw.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    result = dict(fallback) if fallback else {}
    result["raw"] = raw
    return result


def story_system(story: dict) -> str:
    """Bloco system padronizado com o JSON da história (cacheável no Anthropic)."""
    return ("CONTEXTO — HISTÓRIA DO VÍDEO (JSON):\n"
            + json.dumps(story, ensure_ascii=False, indent=2))
