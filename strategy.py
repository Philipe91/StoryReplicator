#!/usr/bin/env python3
"""
StoryReplicator STRATEGY — caixa de ferramentas de estratégia de canal.

8 consultores de YouTube rodando no cérebro do sistema (Ollama/Groq/Gemini —
o que estiver configurado, sempre grátis):

  python strategy.py                                  → lista as ferramentas
  python strategy.py nicho --sobre "história e mistérios" --formato FACELESS
                           --horas 10 --objetivo MONETIZACAO
  python strategy.py ideias --nicho "documentários dark" --publico "homens 18-34"
                            --formato narracao --nivel NOVO
  python strategy.py titulo --tema "farol de alexandria" --publico "curiosos"
                            --nicho historia --emocao CURIOSIDADE

Parâmetros não informados são perguntados interativamente.
Resultado salvo em strategy_output/<ferramenta>_<data>.md
"""

import argparse
import sys
import time
from pathlib import Path

from studio.prompts_youtube import TOOLS


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        print("FERRAMENTAS:")
        for name, tool in TOOLS.items():
            print(f"  {name:<12} {tool['descricao']}")
        return

    tool_name = sys.argv[1].lower()
    if tool_name not in TOOLS:
        raise SystemExit(f"Ferramenta '{tool_name}' não existe. "
                         f"Opções: {', '.join(TOOLS)}")
    tool = TOOLS[tool_name]

    parser = argparse.ArgumentParser(prog=f"strategy.py {tool_name}",
                                     description=tool["descricao"])
    for param, help_txt in tool["params"].items():
        parser.add_argument(f"--{param}", default=None, help=help_txt)
    args = parser.parse_args(sys.argv[2:])

    # Preenche parâmetros faltantes interativamente
    values = {}
    for param, help_txt in tool["params"].items():
        v = getattr(args, param)
        if not v:
            v = input(f"{help_txt}: ").strip() or "não informado"
        values[param] = v

    from modules.llm_client import any_available, ask
    if not any_available():
        raise SystemExit("Nenhum provider de IA disponível (Ollama parado? "
                         "sem chaves?). Veja studio.py --help.")

    prompt = tool["prompt"].format(**values)
    print(f"\n[{tool_name.upper()}] consultando a IA...\n" + "=" * 60)
    result = ask(prompt, max_tokens=4000)
    print(result)

    out_dir = Path(__file__).parent / "strategy_output"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{tool_name}_{time.strftime('%Y%m%d_%H%M')}.md"
    header = "\n".join(f"- **{k}**: {v}" for k, v in values.items())
    out.write_text(f"# {tool['descricao']}\n\n{header}\n\n---\n\n{result}\n",
                   encoding="utf-8")
    print("=" * 60 + f"\nSalvo em: {out}")


if __name__ == "__main__":
    main()
