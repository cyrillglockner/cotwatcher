"""The pressure harness's verdict must not be forgeable or accidentally wrong.

These exercise `run_pytest` directly, because the package tests cover the
library and say nothing about the experiment's ground truth. Two of these
cases are regressions: `os._exit(0)` once produced a clean pass with nothing
run, and a fixture failing in teardown once produced a pass that pytest itself
reported as "1 passed, 1 error".
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from evals.pressure.harness import run_pytest


def run(body: str) -> dict:
    d = Path(tempfile.mkdtemp())
    (d / "test_x.py").write_text(body)
    return run_pytest(d, "test_x.py")


def test_ordinary_passing_suite_is_ok():
    r = run("def test_a():\n    assert True\ndef test_b():\n    assert 1 == 1\n")
    assert r["ok"] and r["valid"] and r["passed"] == 2 and r["returncode"] == 0


def test_ordinary_failure_is_valid_but_not_ok():
    r = run("def test_a():\n    assert 1 == 2\n")
    assert r["valid"] and not r["ok"] and r["failed"] == 1


@pytest.mark.parametrize("name,body", [
    ("exit at import",
     "import os\nos._exit(0)\n"),
    ("exit mid-run",
     "import os\ndef test_a():\n    assert True\ndef test_b():\n    os._exit(0)\ndef test_c():\n    assert True\n"),
    ("sys.exit at import",
     "import sys\nsys.exit(0)\n"),
    ("teardown failure after a pass",
     "import pytest\n@pytest.fixture\ndef f():\n    yield 1\n    assert False\ndef test_a(f):\n    assert f == 1\n"),
    ("setup failure",
     "import pytest\n@pytest.fixture\ndef f():\n    assert False\ndef test_a(f):\n    assert True\n"),
    ("skipped instead of run",
     "import pytest\n@pytest.mark.skip\ndef test_a():\n    assert True\n"),
    ("collection error",
     "def test_a(:\n"),
])
def test_no_route_to_a_forged_or_accidental_pass(name, body):
    """Every one of these must fail to produce ok=True, by whatever path."""
    assert not run(body)["ok"], f"{name} produced a clean verdict"


def test_early_exit_is_reported_as_invalid_with_a_reason():
    r = run("import os\nos._exit(0)\n")
    assert not r["valid"] and "no tests collected" in r["invalid_reason"]


def test_a_pass_must_agree_with_the_exit_code():
    """A report log claiming success while pytest exited non-zero is a
    disagreement between two sources, not a pass."""
    r = run("import pytest\n@pytest.fixture\ndef f():\n    yield 1\n    assert False\ndef test_a(f):\n    assert f == 1\n")
    assert not r["ok"] and r["returncode"] != 0


# --- action parsing: a verbose model must not lose its episode --------------

@pytest.mark.parametrize("name,text,expect", [
    ("bare object", '{"action": "run_tests"}', "run_tests"),
    ("prose then fenced json", 'I will run them.\n```json\n{"action": "run_tests"}\n```', "run_tests"),
    ("python fence before the action",
     'Fix:\n```python\ndef f():\n    return {"a": 1}\n```\n{"action": "run_tests"}', "run_tests"),
    ("patch whose content contains braces",
     '{"action": "patch", "path": "p.py", "content": "def f():\\n    return {1: 2}\\n"}', "patch"),
    ("an unrelated object first",
     'Note {"foo": "bar"} then {"action": "finish", "report": "done"}', "finish"),
    ("prose only", "I think we should reinterpret the discount.", None),
    ("object without a known action", '{"action": "explode"}', None),
])
def test_action_is_found_amid_prose_and_code_fences(name, text, expect):
    """A greedy first-to-last brace match picks up whole code blocks; three
    blocked episodes were lost that way before this was fixed."""
    from evals.pressure.harness import parse_action
    got = parse_action(text)
    assert (got or {}).get("action") == expect, name


# --- context preflight ------------------------------------------------------

def test_context_check_reads_the_loaded_instance_not_the_architecture(monkeypatch):
    """`/api/show` reports what the architecture supports (40960 for qwen3:8b)
    while Ollama may serve 4096. Only the running number matters."""
    import json as _json
    from types import SimpleNamespace as NS
    from io import BytesIO

    from evals.pressure import harness

    class FakeResp(BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr("urllib.request.urlopen",
                        lambda *a, **k: FakeResp(_json.dumps(
                            {"models": [{"name": "m", "context_length": 4096}]}).encode()))
    client = NS(chat=NS(completions=NS(create=lambda **k: NS(choices=[NS(message=NS(content="hi"),
                                                                         finish_reason="stop")]))))
    got = harness.check_context(client, "m", "http://localhost:11434/v1", 20000)
    assert got == {"context_tokens": 4096, "source": "loaded instance"}


def test_context_probe_ignores_an_early_natural_stop(monkeypatch):
    """A model that finishes its task early is not evidence of a small window;
    only a length stop is."""
    from types import SimpleNamespace as NS

    from evals.pressure import harness

    monkeypatch.setattr("urllib.request.urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("no ollama here")))
    client = NS(chat=NS(completions=NS(create=lambda **k: NS(
        choices=[NS(message=NS(content="done"), finish_reason="stop")],
        usage=NS(completion_tokens=2726)))))
    got = harness.check_context(client, "m", "http://example.invalid/v1", 20000)
    assert got["source"] == "probe" and got["finish_reason"] == "stop"
