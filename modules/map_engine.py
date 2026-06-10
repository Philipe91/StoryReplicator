"""
StoryReplicator v4.0 — Map Engine

Detecta locais (países, cidades, regiões, rotas) na narração e, quando
relevante, fornece queries de MAPA para o visual engine inserir mapas reais
como apoio visual (Wikimedia tem muitos mapas históricos de domínio público).

Sem API — detecção por dicionário de lugares + padrões.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
import json


# Locais conhecidos (PT → nome em inglês p/ busca de mapa)
_PLACES = {
    "nova york": "New York", "new york": "New York", "estados unidos": "United States",
    "eua": "United States", "paris": "Paris", "frança": "France", "londres": "London",
    "inglaterra": "England", "reino unido": "United Kingdom", "alemanha": "Germany",
    "berlim": "Berlin", "rússia": "Russia", "moscou": "Moscow", "japão": "Japan",
    "tóquio": "Tokyo", "china": "China", "brasil": "Brazil", "rio de janeiro": "Rio de Janeiro",
    "são paulo": "Sao Paulo", "itália": "Italy", "roma": "Rome", "espanha": "Spain",
    "nova jersey": "New Jersey", "lakehurst": "Lakehurst New Jersey", "chicago": "Chicago",
    "califórnia": "California", "texas": "Texas", "áustria": "Austria", "viena": "Vienna",
    "atlântico": "Atlantic Ocean", "pacífico": "Pacific Ocean", "europa": "Europe",
    "américa": "America", "áfrica": "Africa", "ásia": "Asia",
}


@dataclass
class MapCue:
    scene_id:   int
    place:      str             # nome em inglês
    is_route:   bool = False    # rota/trajeto entre dois lugares
    search_terms: list = field(default_factory=list)


def analyze(storyboard: dict, story: dict = None) -> list:
    """Detecta locais por cena e gera cues de mapa quando fizer sentido."""
    cues = []
    for cena in storyboard.get("cenas", []):
        text = (cena.get("narracao", "") + " " + cena.get("descricao_visual", "")).lower()
        found = [en for pt, en in _PLACES.items() if pt in text]
        found = list(dict.fromkeys(found))   # dedup preservando ordem
        if not found:
            continue

        seg = cena.get("segmento", "")
        # Mapa faz mais sentido em contexto/introdução (situar o espectador)
        if seg not in ("contexto", "introducao", "hook", "personagens"):
            continue

        is_route = len(found) >= 2
        place = found[0]
        terms = []
        if is_route:
            terms.append(f"{found[0]} {found[1]} map route historical")
        terms.append(f"{place} map historical")
        terms.append(f"{place} vintage map")

        cues.append(MapCue(scene_id=cena.get("cena_id", 0), place=place,
                           is_route=is_route, search_terms=terms))
    return cues


def to_scene_index(cues: list) -> dict:
    """{scene_id: search_terms} para o visual engine priorizar mapa naquelas cenas."""
    return {c.scene_id: c.search_terms for c in cues}


def save(cues: list, output_dir: Path) -> None:
    data = [{"scene_id": c.scene_id, "place": c.place, "is_route": c.is_route,
             "search_terms": c.search_terms} for c in cues]
    (Path(output_dir) / "map_cues.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
