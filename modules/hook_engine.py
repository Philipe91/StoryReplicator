"""
StoryReplicator v4.0 — Hook Laboratory

Gera ≥15 hooks por vídeo usando 6 estratégias distintas e seleciona
automaticamente o de maior potencial de retenção.

Estratégias:
  - curiosidade  (perguntas abertas, "o que / como / por que")
  - choque       (afirmações de alto impacto)
  - mistério     (algo inexplicado / incompleto)
  - contradição  (paradoxo / oposição inesperada)
  - estatística  (número marcante)
  - revelação    (promessa de virada / segredo)

O hook é o fator nº 1 de retenção. Funciona sem API (templates por estratégia
sobre os dados da história). Se ANTHROPIC_API_KEY existir, adiciona variantes
criativas via Claude ao laboratório.
"""

import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
import json


@dataclass
class Hook:
    text:      str
    strategy:  str = ""        # curiosidade|choque|mistério|contradição|estatística|revelação
    curiosity: float = 0.0
    impact:    float = 0.0
    retention: float = 0.0
    total:     float = 0.0


_IMPACT_WORDS = {
    "nunca", "jamais", "sempre", "impossível", "incrível", "absurdo", "genial",
    "segredo", "ninguém", "verdade", "mentira", "chocante", "inacreditável",
    "proibido", "escondido", "misterioso", "fatal", "último", "primeiro",
    "maior", "pior", "morte", "morreu", "matou", "desapareceu", "sumiu",
    "roubou", "enganou", "sobreviveu", "explodiu", "afundou",
}
_CURIOSITY_TRIGGERS = {
    "por que", "como", "o que", "quem", "quando", "será que", "imagine",
    "ninguém sabe", "até hoje", "o que aconteceu", "descubra",
}


# ─── Geração ────────────────────────────────────────────────────────────────────

def generate_hooks(story: dict, analysis: dict = None, n: int = 15,
                   storyboard: dict = None) -> list:
    """Gera ≥n hooks (6 estratégias) + a narração da cena 'hook' do roteiro
    (que costuma ser o gancho mais específico) + variantes de Claude."""
    base   = story.get("estrutura", {}).get("hook", "") or story.get("logline", "")
    titulo = story.get("titulo", "")
    person = (story.get("personagem_principal", {}) or {}).get("nome", "")
    facts  = _extract_facts(story)

    hooks = []
    hooks += _strategy_curiosity(person, titulo, facts)
    hooks += _strategy_shock(person, titulo, facts)
    hooks += _strategy_mystery(person, titulo, facts)
    hooks += _strategy_contradiction(person, titulo, facts)
    hooks += _strategy_statistic(facts)
    hooks += _strategy_revelation(person, titulo, facts)
    if base:
        hooks.append(Hook(text=base.strip(), strategy="roteiro"))

    # Candidato forte: a narração da cena de abertura (hook) do storyboard —
    # é específica e escrita para o caso. Frases divididas viram candidatos.
    if storyboard:
        for cena in storyboard.get("cenas", []):
            if cena.get("segmento") == "hook":
                for frag in re.split(r"(?<=[.!?])\s+", cena.get("narracao", "")):
                    frag = frag.strip()
                    if frag and len(frag.split()) <= 16:
                        hooks.append(Hook(text=frag, strategy="roteiro"))
                break

    # Variantes via Claude (opcional)
    hooks += _generate_via_claude(story, analysis)

    # Dedup, score e garantia de quantidade mínima
    seen, scored = set(), []
    for h in hooks:
        t = h.text.strip()
        if t and 4 < len(t) < 120 and t.lower() not in seen:
            seen.add(t.lower())
            scored.append(_score(h))
    return scored


def select_best(hooks: list) -> Hook:
    if not hooks:
        return Hook(text="", strategy="none")
    return max(hooks, key=lambda h: h.total)


def save_hooks(hooks: list, best: Hook, output_dir: Path) -> None:
    data = {"best": asdict(best), "total_generated": len(hooks),
            "by_strategy": _count_by_strategy(hooks),
            "hooks": [asdict(h) for h in sorted(hooks, key=lambda h: -h.total)]}
    (Path(output_dir) / "hooks.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ─── Extração de fatos ──────────────────────────────────────────────────────────

def _extract_facts(story: dict) -> dict:
    """Extrai números, local, época e ação central da história."""
    blob = " ".join(str(v) for v in [
        story.get("logline", ""), story.get("titulo", ""),
        story.get("subtitulo", ""), story.get("epoca_local", ""),
        json.dumps(story.get("estrutura", {}), ensure_ascii=False),
    ])
    numbers = re.findall(r"\b(\d[\d.\,]*)\b", blob)
    years   = re.findall(r"\b(1[5-9]\d\d|20[0-2]\d)\b", blob)
    place   = re.sub(r",.*", "", story.get("epoca_local", "")).strip()
    return {
        "numbers": [n for n in numbers if n not in years][:4],
        "years":   years[:2],
        "place":   place,
        "title":   story.get("titulo", ""),
    }


# ─── Estratégias (cada uma gera 2-3 variantes) ──────────────────────────────────

def _strategy_curiosity(person, titulo, f):
    out = []
    if person:
        out.append(Hook(f"Como {person} conseguiu fazer o impossível?", "curiosidade"))
        out.append(Hook(f"O que {person} fez que ninguém acreditou?", "curiosidade"))
    if titulo:
        t = titulo.lower().replace("o homem que", "um homem que").rstrip(".?!")
        out.append(Hook(f"Você sabia que {t}?", "curiosidade"))
    return out


def _strategy_shock(person, titulo, f):
    out = [Hook("O que você vai ver não deveria ser possível.", "choque")]
    if person:
        out.append(Hook(f"{person} fez algo que mudou a história para sempre.", "choque"))
    if titulo:
        out.append(Hook(f"{titulo.rstrip('.')}. E é tudo verdade.", "choque"))
    return out


def _strategy_mystery(person, titulo, f):
    out = [Hook("Até hoje, ninguém conseguiu explicar o que aconteceu.", "mistério")]
    if f["place"]:
        out.append(Hook(f"Algo aconteceu em {f['place']} que desafia toda lógica.", "mistério"))
    out.append(Hook("Os fatos são reais. A explicação, ninguém tem.", "mistério"))
    return out


def _strategy_contradiction(person, titulo, f):
    out = [Hook("Era impossível. Aconteceu mesmo assim.", "contradição")]
    if person:
        out.append(Hook(f"Todos diziam que {person} jamais conseguiria. Estavam errados.", "contradição"))
    out.append(Hook("Quanto mais seguro parecia, mais perigoso era.", "contradição"))
    return out


def _strategy_statistic(f):
    out = []
    for num in f["numbers"][:2]:
        out.append(Hook(f"Foram {num}. E isso é só o começo da história.", "estatística"))
    if f["years"]:
        out.append(Hook(f"Em {f['years'][0]}, algo aconteceu que ninguém esqueceria.", "estatística"))
    if not out:
        out.append(Hook("Os números desta história são difíceis de acreditar.", "estatística"))
    return out


def _strategy_revelation(person, titulo, f):
    out = [Hook("O que ninguém esperava muda tudo no final.", "revelação")]
    if person:
        out.append(Hook(f"A verdade sobre {person} foi escondida por anos.", "revelação"))
    out.append(Hook("Existe um detalhe nesta história que poucos conhecem.", "revelação"))
    return out


# ─── Claude (opcional) ──────────────────────────────────────────────────────────

def _generate_via_claude(story: dict, analysis: dict) -> list:
    import os
    if not os.getenv("ANTHROPIC_API_KEY"):
        return []
    try:
        import anthropic
        from config import CLAUDE_MODEL
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        prompt = (
            "Gere 6 hooks (frases de abertura, máx 14 palavras) para um vídeo de "
            "história real, um por estratégia: curiosidade, choque, mistério, "
            "contradição, estatística, revelação.\n"
            f"História: {json.dumps(story, ensure_ascii=False)[:1200]}\n"
            'Retorne JSON: {"hooks":[{"text":"...","strategy":"..."}]}'
        )
        msg = client.messages.create(model=CLAUDE_MODEL, max_tokens=700,
                                     messages=[{"role": "user", "content": prompt}])
        raw = msg.content[0].text.strip().replace("```json", "").replace("```", "")
        return [Hook(h["text"], h.get("strategy", "claude"))
                for h in json.loads(raw).get("hooks", [])]
    except Exception:
        return []


# ─── Scoring (mais discriminante) ───────────────────────────────────────────────

def _score(hook: Hook) -> Hook:
    text = hook.text.lower()
    words = text.split()
    nw = len(words)

    # Curiosidade (0-10)
    cur = 4.0 if "?" in hook.text else 0.0
    cur += sum(2 for t in _CURIOSITY_TRIGGERS if t in text)
    if hook.strategy in ("curiosidade", "mistério", "revelação"):
        cur += 2
    hook.curiosity = round(min(cur, 10), 1)

    # Impacto (0-10)
    imp = sum(2 for w in _IMPACT_WORDS if w in text)
    if re.search(r"\b\d", text):
        imp += 3
    if hook.strategy in ("choque", "estatística", "contradição"):
        imp += 2
    hook.impact = round(min(imp, 10), 1)

    # Retenção (0-10): brevidade + começo forte + especificidade
    if   nw <= 8:  ret = 10
    elif nw <= 11: ret = 8
    elif nw <= 14: ret = 6
    else:          ret = 3
    if words and words[0] in ("como", "por", "o", "quem", "imagine", "você", "até", "era", "foram"):
        ret = min(ret + 1, 10)
    hook.retention = round(ret, 1)

    # Concretude: número específico OU nome próprio (depois da 1ª palavra)
    # Concretude: dígitos OU números por extenso OU nome próprio
    has_number = bool(re.search(r"\b\d", text)) or any(w in text for w in _NUMBER_WORDS)
    has_proper = bool(re.search(r"\b[A-Z][a-z]{2,}", hook.text[1:]))

    # Vagueza: clichês que servem para QUALQUER história (baixa retenção real)
    vague = sum(1 for c in _VAGUE_CLICHES if c in text)

    # Total: retenção pesa mais; concretude premiada, vagueza penalizada forte
    base = hook.curiosity * 0.25 + hook.impact * 0.30 + hook.retention * 0.45
    if has_number: base += 1.2     # número específico = gancho forte
    if has_proper: base += 0.5     # nome próprio do caso
    base -= vague * 1.5            # cada clichê vago derruba
    hook.total = round(max(0, min(base, 10)), 2)
    return hook


# Clichês vagos que cabem em qualquer história → baixa retenção real
_VAGUE_CLICHES = [
    "fazer o impossível", "mudou a história", "desafia toda lógica",
    "não deveria ser possível", "difíceis de acreditar", "muda tudo no final",
    "poucos conhecem", "ninguém esqueceria", "só o começo",
    "fez algo que", "que ninguém acreditou", "desafia",
    "ninguém conseguiu explicar", "o que aconteceu", "a explicação, ninguém",
    "algo aconteceu que", "foi escondida por anos",
]

# Números por extenso (PT) — contam como concretude (ex: "Sete vezes")
_NUMBER_WORDS = {
    "dois", "duas", "três", "quatro", "cinco", "seis", "sete", "oito", "nove",
    "dez", "onze", "doze", "vinte", "trinta", "cem", "cento", "mil", "milhão",
    "milhões", "bilhão", "bilhões", "dezenas", "centenas", "milhares",
}


def _count_by_strategy(hooks: list) -> dict:
    out = {}
    for h in hooks:
        out[h.strategy] = out.get(h.strategy, 0) + 1
    return out
