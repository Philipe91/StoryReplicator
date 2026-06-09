"""
PRIORIDADE 1 — Compreensão estruturada de cena.

Extrai metadados precisos de cada cena do storyboard para gerar buscas
de imagem muito mais acuradas. Funciona SEM chamada de API.
"""

import re
from dataclasses import dataclass, field


@dataclass
class SceneContext:
    cena_id:       int
    character:     str = ""
    location:      str = ""
    year:          str = ""
    period:        str = ""      # e.g. "1890s", "Victorian era", "World War II"
    action:        str = ""
    main_object:   str = ""
    emotion:       str = "mystery"
    context:       str = ""
    visual_types:  list = field(default_factory=list)   # ["photograph", "map", "newspaper"]
    search_queries: list = field(default_factory=list)   # 5 queries em inglês


# ─── Mapeamentos ──────────────────────────────────────────────────────────────

_EMOTION_FROM_SEGMENT = {
    "hook":        "mystery",
    "introducao":  "contemplation",
    "contexto":    "curiosity",
    "personagens": "curiosity",
    "conflito":    "tension",
    "escalada":    "tension",
    "plot_twist":  "revelation",
    "desfecho":    "triumph",
    "final":       "resolution",
    "legado":      "contemplation",
    "cta":         "static",
}

# Períodos históricos reconhecidos (PT-BR e EN)
_PERIOD_PATTERNS = [
    (r'\b1[89][0-9]0s?\b',              "{decade}s"),
    (r'\b18[0-9]{2}\b',                 "1800s"),
    (r'\b19[012][0-9]\b',               "early 1900s"),
    (r'\b19[3-5][0-9]\b',               "mid 1900s"),
    (r'\b19[6-9][0-9]\b',               "late 1900s"),
    (r'\b20[012][0-9]\b',               "2000s"),
    (r'vitorian[oa]|victorian',         "Victorian era"),
    (r'primeira guerra|world war i\b',  "World War I 1914-1918"),
    (r'segunda guerra|world war ii',    "World War II 1939-1945"),
    (r'belle[- ]?époque',               "Belle Epoque 1890s"),
    (r'great depression|grande depressão', "Great Depression 1930s"),
    (r'gilded age|era dourada',         "Gilded Age 1880s"),
    (r'prohibition|lei seca',           "Prohibition era 1920s"),
    (r'\bpós[- ]?guerra\b',             "post-war 1945"),
]

# Tipos visuais por contexto
_VISUAL_TYPE_HINTS = {
    "documento":  ["official document", "historical document", "archival record"],
    "jornal":     ["newspaper front page", "newspaper clipping", "press headline"],
    "mapa":       ["historical map", "vintage map", "cartography"],
    "retrato":    ["portrait photograph", "formal portrait"],
    "prisão":     ["prison photograph", "jail cell"],
    "ponte":      ["bridge photograph", "engineering photograph"],
    "cidade":     ["city street photograph", "urban scene"],
    "navio":      ["ship photograph", "steamship"],
    "carta":      ["letter document", "handwritten document"],
    "dinheiro":   ["banknote", "currency photograph"],
    "multidão":   ["crowd photograph", "public gathering"],
}

# Países/cidades comuns → inglês
_LOCATION_MAP = {
    "nova york": "New York City",
    "new york":  "New York City",
    "paris":     "Paris France",
    "london":    "London England",
    "londres":   "London England",
    "berlim":    "Berlin Germany",
    "chicago":   "Chicago USA",
    "washington": "Washington DC USA",
    "são paulo": "Sao Paulo Brazil",
    "rio de janeiro": "Rio de Janeiro Brazil",
    "buenos aires": "Buenos Aires Argentina",
    "madrid":    "Madrid Spain",
    "roma":      "Rome Italy",
    "moscou":    "Moscow Russia",
    "tóquio":    "Tokyo Japan",
    "xangai":    "Shanghai China",
}


# ─── Função principal ─────────────────────────────────────────────────────────

def analyze_scene(cena: dict, story: dict) -> SceneContext:
    """
    Extrai contexto estruturado de uma cena do storyboard.
    Opera apenas com dados já existentes — sem chamada de API.
    """
    desc     = cena.get("descricao_visual", "")
    narracao = cena.get("narracao", "")
    segmento = cena.get("segmento", "")
    full_text = f"{desc} {narracao}".lower()

    ctx = SceneContext(cena_id=cena.get("cena_id", 0))

    # Emoção do segmento
    ctx.emotion = _EMOTION_FROM_SEGMENT.get(segmento, "mystery")

    # Personagem principal (da história ou da cena)
    ctx.character = _extract_character(full_text, desc, story)

    # Local
    ctx.location = _extract_location(full_text, story)

    # Ano e período
    ctx.year, ctx.period = _extract_year_and_period(full_text, story)

    # Ação principal (primeiro verbo significativo)
    ctx.action = _extract_action(desc)

    # Objeto principal
    ctx.main_object = _extract_object(desc)

    # Contexto geral
    ctx.context = f"{ctx.period} {ctx.location}".strip()

    # Tipos visuais sugeridos
    ctx.visual_types = _suggest_visual_types(full_text)
    if not ctx.visual_types:
        ctx.visual_types = ["historical photograph", "documentary photograph"]

    # Gera queries de busca em inglês
    ctx.search_queries = _build_search_queries(ctx)

    return ctx


def analyze_all_scenes(storyboard: dict, story: dict) -> dict:
    """Analisa todas as cenas. Retorna {cena_id: SceneContext}."""
    return {
        c["cena_id"]: analyze_scene(c, story)
        for c in storyboard.get("cenas", [])
    }


# ─── Extratores internos ──────────────────────────────────────────────────────

def _extract_character(text: str, desc: str, story: dict) -> str:
    """Tenta identificar o personagem principal da cena."""
    # Da história
    main_char = story.get("personagem_principal", {}).get("nome", "")
    if main_char and main_char.lower() in text:
        return main_char

    # Padrões comuns
    patterns = [
        r'\b([A-Z][a-z]+ [A-Z][a-z]+)\b',     # Nome Sobrenome
        r'\b([A-Z][a-z]{3,})\b',               # Nome único capitalizado
    ]
    for p in patterns:
        m = re.search(p, desc)
        if m:
            candidate = m.group(1)
            # Filtra palavras comuns não são nomes
            if candidate.lower() not in {"nova", "nova york", "the", "bridge", "police"}:
                return candidate

    return main_char or ""


def _extract_location(text: str, story: dict) -> str:
    """Extrai localização da cena."""
    # Da história
    epoca = story.get("epoca_local", "")
    if epoca:
        # Pega a parte de local (antes da vírgula ou ano)
        local_part = re.sub(r',.*', '', epoca).strip()
        en_loc = _LOCATION_MAP.get(local_part.lower(), local_part)
        if en_loc.lower() in text or local_part.lower() in text:
            return en_loc

    # Tenta detectar diretamente no texto
    for pt_name, en_name in _LOCATION_MAP.items():
        if pt_name in text:
            return en_name

    return _LOCATION_MAP.get(epoca.lower().split(",")[0].strip(), epoca.split(",")[0].strip())


def _extract_year_and_period(text: str, story: dict) -> tuple:
    """Retorna (year_str, period_str) da cena."""
    # Procura anos de 4 dígitos
    years = re.findall(r'\b(1[5-9]\d\d|20[0-2]\d)\b', text)
    year  = years[0] if years else ""

    # Detecta período
    period = ""
    for pattern, label in _PERIOD_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            if "{decade}" in label:
                decade = re.search(r'1[89][0-9]0', m.group(0))
                period = decade.group(0) + "s" if decade else label
            else:
                period = label
            break

    # Fallback: usa epoca_local da história
    if not period:
        epoca = story.get("epoca_local", "")
        year_m = re.search(r'\b(1[5-9]\d\d|20[0-2]\d)\b', epoca)
        if year_m:
            y = int(year_m.group(0))
            period = f"{(y // 10) * 10}s"
            year   = year or year_m.group(0)

    return year, period


def _extract_action(desc: str) -> str:
    """Extrai a ação principal da descrição visual."""
    # Padrões de ação (PT-BR)
    patterns = [
        r'(assinando|observando|caminhando|falando|entregando|recebendo|fugindo|preso|vendendo|comprando|lendo|escrevendo)',
        r'(sign\w+|walk\w+|run\w+|stand\w+|sit\w+|look\w+)',
    ]
    for p in patterns:
        m = re.search(p, desc, re.IGNORECASE)
        if m:
            return m.group(1)
    return ""


def _extract_object(desc: str) -> str:
    """Extrai o objeto/elemento mais importante da cena."""
    # Substantivos de alta relevância para documentários históricos
    objects = [
        "bridge", "tower", "building", "document", "map", "letter",
        "newspaper", "portrait", "prison", "street", "crowd", "ship",
        "money", "contract", "blueprint", "photograph", "handshake",
        "ponte", "torre", "documento", "mapa", "carta", "jornal",
        "prisão", "rua", "multidão", "navio", "dinheiro", "contrato",
    ]
    desc_lower = desc.lower()
    for obj in objects:
        if obj in desc_lower:
            return obj
    return ""


def _suggest_visual_types(text: str) -> list:
    """Sugere tipos de asset visual baseado no conteúdo da cena."""
    types = []
    for keyword, visual_list in _VISUAL_TYPE_HINTS.items():
        if keyword in text:
            types.extend(visual_list)
    return list(dict.fromkeys(types))[:3]   # dedup, máx 3


def _build_search_queries(ctx: SceneContext) -> list:
    """Gera até 5 queries de busca em inglês, do mais ao menos específico."""
    queries = []
    char    = ctx.character
    loc     = ctx.location
    period  = ctx.period
    obj     = ctx.main_object
    action  = ctx.action
    vtype   = ctx.visual_types[0] if ctx.visual_types else "historical photograph"

    # Query 1: personagem + local + período (máx específico)
    if char and loc and period:
        queries.append(f"{char} {loc} {period} {vtype}")

    # Query 2: local + período + objeto
    if loc and period and obj:
        queries.append(f"{loc} {period} {obj} vintage photograph")

    # Query 3: período + objeto + ação
    if period and obj:
        queries.append(f"{period} {obj} {action} historical".strip())

    # Query 4: local + período + tipo visual genérico
    if loc and period:
        queries.append(f"{loc} {period} street scene documentary")

    # Query 5: fallback simples baseado nos visual types
    if ctx.visual_types:
        queries.append(f"{period} {ctx.visual_types[0]}".strip())
    else:
        queries.append(f"{period} historical photograph".strip())

    # Remove duplicatas e strings muito curtas
    seen   = set()
    result = []
    for q in queries:
        q = q.strip()
        if q and len(q) > 10 and q not in seen:
            seen.add(q)
            result.append(q)

    # Garante pelo menos 2 queries
    if not result:
        result = [f"{ctx.period} historical photograph", "vintage documentary photograph"]

    return result[:5]
