"""
StoryReplicator v4.0 — Sound Design Engine

Adiciona efeitos sonoros (SFX) contextuais para reforço emocional, em volume
baixo sob a narração — NUNCA competindo com a voz.

Detecta gatilhos na narração de cada cena (fogo, multidão, trem, mar, passos,
explosão, sirene, máquina de escrever...) e mixa o SFX correspondente no
momento certo. Busca SFX livres no Internet Archive (sem chave); usa cache.

Regras:
- Volume do SFX baixo (~12%), sob a narração
- Máx 1-2 SFX por cena, curtos
- Só quando o gatilho aparece na fala (reforço, não poluição)
"""

import hashlib
import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests


# Gatilho (termos PT/EN na narração) → categoria de SFX + termo de busca
SFX_TRIGGERS = {
    "fire":      {"terms": ["fogo", "chama", "chamas", "incêndio", "queimar", "ardência", "fire", "flames"],
                  "search": "fire crackling sound effect", "vol": 0.14},
    "explosion": {"terms": ["explosão", "explodiu", "estrondo", "bomba", "explosion", "blast"],
                  "search": "explosion sound effect", "vol": 0.16},
    "crowd":     {"terms": ["multidão", "plateia", "torcida", "gritos", "pessoas", "crowd", "cheering"],
                  "search": "crowd ambience sound effect", "vol": 0.10},
    "ship":      {"terms": ["navio", "mar", "oceano", "barco", "ondas", "porto", "ship", "ocean", "sea"],
                  "search": "ocean waves ship sound effect", "vol": 0.10},
    "train":     {"terms": ["trem", "locomotiva", "trilhos", "estação", "train", "locomotive"],
                  "search": "steam train sound effect", "vol": 0.12},
    "wind":      {"terms": ["vento", "tempestade", "ventania", "wind", "storm"],
                  "search": "wind howling sound effect", "vol": 0.10},
    "rain":      {"terms": ["chuva", "tempestade", "trovão", "rain", "thunder"],
                  "search": "rain thunder sound effect", "vol": 0.12},
    "siren":     {"terms": ["sirene", "alarme", "polícia", "ambulância", "siren", "alarm"],
                  "search": "siren alarm sound effect", "vol": 0.12},
    "typewriter":{"terms": ["máquina de escrever", "datilografar", "jornal", "manchete", "typewriter"],
                  "search": "typewriter sound effect", "vol": 0.12},
    "footsteps": {"terms": ["passos", "caminhava", "correu", "fugiu", "footsteps", "running"],
                  "search": "footsteps sound effect", "vol": 0.10},
    "clock":     {"terms": ["relógio", "tempo", "segundos", "minutos", "hora", "clock", "ticking"],
                  "search": "clock ticking sound effect", "vol": 0.10},
    "radio":     {"terms": ["rádio", "transmissão", "ao vivo", "locutor", "radio", "broadcast"],
                  "search": "old radio static sound effect", "vol": 0.10},
    "engine":    {"terms": ["motor", "máquina", "hélice", "avião", "engine", "motor", "propeller"],
                  "search": "engine motor sound effect", "vol": 0.10},
}


@dataclass
class SfxCue:
    scene_id:  int
    category:  str
    start:     float       # segundos (global)
    duration:  float
    volume:    float
    local_path: str = ""
    source:    str = ""


class SoundDesignEngine:

    CACHE_TTL = 30 * 24 * 3600
    MIN_BYTES = 20_000
    MAX_BYTES = 8 * 1024 * 1024

    def __init__(self, output_dir: Path, cache_dir: Path = None):
        self.output_dir = Path(output_dir)
        self.sfx_dir    = self.output_dir / "sfx"
        self.cache_dir  = Path(cache_dir) if cache_dir else self.output_dir / "cache"
        self.meta_dir   = self.cache_dir / "sfx_metadata"
        self.dl_dir     = self.cache_dir / "sfx_downloads"
        for d in (self.sfx_dir, self.meta_dir, self.dl_dir):
            d.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "StoryReplicator/4.0 (educational)"

    # ── Detecção de gatilhos ──────────────────────────────────────────────────

    def detect_cues(self, storyboard: dict) -> list:
        """Identifica quais SFX cabem em cada cena (pela narração)."""
        cues = []
        for cena in storyboard.get("cenas", []):
            text = (cena.get("narracao", "") + " " + cena.get("descricao_visual", "")).lower()
            start = float(cena.get("start", 0))
            dur   = float(cena.get("duracao", 4))
            matched = []
            for cat, cfg in SFX_TRIGGERS.items():
                if any(t in text for t in cfg["terms"]):
                    matched.append((cat, cfg))
            # Máx 1 SFX por cena (o mais específico/primeiro) p/ não poluir
            if matched:
                cat, cfg = matched[0]
                cues.append(SfxCue(
                    scene_id=cena.get("cena_id", 0), category=cat,
                    start=start, duration=min(dur, 5.0), volume=cfg["vol"],
                ))
        return cues

    # ── Aquisição de SFX (Internet Archive) ───────────────────────────────────

    def acquire(self, cues: list) -> list:
        """Baixa o SFX de cada cue. Retorna cues com local_path preenchido."""
        downloaded = {}
        for cue in cues:
            if cue.category in downloaded:
                cue.local_path = downloaded[cue.category]
                cue.source = "cache"
                continue
            path = self._fetch_sfx(cue.category)
            if path:
                cue.local_path = path
                cue.source = "archive"
                downloaded[cue.category] = path
        return [c for c in cues if c.local_path]

    def _fetch_sfx(self, category: str) -> str:
        cfg = SFX_TRIGGERS.get(category, {})
        query = cfg.get("search", f"{category} sound effect")
        key = hashlib.md5(f"sfx:{category}".encode()).hexdigest()
        cached_meta = self._load_cache(key)
        url = cached_meta.get("url") if cached_meta else None

        if not url:
            url = self._search_archive_audio(query)
            if url:
                self._save_cache(key, {"url": url})
        if not url:
            return ""

        dest = self.sfx_dir / f"sfx_{category}.mp3"
        if self._download(url, dest):
            return str(dest.relative_to(self.output_dir))
        return ""

    def _search_archive_audio(self, query: str) -> str:
        try:
            r = self.session.get(
                "https://archive.org/advancedsearch.php",
                params={"q": f"({query}) AND mediatype:audio",
                        "fl[]": "identifier", "rows": "5",
                        "output": "json", "sort[]": "downloads desc"},
                timeout=15,
            )
            if r.status_code != 200:
                return ""
            for doc in r.json().get("response", {}).get("docs", []):
                iid = doc.get("identifier", "")
                if not iid:
                    continue
                meta = self.session.get(f"https://archive.org/metadata/{iid}", timeout=12)
                if meta.status_code != 200:
                    continue
                for f in meta.json().get("files", []):
                    name = f.get("name", "")
                    if name.lower().endswith((".mp3", ".ogg", ".wav")):
                        return f"https://archive.org/download/{iid}/{name}"
        except Exception as e:
            print(f"[sfx] busca '{query}': {e}")
        return ""

    def _download(self, url: str, dest: Path) -> bool:
        h = hashlib.md5(url.encode()).hexdigest()
        cache = self.dl_dir / f"{h}.bin"
        if cache.exists() and (time.time() - cache.stat().st_mtime) < self.CACHE_TTL:
            try:
                dest.write_bytes(cache.read_bytes()); return True
            except Exception:
                pass
        try:
            r = self.session.get(url, timeout=25, stream=True)
            if r.status_code != 200:
                return False
            data = b"".join(r.iter_content(65536))
            if not (self.MIN_BYTES <= len(data) <= self.MAX_BYTES):
                if len(data) < self.MIN_BYTES:
                    return False
            cache.write_bytes(data)
            dest.write_bytes(data)
            return True
        except Exception:
            return False

    # ── Mixagem dos SFX no áudio final ────────────────────────────────────────

    def mix_into_audio(self, audio_path: Path, cues: list, output_path: Path,
                       ffmpeg_exe: str = "ffmpeg") -> bool:
        """
        Sobrepõe os SFX ao áudio (narração+música) nos tempos certos, em volume
        baixo. A narração permanece dominante. Retorna True se aplicou.
        """
        audio_path = Path(audio_path)
        cues = [c for c in cues if c.local_path and (self.output_dir / c.local_path).exists()]
        if not audio_path.exists() or not cues:
            return False

        cues = cues[:8]   # limite de segurança
        inputs = ["-i", str(audio_path)]
        for c in cues:
            inputs += ["-i", str(self.output_dir / c.local_path)]

        # Cada SFX: volume baixo + atraso para o tempo da cena (adelay em ms)
        filters = []
        mix_labels = ["[0:a]"]
        for i, c in enumerate(cues, start=1):
            delay_ms = int(c.start * 1000)
            filters.append(
                f"[{i}:a]volume={c.volume},atrim=0:{c.duration:.1f},"
                f"adelay={delay_ms}|{delay_ms},"
                f"afade=t=out:st={max(0,c.duration-0.4):.1f}:d=0.4[s{i}]"
            )
            mix_labels.append(f"[s{i}]")
        n = len(mix_labels)
        filters.append(f"{''.join(mix_labels)}amix=inputs={n}:duration=first:normalize=0[out]")
        fc = ";".join(filters)

        cmd = [ffmpeg_exe, "-y"] + inputs + [
            "-filter_complex", fc, "-map", "[out]",
            "-ar", "24000", "-ac", "1", str(output_path)
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=180)
            return r.returncode == 0 and Path(output_path).exists()
        except Exception as e:
            print(f"[sfx] mix erro: {e}")
            return False

    def save_report(self, cues: list) -> None:
        data = {"total_cues": len(cues),
                "cues": [{"scene_id": c.scene_id, "category": c.category,
                          "start": c.start, "volume": c.volume, "source": c.source}
                         for c in cues]}
        (self.output_dir / "sound_design.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── Cache ──────────────────────────────────────────────────────────────────
    def _load_cache(self, key):
        p = self.meta_dir / f"{key}.json"
        if not p.exists() or (time.time()-p.stat().st_mtime) > self.CACHE_TTL:
            return None
        try:    return json.loads(p.read_text(encoding="utf-8"))
        except Exception: return None

    def _save_cache(self, key, data):
        try: (self.meta_dir / f"{key}.json").write_text(json.dumps(data), encoding="utf-8")
        except Exception: pass
