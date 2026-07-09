"""
v6.4 — Scene Sync: a imagem entra NA PALAVRA exata da narração.

Antes, as cenas tinham duração estimada (~4s) e o corte caía "perto" da
fala. Este módulo realinha cada cena aos word boundaries REAIS do TTS:
localiza onde as primeiras palavras da narração da cena são faladas no
áudio e corta ali — narrador diz "Suíça", a imagem da Suíça entra naquele
frame. É o padrão de sincronização dos grandes canais (voz manda no tempo).

Também define a transição pelo RITMO da cena (rápido = corte seco;
lento = dissolve) — cortes variados, sem cara de template.
"""

import re
import unicodedata


def _norm(w: str) -> str:
    w = unicodedata.normalize("NFD", w.lower())
    w = "".join(ch for ch in w if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]", "", w)


def align_scenes_to_speech(scenes: list, boundaries: list,
                           audio_duration: float) -> tuple:
    """
    Realinha start/end/duration de cada cena ao momento em que sua narração
    é REALMENTE falada. scenes = storyboard["cenas"] (com campo `narracao`).
    Retorna (cenas_alinhadas, n_alinhadas).
    """
    if not scenes or not boundaries:
        return scenes, 0

    words = [(_norm(b["word"]), b["start"]) for b in boundaries]
    aligned, starts = [], []
    pos = 0

    for scene in scenes:
        target = [_norm(w) for w in str(scene.get("narracao", "")).split()[:3]]
        target = [t for t in target if t]
        found = None
        if target:
            # procura o trigrama da fala numa janela à frente da posição atual
            window_end = min(pos + 60, len(words))
            for j in range(pos, window_end):
                if words[j][0] == target[0]:
                    nxt = [w[0] for w in words[j:j + len(target)]]
                    if nxt == target or (len(target) >= 2
                                         and nxt[:2] == target[:2]):
                        found = j
                        break
        starts.append(words[found][1] if found is not None else None)
        if found is not None:
            pos = found + 1

    # completa lacunas por interpolação e monta os tempos finais
    n_aligned = sum(1 for s in starts if s is not None)
    if starts and starts[0] is None:
        starts[0] = 0.0
    for i in range(1, len(starts)):
        if starts[i] is None:
            prev_s = starts[i - 1]
            nxt = next((s for s in starts[i + 1:] if s is not None),
                       audio_duration)
            starts[i] = prev_s + (nxt - prev_s) / 2  # ponto médio simples

    # garante monotonicidade
    for i in range(1, len(starts)):
        if starts[i] <= starts[i - 1]:
            starts[i] = starts[i - 1] + 1.0

    for i, scene in enumerate(scenes):
        s = dict(scene)
        start = round(max(0.0, starts[i] - 0.15), 3)   # corte 150ms ANTES da palavra
        end = round(starts[i + 1] - 0.15, 3) if i + 1 < len(starts) \
            else round(audio_duration, 3)
        end = max(end, start + 1.2)
        s["start"], s["end"], s["duracao"] = start, end, round(end - start, 3)
        s["sync"] = "word-boundary" if (i < len(starts)
                                        and n_aligned) else "estimated"
        aligned.append(s)

    return aligned, n_aligned


# ─── Transições por ritmo (anti-template) ──────────────────────────────────────

_RHYTHM_TRANSITION = {
    "fast":   ("cut", 0.07),        # ação/escalada: corte seco
    "medium": ("fade", 0.30),       # padrão: fade curto
    "slow":   ("dissolve", 0.55),   # contexto/reflexão: dissolve longo
}


def apply_rhythm_transitions(scenes: list, edit_decisions: list) -> list:
    """
    Define transicao_entrada pelo RITMO decidido pelo Editor AI por cena —
    cortes rápidos nos momentos de tensão, dissolves nos contemplativos.
    """
    rhythm_by_id = {d.scene_id: getattr(d, "rhythm", "medium")
                    for d in (edit_decisions or [])}
    out = []
    for s in scenes:
        s = dict(s)
        rhythm = rhythm_by_id.get(s.get("cena_id") or s.get("scene_id"), "medium")
        trans, dur = _RHYTHM_TRANSITION.get(rhythm, _RHYTHM_TRANSITION["medium"])
        s["transicao_entrada"] = trans
        s["transition_in"] = trans
        s["transition_duration"] = dur
        out.append(s)
    return out
