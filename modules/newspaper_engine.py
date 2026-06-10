"""
StoryReplicator v4.0 — Newspaper Engine

Detecta marcos noticiáveis na narração (datas importantes, prisões, guerras,
golpes, desastres, mortes, recordes) e fornece queries para o visual engine
priorizar MANCHETES / JORNAIS / DOCUMENTOS reais naquelas cenas — recurso
clássico de documentário para dar autenticidade.

Sem API — detecção por padrões e gatilhos.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
import json


# Gatilhos de evento noticiável (PT/EN) → tipo de documento
_NEWS_TRIGGERS = {
    "arrest":    ["preso", "prisão", "condenado", "perpétua", "julgamento", "arrested", "convicted"],
    "disaster":  ["desastre", "tragédia", "explosão", "acidente", "afundou", "disaster", "crash"],
    "war":       ["guerra", "batalha", "invasão", "ataque", "war", "battle", "invasion"],
    "crime":     ["golpe", "fraude", "roubo", "crime", "assassinato", "scam", "fraud", "heist"],
    "death":     ["morreu", "morte", "faleceu", "mortos", "vítimas", "died", "death", "killed"],
    "record":    ["recorde", "maior", "primeiro", "histórico", "record", "largest", "first"],
}


@dataclass
class NewspaperCue:
    scene_id:   int
    event_type: str
    year:       str = ""
    search_terms: list = field(default_factory=list)


def analyze(storyboard: dict, story: dict = None) -> list:
    """Detecta cenas que pedem manchete/jornal e gera queries."""
    cues = []
    subject = _subject_terms(story or {})

    for cena in storyboard.get("cenas", []):
        text = (cena.get("narracao", "") + " " + cena.get("descricao_visual", "")).lower()
        year = _extract_year(text) or _extract_year(str(story.get("epoca_local", "")) if story else "")

        matched = [etype for etype, terms in _NEWS_TRIGGERS.items()
                   if any(t in text for t in terms)]
        if not matched:
            continue

        etype = matched[0]
        # Queries: assunto + 'newspaper headline' + ano + tipo de evento
        terms = []
        base = subject or "historical"
        terms.append(f"{base} newspaper headline {year}".strip())
        terms.append(f"{base} {etype} newspaper {year}".strip())
        terms.append(f"{base} newspaper front page")
        cues.append(NewspaperCue(scene_id=cena.get("cena_id", 0),
                                 event_type=etype, year=year, search_terms=terms))
    return cues


def to_scene_index(cues: list) -> dict:
    """{scene_id: search_terms} para o visual engine priorizar jornal."""
    return {c.scene_id: c.search_terms for c in cues}


def save(cues: list, output_dir: Path) -> None:
    data = [{"scene_id": c.scene_id, "event_type": c.event_type, "year": c.year,
             "search_terms": c.search_terms} for c in cues]
    (Path(output_dir) / "newspaper_cues.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ─── Internos ──────────────────────────────────────────────────────────────────

def _subject_terms(story: dict) -> str:
    """Termo principal do assunto (p/ ancorar a busca de jornal)."""
    nome = (story.get("personagem_principal", {}) or {}).get("nome", "")
    if nome and nome.isascii():
        return nome.split()[0] if " " in nome else nome
    return ""


def _extract_year(text: str) -> str:
    m = re.search(r"\b(1[5-9]\d\d|20[0-2]\d)\b", text or "")
    return m.group(0) if m else ""
