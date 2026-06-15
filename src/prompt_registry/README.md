# Extensão: Prompt Registry — versionamento e rollback

[🇧🇷 Português](#-português) · [🇺🇸 English](#-english)

Extensão do `llmops-mlflow-guardrails`. Cobre o post **C34** (rollback e
versionamento de prompts) e reforça o **A9**. Sem dependências além da stdlib +
pytest. 100% offline, LLM mockado.

---

## 🇧🇷 Português

### A tese

Um prompt é um **artefato de produção**, igual a um modelo ou a um schema de banco.
Mesmo assim, a maioria dos times edita prompt direto no código, sem versão, sem
avaliação e sem caminho de volta quando a "melhoria" quebra. Este módulo trata
prompt como artefato versionado: **versões imutáveis + um alias móvel de produção
+ avaliação antes de promover + rollback em uma chamada.**

### O ciclo demonstrado (`demo.py`, números reais)

1. Registra a **v1** (com instrução de fundamentação no contexto), avalia no golden
   set: **100%**. Promove a produção.
2. Alguém "enxuga" o prompt e cria a **v2**, removendo sem querer a instrução de
   grounding. Avaliação: **50%** — a v2 passa a alucinar nas perguntas adversariais
   (aquelas cuja resposta não está no contexto).
3. Como `acc_v2 < acc_v1`, a v2 **não é promovida**: produção segue na v1.
4. Cenário de incidente: a v2 vai para produção por engano. `rollback()` devolve a
   produção para a v1 (de volta a 100%) **sem deploy de código**.

A regressão é 100% concentrada nas perguntas adversariais — exatamente a classe de
falha que um "ajuste de estilo" no prompt costuma introduzir sem ninguém notar.
Por isso a avaliação **antes** de promover é o que transforma rollback em decisão.

### Por que o LLM é mockado

O `mock_llm` é uma função pura cujo comportamento depende do **texto do prompt**:
se o prompt instrui responder apenas com base no contexto, o modelo recusa
("NÃO SEI") perguntas sem resposta no contexto; se essa instrução some, ele
alucina. Isso isola a lição — o efeito de uma mudança de prompt na qualidade — sem
custo, sem API key e de forma 100% reprodutível. Plugue o seu LLM real
implementando a mesma assinatura.

### Equivalente em produção (MLflow Prompt Registry)

A interface aqui espelha o MLflow 3 de propósito. Em produção:

```python
import mlflow

# registra uma nova versão imutável
pv = mlflow.genai.register_prompt(name="rh_qa", template=PROMPT_V1,
                                  commit_message="versão inicial com grounding")
mlflow.genai.set_prompt_alias("rh_qa", alias="producao", version=pv.version)

# carrega pelo alias em runtime
prompt = mlflow.genai.load_prompt("prompts:/rh_qa@producao")

# rollback = reaponta o alias para a versão anterior
mlflow.genai.set_prompt_alias("rh_qa", alias="producao", version=pv.version - 1)
```

Versões imutáveis + aliases móveis = o mesmo padrão deste repo, agora com UI,
permissões e auditoria.

### Execução

```
pytest tests/ -v                         # 7 testes
python src/prompt_registry/demo.py       # o ciclo completo com rollback (~1s)
```

### Estrutura

```
src/prompt_registry/
├── registry.py   # PromptRegistry: versões imutáveis, aliases, rollback (JSON)
├── evaluate.py   # LLM mock determinístico + golden set + acurácia
├── demo.py       # o ciclo de vida com a regressão e o rollback
└── __init__.py
tests/
└── test_prompt_registry.py   # 7 invariantes (rollback, regressão, persistência)
```

---

## 🇺🇸 English

### The thesis

A prompt is a **production artifact**, like a model or a DB schema — yet most teams
edit prompts inline, with no version, no evaluation and no way back when an
"improvement" breaks. This module treats prompts as versioned artifacts: **immutable
versions + a movable production alias + evaluation before promotion + one-call
rollback.**

### The demonstrated cycle (`demo.py`, real numbers)

1. Register **v1** (with a grounding instruction), evaluate on the golden set:
   **100%**. Promote to production.
2. Someone "trims" the prompt into **v2**, accidentally dropping the grounding
   instruction. Evaluation: **50%** — v2 now hallucinates on adversarial questions
   (those whose answer is not in the context).
3. Since `acc_v2 < acc_v1`, v2 is **not promoted**; production stays on v1.
4. Incident scenario: v2 reaches production by mistake. `rollback()` returns
   production to v1 (back to 100%) **with no code deploy**.

The regression is entirely on the adversarial questions — exactly the failure class
a "style tweak" tends to sneak in. Evaluating **before** promotion is what turns
rollback into a decision instead of a guess.

### Why the LLM is mocked

`mock_llm` is a pure function whose behavior depends on the **prompt text**: with a
grounding instruction it refuses ("NÃO SEI") unanswerable questions; without it, it
hallucinates. This isolates the lesson — the effect of a prompt change on quality —
with no cost, no API key and full reproducibility. Plug your real LLM in via the
same signature.

### Production equivalent (MLflow Prompt Registry)

The interface mirrors MLflow 3 on purpose: immutable versions + movable aliases,
`register_prompt` / `load_prompt` / `set_prompt_alias`, with rollback as a re-point
of the alias to the previous version.

### Running

```
pytest tests/ -v                         # 7 tests
python src/prompt_registry/demo.py       # full cycle with rollback (~1s)
```

---

Part of my LinkedIn series on LLMOps → [Flávia Gaia](https://www.linkedin.com/in/flavia-gaia/)
