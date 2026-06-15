"""Prompt Registry offline — versionamento e rollback de prompts.

Posts C34 (rollback/versionamento de prompts) e reforço do A9.

A tese: um prompt é um ARTEFATO DE PRODUÇÃO, igual a um modelo ou a um
schema de banco. Merece versão imutável, mensagem de commit, avaliação
e um alias de "produção" que aponta para a versão vigente — e que pode
ser revertido em segundos quando uma versão nova regride.

Este registry é um arquivo JSON local (sem dependências). Espelha os
conceitos do MLflow Prompt Registry: versões imutáveis + aliases móveis.
Em produção, troque por `mlflow.genai.register_prompt` / `load_prompt`
(ver a seção MLflow no README) — a interface aqui é a mesma de propósito.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class PromptVersion:
    name: str
    version: int
    template: str
    commit_message: str
    created_at: str

    @property
    def variables(self) -> list[str]:
        """Variáveis {assim} declaradas no template."""
        return sorted(set(re.findall(r"\{(\w+)\}", self.template)))

    def render(self, **kwargs) -> str:
        faltando = set(self.variables) - set(kwargs)
        if faltando:
            raise KeyError(f"Variáveis faltando ao renderizar: {sorted(faltando)}")
        return self.template.format(**kwargs)


class PromptRegistry:
    """Registry append-only: versões são imutáveis; aliases se movem."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if self.path.exists():
            self._db = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self._db = {"versions": {}, "aliases": {}}
            self._flush()

    def _flush(self) -> None:
        self.path.write_text(json.dumps(self._db, ensure_ascii=False, indent=2), encoding="utf-8")

    # ----------------------------------------------------------- registro
    def register(self, name: str, template: str, commit_message: str) -> PromptVersion:
        """Cria uma NOVA versão imutável do prompt `name`."""
        versions = self._db["versions"].setdefault(name, [])
        version = len(versions) + 1
        pv = PromptVersion(
            name=name,
            version=version,
            template=template,
            commit_message=commit_message,
            created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        versions.append(asdict(pv))
        self._flush()
        return pv

    def get(self, name: str, version: int | None = None) -> PromptVersion:
        versions = self._db["versions"].get(name)
        if not versions:
            raise KeyError(f"Prompt '{name}' não existe")
        if version is None:
            version = len(versions)  # mais recente
        if not 1 <= version <= len(versions):
            raise KeyError(f"Versão {version} inexistente para '{name}'")
        return PromptVersion(**versions[version - 1])

    def list_versions(self, name: str) -> list[PromptVersion]:
        return [PromptVersion(**v) for v in self._db["versions"].get(name, [])]

    # ------------------------------------------------------------- aliases
    def set_alias(self, name: str, alias: str, version: int) -> None:
        """Aponta um alias (ex.: 'producao') para uma versão. O alias se MOVE."""
        self.get(name, version)  # valida
        self._db["aliases"].setdefault(name, {})[alias] = version
        self._flush()

    def get_alias_version(self, name: str, alias: str) -> int:
        try:
            return self._db["aliases"][name][alias]
        except KeyError as e:
            raise KeyError(f"Alias '{alias}' não definido para '{name}'") from e

    def get_by_alias(self, name: str, alias: str) -> PromptVersion:
        return self.get(name, self.get_alias_version(name, alias))

    # ------------------------------------------------------------ rollback
    def rollback(self, name: str, alias: str = "producao") -> PromptVersion:
        """Reverte o alias para a versão imediatamente anterior.

        Esta é a operação de incidente: a versão nova quebrou, volte a
        produção para a anterior em UMA chamada, sem reimplantar código.
        """
        atual = self.get_alias_version(name, alias)
        if atual <= 1:
            raise ValueError("Não há versão anterior para reverter")
        self.set_alias(name, alias, atual - 1)
        return self.get_by_alias(name, alias)
