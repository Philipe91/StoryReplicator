"""
PRIORIDADE 1+2 — Image Acquisition Engine v2.

Melhorias vs v1:
- Usa SceneContext do scene_analyzer para queries muito mais precisas
- Busca por tipos visuais variados: fotos, jornais, documentos, mapas, retratos
- Scoring avançado: 6 critérios ponderados
- Suporte a more visual types no Wikimedia
- Fallback para Archive.org com tipos MIME corretos
"""

import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import requests
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL


# ─── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class ImageCandidate:
    url: str
    title: str
    description: str = ""
    width: int = 0
    height: int = 0
    mime: str = "image/jpeg"
    source: str = ""
    license: str = "unknown"
    visual_type: str = "photograph"   # NOVO: photograph, newspaper, document, map, portrait
    score: float = 0.0


@dataclass
class SceneAssignment:
    cena_id: int
    status: str           # "found" | "missing"
    source: str = ""
    image_url: str = ""
    local_path: str = ""
    score: float = 0.0
    visual_type: str = ""
    keywords_used: list = field(default_factory=list)
    candidates_found: int = 0


# ─── Engine ────────────────────────────────────────────────────────────────────

class ImageAcquisitionEngine:
    """Busca, pontua e baixa imagens históricas para cada cena."""

    CACHE_TTL   = 7 * 24 * 3600
    REQ_DELAY   = 0.5
    MIN_BYTES   = 8_000
    MAX_QUERIES = 4

    def __init__(self, output_dir: Path, cache_dir: Path = None):
        self.output_dir = Path(output_dir)
        self.assets_dir = self.output_dir / "assets"
        self.cache_dir  = Path(cache_dir) if cache_dir else self.output_dir / "cache"
        self.meta_dir   = self.cache_dir / "metadata"
        self.img_dir    = self.cache_dir / "downloads"

        for d in [self.assets_dir, self.meta_dir, self.img_dir]:
            d.mkdir(parents=True, exist_ok=True)

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "StoryReplicator/2.0 (educational; historical image research)"
        })

    # ── Public entry point ──────────────────────────────────────────────────────

    def run(self, storyboard: dict, story: dict, timeline: dict,
            scene_contexts: dict = None) -> tuple:
        """
        scene_contexts: {cena_id: SceneContext} do scene_analyzer (opcional).
        Sem scene_contexts, usa Claude API para keywords (comportamento v1).
        """
        scenes = storyboard.get("cenas", [])
        if not scenes:
            return timeline, {"total_scenes": 0, "found": 0, "missing": 0}

        # Obtém keywords — prefere SceneContext, fallback para Claude API
        if scene_contexts:
            keywords_map = {
                cid: {
                    "search_queries": ctx.search_queries,
                    "period":         ctx.period,
                    "location":       ctx.location,
                    "subjects":       [ctx.main_object, ctx.character],
                    "visual_types":   ctx.visual_types,
                    "emotion":        ctx.emotion,
                }
                for cid, ctx in scene_contexts.items()
            }
        else:
            print("  [img] Extraindo keywords via Claude...")
            keywords_map = self._extract_keywords_all(storyboard, story)

        assignments: dict[int, SceneAssignment] = {}

        for cena in scenes:
            cid = cena["cena_id"]
            kw  = keywords_map.get(cid, {})
            queries      = kw.get("search_queries", [cena.get("descricao_visual", "historical photograph")[:60]])
            visual_types = kw.get("visual_types", ["photograph"])

            print(f"  [cena {cid:02d}] {queries[0][:50]}")

            candidates: list[ImageCandidate] = []
            for q in queries[:self.MAX_QUERIES]:
                # Busca por tipo visual quando disponível
                for vtype in visual_types[:2]:
                    query_full = f"{q} {vtype}" if vtype not in q else q
                    candidates.extend(self._search_all(query_full, vtype))
                    if len(candidates) >= 20:
                        break
                    time.sleep(self.REQ_DELAY)
                if len(candidates) >= 20:
                    break

            # Pontuação com contexto completo
            candidates = self._score(candidates, kw, cena)

            local_path = None
            used: Optional[ImageCandidate] = None
            for cand in candidates:
                dest = self.assets_dir / f"image_{cid:02d}.jpg"
                if self._download(cand.url, dest):
                    local_path = f"assets/image_{cid:02d}.jpg"
                    used       = cand
                    break

            if local_path and used:
                assignments[cid] = SceneAssignment(
                    cena_id=cid, status="found",
                    source=used.source, image_url=used.url,
                    local_path=local_path, score=used.score,
                    visual_type=used.visual_type,
                    keywords_used=queries, candidates_found=len(candidates),
                )
                print(f"    ✓ [{used.source}/{used.visual_type}] score={used.score:.2f}")
            else:
                assignments[cid] = SceneAssignment(
                    cena_id=cid, status="missing",
                    keywords_used=queries, candidates_found=len(candidates),
                )
                print(f"    ✗ não encontrada ({len(candidates)} cand.)")

        updated_timeline = self._update_timeline(timeline, assignments)
        found   = sum(1 for a in assignments.values() if a.status == "found")
        missing = len(assignments) - found

        return updated_timeline, {
            "total_scenes": len(scenes),
            "found":        found,
            "missing":      missing,
            "success_rate": round(found / len(scenes) * 100, 1),
            "sources_used": sorted({a.source for a in assignments.values() if a.source}),
            "assignments":  {k: asdict(v) for k, v in assignments.items()},
        }

    # ── Keywords via Claude (fallback) ─────────────────────────────────────────

    def _extract_keywords_all(self, storyboard: dict, story: dict) -> dict:
        scenes_summary = [
            {
                "cena_id":   c["cena_id"],
                "descricao": c.get("descricao_visual", "")[:120],
                "narracao":  c.get("narracao", "")[:80],
                "emotion":   c.get("emotion", "mystery"),
            }
            for c in storyboard.get("cenas", [])
        ]
        prompt = (
            "You are a historical image researcher. For each scene extract English search terms.\n"
            f"Story: {story.get('titulo','')}\nEra: {story.get('epoca_local','')}\n\n"
            f"Scenes:\n{json.dumps(scenes_summary, ensure_ascii=False)}\n\n"
            'Return ONLY JSON: {"scenes":[{"cena_id":1,"search_queries":["specific","broader","fallback"],'
            '"period":"1920s","location":"New York","subjects":["bridge","crowd"],'
            '"visual_types":["photograph","newspaper"]}]}'
        )
        try:
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            msg    = client.messages.create(
                model=CLAUDE_MODEL, max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            raw  = msg.content[0].text.strip().replace("```json","").replace("```","")
            data = json.loads(raw)
            return {s["cena_id"]: s for s in data.get("scenes", [])}
        except Exception as e:
            print(f"  [img] keyword extraction error: {e}")
            return {
                c["cena_id"]: {
                    "search_queries": [c.get("descricao_visual","historical photo")[:60]],
                    "period": story.get("epoca_local",""),
                    "location": "", "subjects": [], "visual_types": ["photograph"],
                }
                for c in storyboard.get("cenas", [])
            }

    # ── Busca em todas as fontes ────────────────────────────────────────────────

    def _search_all(self, query: str, visual_type: str = "photograph") -> list:
        cache_key = hashlib.md5(f"v2:{query}:{visual_type}".encode()).hexdigest()
        cached    = self._load_cache(cache_key)
        if cached is not None:
            return [ImageCandidate(**c) for c in cached]

        results: list[ImageCandidate] = []
        results.extend(self._search_wikimedia(query, visual_type))
        time.sleep(self.REQ_DELAY)
        results.extend(self._search_archive(query, visual_type))

        self._save_cache(cache_key, [asdict(r) for r in results])
        return results

    def _search_wikimedia(self, query: str, visual_type: str = "photograph") -> list:
        """Wikimedia Commons — suporta todos os tipos visuais históricos."""
        results = []
        try:
            r = self.session.get(
                "https://commons.wikimedia.org/w/api.php",
                params={"action":"query","list":"search","srnamespace":"6",
                        "srsearch":query,"srlimit":"8","format":"json"},
                timeout=15,
            )
            if r.status_code != 200 or not r.text.strip():
                return results

            items = r.json().get("query",{}).get("search",[])
            if not items:
                return results

            titles = "|".join(i["title"] for i in items[:6])
            time.sleep(0.3)
            r2 = self.session.get(
                "https://commons.wikimedia.org/w/api.php",
                params={"action":"query","titles":titles,"prop":"imageinfo",
                        "iiprop":"url|size|mime|extmetadata","format":"json"},
                timeout=15,
            )
            if not r2.text.strip():
                return results

            for page in r2.json().get("query",{}).get("pages",{}).values():
                ii   = (page.get("imageinfo") or [{}])[0]
                url  = ii.get("url","")
                mime = ii.get("mime","")
                if not url or not any(m in mime for m in ["image/","application/pdf"]):
                    continue
                if url.lower().endswith(".svg"):
                    continue
                meta = ii.get("extmetadata",{})
                results.append(ImageCandidate(
                    url=url, title=page.get("title",""),
                    description=(meta.get("ImageDescription",{}).get("value","") or "")[:200],
                    width=ii.get("width",0), height=ii.get("height",0),
                    mime=mime, source="wikimedia",
                    license=meta.get("LicenseShortName",{}).get("value","unknown"),
                    visual_type=visual_type,
                ))
        except Exception as e:
            pass
        return results

    def _search_archive(self, query: str, visual_type: str = "photograph") -> list:
        """Internet Archive — textos, fotos, gravuras de domínio público."""
        results = []
        try:
            # Mapeia tipo visual para termos de busca Archive
            type_terms = {
                "newspaper":  "newspaper",
                "document":   "document OR letter OR manuscript",
                "map":        "map OR cartography",
                "portrait":   "portrait",
                "engraving":  "engraving OR illustration",
            }.get(visual_type, "")

            q = f"{query} AND mediatype:image"
            if type_terms:
                q += f" AND subject:({type_terms})"

            r = self.session.get(
                "https://archive.org/advancedsearch.php",
                params={"q":q,"fl[]":"identifier,title,description,subject",
                        "rows":"6","output":"json"},
                timeout=15,
            )
            if r.status_code != 200:
                return results

            for doc in r.json().get("response",{}).get("docs",[]):
                iid = doc.get("identifier","")
                if not iid:
                    continue
                desc = doc.get("description","") or ""
                if isinstance(desc, list):
                    desc = desc[0] if desc else ""
                results.append(ImageCandidate(
                    url=f"https://archive.org/services/img/{iid}",
                    title=doc.get("title",""), description=str(desc)[:200],
                    source="archive", license="public domain", visual_type=visual_type,
                ))
        except Exception as e:
            pass
        return results

    # ── Scoring avançado (P2) ───────────────────────────────────────────────────

    def _score(self, candidates: list, kw: dict, cena: dict = None) -> list:  # noqa: ARG002
        """
        6 critérios ponderados:
        query_match (30%) + subject_match (20%) + period_match (15%)
        + location_match (10%) + visual_type_match (10%) + resolution (15%)
        """
        queries   = [q.lower() for q in kw.get("search_queries", [])]
        subjects  = [s.lower() for s in kw.get("subjects", []) if s]
        period    = kw.get("period", "").lower()
        location  = kw.get("location", "").lower()
        vtypes    = [v.lower() for v in kw.get("visual_types", [])]

        for c in candidates:
            text  = f"{c.title} {c.description}".lower()
            score = 0.0

            # 30% query
            if queries:
                hits = sum(1 for q in queries if any(w in text for w in q.split() if len(w) > 3))
                score += min(hits / len(queries), 1.0) * 0.30

            # 20% subjects
            if subjects:
                hits = sum(1 for s in subjects if s and s in text)
                score += min(hits / len(subjects), 1.0) * 0.20

            # 15% period
            if period:
                decade = period[:4]
                if decade.isdigit() and decade in text:
                    score += 0.15
                elif any(w in text for w in period.split() if len(w) > 3):
                    score += 0.08

            # 10% location
            if location:
                loc_words = [w for w in location.split() if len(w) > 3]
                if loc_words and any(w in text for w in loc_words):
                    score += 0.10

            # 10% visual type match
            if vtypes and c.visual_type in vtypes:
                score += 0.10

            # 15% resolution
            if c.width and c.height:
                mp = c.width * c.height / 1_000_000
                score += min(mp / 4.0, 1.0) * 0.15
            else:
                score += 0.04

            c.score = round(score, 3)

        return sorted(candidates, key=lambda x: x.score, reverse=True)

    # ── Download ────────────────────────────────────────────────────────────────

    def _download(self, url: str, dest: Path) -> bool:
        url_hash = hashlib.md5(url.encode()).hexdigest()
        cached   = self.img_dir / f"{url_hash}.bin"

        if cached.exists() and (time.time() - cached.stat().st_mtime) < self.CACHE_TTL:
            try:
                jpeg = self._to_jpeg(cached.read_bytes())
                dest.write_bytes(jpeg)
                return True
            except Exception:
                pass

        try:
            r = self.session.get(url, timeout=20, stream=True)
            if r.status_code != 200:
                return False
            if "text/html" in r.headers.get("content-type",""):
                return False
            raw = b"".join(r.iter_content(65536))
            if len(raw) < self.MIN_BYTES:
                return False
            cached.write_bytes(raw)
            jpeg = self._to_jpeg(raw)
            dest.write_bytes(jpeg)
            return True
        except Exception as e:
            return False

    def _to_jpeg(self, raw: bytes) -> bytes:
        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(raw)).convert("RGB")
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=92, optimize=True)
            return buf.getvalue()
        except Exception:
            return raw

    # ── Timeline update ─────────────────────────────────────────────────────────

    def _update_timeline(self, timeline: dict, assignments: dict) -> dict:
        updated = dict(timeline)
        scenes  = []
        for scene in timeline.get("scenes", []):
            cid    = scene.get("scene_id")
            assign = assignments.get(cid)
            s      = dict(scene)
            if assign and assign.status == "found":
                s["image_file"]    = assign.local_path
                s["image_source"]  = assign.source
                s["image_score"]   = assign.score
                s["visual_type"]   = assign.visual_type
            scenes.append(s)
        updated["scenes"] = scenes
        return updated

    # ── Cache ───────────────────────────────────────────────────────────────────

    def _load_cache(self, key: str) -> Optional[list]:
        path = self.meta_dir / f"{key}.json"
        if not path.exists() or (time.time() - path.stat().st_mtime) > self.CACHE_TTL:
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _save_cache(self, key: str, data: list) -> None:
        try:
            (self.meta_dir / f"{key}.json").write_text(json.dumps(data), encoding="utf-8")
        except Exception:
            pass


# ─── Report helpers ────────────────────────────────────────────────────────────

def save_acquisition_reports(result: dict, output_dir: Path) -> None:
    output_dir = Path(output_dir)
    path = output_dir / "08_acquisition_report.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Relatório: {path.name}")

    missing = [
        {
            "cena_id": a["cena_id"],
            "keywords_tried": a.get("keywords_used",[]),
            "suggestion": f"Search: {a.get('keywords_used',[''])[0]}",
        }
        for a in result.get("assignments",{}).values()
        if a["status"] == "missing"
    ]
    if missing:
        mp = output_dir / "missing_assets.json"
        mp.write_text(json.dumps({"missing_count":len(missing),"scenes":missing},
                                  ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  Faltando: {mp.name} ({len(missing)} cenas)")
