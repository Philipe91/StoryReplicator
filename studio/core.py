"""
StoryReplicator Studio — núcleo da arquitetura multi-agentes.

Três peças:

- JobContext  → o "blackboard" compartilhado. Agentes leem/escrevem artefatos
                nomeados e trocam mensagens dirigidas — é assim que conversam
                sem acoplamento direto.
- Agent       → unidade especializada. Declara o que exige (requires) e o que
                produz (produces); o orquestrador valida o contrato.
- Orchestrator→ executa o pipeline em ordem, registra histórico e roda o LOOP
                DE QUALIDADE: se o Agente de Qualidade pedir retrabalho, os
                agentes apontados re-executam (com as notas do QA na caixa de
                entrada) até max_qa_rounds.

Novos agentes podem ser adicionados sem tocar nos existentes: basta declarar
requires/produces e inserir na lista do pipeline.
"""

import json
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path


class MissingArtifact(RuntimeError):
    pass


# ─── Blackboard ────────────────────────────────────────────────────────────────

@dataclass
class JobContext:
    theme: str
    workdir: Path
    config: dict = field(default_factory=dict)
    artifacts: dict = field(default_factory=dict)
    messages: list = field(default_factory=list)   # [{from, to, note, ts}]
    history: list = field(default_factory=list)    # execuções de agentes

    # — artefatos —
    def set(self, key: str, value, agent: str = "?") -> None:
        self.artifacts[key] = value
        self.history.append({"ts": time.time(), "agent": agent, "set": key})

    def get(self, key: str, default=None):
        return self.artifacts.get(key, default)

    def require(self, *keys):
        missing = [k for k in keys if k not in self.artifacts]
        if missing:
            raise MissingArtifact(f"Artefatos ausentes: {missing}")
        vals = [self.artifacts[k] for k in keys]
        return vals[0] if len(vals) == 1 else vals

    # — mensagens entre agentes —
    def send(self, sender: str, to: str, note: str) -> None:
        self.messages.append({"from": sender, "to": to, "note": note,
                              "ts": time.time(), "read": False})

    def inbox(self, agent: str, mark_read: bool = True) -> list:
        msgs = [m for m in self.messages if m["to"] == agent and not m["read"]]
        if mark_read:
            for m in msgs:
                m["read"] = True
        return msgs

    # — persistência p/ depuração e retomada —
    def snapshot(self) -> None:
        state = {
            "theme":    self.theme,
            "config":   self.config,
            "artifacts": {k: v for k, v in self.artifacts.items()
                          if _is_jsonable(v)},
            "messages": self.messages,
            "history":  self.history[-200:],
        }
        path = Path(self.workdir) / "studio_state.json"
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2,
                                   default=str), encoding="utf-8")


def _is_jsonable(v) -> bool:
    try:
        json.dumps(v, default=str)
        return True
    except Exception:
        return False


# ─── Agente base ───────────────────────────────────────────────────────────────

class Agent:
    """Subclasses definem name/requires/produces e implementam run(ctx)."""
    name:     str   = "agent"
    label:    str   = ""
    requires: tuple = ()
    produces: tuple = ()

    def run(self, ctx: JobContext) -> None:
        raise NotImplementedError

    def __call__(self, ctx: JobContext) -> bool:
        title = self.label or self.name
        print(f"\n[{self.name.upper()}] {title}")
        print("-" * 56)
        ctx.require(*self.requires)
        t0 = time.time()
        try:
            self.run(ctx)
        except Exception as e:
            elapsed = time.time() - t0
            ctx.history.append({"ts": time.time(), "agent": self.name,
                                "status": "error", "error": str(e),
                                "elapsed": round(elapsed, 1)})
            print(f"  [ERRO] {type(e).__name__}: {e}")
            traceback.print_exc()
            return False

        elapsed = time.time() - t0
        missing = [k for k in self.produces if k not in ctx.artifacts]
        if missing:
            print(f"  [AVISO] {self.name} não produziu: {missing}")
        ctx.history.append({"ts": time.time(), "agent": self.name,
                            "status": "ok", "elapsed": round(elapsed, 1)})
        ctx.snapshot()
        print(f"  ({elapsed:.1f}s)")
        return True


# ─── Orquestrador ──────────────────────────────────────────────────────────────

class Orchestrator:
    """
    Executa os agentes em ordem. Depois do QA, se qa_report.rework indicar
    agentes, re-executa apenas eles (as notas do QA chegam via inbox) e roda
    o QA de novo — até max_qa_rounds.
    """

    def __init__(self, agents: list, qa_agent: Agent = None, max_qa_rounds: int = 2,
                 critical: tuple = ()):
        self.agents        = agents
        self.qa_agent      = qa_agent
        self.max_qa_rounds = max_qa_rounds
        self.critical      = set(critical)   # agentes cuja falha aborta o job

    def run(self, ctx: JobContext) -> JobContext:
        by_name = {a.name: a for a in self.agents}

        for agent in self.agents:
            ok = agent(ctx)
            if not ok and agent.name in self.critical:
                print(f"\n[ORQUESTRADOR] Agente crítico '{agent.name}' falhou — abortando.")
                return ctx

        if not self.qa_agent:
            return ctx

        for round_n in range(1, self.max_qa_rounds + 1):
            self.qa_agent(ctx)
            report = ctx.get("qa_report", {})
            rework = report.get("rework", [])
            if not rework:
                print(f"\n[ORQUESTRADOR] QA aprovou (rodada {round_n}).")
                break
            print(f"\n[ORQUESTRADOR] QA pediu retrabalho (rodada {round_n}): "
                  f"{[r['agent'] for r in rework]}")
            for item in rework:
                target = by_name.get(item["agent"])
                if not target:
                    continue
                ctx.send("qa", target.name, item.get("note", ""))
                target(ctx)
        return ctx
