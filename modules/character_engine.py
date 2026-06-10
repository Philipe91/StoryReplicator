"""
StoryReplicator v4.0 — Character Engine

Para cada personagem da história, gera uma ficha (nome, época, papel, traços
visuais) usada para tornar a BUSCA VISUAL mais precisa — ex: ao procurar a
imagem de uma cena com a pessoa, usar 'nome + época + profissão'.

Funciona sem API (heurística sobre a história). Se ANTHROPIC_API_KEY existir,
enriquece a descrição via Claude.
"""

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class Character:
    name:        str
    role:        str = ""          # protagonista | antagonista | secundário
    era:         str = ""          # ex: "1930s"
    occupation:  str = ""
    description: str = ""          # traços físicos/roupas (p/ busca/IA futura)
    search_terms: list = field(default_factory=list)   # termos p/ buscar imagem real


def analyze(story: dict, storyboard: dict = None) -> list:
    """Extrai e descreve os personagens da história."""
    chars = []

    main = story.get("personagem_principal", {}) or {}
    if main.get("nome"):
        chars.append(_build_character(main, story, role="protagonista"))

    # Personagens secundários citados na história/segmentos
    for sec in story.get("personagens_secundarios", []) or []:
        if isinstance(sec, dict) and sec.get("nome"):
            chars.append(_build_character(sec, story, role="secundário"))
        elif isinstance(sec, str):
            chars.append(_build_character({"nome": sec}, story, role="secundário"))

    # Enriquecimento opcional via Claude
    _enrich_via_claude(chars, story)
    return chars


def to_search_index(characters: list) -> dict:
    """{nome_lower: search_terms} para o visual engine consultar por cena."""
    idx = {}
    for c in characters:
        idx[c.name.lower()] = c.search_terms
    return idx


def save(characters: list, output_dir: Path) -> None:
    (Path(output_dir) / "characters.json").write_text(
        json.dumps([asdict(c) for c in characters], ensure_ascii=False, indent=2),
        encoding="utf-8")


# ─── Internos ──────────────────────────────────────────────────────────────────

def _build_character(data: dict, story: dict, role: str) -> Character:
    nome = data.get("nome", "")
    era  = _extract_era(story.get("epoca_local", "") + " " + data.get("descricao", ""))
    occ  = _extract_occupation(data.get("descricao", "") + " " + data.get("motivacao", ""))

    c = Character(
        name=nome, role=role, era=era, occupation=occ,
        description=data.get("descricao", ""),
    )
    # Termos de busca para achar imagem REAL da pessoa
    terms = [nome]
    if era:
        terms.append(f"{nome} {era}")
    if occ:
        terms.append(f"{nome} {occ}")
    terms.append(f"{nome} portrait")
    c.search_terms = [t for t in terms if t.strip()]
    return c


_OCCUPATIONS = {
    "golpista": "con artist", "vigarista": "con artist", "criminoso": "criminal",
    "presidente": "president", "general": "general", "soldado": "soldier",
    "cientista": "scientist", "inventor": "inventor", "engenheiro": "engineer",
    "médico": "doctor", "advogado": "lawyer", "rei": "king", "rainha": "queen",
    "espião": "spy", "detetive": "detective", "policial": "police officer",
    "piloto": "pilot", "capitão": "captain", "explorador": "explorer",
    "empresário": "businessman", "banqueiro": "banker", "artista": "artist",
}

def _extract_occupation(text: str) -> str:
    t = text.lower()
    for pt, en in _OCCUPATIONS.items():
        if pt in t:
            return en
    return ""


def _extract_era(text: str) -> str:
    m = re.search(r"\b(1[5-9]\d\d|20[0-2]\d)\b", text)
    if m:
        y = int(m.group(0))
        return f"{(y // 10) * 10}s"
    for pat, label in [(r"vitorian|victorian", "Victorian era"),
                       (r"medieval|idade média", "medieval"),
                       (r"guerra fria|cold war", "Cold War")]:
        if re.search(pat, text, re.IGNORECASE):
            return label
    return ""


def _enrich_via_claude(chars: list, story: dict) -> None:
    import os
    if not os.getenv("ANTHROPIC_API_KEY") or not chars:
        return
    try:
        import anthropic
        from config import CLAUDE_MODEL
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        names = [c.name for c in chars]
        prompt = (
            f"Para cada personagem, descreva em inglês traços visuais para busca de "
            f"imagem (idade, roupas típicas da época, aparência). História: "
            f"{json.dumps(story, ensure_ascii=False)[:1200]}\nPersonagens: {names}\n"
            'Retorne JSON: {"chars":[{"name":"...","description":"..."}]}'
        )
        msg = client.messages.create(model=CLAUDE_MODEL, max_tokens=800,
                                     messages=[{"role": "user", "content": prompt}])
        raw = msg.content[0].text.strip().replace("```json", "").replace("```", "")
        data = {d["name"]: d.get("description", "") for d in json.loads(raw).get("chars", [])}
        for c in chars:
            if c.name in data and data[c.name]:
                c.description = data[c.name]
    except Exception:
        pass
