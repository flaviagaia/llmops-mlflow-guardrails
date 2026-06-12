"""Pipeline com guardrails + observabilidade MLflow.

Fluxo por requisição:

    entrada do usuário
      1. scan de prompt injection  → bloqueia se score >= threshold
      2. mascaramento de PII       → o LLM nunca vê o dado original
      3. chamada do LLM            → mock offline (ou plugue o seu)
      4. scan de PII na SAÍDA      → o modelo pode vazar PII do contexto
      5. log estruturado no MLflow → métricas e eventos, nunca PII crua

O que vai para o MLflow: decisões, scores, padrões disparados e
versões de PII já mascaradas. O que NUNCA vai: o dado sensível.
"""

import time
from dataclasses import asdict, dataclass

import mlflow

from guardrails import injection, pii


@dataclass
class PipelineResult:
    answer: str | None
    blocked: bool
    block_reason: str | None
    injection_score: float
    injection_patterns: list[str]
    pii_in_masked: int
    pii_out_masked: int
    latency_ms: float


class MockLLM:
    """LLM determinístico para demonstração offline.

    Substitua por qualquer cliente real (OpenAI, Azure, Databricks)
    mantendo o contrato: complete(prompt) -> str.
    """

    def complete(self, prompt: str) -> str:
        return (
            "Resposta simulada com base no contexto fornecido. "
            f"(prompt com {len(prompt)} caracteres processado)"
        )


def guarded_invoke(user_input: str, llm=None) -> PipelineResult:
    llm = llm or MockLLM()
    start = time.perf_counter()

    # 1. Prompt injection na entrada
    inj = injection.scan(user_input)
    if inj.blocked:
        result = PipelineResult(
            answer=None,
            blocked=True,
            block_reason="prompt_injection",
            injection_score=inj.score,
            injection_patterns=inj.triggered,
            pii_in_masked=0,
            pii_out_masked=0,
            latency_ms=(time.perf_counter() - start) * 1000,
        )
        _log_to_mlflow(user_input_masked="[bloqueado antes do processamento]", result=result)
        return result

    # 2. PII na entrada: mascarar ANTES do LLM
    pii_in = pii.scan_and_mask(user_input)

    # 3. Chamada do modelo com texto já sanitizado
    raw_answer = llm.complete(pii_in.text)

    # 4. PII na saída: o modelo pode reproduzir dados do contexto
    pii_out = pii.scan_and_mask(raw_answer)

    result = PipelineResult(
        answer=pii_out.text,
        blocked=False,
        block_reason=None,
        injection_score=inj.score,
        injection_patterns=inj.triggered,
        pii_in_masked=len(pii_in.findings),
        pii_out_masked=len(pii_out.findings),
        latency_ms=(time.perf_counter() - start) * 1000,
    )
    _log_to_mlflow(user_input_masked=pii_in.text, result=result)
    return result


def _log_to_mlflow(user_input_masked: str, result: PipelineResult) -> None:
    """Loga o evento como run aninhada. Apenas dados já sanitizados."""
    with mlflow.start_run(nested=True, run_name="guarded_request"):
        mlflow.log_metrics(
            {
                "blocked": int(result.blocked),
                "injection_score": result.injection_score,
                "pii_in_masked": result.pii_in_masked,
                "pii_out_masked": result.pii_out_masked,
                "latency_ms": round(result.latency_ms, 2),
            }
        )
        mlflow.log_params(
            {
                "block_reason": result.block_reason or "none",
                "injection_patterns": ",".join(result.injection_patterns) or "none",
            }
        )
        mlflow.log_dict(
            {"input_masked": user_input_masked, **asdict(result)},
            "event.json",
        )
