from pathlib import Path

import pytest

from cotwatcher import Settings, load
from cotwatcher.config import OLLAMA_URL


def test_defaults_are_local_ollama(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # no cotwatcher.toml here
    s = load(env={})
    assert s.model.url == OLLAMA_URL and s.judge.url == OLLAMA_URL
    assert s.model.model == "gpt-oss:20b"
    assert s.judge_reasoning_effort == "low"
    assert s.rubric_path is None
    assert s.rubric().names[0] == "deception"


def test_toml_then_env_override(tmp_path):
    cfg = tmp_path / "cotwatcher.toml"
    cfg.write_text(
        '[model]\nurl = "http://gpu-box:8000/v1"\nmodel = "gpt-oss:120b"\n'
        '[judge]\nurl = "http://gpu-box:8000/v1"\n'
        'judge_reasoning_effort = "medium"\n'
    )
    s = load(cfg, env={"COTWATCHER_JUDGE_MODEL": "phi4", "COTWATCHER_JUDGE_EFFORT": "none"})
    assert s.model.url == "http://gpu-box:8000/v1"
    assert s.model.model == "gpt-oss:120b"
    assert s.judge.url == "http://gpu-box:8000/v1"
    assert s.judge.model == "phi4"          # env wins over file
    assert s.judge_reasoning_effort is None  # "none" clears it
    assert s.model.api_key == "ollama"       # untouched default survives


def test_config_env_points_at_file(tmp_path):
    cfg = tmp_path / "elsewhere.toml"
    cfg.write_text('[judge]\nurl = "https://api.openai.com/v1"\nmodel = "gpt-5-mini"\n')
    s = load(env={"COTWATCHER_CONFIG": str(cfg), "COTWATCHER_JUDGE_API_KEY": "sk-test"})
    assert s.judge.url == "https://api.openai.com/v1"
    assert s.judge.api_key == "sk-test"


def test_cwd_file_is_picked_up(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    Path("cotwatcher.toml").write_text('rubric_path = "r.yaml"\n')
    assert load(env={}).rubric_path == Path("r.yaml")


def test_bad_toml_raises(tmp_path):
    cfg = tmp_path / "cotwatcher.toml"
    cfg.write_text("[model\nurl = 1\n")
    with pytest.raises(Exception):
        load(cfg, env={})


def test_make_judge_wires_everything(tmp_path):
    rubric = tmp_path / "r.yaml"
    rubric.write_text("categories:\n  - name: only\n    definition: d\n")
    s = Settings(rubric_path=rubric, judge_reasoning_effort=None)
    j = s.make_judge()
    assert j.model == "gpt-oss:20b"
    assert j.rubric.names == ("only",)
    assert j.reasoning_effort is None
    assert str(j.client.base_url).rstrip("/") == OLLAMA_URL
