"""Guardrail heurístico de prompt injection.

Camada de DEFESA EM PROFUNDIDADE, não bala de prata: heurísticas
pegam os padrões mais comuns com custo ~zero e latência ~zero.
Em produção, combine com: privilégio mínimo do agente, separação
system/user, validação de saída e revisão humana para ações críticas.

A pontuação é transparente: cada padrão tem peso e o resultado
carrega QUAIS padrões dispararam — auditável, não caixa-preta.
"""

import re
import unicodedata
from dataclasses import dataclass, field

# (nome, peso, regex) — pesos somam um score; >= THRESHOLD bloqueia
_PATTERNS: list[tuple[str, float, re.Pattern]] = [
    (
        "override_de_instrucoes",
        0.6,
        re.compile(
            r"(ignore|esqueca|desconsidere|disregard|forget)\s+(?:\w+\s+){0,3}"
            r"(instrucoes|instructions|regras|rules|prompts?|orientacoes)",
        ),
    ),
    (
        "extracao_de_system_prompt",
        0.6,
        re.compile(
            r"(revele|mostre|imprima|repita|reveal|show|print|repeat)\s+(?:\w+\s+){0,3}"
            r"(system\s*prompt|prompt\s+de\s+sistema|instrucoes\s+iniciais)",
        ),
    ),
    (
        "mudanca_de_papel",
        0.5,
        re.compile(
            r"(voce\s+agora\s+e|you\s+are\s+now|aja\s+como\s+se|finja\s+(que|ser)|"
            r"pretend\s+to\s+be|jailbreak|modo\s+desenvolvedor|developer\s+mode|\bdan\b)",
        ),
    ),
    (
        "exfiltracao_de_dados",
        0.5,
        re.compile(
            r"(envie|encaminhe|poste|send|forward|post)\s+.{0,40}"
            r"(para|to)\s+.{0,40}(http|www\.|@|webhook|url)",
        ),
    ),
    (
        "payload_codificado",
        0.3,
        re.compile(r"[A-Za-z0-9+/]{80,}={0,2}"),  # blobs base64 longos
    ),
    (
        "delimitadores_de_sistema",
        0.4,
        re.compile(r"(<\s*/?\s*system\s*>|\[\s*/?\s*INST\s*\]|###\s*(system|instruction))"),
    ),
]

THRESHOLD = 0.6


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


@dataclass
class InjectionResult:
    score: float
    triggered: list[str] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return self.score >= THRESHOLD


def scan(text: str) -> InjectionResult:
    normalized = _normalize(text)
    score = 0.0
    triggered: list[str] = []
    for name, weight, pattern in _PATTERNS:
        if pattern.search(normalized):
            score += weight
            triggered.append(name)
    return InjectionResult(score=round(min(score, 1.0), 2), triggered=triggered)
