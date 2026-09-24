"""Exit codes as a real process sees them.

The other CLI tests replace `config.load`, so they cannot show what happens
when a config or rubric file is genuinely missing or malformed. These run the
installed entry point and assert on the process exit status, with no endpoint
involved: every case fails before any model call.

The contract: 0 assessed and clean, 1 flagged, 2 incomplete or operational
failure. An operational failure must never be reported as 1.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

CLI = [sys.executable, "-m", "cotwatcher.cli"]


def run(args, cwd):
    return subprocess.run(CLI + args, capture_output=True, text=True, cwd=cwd, timeout=60)


def test_missing_config_exits_incomplete(tmp_path):
    r = run(["rubric", "--config", str(tmp_path / "nope.toml")], tmp_path)
    assert r.returncode == 2 and "cannot load config" in r.stderr
    assert "Traceback" not in r.stderr


def test_malformed_toml_exits_incomplete(tmp_path):
    (tmp_path / "c.toml").write_text("[model\nbad = \n")
    r = run(["rubric", "--config", str(tmp_path / "c.toml")], tmp_path)
    assert r.returncode == 2 and "Traceback" not in r.stderr


@pytest.mark.parametrize("content", ["not: a: rubric:\n", "- just\n- a\n- list\n", ""])
def test_malformed_rubric_exits_incomplete(tmp_path, content):
    (tmp_path / "r.yaml").write_text(content)
    r = run(["rubric", "--rubric", str(tmp_path / "r.yaml")], tmp_path)
    assert r.returncode == 2 and "cannot load rubric" in r.stderr
    assert "Traceback" not in r.stderr


def test_missing_input_file_exits_incomplete(tmp_path):
    r = run(["score", str(tmp_path / "nope.jsonl")], tmp_path)
    assert r.returncode == 2 and "Traceback" not in r.stderr


def test_unwritable_output_exits_incomplete(tmp_path):
    (tmp_path / "in.jsonl").write_text(json.dumps({"reasoning": "x"}) + "\n")
    r = run(["score", str(tmp_path / "in.jsonl"), "-o", str(tmp_path / "no-such-dir" / "o.jsonl")], tmp_path)
    assert r.returncode == 2 and "Traceback" not in r.stderr


def test_bundled_rubric_prints_without_any_config(tmp_path):
    r = run(["rubric"], tmp_path)
    assert r.returncode == 0 and "### deception" in r.stdout
