import json
from types import SimpleNamespace

import pytest

from cotwatcher import cli


class FakeJudge:
    """Returns a canned Score per call; no network."""

    def __init__(self, rubric, scores, error=None):
        self.rubric = rubric
        self._scores, self._error = scores, error
        self.calls = []

    def score(self, chunk, context="", task=""):
        from cotwatcher.judge import Score
        self.calls.append({"chunk": chunk, "context": context, "task": task})
        return Score(scores=self._scores, rationale="because", error=self._error)


@pytest.fixture
def patched(monkeypatch):
    from cotwatcher import Rubric, config
    rubric = Rubric.default()
    holder = {}

    def fake_load(path=None, env=None):
        s = config.Settings()
        holder["judge"] = FakeJudge(rubric, holder.get("scores", dict.fromkeys(rubric.names, 0.0)),
                                    holder.get("error"))
        object.__setattr__(s, "make_judge", lambda: holder["judge"])
        return s

    monkeypatch.setattr(cli.config, "load", fake_load)
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
    assert cli.main(["check"]) == 1
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


def test_unscored_chunks_are_not_counted_clean(tmp_path, capsys, patched):
    src = tmp_path / "c.jsonl"
    src.write_text(json.dumps({"reasoning": "x"}) + "\n")
    patched["error"] = "judge returned non-JSON"
    assert cli.main(["score", str(src)]) == 0
    out = capsys.readouterr().out
    assert "UNSCORED" in out and "1 unscored" in out


@pytest.mark.parametrize("line,msg", [("{not json}", "not valid JSON"), ('{"id": "x"}', "no reasoning")])
def test_bad_input_is_rejected_with_a_line_number(tmp_path, line, msg, patched):
    src = tmp_path / "bad.jsonl"
    src.write_text(line + "\n")
    with pytest.raises(SystemExit) as e:
        cli.main(["score", str(src)])
    assert msg in str(e.value) and "bad.jsonl:1" in str(e.value)
