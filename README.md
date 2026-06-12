# LLMOps Guardrails — PII, Prompt Injection & MLflow Observability

[🇧🇷 Português](#-português) · [🇺🇸 English](#-english)

Python 3.10+ · MLflow 3 · 100% offline (LLM mockado, plugue o seu) · MIT License

---

## 🇧🇷 Português

### O problema

A maioria dos pipelines de LLM em produção loga prompts crus e responde a qualquer entrada. Isso cria dois riscos: **vazamento de PII** (para o provedor do modelo E para os próprios logs) e **prompt injection** (usuários manipulando o comportamento do sistema).

Este projeto implementa o padrão de defesa em camadas, com cada decisão rastreada no MLflow.

### Arquitetura

```
entrada do usuário
  │ 1. scan de prompt injection ──► bloqueia se score ≥ 0.6
  │ 2. mascaramento de PII      ──► o LLM nunca vê o dado original
  ▼
LLM (mock offline; contrato substituível por OpenAI/Azure/Databricks)
  │ 3. scan de PII na SAÍDA     ──► o modelo pode vazar PII do contexto
  ▼
MLflow ◄── métricas, decisões e padrões disparados — NUNCA PII crua
```

### Decisões de segurança que importam

1. **PII mascarada antes do LLM e antes do log.** O dado sensível não sai do perímetro: nem para o provedor do modelo, nem para o MLflow. O teste `test_achados_nunca_contem_valor_original` garante isso.
2. **CPF com validação de dígitos verificadores** (algoritmo oficial). Um número de pedido como `111.111.111-11` *parece* CPF mas falha na validação e não é mascarado, eliminando uma classe inteira de falsos positivos.
3. **Detecção de injection auditável, não caixa-preta.** Cada padrão tem nome e peso; o resultado carrega *quais* padrões dispararam. Normalização Unicode impede burla por acentuação ("INSTRUÇÕES" ≡ "instrucoes").
4. **Scan de PII também na saída.** Em RAG, o modelo pode reproduzir PII presente nos documentos de contexto, mesmo com entrada limpa.
5. **Honestidade sobre limites.** Heurísticas são defesa em profundidade, não bala de prata. Em produção, combine com: privilégio mínimo do agente, separação system/user, validação de saída e revisão humana para ações críticas.

### O que vai para o MLflow

Por requisição (run aninhada): `blocked`, `injection_score`, padrões disparados, contagem de PII mascarada na entrada/saída, latência e o evento completo como artifact JSON — sempre com dados já sanitizados.

Isso responde perguntas de operação: qual a taxa de bloqueio? Quais padrões mais disparam? A taxa de PII na entrada está subindo?

### Execução

```bash
pip install -r requirements.txt
pytest tests/ -v        # 11 testes de segurança
python src/main.py      # demo com 5 casos (limpo, PII, falso positivo, 2 ataques)
mlflow ui               # explore as runs em http://localhost:5000
```

### Estrutura

```
src/
├── guardrails/
│   ├── pii.py          # CPF (validado), CNPJ, e-mail, telefone + masking
│   └── injection.py    # 6 padrões com pesos, score transparente
├── pipeline.py         # orquestração das camadas + log MLflow
└── main.py             # demonstração com casos reais
tests/
└── test_guardrails.py  # inclui testes de bypass (acentos, falsos positivos)
```

---

## 🇺🇸 English

### The problem

Most production LLM pipelines log raw prompts and answer anything. That creates two risks: **PII leakage** (to the model provider AND to your own logs) and **prompt injection** (users manipulating system behavior).

This project implements layered defense, with every decision traced in MLflow.

### Architecture

```
user input
  │ 1. prompt injection scan ──► block if score ≥ 0.6
  │ 2. PII masking           ──► the LLM never sees the original data
  ▼
LLM (offline mock; contract swappable for OpenAI/Azure/Databricks)
  │ 3. PII scan on OUTPUT    ──► the model can leak PII from context
  ▼
MLflow ◄── metrics, decisions and triggered patterns — NEVER raw PII
```

### Security decisions that matter

1. **PII masked before the LLM and before logging.** Sensitive data never leaves the perimeter — not to the model provider, not to MLflow. A dedicated test enforces this invariant.
2. **CPF with check-digit validation** (official algorithm). An order number like `111.111.111-11` *looks* like a CPF but fails validation and is left untouched, removing a whole class of false positives.
3. **Auditable injection detection, not a black box.** Every pattern has a name and a weight; results carry *which* patterns fired. Unicode normalization prevents accent-based bypasses.
4. **PII scan on output too.** In RAG, the model can reproduce PII present in context documents even when the input is clean.
5. **Honest about limits.** Heuristics are defense in depth, not a silver bullet. In production, combine with least-privilege agents, system/user separation, output validation and human review for critical actions.

### What goes to MLflow

Per request (nested run): `blocked`, `injection_score`, triggered patterns, masked-PII counts for input/output, latency, and the full event as a JSON artifact — always sanitized.

### Running

```bash
pip install -r requirements.txt
pytest tests/ -v
python src/main.py
mlflow ui
```

---

Part of my LinkedIn series on LLMOps → [Flávia Gaia](https://www.linkedin.com/in/flavia-gaia/)
