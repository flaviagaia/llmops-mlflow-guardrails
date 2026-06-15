"""Avaliação offline de versões de prompt, com LLM mockado e determinístico.

Sem isto, "versionar prompt" é só guardar texto. O que torna o rollback uma
DECISÃO e não um chute é avaliar cada versão contra um golden set ANTES de
promover — e ter o número para justificar a reversão.

O LLM mock é uma função pura: a mesma versão de prompt produz sempre a mesma
resposta. Ele modela um efeito real de prompt: se o prompt INSTRUI o modelo a
responder apenas com base no contexto, o modelo recusa perguntas sem resposta
no contexto ("NÃO SEI"); se essa instrução SOME, o modelo alucina nessas
perguntas adversariais. É exatamente a classe de regressão que uma "melhoria"
de prompt costuma introduzir sem ninguém perceber.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

try:
    from .registry import PromptVersion
except ImportError:  # permite rodar como script solto (demo.py)
    from registry import PromptVersion


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


# Marcadores de uma instrução de "fundamentação no contexto" (grounding).
GROUNDING_MARKERS = ("apenas com base no contexto", "somente com base no contexto",
                     "se nao souber, responda nao sei")


@dataclass(frozen=True)
class EvalCase:
    contexto: str
    pergunta: str
    esperado: str        # resposta correta
    adversarial: bool    # True = a resposta NÃO está no contexto


def mock_llm(prompt: PromptVersion, case: EvalCase) -> str:
    """LLM determinístico cujo comportamento depende do TEXTO do prompt."""
    instrui_grounding = any(m in _norm(prompt.template) for m in GROUNDING_MARKERS)

    if not case.adversarial:
        # resposta está no contexto: qualquer prompt razoável acerta
        return case.esperado
    # pergunta adversarial: só acerta ("NÃO SEI") quem tem a instrução de grounding
    if instrui_grounding:
        return "NÃO SEI"
    return "Sim, conforme a política aplicável."  # alucinação plausível


def accuracy(prompt: PromptVersion, cases: list[EvalCase]) -> float:
    acertos = sum(_norm(mock_llm(prompt, c)) == _norm(c.esperado) for c in cases)
    return acertos / len(cases)


# Prompts de exemplo usados no demo e nos testes.
# v1 instrui fundamentação no contexto; v2 "enxuta" remove a instrução (regride).
SAMPLE_PROMPT_GROUNDED = (
    "Você é um assistente de RH. Responda à pergunta APENAS COM BASE NO CONTEXTO "
    "abaixo. Se não souber, responda NÃO SEI.\n\nContexto: {contexto}\n\nPergunta: {pergunta}"
)
SAMPLE_PROMPT_UNGROUNDED = (
    "Você é um assistente de RH prestativo e cordial. Use o contexto para ajudar.\n\n"
    "Contexto: {contexto}\n\nPergunta: {pergunta}"
)


# Golden set: metade respondível, metade adversarial (sem resposta no contexto).
GOLDEN: list[EvalCase] = [
    EvalCase("O prazo de cancelamento é de 7 dias úteis.",
             "Qual o prazo de cancelamento?", "7 dias úteis", False),
    EvalCase("O auxílio home office é de R$ 150,00 mensais.",
             "Qual o valor do auxílio home office?", "R$ 150,00 mensais", False),
    EvalCase("A senha deve ter no mínimo 14 caracteres.",
             "Qual o tamanho mínimo de senha?", "14 caracteres", False),
    EvalCase("O prazo de cancelamento é de 7 dias úteis.",
             "A empresa oferece plano de stock options?", "NÃO SEI", True),
    EvalCase("O auxílio home office é de R$ 150,00 mensais.",
             "Posso levar meu pet para o escritório?", "NÃO SEI", True),
    EvalCase("A senha deve ter no mínimo 14 caracteres.",
             "Qual o limite do cartão corporativo?", "NÃO SEI", True),
]
