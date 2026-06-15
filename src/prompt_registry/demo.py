"""Demo: o ciclo de vida de um prompt em produção, com rollback (~1s).

    python src/prompt_registry/demo.py

Roteiro: registramos v1 (bom), avaliamos, promovemos para produção.
Depois alguém "melhora" o prompt (v2) e remove sem querer a instrução de
fundamentação no contexto. A avaliação acusa a regressão. Fazemos rollback
da produção para a v1 em uma chamada.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from evaluate import (
    GOLDEN,
    SAMPLE_PROMPT_GROUNDED as PROMPT_V1,
    SAMPLE_PROMPT_UNGROUNDED as PROMPT_V2,
    accuracy,
)
from registry import PromptRegistry


def main() -> None:
    tmp = Path(tempfile.mkdtemp()) / "prompts.json"
    reg = PromptRegistry(tmp)

    print("=" * 64)
    print("PROMPT REGISTRY — versionamento e rollback")
    print("=" * 64)

    v1 = reg.register("rh_qa", PROMPT_V1, "versão inicial com grounding")
    acc_v1 = accuracy(v1, GOLDEN)
    reg.set_alias("rh_qa", "producao", v1.version)
    print(f"\n1) Registrada v{v1.version} — acurácia {acc_v1:.0%} — promovida a produção")

    v2 = reg.register("rh_qa", PROMPT_V2, "enxugar prompt (remove instrução redundante)")
    acc_v2 = accuracy(v2, GOLDEN)
    print(f"2) Registrada v{v2.version} — acurácia {acc_v2:.0%}")

    print("\n   Avaliação antes de promover a v2:")
    print(f"     v1 (produção atual): {acc_v1:.0%}")
    print(f"     v2 (candidata)     : {acc_v2:.0%}")

    if acc_v2 < acc_v1:
        print(f"\n3) 🚨 v2 REGRIDE {(acc_v1-acc_v2):.0%} — NÃO promover. Produção segue na v1.")
    else:
        reg.set_alias("rh_qa", "producao", v2.version)
        print("\n3) v2 não regride — promovida.")

    # cenário de incidente: imagine que a v2 foi promovida por engano
    reg.set_alias("rh_qa", "producao", v2.version)
    prod = reg.get_by_alias("rh_qa", "producao")
    print(f"\n4) Incidente: produção foi para v{prod.version} por engano "
          f"(acurácia {accuracy(prod, GOLDEN):.0%} em produção).")
    revertida = reg.rollback("rh_qa", "producao")
    print(f"   rollback() -> produção de volta na v{revertida.version} "
          f"(acurácia {accuracy(revertida, GOLDEN):.0%}). Sem deploy de código.")

    print("\n   Histórico imutável de versões:")
    for v in reg.list_versions("rh_qa"):
        print(f"     v{v.version}: {v.commit_message}")


if __name__ == "__main__":
    main()
