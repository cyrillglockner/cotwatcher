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


def test_the_declared_version_matches_the_package():
    """A manifest recording a version the code is not would misattribute every
    artifact written by it."""
    import tomllib

    import cotwatcher
    root = pathlib.Path(__file__).resolve().parents[1]
    declared = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    assert cotwatcher.__version__ == declared


def test_the_guides_are_packaged_with_the_wheel():
    """An agent that pip installs cotwatcher must be able to read the guide
    without reaching GitHub."""
    import tomllib
    root = pathlib.Path(__file__).resolve().parents[1]
    config = tomllib.loads((root / "pyproject.toml").read_text())
    included = config["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
    for source in ("docs/INTEGRATION.md", "docs/REVIEW.md"):
        assert source in included, f"{source} would not ship in the wheel"
        assert (root / source).is_file()


def test_the_readme_does_not_imply_probes_are_installed():
    """`0.1.0a2` shipped with the probe AUROC numbers under Status. Nothing in
    the package reads activations, and the numbers are a replay over saved
    text, so the paragraph has to say both."""
    readme = (GUIDE.parents[1] / "README.md").read_text(encoding="utf-8")
    paragraph = next(p for p in readme.split("\n\n") if p.startswith("Linear probes"))
    assert "not in the installed package" in paragraph
    import cotwatcher
    package = pathlib.Path(cotwatcher.__file__).parent
    names = {p.stem for p in package.rglob("*.py")}
    assert not {"probe", "probes", "activations", "probe_judge"} & names


def test_help_names_a_guide_that_exists():
    """An agent's first move is `--help`. A path printed there that is not a
    file sends it looking for documentation that appears to be missing."""
    from cotwatcher.cli import guide_paths
    for name, where in guide_paths().items():
        assert name in where
        assert where.startswith("http") or pathlib.Path(where).is_file(), where


def test_help_falls_back_to_the_url_when_no_copy_is_installed(monkeypatch, tmp_path):
    from cotwatcher import cli
    monkeypatch.setattr(cli, "__file__", str(tmp_path / "cotwatcher" / "cli.py"))
    assert all(v.startswith(cli.DOCS_URL) for v in cli.guide_paths().values())


def test_claude_md_and_agents_md_do_not_drift():
    """Agents that look for AGENTS.md and agents that load CLAUDE.md must get
    the same instructions.

    Two real files rather than a symlink: git stores a link as a blob holding
    its target's name, so a checkout without symlink support writes CLAUDE.md
    as a nine-byte file reading "AGENTS.md", and every rule in it is silently
    gone. Drift is possible here, and caught on every push instead."""
    root = GUIDE.parents[1]
    claude, agents = root / "CLAUDE.md", root / "AGENTS.md"
    assert not claude.is_symlink(), "a symlink reads as plain text where symlinks are unsupported"
    assert claude.read_text(encoding="utf-8") == agents.read_text(encoding="utf-8"), (
        "AGENTS.md and CLAUDE.md differ; copy one over the other")


def test_the_sdist_has_no_dangling_symlink():
    """CLAUDE.md is a symlink to AGENTS.md. Packaging the link without its
    target shipped a source distribution whose instructions could not be read
    at all."""
    import tomllib
    root = GUIDE.parents[1]
    include = tomllib.loads((root / "pyproject.toml").read_text())["tool"]["hatch"]["build"]["targets"]["sdist"]["include"]
    for path in root.iterdir():
        if path.is_symlink() and path.name in include:
            assert path.resolve().name in include, (
                f"{path.name} is packaged but its target {path.resolve().name} is not")
