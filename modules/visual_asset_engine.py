"""
StoryReplicator v3.6 — Universal Visual Asset Engine

Para cada cena, encontra o MELHOR material visual possível seguindo a
ordem de prioridade (vídeo relevante > vídeo contexto > vídeo histórico >
foto histórica > documento > jornal > mapa > gravura > imagem complementar).

Orquestra todos os providers, pontua candidatos multi-critério, respeita
a mistura-alvo de ativos (40-60% vídeo) e baixa cortando para 2-6s.

Reutiliza scene_analyzer (contexto/queries) e os padrões de download/cache
dos engines de aquisição anteriores.
"""

import hashlib
import json
import time
from dataclasses import asdict
from pathlib import Path

import requests

from config import (
    ASSET_PRIORITY, ASSET_DURATION_MIN, ASSET_DURATION_MAX,
    ASSET_MIX_TARGET,
)
from modules import asset_providers as prov
from modules.asset_providers import VisualAsset
from modules import quality_filter as qf   # v3.7 Visual Quality Filter


# Categorias consideradas "histórico" (para contagem no report)
_HISTORICAL = {"video_historical", "photo_historical", "document", "newspaper", "map", "engraving"}
# Categorias de documento/mapa/jornal (fatia "document" do mix)
_DOCUMENT_LIKE = {"document", "newspaper", "map", "engraving"}


class UniversalVisualEngine:

    CACHE_TTL   = 7 * 24 * 3600
    REQ_DELAY   = 0.45
    MIN_IMG_BYTES = 8_000
    MIN_VID_BYTES = 40_000
    MAX_VID_BYTES = 60 * 1024 * 1024

    def __init__(self, output_dir: Path, cache_dir: Path = None, prefer_video: bool = True,
                 ffmpeg_exe: str = "ffmpeg"):
        self.output_dir = Path(output_dir)
        self.ffmpeg_exe = ffmpeg_exe
        self.assets_dir = self.output_dir / "assets"
        self.cache_dir  = Path(cache_dir) if cache_dir else self.output_dir / "cache"
        self.meta_dir   = self.cache_dir / "asset_metadata"
        self.dl_dir     = self.cache_dir / "asset_downloads"
        for d in (self.assets_dir, self.meta_dir, self.dl_dir):
            d.mkdir(parents=True, exist_ok=True)

        self.session = requests.Session()
        self.session.headers["User-Agent"] = "StoryReplicator/3.6 (educational research)"
        self.prefer_video = prefer_video

        # v4.0 — deduplicação de assets entre cenas (variedade visual)
        self._used_keys = set()
        self.subject_anchor = []   # termos-chave do assunto (precisão visual)

        # v3.7 — estatísticas do Visual Quality Filter
        self.quality_stats = {
            "low_resolution_rejected": 0,
            "blurry_rejected":         0,
            "upscaled_assets":         0,
            "resolutions":             [],   # (w,h) dos ativos aceitos
            "quality_scores":          [],
        }

    # ── Entry point ────────────────────────────────────────────────────────────

    def run(self, storyboard: dict, story: dict, scene_contexts: dict) -> dict:
        """
        Processa todas as cenas. Retorna report com assignments e mix.
        scene_contexts: {cena_id: SceneContext}
        """
        scenes = storyboard.get("cenas", [])
        active = prov.active_providers()
        print(f"  Providers ativos: {', '.join(k for k,v in active.items() if v)}")

        # ÂNCORA DE ASSUNTO: termos-chave que TODA imagem/vídeo deve mencionar.
        # Garante precisão — sem isso, buscas genéricas trazem imagens erradas.
        self.subject_anchor = self._extract_subject_anchor(storyboard, story)
        print(f"  Âncora de assunto: {self.subject_anchor}")

        assignments = {}
        mix_counter = {"video": 0, "image": 0, "document": 0}

        for cena in scenes:
            cid = cena["cena_id"]
            ctx = scene_contexts.get(cid)
            if ctx is None:
                assignments[cid] = self._missing(cid, [])
                continue

            # Decide se esta cena deve priorizar vídeo (ritmo/ação) ou pode ser imagem
            want_video_first = self._should_prefer_video(cena, mix_counter)

            print(f"  [cena {cid:02d}] {cena.get('segmento','')} "
                  f"({'vídeo' if want_video_first else 'imagem'} primeiro)")

            chosen = self._acquire_for_scene(ctx, cid, want_video_first)

            if chosen:
                # Atualiza contador de mix
                bucket = self._mix_bucket(chosen.category)
                mix_counter[bucket] += 1
                assignments[cid] = {
                    "cena_id":     cid,
                    "status":      "found",
                    "asset_type":  chosen.asset_type,
                    "category":    chosen.category,
                    "source":      chosen.source,
                    "url":         chosen.url,
                    "local_path":  chosen.local_path,
                    "duration":    round(chosen.duration, 2),
                    "score":       chosen.score,
                    "license":     chosen.license,
                }
                tag = chosen.asset_type.upper()
                print(f"    ✓ [{tag}/{chosen.source}] {chosen.category} "
                      f"score={chosen.score:.2f}")
            else:
                assignments[cid] = self._missing(cid, ctx.search_queries)
                print(f"    ✗ não encontrada")

        # Preenche cenas sem ativo reusando imagens boas (evita placeholder preto)
        self._fill_gaps(assignments)

        return self._build_report(assignments, mix_counter, len(scenes))

    def _fill_gaps(self, assignments: dict) -> None:
        """
        Para cada cena sem ativo, copia uma imagem boa já baixada (a de maior
        score), garantindo cobertura visual total sem telas pretas.
        """
        found_imgs = [
            a for a in assignments.values()
            if a.get("status") == "found" and a.get("asset_type") == "image"
        ]
        if not found_imgs:
            return
        found_imgs.sort(key=lambda a: a.get("score", 0), reverse=True)
        pool = [self.output_dir / a["local_path"] for a in found_imgs]

        i = 0
        for cid, a in assignments.items():
            if a.get("status") == "found":
                continue
            src  = pool[i % len(pool)]
            dest = self.assets_dir / f"image_{cid:02d}.jpg"
            try:
                import shutil
                shutil.copy2(src, dest)
                assignments[cid] = {
                    "cena_id": cid, "status": "found", "asset_type": "image",
                    "category": "image_complement", "source": "reused",
                    "url": "", "local_path": f"assets/image_{cid:02d}.jpg",
                    "duration": 0.0, "score": 0.0, "license": "reused",
                }
                print(f"    ⟳ cena {cid:02d}: reusando imagem de qualidade (sem tela preta)")
                i += 1
            except Exception:
                pass

    # ── Aquisição de uma cena (segue a ordem de prioridade) ──────────────────────

    def _extract_subject_anchor(self, storyboard: dict, story: dict) -> list:
        """
        Extrai os termos-chave do ASSUNTO (ex: 'hindenburg', 'zeppelin') que
        identificam o caso. Toda busca deve conter ≥1 desses termos e todo
        candidato deve mencioná-los — senão é descartado por irrelevância.
        """
        import re
        # Termos genéricos que NÃO identificam o assunto (não servem de âncora)
        generic = {
            "historical", "photograph", "photo", "vintage", "archival", "footage",
            "newsreel", "documentary", "1920s", "1930s", "1937", "1936", "1900s",
            "scene", "image", "picture", "old", "antique", "the", "and", "with",
            "structure", "frame", "interior", "aerial", "view", "size", "city",
            "over", "passenger", "lounge", "headline", "newspaper", "memorial",
            "disaster", "explosion", "fire", "wreckage", "aftermath", "landing",
        }
        # Conta frequência de termos nas descrições visuais
        freq = {}
        for c in storyboard.get("cenas", []):
            desc = (c.get("descricao_visual", "") or "").lower()
            for w in re.findall(r"[a-z]{4,}", desc):
                if w not in generic:
                    freq[w] = freq.get(w, 0) + 1
        # Âncoras = termos que aparecem em ao menos 2 cenas (recorrentes = assunto)
        anchor = sorted([w for w, n in freq.items() if n >= 2], key=lambda w: -freq[w])

        # Reforço pelo nome do personagem/assunto da história
        nome = (story.get("personagem_principal", {}) or {}).get("nome", "")
        for w in re.findall(r"[A-Za-z]{4,}", nome):
            wl = w.lower()
            if wl not in generic and wl not in anchor:
                anchor.insert(0, wl)

        return anchor[:4] if anchor else []

    def _matches_anchor(self, text: str) -> bool:
        """True se o texto menciona ≥1 termo da âncora de assunto."""
        if not self.subject_anchor:
            return True   # sem âncora definida, não filtra
        t = text.lower()
        return any(a in t for a in self.subject_anchor)

    # Termos genéricos que não distinguem o MOMENTO da cena
    _SCENE_GENERIC = {
        "historical", "photograph", "photo", "vintage", "archival", "footage",
        "newsreel", "documentary", "image", "picture", "scene", "old", "antique",
        "1936", "1937", "1935", "1900s", "mid", "the", "of", "a", "an", "and", "with",
    }
    # Indícios de que a imagem é um RETRATO/FOTO DE PESSOA (PT/EN/DE/NL/ES/FR/IT)
    _PERSON_HINTS = {
        # inglês
        "portrait", "president", "von", "captain", "commander", "crew member",
        "official", "politician", "general", "minister", "man ", "woman ",
        "headshot", "posing", "bust", "survivors", "survivor", "people",
        # holandês (ex: 'Overlevenden van de ramp')
        "overlevenden", "slachtoffers", "mensen", "portret",
        # alemão
        "porträt", "überlebende", "menschen", "besatzung",
        # português / espanhol
        "retrato", "sobreviventes", "sobrevivientes", "vítimas", "víctimas",
        "tripulação", "tripulación", "pessoas", "personas",
        # francês / italiano
        "portrait de", "survivants", "ritratto", "sopravvissuti",
    }
    # Termos que indicam que a CENA é sobre pessoa(s)
    _SCENE_ABOUT_PERSON = {
        "passenger", "crew", "survivor", "people", "man", "woman", "captain",
        "person", "portrait", "victim", "officer", "passageiro", "tripulação",
        "sobrevivente", "pessoa", "vítima",
    }

    def _scene_terms(self, ctx) -> list:
        """
        Termos DISTINTIVOS da cena (do que a narração mostra naquele momento):
        ex 'flying', 'interior', 'wreckage', 'structure'. Excluem a âncora de
        assunto e termos genéricos. Usados para casar a imagem com o MOMENTO da fala.
        """
        import re
        primary = ctx.search_queries[0] if ctx.search_queries else ""
        terms = []
        for w in re.findall(r"[a-z]{4,}", primary.lower()):
            if w in self._SCENE_GENERIC:        continue
            if w in self.subject_anchor:        continue
            terms.append(w)
        return terms

    def _scene_is_about_person(self, ctx) -> bool:
        primary = (ctx.search_queries[0] if ctx.search_queries else "").lower()
        return any(p in primary for p in self._SCENE_ABOUT_PERSON)

    def _looks_like_person(self, text: str) -> bool:
        t = text.lower()
        return any(h in t for h in self._PERSON_HINTS)

    def _acquire_for_scene(self, ctx, cid: int, want_video_first: bool) -> VisualAsset | None:
        candidates: list[VisualAsset] = []

        # 1-3. VÍDEOS (relevante → contexto → histórico)
        if want_video_first:
            vids = self._gather_videos(ctx)
            candidates.extend(vids)

        # 4-9. IMAGENS (foto histórica, documento, jornal, mapa, gravura, complemento)
        imgs = self._gather_images(ctx)
        candidates.extend(imgs)

        # Se não priorizou vídeo antes, ainda tenta vídeo como reforço (prioridade menor)
        if not want_video_first:
            candidates.extend(self._gather_videos(ctx, limit_queries=2))

        if not candidates:
            return None

        # Pontua e ordena
        self._score_all(candidates, ctx)
        candidates.sort(key=lambda a: a.score, reverse=True)

        # FILTRO DE RELEVÂNCIA: só considera candidatos que mencionam o assunto
        # (âncora). Sem isso, buscas genéricas trariam imagens erradas.
        relevant = [c for c in candidates if self._matches_anchor(f"{c.title} {c.description}")]

        # PRECISÃO TEMPORAL/CONTEXTUAL (genérico p/ qualquer caso):
        # ordena preferindo candidatos que batem os TERMOS DISTINTIVOS da cena
        # (o momento exato da fala) e penaliza retratos de pessoa quando a cena
        # NÃO é sobre pessoa (ex: foto de gente durante a fala sobre "tamanho").
        scene_terms      = self._scene_terms(ctx)
        scene_has_person = self._scene_is_about_person(ctx)

        def rank(c):
            text   = f"{c.title} {c.description}".lower()
            n_term = sum(1 for t in scene_terms if t in text)   # casa o momento
            person_penalty = 0
            if not scene_has_person and self._looks_like_person(text):
                person_penalty = -1                              # foto de pessoa fora de hora
            return (person_penalty, n_term, c.score)

        relevant.sort(key=rank, reverse=True)
        pool = relevant   # se vazio, vai p/ fill_gaps

        # DEDUP: pula candidatos já usados em outra cena (variedade + mescla).
        for cand in pool[:18]:
            akey = self._asset_key(cand)
            if akey in self._used_keys:
                continue
            if self._download(cand, cid):
                self._used_keys.add(akey)
                return cand
        return None

    def _asset_key(self, asset: VisualAsset) -> str:
        """Chave de identidade do asset para deduplicação."""
        ident = asset.extra.get("identifier") if asset.extra else None
        return ident or asset.url

    # Termos genéricos que poluem buscas no Wikimedia (queries longas falham)
    # Genéricos REMOVIDOS da query (não distinguem nada). NÃO inclui termos de
    # momento como 'flying', 'landing', 'interior', 'wreckage' — esses são
    # distintivos e ajudam a achar a imagem do instante certo da fala.
    _GENERIC_TERMS = {
        "historical", "photograph", "photo", "vintage", "archival", "footage",
        "newsreel", "documentary", "image", "picture", "scene", "old", "antique",
        "1936", "1937", "1935", "1900s", "mid", "the", "of", "a", "an", "and",
    }

    def _shorten_query(self, query: str) -> str:
        """
        Reduz a query aos termos essenciais (assunto + até 2 distintivos).
        Wikimedia retorna melhores resultados com 2-3 palavras-chave que com
        frases longas. Mantém a âncora + termos específicos da cena.
        """
        words = query.split()
        kept = []
        for w in words:
            wl = w.lower().strip(",.;:")
            if wl in self._GENERIC_TERMS:
                continue
            kept.append(w)
            if len(kept) >= 3:        # máx 3 palavras-chave
                break
        short = " ".join(kept) if kept else query
        return self._anchor_query(short)

    def _anchor_query(self, query: str) -> str:
        """Garante que a query contenha a âncora de assunto (precisão da busca)."""
        if not self.subject_anchor:
            return query
        q_low = query.lower()
        if any(a in q_low for a in self.subject_anchor):
            return query
        # Prefixa o termo principal do assunto
        return f"{self.subject_anchor[0]} {query}"

    # ── Coleta de vídeos (categorias 1-3) ────────────────────────────────────────

    def _gather_videos(self, ctx, limit_queries: int = 3) -> list:
        out = []
        queries = ctx.video_queries[:limit_queries]
        for i, q in enumerate(queries):
            q = self._shorten_query(q)  # encurta + ancora (Wikimedia prefere queries curtas)
            # Categoria por posição da query (1ª=relevante, 2ª=contexto, resto=histórico)
            category = ("video_relevant" if i == 0 else
                        "video_context" if i == 1 else "video_historical")
            found = self._cached_search(q, want_video=True)
            for a in found:
                a.category = category
            out.extend(found)
            time.sleep(self.REQ_DELAY)
            if len(out) >= 12:
                break
        return out

    # ── Coleta de imagens (categorias 4-9) ───────────────────────────────────────

    def _gather_images(self, ctx, limit_queries: int = 3) -> list:
        out = []
        # Mapeia visual_type → categoria de prioridade
        vtype_cat = {
            "photograph": "photo_historical", "portrait": "photo_historical",
            "document":   "document",          "newspaper": "newspaper",
            "map":        "map",               "engraving": "engraving",
        }
        primary_cat = "photo_historical"
        for vt in ctx.visual_types:
            for key, cat in vtype_cat.items():
                if key in vt:
                    primary_cat = cat
                    break

        for q in ctx.search_queries[:limit_queries]:
            q = self._shorten_query(q)  # encurta + ancora (Wikimedia prefere queries curtas)
            found = self._cached_search(q, want_video=False)
            for a in found:
                a.category = self._infer_image_category(a, primary_cat)
            out.extend(found)
            time.sleep(self.REQ_DELAY)
            if len(out) >= 16:
                break
        return out

    def _infer_image_category(self, asset: VisualAsset, default_cat: str) -> str:
        """Refina categoria da imagem pelo título/descrição."""
        text = f"{asset.title} {asset.description}".lower()
        if any(w in text for w in ("newspaper", "gazette", "headline", "press")):
            return "newspaper"
        if any(w in text for w in ("map", "plan", "cartograph", "atlas")):
            return "map"
        if any(w in text for w in ("document", "deed", "letter", "manuscript", "contract")):
            return "document"
        if any(w in text for w in ("engraving", "etching", "lithograph", "illustration")):
            return "engraving"
        if any(w in text for w in ("portrait", "photograph", "photo")):
            return "photo_historical"
        return default_cat

    # ── Busca com cache ──────────────────────────────────────────────────────────

    def _cached_search(self, query: str, want_video: bool) -> list:
        key = hashlib.md5(f"v36:{query}:{'V' if want_video else 'I'}".encode()).hexdigest()
        cached = self._load_cache(key)
        if cached is not None:
            return [VisualAsset(**c) for c in cached]

        results = []
        results.extend(prov.wikimedia_search(self.session, query, want_video))
        time.sleep(self.REQ_DELAY)
        results.extend(prov.archive_search(self.session, query, want_video))
        if not want_video:
            time.sleep(self.REQ_DELAY)
            results.extend(prov.loc_search(self.session, query))
        # Providers com chave (só rodam se key existir)
        results.extend(prov.pexels_search(self.session, query, want_video))
        results.extend(prov.pixabay_search(self.session, query, want_video))

        self._save_cache(key, [asdict(r) for r in results])
        return results

    # ── Scoring multi-critério ───────────────────────────────────────────────────

    def _score_all(self, candidates: list, ctx) -> None:
        queries  = [q.lower() for q in (ctx.search_queries + ctx.video_queries)]
        subjects = [s.lower() for s in (ctx.main_object, ctx.character) if s]
        period   = (ctx.period or "").lower()
        location = (ctx.location or "").lower()

        for c in candidates:
            text  = f"{c.title} {c.description}".lower()
            score = 0.0

            # Prioridade do tipo de ativo (peso forte: 0–0.30)
            prio  = ASSET_PRIORITY.get(c.category, 9)
            score += (10 - prio) / 9 * 0.30

            # Aderência à cena/ação (0–0.25)
            if queries:
                hits = sum(1 for q in queries
                           if any(w in text for w in q.split() if len(w) > 3))
                score += min(hits / len(queries), 1.0) * 0.25

            # Aderência ao objeto/personagem (0–0.15)
            if subjects:
                hits = sum(1 for s in subjects if s in text)
                score += min(hits / len(subjects), 1.0) * 0.15

            # Período (0–0.10)
            if period and period[:4] in text:
                score += 0.10

            # Local (0–0.08)
            if location:
                loc_words = [w for w in location.split() if len(w) > 3]
                if loc_words and any(w in text for w in loc_words):
                    score += 0.08

            # Qualidade visual (0–0.12) — v3.7: resolução + proporção
            score += qf.visual_quality_weight(c) * 0.12

            # Duração útil para vídeo (0–0.05): premia clipes 3-30s
            if c.asset_type == "video" and c.duration:
                if 3 <= c.duration <= 30:
                    score += 0.05
                elif c.duration > 60:
                    score -= 0.05

            c.score = round(max(0.0, score), 3)

    # ── Download (imagem ou vídeo, com corte 2-6s) ───────────────────────────────

    def _download(self, asset: VisualAsset, cid: int) -> bool:
        if asset.asset_type == "video":
            return self._download_video(asset, cid)
        return self._download_image(asset, cid)

    def _download_image(self, asset: VisualAsset, cid: int) -> bool:
        h     = hashlib.md5(asset.url.encode()).hexdigest()
        cache = self.dl_dir / f"{h}.bin"
        dest  = self.assets_dir / f"image_{cid:02d}.jpg"

        raw = None
        if cache.exists() and (time.time() - cache.stat().st_mtime) < self.CACHE_TTL:
            raw = cache.read_bytes()
        else:
            try:
                r = self.session.get(asset.url, timeout=20, stream=True)
                if r.status_code != 200 or "text/html" in r.headers.get("content-type", ""):
                    return False
                raw = b"".join(r.iter_content(65536))
                if len(raw) < self.MIN_IMG_BYTES:
                    return False
                cache.write_bytes(raw)
            except Exception:
                return False

        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(raw)).convert("RGB")
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=92, optimize=True)
            dest.write_bytes(buf.getvalue())
        except Exception:
            dest.write_bytes(raw)

        # v3.7 — Visual Quality Filter (pós-download)
        verdict = qf.evaluate_image_file(dest, relevance_score=asset.score)
        if verdict.get("needs_upscale"):
            if qf.upscale_image(dest):
                self.quality_stats["upscaled_assets"] += 1
                verdict = qf.evaluate_image_file(dest, relevance_score=asset.score)
        if not verdict.get("ok"):
            reason = verdict.get("reason", "")
            if "blur" in reason:
                self.quality_stats["blurry_rejected"] += 1
            else:
                self.quality_stats["low_resolution_rejected"] += 1
            dest.unlink(missing_ok=True)
            return False

        self.quality_stats["resolutions"].append((verdict["width"], verdict["height"]))
        self.quality_stats["quality_scores"].append(verdict["quality_score"])
        asset.width  = verdict["width"]
        asset.height = verdict["height"]
        asset.local_path = f"assets/image_{cid:02d}.jpg"
        return True

    def _download_video(self, asset: VisualAsset, cid: int) -> bool:
        h     = hashlib.md5(asset.url.encode()).hexdigest()
        cache = self.dl_dir / f"{h}.mp4"
        dest  = self.assets_dir / f"video_{cid:02d}.mp4"

        if cache.exists() and (time.time() - cache.stat().st_mtime) < self.CACHE_TTL:
            try:
                dest.write_bytes(cache.read_bytes())
                asset.local_path = f"assets/video_{cid:02d}.mp4"
                return True
            except Exception:
                pass
        try:
            r = self.session.get(asset.url, timeout=30, stream=True)
            if r.status_code != 200:
                return False
            ct = r.headers.get("content-type", "")
            if "video" not in ct and "octet-stream" not in ct:
                return False
            total = int(r.headers.get("content-length", 0))
            if total and total > self.MAX_VID_BYTES:
                return False
            data = b"".join(r.iter_content(131072))
            if len(data) < self.MIN_VID_BYTES:
                return False
            cache.write_bytes(data)
            dest.write_bytes(data)
        except Exception:
            return False

        # v3.7 — Visual Quality Filter (resolução mínima de vídeo)
        verdict = qf.evaluate_video_file(dest, ffmpeg_exe=self.ffmpeg_exe)
        if not verdict.get("ok"):
            self.quality_stats["low_resolution_rejected"] += 1
            dest.unlink(missing_ok=True)
            return False
        if verdict["width"]:
            self.quality_stats["resolutions"].append((verdict["width"], verdict["height"]))
        self.quality_stats["quality_scores"].append(verdict["quality_score"])
        asset.local_path = f"assets/video_{cid:02d}.mp4"
        return True

    # ── Decisão de mix ───────────────────────────────────────────────────────────

    def _should_prefer_video(self, cena: dict, mix_counter: dict) -> bool:
        """Decide se a cena prioriza vídeo, equilibrando ritmo + mix-alvo."""
        if not self.prefer_video:
            return False
        seg = cena.get("segmento", "")
        # Segmentos de ação/tensão favorecem vídeo
        action_seg = seg in ("conflito", "escalada", "plot_twist", "hook")
        total = sum(mix_counter.values()) or 1
        video_ratio = mix_counter["video"] / total
        # Se já está acima do alvo de vídeo, segura
        if video_ratio >= ASSET_MIX_TARGET["video"] + 0.1:
            return False
        # Se está abaixo do alvo, empurra vídeo
        if video_ratio < ASSET_MIX_TARGET["video"] - 0.1:
            return True
        return action_seg

    def _mix_bucket(self, category: str) -> str:
        if category.startswith("video"):
            return "video"
        if category in _DOCUMENT_LIKE:
            return "document"
        return "image"

    # ── Report ─────────────────────────────────────────────────────────────────

    def _build_report(self, assignments: dict, mix_counter: dict, total: int) -> dict:
        found      = [a for a in assignments.values() if a["status"] == "found"]
        video_n    = sum(1 for a in found if a.get("asset_type") == "video")
        image_n    = sum(1 for a in found if a.get("asset_type") == "image")
        hist_n     = sum(1 for a in found if a.get("category") in _HISTORICAL)
        doc_n      = sum(1 for a in found if a.get("category") in _DOCUMENT_LIKE)
        n_found    = len(found)

        mix_pct = {}
        if n_found:
            mix_pct = {
                "video":    round(video_n / n_found * 100, 1),
                "image":    round((image_n - doc_n) / n_found * 100, 1) if image_n >= doc_n else round(image_n/n_found*100,1),
                "document": round(doc_n / n_found * 100, 1),
            }

        # v3.7 — métricas do Visual Quality Filter
        qs   = self.quality_stats
        res  = qs["resolutions"]
        avg_w = round(sum(r[0] for r in res) / len(res)) if res else 0
        avg_h = round(sum(r[1] for r in res) / len(res)) if res else 0
        avg_q = round(sum(qs["quality_scores"]) / len(qs["quality_scores"]), 1) if qs["quality_scores"] else 0.0

        return {
            "version":        "3.7",
            "total_scenes":   total,
            "found":          n_found,
            "missing":        total - n_found,
            "success_rate":   round(n_found / max(total, 1) * 100, 1),
            "video_count":    video_n,
            "image_count":    image_n,
            "historical_assets_count": hist_n,
            "document_count": doc_n,
            "mix_pct":        mix_pct,
            "mix_target":     {k: round(v*100) for k, v in ASSET_MIX_TARGET.items()},
            "sources_used":   sorted({a["source"] for a in found if a.get("source")}),
            # Visual Quality Filter
            "low_resolution_rejected": qs["low_resolution_rejected"],
            "blurry_rejected":         qs["blurry_rejected"],
            "upscaled_assets":         qs["upscaled_assets"],
            "average_resolution":      f"{avg_w}x{avg_h}",
            "visual_quality_score":    avg_q,
            "assignments":    assignments,
        }

    def _missing(self, cid: int, queries: list) -> dict:
        return {"cena_id": cid, "status": "missing", "keywords_tried": queries[:3]}

    # ── Cache helpers ────────────────────────────────────────────────────────────

    def _load_cache(self, key: str):
        p = self.meta_dir / f"{key}.json"
        if not p.exists() or (time.time() - p.stat().st_mtime) > self.CACHE_TTL:
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _save_cache(self, key: str, data: list) -> None:
        try:
            (self.meta_dir / f"{key}.json").write_text(json.dumps(data), encoding="utf-8")
        except Exception:
            pass


# ─── Report / timeline helpers ─────────────────────────────────────────────────

def save_reports(result: dict, output_dir: Path) -> None:
    out = Path(output_dir)
    (out / "08_visual_assets_report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Relatório: 08_visual_assets_report.json")

    missing = [
        {"cena_id": a["cena_id"], "keywords_tried": a.get("keywords_tried", [])}
        for a in result.get("assignments", {}).values()
        if a["status"] == "missing"
    ]
    if missing:
        (out / "missing_assets.json").write_text(
            json.dumps({"missing_count": len(missing), "scenes": missing},
                       ensure_ascii=False, indent=2), encoding="utf-8")


def extract_assignments(result: dict) -> tuple:
    """Retorna (image_assignments, video_assignments) para o timeline_builder."""
    image_assign, video_assign = {}, {}
    for cid, a in result.get("assignments", {}).items():
        if a.get("status") != "found":
            continue
        cid_int = int(cid) if isinstance(cid, str) else cid
        if a.get("asset_type") == "video":
            video_assign[cid_int] = a["local_path"]
        else:
            image_assign[cid_int] = a["local_path"]
    return image_assign, video_assign
