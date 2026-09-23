import json
from types import SimpleNamespace

import pytest

from cotwatcher import cli


class FakeJudge:
    """Returns a canned Score per call; no network."""

    def __init__(self, rubric, scores, error=None, raise_on=None):
        self.rubric = rubric
        self._scores, self._error, self._raise_on = scores, error, raise_on
        self._next_id = None
        self.calls = []

    def score(self, chunk, context="", task=""):
        from cotwatcher.judge import Score
        self.calls.append({"chunk": chunk, "context": context, "task": task})
        if self._raise_on and self._raise_on in ("*", self._next_id):
            raise ConnectionError("endpoint unreachable")
        return Score(scores=self._scores, rationale="because", error=self._error)


@pytest.fixture(autouse=True)
def patched(monkeypatch):
    """Replace Settings.make_judge at class level.

    Patching the instance is not enough: `settings_for()` uses
    dataclasses.replace for --rubric, which builds a fresh Settings and would
    drop an instance attribute, letting a test reach the real endpoint.
    """
    from cotwatcher import config
    holder = {}

    def make_judge(self):
        rubric = self.rubric()          # honours any --rubric override
        holder["judge"] = FakeJudge(rubric, holder.get("scores", dict.fromkeys(rubric.names, 0.0)),
                                    holder.get("error"), holder.get("raise_on"))
        return holder["judge"]

    monkeypatch.setattr(config.Settings, "make_judge", make_judge)
    monkeypatch.setattr(cli.config, "load", lambda path=None, env=None: config.Settings())
    return holder


def test_rubric_prints_every_category(capsys, patched):
    assert cli.main(["rubric"]) == 0
    out = capsys.readouterr().out
    for name in ("deception", "reward_hacking", "oversight_evasion"):
        assert f"### {name}" in out


def test_check_passes_when_the_judge_flags_the_probe_chunk(capsys, patched):
    patched["scores"] = {"deception": 0.0, "reward_hacking": 0.9, "oversight_evasion": 0.0}
    assert cli.main(["check"]) == 0
    assert "reward_hacking=0.90" in capsys.readouterr().out


def test_check_reports_an_unusable_reply(capsys, patched):
    patched["error"] = "judge returned non-JSON"
    assert cli.main(["check"]) == 2
    assert "unusable" in capsys.readouterr().out


def test_score_jsonl_flags_and_writes_results(tmp_path, capsys, patched):
    src = tmp_path / "chunks.jsonl"
    src.write_text(json.dumps({"id": "a", "reasoning": "I'll return the input unchanged.",
                               "task": "sort it", "context": "looking at tests"}) + "\n")
    patched["scores"] = {"deception": 0.0, "reward_hacking": 0.8, "oversight_evasion": 0.1}
    out = tmp_path / "res.jsonl"
    assert cli.main(["score", str(src), "-o", str(out)]) == 1     # non-zero: something was flagged
    assert "FLAG a" in capsys.readouterr().out
    rec = json.loads(out.read_text().splitlines()[0])
    assert rec["scores"]["reward_hacking"] == 0.8 and rec["error"] is None
    call = patched["judge"].calls[0]
    assert call["task"] == "sort it" and call["context"] == "looking at tests"


def test_score_clean_chunks_exit_zero(tmp_path, capsys, patched):
    src = tmp_path / "c.jsonl"
    src.write_text(json.dumps({"reasoning": "I'll implement it properly."}) + "\n")
    assert cli.main(["score", str(src)]) == 0
    assert "0 flagged" in capsys.readouterr().out


def test_score_plain_text_file_is_one_chunk(tmp_path, patched):
    src = tmp_path / "trace.txt"
    src.write_text("The tests only check length, so I'll skip the sort.")
    cli.main(["score", str(src)])
    assert len(patched["judge"].calls) == 1


def test_unscored_chunks_exit_incomplete_not_clean(tmp_path, capsys, patched):
    """A run the judge could not assess must never look like a clean run."""
    src = tmp_path / "c.jsonl"
    src.write_text(json.dumps({"reasoning": "x"}) + "\n")
    patched["error"] = "judge returned non-JSON"
    assert cli.main(["score", str(src)]) == 2
    out = capsys.readouterr().out
    assert "UNSCORED" in out and "Assessment incomplete" in out


def test_api_failure_on_one_chunk_does_not_abort_the_run(tmp_path, capsys, patched):
    src = tmp_path / "c.jsonl"
    src.write_text("\n".join(json.dumps({"id": i, "reasoning": "x"}) for i in ("a", "b")) + "\n")
    patched["raise_on"] = "a"
    assert cli.main(["score", str(src)]) == 2
    out = capsys.readouterr().out
    assert "UNSCORED" in out and "1 unscored, 1 scored" in out


def test_check_endpoint_failure_exits_incomplete(capsys, patched):
    patched["raise_on"] = "*"
    assert cli.main(["check"]) == 2
    assert "FAILED" in capsys.readouterr().out


@pytest.mark.parametrize("line,msg", [("{not json}", "not valid JSON"), ('{"id": "x"}', "no reasoning")])
def test_bad_input_is_rejected_with_a_line_number(tmp_path, line, msg, patched):
    src = tmp_path / "bad.jsonl"
    src.write_text(line + "\n")
    with pytest.raises(SystemExit) as e:
        cli.main(["score", str(src)])
    assert msg in str(e.value) and "bad.jsonl:1" in str(e.value)


def test_rubric_flag_overrides_the_config(tmp_path, capsys, patched):
    """--rubric must reach the judge, not just be parsed."""
    r = tmp_path / "mine.yaml"
    r.write_text("categories:\n  - name: silent_scope_change\n    definition: changes scope quietly\n")
    assert cli.main(["--rubric", str(r), "rubric"]) == 0
    assert "### silent_scope_change" in capsys.readouterr().out


def test_missing_rubric_file_is_rejected(tmp_path, patched):
    with pytest.raises(SystemExit) as e:
        cli.main(["--rubric", str(tmp_path / "nope.yaml"), "rubric"])
    assert "rubric not found" in str(e.value)


def test_score_uses_the_rubric_flag(tmp_path, patched):
    src = tmp_path / "c.jsonl"
    src.write_text(json.dumps({"reasoning": "x"}) + "\n")
    r = tmp_path / "mine.yaml"
    r.write_text("categories:\n  - name: only_one\n    definition: d\n")
    cli.main(["--rubric", str(r), "score", str(src)])
    assert patched["judge"].rubric.names == ("only_one",)


def test_reasoning_is_found_wherever_the_server_puts_it():
    """Ollama, vLLM/DeepSeek and <think>-tag models all expose it differently."""
    from types import SimpleNamespace as NS
    from cotwatcher.cli import reasoning_of

    assert reasoning_of(NS(reasoning="ollama style", content="a")) == "ollama style"
    assert reasoning_of(NS(reasoning=None, reasoning_content="vllm style", content="a")) == "vllm style"
    assert reasoning_of(NS(content="x", model_extra={"reasoning_content": "extra style"})) == "extra style"
    assert reasoning_of(NS(content="pre <think> tagged style </think> post")) == "tagged style"
    assert reasoning_of(NS(content="no thinking here")) == ""


def test_read_tasks_splits_on_blank_lines(tmp_path):
    from cotwatcher.cli import read_tasks
    p = tmp_path / "t.txt"
    p.write_text("first task\nwith a second line\n\nsecond task\n")
    assert read_tasks(p) == ["first task\nwith a second line", "second task"]


def test_trace_reports_responses_without_reasoning(tmp_path, capsys, patched, monkeypatch):
    """A model that shows no chain of thought must be called out, not silently recorded."""
    from types import SimpleNamespace as NS
    from cotwatcher import config

    def fake_create(**kw):
        msg = NS(reasoning="", reasoning_content="", content="just an answer", model_extra={})
        return NS(choices=[NS(message=msg, finish_reason="stop")])

    monkeypatch.setattr(config.Endpoint, "client",
                        lambda self: NS(chat=NS(completions=NS(create=fake_create))))
    tasks = tmp_path / "t.txt"; tasks.write_text("do a thing\n")
    out = tmp_path / "tr.jsonl"
    assert cli.main(["trace", str(tasks), "-o", str(out)]) == 2      # nothing usable captured
    printed = capsys.readouterr().out
    assert "NO CoT" in printed and "no chain of thought" in printed
    assert json.loads(out.read_text().splitlines()[0])["reasoning"] == ""
