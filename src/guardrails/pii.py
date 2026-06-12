"""Guardrail de PII para português brasileiro.

Detecta e mascara: CPF (com validação de dígitos verificadores,
reduzindo falso positivo de números quaisquer), CNPJ, e-mail e
telefone BR.

Princípio de segurança: PII é mascarada ANTES de o texto chegar
ao LLM e ANTES de qualquer log. O dado sensível nunca sai do
perímetro — nem para o provedor do modelo, nem para o MLflow.
"""

import re
from dataclasses import dataclass, field

_CPF_RE = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
_CNPJ_RE = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+55\s?)?(?:\(?\d{2}\)?\s?)?9?\d{4}[-\s]?\d{4}(?!\d)")


def cpf_is_valid(cpf: str) -> bool:
    """Valida os dígitos verificadores do CPF (algoritmo oficial)."""
    digits = re.sub(r"\D", "", cpf)
    if len(digits) != 11 or digits == digits[0] * 11:
        return False
    for position in (9, 10):
        weights = range(position + 1, 1, -1)
        total = sum(int(d) * w for d, w in zip(digits, weights))
        check = (total * 10) % 11 % 10
        if check != int(digits[position]):
            return False
    return True


@dataclass
class PiiFinding:
    kind: str
    masked: str


@dataclass
class PiiResult:
    text: str                       # texto já mascarado (seguro para uso/log)
    findings: list[PiiFinding] = field(default_factory=list)

    @property
    def has_pii(self) -> bool:
        return bool(self.findings)


def _mask(value: str, keep: int = 2) -> str:
    """Mantém apenas os últimos `keep` caracteres visíveis."""
    visible = value[-keep:] if keep else ""
    return "*" * max(len(value) - keep, 4) + visible


def scan_and_mask(text: str) -> PiiResult:
    """Detecta PII e devolve o texto mascarado + achados (já mascarados).

    Os achados carregam apenas a versão mascarada — nunca o valor
    original — para que possam ser logados com segurança.
    """
    findings: list[PiiFinding] = []

    def _sub(kind: str, validator=None):
        def repl(match: re.Match) -> str:
            value = match.group(0)
            if validator and not validator(value):
                return value  # número que parece CPF mas não é: não tocar
            masked = _mask(value)
            findings.append(PiiFinding(kind=kind, masked=masked))
            return f"[{kind}:{masked}]"

        return repl

    text = _CNPJ_RE.sub(_sub("CNPJ"), text)
    text = _CPF_RE.sub(_sub("CPF", validator=cpf_is_valid), text)
    text = _EMAIL_RE.sub(_sub("EMAIL"), text)
    text = _PHONE_RE.sub(_sub("TELEFONE"), text)
    return PiiResult(text=text, findings=findings)
