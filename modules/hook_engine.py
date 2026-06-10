"""
StoryReplicator v4.0 — Hook Intelligence

Gera múltiplos hooks (ganchos de abertura) e pontua cada um por
curiosidade, impacto e potencial de retenção, selecionando o melhor.

O hook é o fator #1 de retenção em vídeos curtos: define se o
espectador continua assistindo nos primeiros 3 segundos.

Funciona SEM API: gera variantes por transformação do gancho original
e pontua por heurísticas linguísticas. Se ANTHROPIC_API_KEY existir,
usa Claude para gerar variantes mais criativas.
"""

import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
import json


@dataclass
class Hook:
    text:      str
    style:     str = ""        # question | shocking | number | mystery | direct
    curiosity: float = 0.0     # 0-10
    impact:    float = 0.0     # 0-10
    retention: float = 0.0     # 0-10
    total:     float = 0.0     # 0-10


# Palavras de alto impacto em PT-BR (geram curiosidade/tensão)
_IMPACT_WORDS = {
    "nunca", "jamais", "sempre", "impossível", "incrível", "absurdo", "genial",
    "segredo", "ninguém", "verdade", "mentira", "chocante", "inacreditável",
    "proibido", "escondido", "misterioso", "fatal", "último", "primeiro",
    "maior", "pior", "morte", "morreu", "matou", "desapareceu", "sumiu",
}
_CURIOSITY_TRIGGERS = {
    "por que", "como", "o que", "quem", "quando", "será que", "imagine",
    "ninguém sabe", "até hoje", "o que aconteceu", "descubra",
}


def generate_hooks(story: dict, analysis: dict = None, n: int = 3) -> list:
    """
    Gera n hooks candidatos. Tenta Claude se disponível; senão, templates.
    """
    base_hook = story.get("estrutura", {}).get("hook", "") or story.get("logline", "")
    titulo    = story.get("titulo", "")
    personagem = story.get("personagem_principal", {}).get("nome", "")

    hooks = _generate_via_claude(story, analysis, n)
    if hooks:
        return [_score(h) for h in hooks]

    # Fallback sem API: gera variantes por template a partir dos dados
    variants = _template_variants(base_hook, titulo, personagem, story)
    return [_score(h) for h in variants[:max(n, 3)]]


def select_best(hooks: list) -> Hook:
    """Retorna o hook de maior score total."""
    if not hooks:
        return Hook(text="", style="none")
    return max(hooks, key=lambda h: h.total)


def save_hooks(hooks: list, best: Hook, output_dir: Path) -> None:
    data = {
        "best":  asdict(best),
        "hooks": [asdict(h) for h in hooks],
    }
    (Path(output_dir) / "hooks.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ─── Geração via Claude (opcional) ─────────────────────────────────────────────

def _generate_via_claude(story: dict, analysis: dict, n: int) -> list:
    import os
    if not os.getenv("ANTHROPIC_API_KEY"):
        return []
    try:
        import anthropic
        from config import CLAUDE_MODEL
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        prompt = (
            f"Gere {n} hooks (frases de abertura, máx 15 palavras) para um vídeo "
            f"de história real inacreditável. Cada hook deve prender o espectador "
            f"nos primeiros 3 segundos.\n\nHistória: {json.dumps(story, ensure_ascii=False)[:1500]}\n\n"
            'Retorne APENAS JSON: {"hooks":[{"text":"...","style":"question|shocking|number|mystery|direct"}]}'
        )
        msg = client.messages.create(model=CLAUDE_MODEL, max_tokens=800,
                                     messages=[{"role": "user", "content": prompt}])
        raw = msg.content[0].text.strip().replace("```json", "").replace("```", "")
        data = json.loads(raw)
        return [Hook(text=h["text"], style=h.get("style", "")) for h in data.get("hooks", [])]
    except Exception:
        return []


# ─── Geração por template (sem API) ────────────────────────────────────────────

def _template_variants(base: str, titulo: str, personagem: str, story: dict) -> list:
    """Cria 3+ variantes de hook a partir dos dados da história."""
    variants = []

    # Variante 1: o hook original (direto)
    if base:
        variants.append(Hook(text=base.strip(), style="direct"))

    # Variante 2: pergunta de curiosidade
    if personagem:
        variants.append(Hook(
            text=f"Como {personagem} enganou o mundo inteiro?",
            style="question"))
    elif titulo:
        q = titulo.replace("O homem que", "Como um homem").rstrip(".?!") + "?"
        variants.append(Hook(text=q, style="question"))

    # Variante 3: afirmação chocante (extrai número/superlativo do logline)
    logline = story.get("logline", "")
    num_m   = re.search(r'\b(\d[\d.,]*)\b', logline + " " + base)
    if num_m:
        variants.append(Hook(
            text=f"Isto aconteceu {num_m.group(1)} vezes — e ninguém percebeu.",
            style="number"))
    else:
        variants.append(Hook(
            text="O que você vai ver não deveria ser possível.",
            style="shocking"))

    # Variante 4: mistério
    if titulo:
        variants.append(Hook(
            text=f"A história real por trás de {titulo.lower()}.",
            style="mystery"))

    # Garante unicidade
    seen, out = set(), []
    for v in variants:
        if v.text and v.text not in seen:
            seen.add(v.text)
            out.append(v)
    return out


# ─── Scoring ───────────────────────────────────────────────────────────────────

def _score(hook: Hook) -> Hook:
    text = hook.text.lower()
    words = text.split()
    n_words = len(words)

    # Curiosidade (0-10): perguntas, gatilhos de curiosidade
    cur = 0.0
    if "?" in hook.text:
        cur += 4
    cur += sum(2 for t in _CURIOSITY_TRIGGERS if t in text)
    if hook.style in ("question", "mystery"):
        cur += 2
    hook.curiosity = round(min(cur, 10), 1)

    # Impacto (0-10): palavras de alto impacto, números, superlativos
    imp = 0.0
    imp += sum(2 for w in _IMPACT_WORDS if w in text)
    if re.search(r'\b\d', text):
        imp += 3
    if hook.style in ("shocking", "number"):
        imp += 2
    hook.impact = round(min(imp, 10), 1)

    # Retenção (0-10): brevidade é rei em short-form
    ret = 0.0
    if n_words <= 8:
        ret = 10
    elif n_words <= 12:
        ret = 8
    elif n_words <= 16:
        ret = 6
    else:
        ret = 3
    # Bônus se começa com gatilho forte
    if words and words[0] in ("como", "por", "o", "quem", "imagine", "isto", "isso"):
        ret = min(ret + 1, 10)
    hook.retention = round(ret, 1)

    # Total ponderado: retenção pesa mais em short-form
    hook.total = round(
        hook.curiosity * 0.30 + hook.impact * 0.30 + hook.retention * 0.40, 2)
    return hook
