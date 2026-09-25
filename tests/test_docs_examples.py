"""The guide's examples are executable claims, so they are tested.

An agent reads this guide and copies from it. A configuration example that
loads with the budget silently unset, or a code example calling an API that
does not exist, produces a broken integration that looks finished.
"""

import ast
import pathlib
import re
import tomllib

import pytest

from cotwatcher import config

GUIDE = pathlib.Path(__file__).resolve().parents[1] / "docs" / "INTEGRATION.md"


def _blocks(lang: str) -> list[str]:
    return re.findall(rf"```{lang}\n(.*?)```", GUIDE.read_text(encoding="utf-8"), re.S)


def test_the_documented_config_loads_with_the_budget_it_shows():
    """It was documented under [judge], where the loader did not read it, so
    the example disabled the limit it was demonstrating."""
    block = _blocks("toml")[0]
    assert "judge_max_input_tokens = 48000" in block
    settings = config._from_dict(tomllib.loads(block))
    assert settings.judge_max_input_tokens == 48000


def test_the_documented_models_are_long_context_variants():
    """The stock tags are what Ollama serves at 4,096 tokens, which the same
    example's budget cannot fit inside."""
    settings = config._from_dict(tomllib.loads(_blocks("toml")[0]))
    assert settings.judge.model.endswith("-64k")
    assert settings.model.model.endswith("-32k")


@pytest.mark.parametrize("key", ["max_input_tokens", "judge_max_input_tokens"])
def test_the_budget_is_read_wherever_it_reads_naturally(key):
    settings = config._from_dict(tomllib.loads(f"[judge]\n{key} = 1234"))
    assert settings.judge_max_input_tokens == 1234


def test_every_python_example_parses():
    for block in _blocks("python"):
        ast.parse(block.replace("...", "None"))


def test_the_example_catches_a_judge_call_that_raises():
    """`judge.score()` raises on transport failure, before `score.ok` exists."""
    example = next(b for b in _blocks("python") if "judge.score" in b)
    tree = ast.parse(example.replace("...", "None"))
    calls_in_try = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Try)
        for child in ast.walk(node)
        if isinstance(child, ast.Call) and getattr(child.func, "attr", "") == "score"
    ]
    assert calls_in_try, "judge.score() must be shown inside an exception boundary"


def test_the_example_loads_configuration_rather_than_defaults():
    """`Settings()` ignores the TOML file and the environment the guide just
    told the reader to configure."""
    example = next(b for b in _blocks("python") if "make_judge" in b)
    assert "config.load()" in example
    # In the code, not in a comment: the example names Settings() to warn
    # against it, and a text search cannot tell the two apart.
    tree = ast.parse(example.replace("...", "None"))
    constructed = {getattr(node.func, "id", getattr(node.func, "attr", ""))
                   for node in ast.walk(tree) if isinstance(node, ast.Call)}
    assert "Settings" not in constructed


def test_every_command_the_guide_tells_an_agent_to_run_exists():
    from cotwatcher.cli import main
    text = GUIDE.read_text(encoding="utf-8")
    for command in set(re.findall(r"`cotwatcher (\w+)", text)):
        with pytest.raises(SystemExit) as exit_info:
            main([command, "--help"])
        assert exit_info.value.code == 0, f"cotwatcher {command} is documented but not a command"
