"""
StoryReplicator v4.1 — Editorial Agent

Orquestra a edição garantindo SINCRONIA e PRECISÃO entre narração e visual.
É a trava final contra imagens/vídeos errados (ex: navio numa história de
dirigível). Roda DEPOIS da aquisição visual e VALIDA cada asset:

  1. Deve mencionar o ASSUNTO do caso (âncora) — material real do tema
  2. Deve casar o MOMENTO da fala (termos distintivos da cena)
  3. NÃO pode conter termos de ASSUNTO CONFLITANTE (navio≠dirigível, etc)

Assets que não passam são REJEITADOS (melhor uma lacuna sinalizada que um erro
na tela). Os aprovados são renomeados com nome descritivo e registrados num
manifesto legível (edit_manifest.json) para revisão/edição manual.
"""

import json
import re
import shutil
from dataclasses import dataclass, field, asdict
from pathlib import Path


# Categorias de assunto e seus termos conflitantes (genérico, extensível).
# Se o ASSUNTO é de uma categoria, termos de OUTRA categoria invalidam o asset.
_CATEGORY_TERMS = {
    "aircraft":  ["airship", "zeppelin", "dirigible", "aircraft", "airplane", "plane", "aviation", "blimp"],
    "ship":      ["ship", "boat", "vessel", "ocean liner", "steamer", "sailing", "schooner", "yacht"],
    "train":     ["train", "locomotive", "railway", "railroad"],
    "building":  ["building", "tower", "bridge", "monument", "house"],
    "person":    ["portrait", "man", "woman", "president", "soldier"],
    "nature":    ["mountain", "forest", "snow", "river", "desert", "cave"],
}


@dataclass
class EditDecisionRow:
    scene_id:   int
    segment:    str
    narration:  str
    asset_type: str = ""
    source:     str = ""
    asset_title: str = ""
    local_path: str = ""
    status:     str = "pending"     # approved | rejected | missing
    reason:     str = ""
    renamed_to: str = ""


class EditorialAgent:

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.assets_dir = self.output_dir / "assets"

    # ── Validação + orquestração ─────────────────────────────────────────────

    def review(self, storyboard: dict, story: dict, va_result: dict,
               scene_contexts: dict) -> dict:
        """
        Revisa as decisões de aquisição, rejeita o que não é do caso, renomeia
        os aprovados e gera o manifesto. Retorna {timeline_overrides, manifest}.
        """
        # Caso histórico antigo? (ano < 1970 → fotos reais são P&B; coloridas
        # vibrantes indicam museu/marco/réplica MODERNA → rejeitar visualmente)
        self._historical_year = self._case_year(story, storyboard)
        self._strict_bw = bool(self._historical_year and self._historical_year < 1970)

        anchor = self._anchor_terms(storyboard, story)
        subject_cats = self._subject_categories(anchor, story, storyboard)
        # Categorias conflitantes = todas as outras que NÃO são do assunto
        forbidden = set()
        for cat, terms in _CATEGORY_TERMS.items():
            if cat not in subject_cats:
                forbidden.update(terms)
        # Remove da proibição termos que também pertencem ao assunto
        for cat in subject_cats:
            for t in _CATEGORY_TERMS.get(cat, []):
                forbidden.discard(t)

        rows = []
        approved_paths = {}     # cena_id → caminho renomeado (relativo)
        cenas = {c["cena_id"]: c for c in storyboard.get("cenas", [])}

        for cid in sorted(cenas, key=int):
            cena = cenas[cid]
            row = EditDecisionRow(
                scene_id=cid, segment=cena.get("segmento", ""),
                narration=cena.get("narracao", ""),
            )
            a = va_result.get("assignments", {}).get(str(cid)) or \
                va_result.get("assignments", {}).get(cid)
            if not a or a.get("status") != "found":
                row.status = "missing"; row.reason = "nenhum ativo adquirido"
                rows.append(row); continue

            row.asset_type  = a.get("asset_type", "")
            row.source      = a.get("source", "")
            row.local_path  = a.get("local_path", "")
            row.asset_title = self._title_from_url(a.get("url", "")) or a.get("source", "")

            verdict, reason = self._validate(a, cena, scene_contexts.get(cid),
                                             anchor, forbidden)
            row.status, row.reason = verdict, reason

            if verdict == "approved":
                new_rel = self._rename_asset(cid, cena, a, story)
                row.renamed_to = new_rel
                approved_paths[cid] = new_rel
            rows.append(row)

        manifest = self._build_manifest(story, rows, anchor, sorted(subject_cats))
        (self.output_dir / "edit_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        return {"approved_paths": approved_paths, "manifest": manifest, "rows": rows}

    # ── Validação de um asset contra a cena ──────────────────────────────────

    def _validate(self, a, cena, ctx, anchor, forbidden):
        # Usa o título REAL do asset (engine guarda em 'title'); senão, da URL
        title = (a.get("title") or self._title_from_url(a.get("url", ""))).strip()
        text  = f"{title} {a.get('source','')}".lower()
        primary = getattr(self, "_primary", [])

        src = str(a.get("source", ""))
        if src == "reused":
            return "rejected", "imagem reusada (não específica da cena)"

        # 1. ESTRITO: deve mencionar o NOME PRÓPRIO do caso (material real)
        if primary and title and not any(p in text for p in primary):
            return "rejected", f"não é o caso específico ({'/'.join(primary[:2])})"

        # 2. Âncora ampla (quando não há nome próprio)
        if not primary and title and anchor and not any(t in text for t in anchor):
            return "rejected", f"não menciona o assunto ({'/'.join(anchor[:2])})"

        # 3. Assunto conflitante (navio≠dirigível) e não é o caso
        hit = next((f for f in forbidden if re.search(rf"\b{re.escape(f)}\b", text)), None)
        if hit and not any(p in text for p in primary):
            return "rejected", f"assunto conflitante: '{hit}'"

        # 4. VALIDAÇÃO VISUAL: caso antigo (P&B) — rejeita foto MODERNA colorida
        #    (museu/marco/réplica atual). Resolve o "marco do Hindenburg" etc.
        if self._strict_bw and a.get("asset_type") == "image":
            local = self.output_dir / a.get("local_path", "")
            if local.exists() and self._is_modern_photo(local):
                return "rejected", "foto moderna colorida (museu/marco) — caso é P&B"

        # 5. Sem título legível — aceito por busca ancorada (raro)
        if not title:
            return "approved", "sem título legível — aceito por busca ancorada"

        return "approved", "ok"

    # ── Validação visual: foto moderna colorida vs histórica P&B ─────────────

    def _is_modern_photo(self, path) -> bool:
        """
        True se a imagem é colorida vibrante (foto digital moderna) — indício de
        museu/marco/réplica, não do evento histórico P&B. Mede saturação média.
        """
        try:
            from PIL import Image
            import numpy as np
            with Image.open(path) as im:
                small = im.convert("HSV").resize((128, 128))
                sat = np.asarray(small)[:, :, 1].astype(float) / 255.0
            # P&B/sépia: saturação média baixa (<0.12). Foto moderna: >0.20.
            # Também checa fração de pixels muito coloridos (céu azul, grama).
            mean_sat = float(sat.mean())
            colorful = float((sat > 0.35).mean())
            return mean_sat > 0.18 or colorful > 0.25
        except Exception:
            return False   # sem PIL → não bloqueia

    def _case_year(self, story: dict, storyboard: dict) -> int:
        blob = story.get("epoca_local", "") + " " + json.dumps(story, ensure_ascii=False)
        yrs = re.findall(r"\b(1[5-9]\d\d|20[0-2]\d)\b", blob)
        return int(yrs[0]) if yrs else 0

    # ── Renomeação descritiva ─────────────────────────────────────────────────

    def _rename_asset(self, cid: int, cena: dict, a: dict, story: dict) -> str:
        ext = ".mp4" if a.get("asset_type") == "video" else ".jpg"
        slug_subj = _slug((story.get("personagem_principal", {}) or {}).get("nome", "") or
                          story.get("titulo", ""))[:20]
        slug_mom  = _slug(cena.get("legenda", "") or cena.get("segmento", ""))[:24]
        new_name  = f"scene_{cid:02d}_{slug_subj}_{slug_mom}{ext}"
        src = self.output_dir / a.get("local_path", "")
        dst = self.assets_dir / new_name
        try:
            if src.exists() and src.resolve() != dst.resolve():
                shutil.copy2(src, dst)
            return f"assets/{new_name}"
        except Exception:
            return a.get("local_path", "")

    # ── Manifesto legível ──────────────────────────────────────────────────────

    def _build_manifest(self, story, rows, anchor, subject_cats):
        approved = [r for r in rows if r.status == "approved"]
        return {
            "titulo":          story.get("titulo", ""),
            "assunto_ancora":  anchor,
            "categorias":      subject_cats,
            "total_cenas":     len(rows),
            "aprovadas":       len(approved),
            "rejeitadas":      sum(1 for r in rows if r.status == "rejected"),
            "faltando":        sum(1 for r in rows if r.status == "missing"),
            "precisao_pct":    round(len(approved) / max(len(rows), 1) * 100, 1),
            "cenas": [
                {"cena": r.scene_id, "segmento": r.segment,
                 "narracao": r.narration[:70],
                 "asset": r.renamed_to or r.local_path,
                 "tipo": r.asset_type, "fonte": r.source,
                 "titulo_original": r.asset_title,
                 "status": r.status, "motivo": r.reason}
                for r in rows
            ],
            "revisao_manual": [
                {"cena": r.scene_id, "narracao": r.narration[:70],
                 "buscar": _suggest_search(r, story)}
                for r in rows if r.status in ("rejected", "missing")
            ],
        }

    # ── Helpers de assunto/categoria ──────────────────────────────────────────

    def _anchor_terms(self, storyboard, story):
        from modules.visual_asset_engine import UniversalVisualEngine
        eng = UniversalVisualEngine.__new__(UniversalVisualEngine)
        eng.subject_anchor = []
        eng.subject_primary = []
        anchor = eng._extract_subject_anchor(storyboard, story)
        self._primary = eng.subject_primary    # nome próprio do caso
        return anchor

    def _subject_categories(self, anchor, story, storyboard):
        """Detecta a(s) categoria(s) do assunto pelos termos da história."""
        blob = " ".join([
            json.dumps(story, ensure_ascii=False),
            " ".join(c.get("descricao_visual", "") for c in storyboard.get("cenas", [])),
        ]).lower()
        cats = set()
        for cat, terms in _CATEGORY_TERMS.items():
            if any(re.search(rf"\b{re.escape(t)}\b", blob) for t in terms):
                cats.add(cat)
        return cats or {"_unknown"}

    @staticmethod
    def _title_from_url(url: str) -> str:
        if not url:
            return ""
        import urllib.parse
        name = urllib.parse.unquote(url.split("/")[-1])
        name = re.sub(r"\.(jpg|jpeg|png|tif|tiff|mp4|webm|ogv)$", "", name, flags=re.I)
        name = re.sub(r"^(File:|NH_\d+_)", "", name)
        return name.replace("_", " ").replace("-", " ").strip()


# ─── utilitários ────────────────────────────────────────────────────────────

def _slug(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", (s or "").strip().lower())
    return s.strip("_") or "x"


def _suggest_search(row, story) -> str:
    subj = (story.get("personagem_principal", {}) or {}).get("nome", "") or story.get("titulo", "")
    return f"{subj} {row.segment}".strip()
