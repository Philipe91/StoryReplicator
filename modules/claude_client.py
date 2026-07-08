"""
Compatibilidade — o "cérebro" agora é o modules/llm_client.py (multi-provider
com fallback: Anthropic opcional → Groq → Gemini → OpenRouter → Ollama local).

Todos os módulos continuam importando ask/ask_json/story_system daqui.
"""

from modules.llm_client import ask, ask_json, story_system, available_providers, any_available  # noqa: F401
