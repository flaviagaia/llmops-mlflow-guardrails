"""Testes do Prompt Registry — cada garantia de operação vira invariante."""

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC))

from prompt_registry import (  # noqa: E402
    GOLDEN,
    SAMPLE_PROMPT_GROUNDED as PROMPT_V1,
    SAMPLE_PROMPT_UNGROUNDED as PROMPT_V2,
    PromptRegistry,
    accuracy,
)


@pytest.fixture
def reg(tmp_path):
    return PromptRegistry(tmp_path / "prompts.json")


def test_versoes_sao_incrementais_e_imutaveis(reg):
    v1 = reg.register("p", "a {x}", "primeira")
    v2 = reg.register("p", "b {x}", "segunda")
    assert (v1.version, v2.version) == (1, 2)
    # registrar de novo não altera versões antigas
    assert reg.get("p", 1).template == "a {x}"
    assert reg.get("p", 2).template == "b {x}"


def test_render_valida_variaveis(reg):
    v = reg.register("p", "Olá {nome}, {saudacao}", "c")
    assert v.variables == ["nome", "saudacao"]
    assert v.render(nome="Ana", saudacao="bom dia") == "Olá Ana, bom dia"
    with pytest.raises(KeyError):
        v.render(nome="Ana")  # falta 'saudacao'


def test_alias_se_move_e_resolve(reg):
    reg.register("p", "v1 {x}", "um")
    reg.register("p", "v2 {x}", "dois")
    reg.set_alias("p", "producao", 1)
    assert reg.get_by_alias("p", "producao").version == 1
    reg.set_alias("p", "producao", 2)
    assert reg.get_by_alias("p", "producao").version == 2


def test_rollback_volta_para_versao_anterior(reg):
    reg.register("p", "v1 {x}", "um")
    reg.register("p", "v2 {x}", "dois")
    reg.set_alias("p", "producao", 2)
    revertida = reg.rollback("p", "producao")
    assert revertida.version == 1
    assert reg.get_by_alias("p", "producao").version == 1


def test_rollback_sem_anterior_falha(reg):
    reg.register("p", "v1 {x}", "um")
    reg.set_alias("p", "producao", 1)
    with pytest.raises(ValueError):
        reg.rollback("p", "producao")


def test_avaliacao_detecta_regressao_de_prompt(reg):
    """A lição central do C34: a v2 'enxuta' regride no golden set."""
    v1 = reg.register("rh", PROMPT_V1, "com grounding")
    v2 = reg.register("rh", PROMPT_V2, "sem grounding")
    assert accuracy(v1, GOLDEN) == 1.0
    assert accuracy(v2, GOLDEN) < accuracy(v1, GOLDEN)
    # a regressão vem inteira das perguntas adversariais
    adversariais = [c for c in GOLDEN if c.adversarial]
    assert accuracy(v2, adversariais) == 0.0


def test_persistencia_em_disco(tmp_path):
    """Reabrir o registry recupera versões e aliases (é um artefato durável)."""
    path = tmp_path / "prompts.json"
    reg1 = PromptRegistry(path)
    reg1.register("p", "v1 {x}", "um")
    reg1.set_alias("p", "producao", 1)
    reg2 = PromptRegistry(path)  # reabre do disco
    assert reg2.get_by_alias("p", "producao").template == "v1 {x}"
