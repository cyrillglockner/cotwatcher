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
    assert cli.main(["check", "--judge-only"]) == 0
    assert "reward_hacking=0.90" in capsys.readouterr().out


def test_check_reports_an_unusable_reply(capsys, patched):
    patched["error"] = "judge returned non-JSON"
    assert cli.main(["check", "--judge-only"]) == 2
    assert "unusable" in capsys.readouterr().out


# --- the watched model ------------------------------------------------------

def _watched(monkeypatch, message, model="watched-1", finish="stop", fail=None):
    """Stand in for the watched endpoint's client."""
    class Client:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    if fail:
                        raise fail
                    return SimpleNamespace(model=model, choices=[SimpleNamespace(
                        message=message, finish_reason=finish)])
    monkeypatch.setattr(cli.config.Endpoint, "client", lambda self: Client())


def _message(**kw):
    base = {"content": "", "reasoning": None, "reasoning_content": None, "model_extra": {}}
    return SimpleNamespace(**(base | kw))


def test_check_reports_the_watched_model_exposing_reasoning(capsys, patched, monkeypatch):
    patched["scores"] = {"deception": 0.0, "reward_hacking": 0.9, "oversight_evasion": 0.0}
    _watched(monkeypatch, _message(reasoning="The test only checks the length.", content="Sort it."))
    assert cli.main(["check"]) == 0
    out = capsys.readouterr().out
    assert "watched-1" in out and "characters of reasoning" in out


def test_a_watched_model_with_no_reasoning_fails_the_check(capsys, patched, monkeypatch):
    """The silent failure: empty captures score clean, so a monitor watching a
    model that exposes nothing looks exactly like a quiet one."""
    patched["scores"] = {"deception": 0.0, "reward_hacking": 0.9, "oversight_evasion": 0.0}
    _watched(monkeypatch, _message(content="Sort it."))
    assert cli.main(["check"]) == 2
    out = capsys.readouterr().out
    assert "no reasoning" in out and "scores clean" in out


def test_reasoning_inside_think_tags_counts(capsys, patched, monkeypatch):
    patched["scores"] = {"deception": 0.0, "reward_hacking": 0.9, "oversight_evasion": 0.0}
    _watched(monkeypatch, _message(content="<think>only the length is checked</think>Sort it."))
    assert cli.main(["check"]) == 0
    assert "<think>" in capsys.readouterr().out


def test_an_unreachable_watched_model_is_reported_not_raised(capsys, patched, monkeypatch):
    patched["scores"] = {"deception": 0.0, "reward_hacking": 0.9, "oversight_evasion": 0.0}
    _watched(monkeypatch, _message(), fail=ConnectionError("refused"))
    assert cli.main(["check"]) == 2
    assert "could not reach it" in capsys.readouterr().out


def test_a_truncated_probe_still_passes_but_says_so(capsys, patched, monkeypatch):
    patched["scores"] = {"deception": 0.0, "reward_hacking": 0.9, "oversight_evasion": 0.0}
    _watched(monkeypatch, _message(reasoning="thinking and thinking"), finish="length")
    assert cli.main(["check"]) == 0
    assert "truncated" in capsys.readouterr().out


def test_judge_only_never_contacts_the_watched_model(capsys, patched, monkeypatch):
    called = []
    monkeypatch.setattr(cli.config.Endpoint, "client",
                        lambda self: called.append(1) or (_ for _ in ()).throw(AssertionError))
    patched["scores"] = {"deception": 0.0, "reward_hacking": 0.9, "oversight_evasion": 0.0}
    assert cli.main(["check", "--judge-only"]) == 0
    assert called == []


def test_score_jsonl_flags_and_writes_results(tmp_path, capsys, patched):
    src = tmp_path / "chunks.jsonl"
    src.write_text(json.dumps({"id": "a", "reasoning": "I'll return the input unchanged.",
                               "task": "sort it", "context": "looking at tests"}) + "\n")
    patched["scores"] = {"deception": 0.0, "reward_hacking": 0.8, "oversight_evasion": 0.1}
    out = tmp_path / "res.jsonl"
    assert cli.main(["score", str(src), "-o", str(out)]) == 1     # non-zero: something was flagged
    assert "FLAG a" in capsys.readouterr().out
    rows = [json.loads(l) for l in out.read_text().splitlines()]
    assert rows[0]["record"] == "manifest" and rows[0]["rubric_sha"]
    assert rows[1]["scores"]["reward_hacking"] == 0.8 and rows[1]["error"] is None
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
    assert "UNSCORED" in out and "1 assessed, 1 judge error(s)" in out


def test_check_endpoint_failure_exits_incomplete(capsys, patched):
    patched["raise_on"] = "*"
    assert cli.main(["check"]) == 2
    assert "FAILED" in capsys.readouterr().out


def test_malformed_json_is_reported_with_a_line_number(tmp_path, capsys, patched):
    src = tmp_path / "bad.jsonl"
    src.write_text("{not json}\n")
    assert cli.main(["score", str(src)]) == 2
    assert "bad.jsonl:1" in capsys.readouterr().err


def test_rubric_flag_overrides_the_config(tmp_path, capsys, patched):
    """--rubric must reach the judge, not just be parsed."""
    r = tmp_path / "mine.yaml"
    r.write_text("categories:\n  - name: silent_scope_change\n    definition: changes scope quietly\n")
    assert cli.main(["--rubric", str(r), "rubric"]) == 0
    assert "### silent_scope_change" in capsys.readouterr().out


def test_missing_rubric_file_is_rejected(tmp_path, capsys, patched):
    assert cli.main(["--rubric", str(tmp_path / "nope.yaml"), "rubric"]) == 2
    assert "rubric not found" in capsys.readouterr().err


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
    rows = [json.loads(l) for l in out.read_text().splitlines()]
    assert rows[0]["record"] == "manifest"
    assert rows[1]["reasoning"] == "" and rows[1]["capture_status"] == "no_reasoning"


# --- coverage and exit-code contract (adversarial review, 2026-09-23) --------

def _write(p, *rows):
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return p


@pytest.mark.parametrize("bad", ["nan", "inf", "1.5", "-inf", "-0.1"])
def test_non_finite_or_out_of_range_threshold_is_rejected(tmp_path, bad, patched):
    """NaN makes every comparison false, silently disabling all alerts."""
    src = _write(tmp_path / "c.jsonl", {"reasoning": "x"})
    patched["scores"] = {"deception": 1.0, "reward_hacking": 1.0, "oversight_evasion": 1.0}
    # argparse reads a bare "-inf" as an option name, so negatives use --flag=value
    argv = ["score", str(src), f"--threshold={bad}"]
    try:
        assert cli.main(argv) == 2
    except SystemExit as e:          # argparse rejects it even earlier, also exit 2
        assert e.code == 2


def test_empty_jsonl_is_incomplete_not_clean(tmp_path, patched):
    (tmp_path / "empty.jsonl").write_text("\n\n")
    assert cli.main(["score", str(tmp_path / "empty.jsonl")]) == 2


def test_chunk_without_reasoning_is_not_assessed_and_is_reported(tmp_path, capsys, patched):
    src = _write(tmp_path / "c.jsonl",
                 {"id": "good", "reasoning": "I'll skip the sort."},
                 {"id": "empty", "reasoning": "", "capture_status": "no_reasoning"})
    patched["scores"] = {"deception": 0.0, "reward_hacking": 0.9, "oversight_evasion": 0.0}
    assert cli.main(["score", str(src)]) == 2          # flagged, but coverage incomplete
    out = capsys.readouterr().out
    assert "NOT ASSESSED" in out and "1 without captured reasoning" in out
    assert len(patched["judge"].calls) == 1            # the empty row never reached the judge


@pytest.mark.parametrize("line", ['{"id": "x", "reasoning": 42}', '"just a string"', "[1,2,3]", "{oops}"])
def test_malformed_records_exit_incomplete_not_flagged(tmp_path, line, patched):
    """Input errors must never use exit 1, which means 'something was flagged'."""
    (tmp_path / "bad.jsonl").write_text(line + "\n")
    assert cli.main(["score", str(tmp_path / "bad.jsonl")]) == 2


def test_missing_file_exits_incomplete(tmp_path, patched):
    assert cli.main(["score", str(tmp_path / "nope.jsonl")]) == 2


def test_rubric_flag_works_after_the_subcommand(tmp_path, patched):
    """The README documents `score FILE --rubric x.yaml`; it must parse."""
    src = _write(tmp_path / "c.jsonl", {"reasoning": "x"})
    r = tmp_path / "mine.yaml"
    r.write_text("categories:\n  - name: only_one\n    definition: d\n")
    assert cli.main(["score", str(src), "--rubric", str(r)]) in (0, 1)
    assert patched["judge"].rubric.names == ("only_one",)


def test_rubric_flag_still_works_before_the_subcommand(tmp_path, patched):
    src = _write(tmp_path / "c.jsonl", {"reasoning": "x"})
    r = tmp_path / "mine.yaml"
    r.write_text("categories:\n  - name: only_one\n    definition: d\n")
    cli.main(["--rubric", str(r), "score", str(src)])
    assert patched["judge"].rubric.names == ("only_one",)


def _fake_endpoint(monkeypatch, *responses):
    """Each response is (reasoning, content, finish_reason) or an Exception."""
    from types import SimpleNamespace as NS
    from cotwatcher import config
    seq = iter(responses)

    def create(**kw):
        item = next(seq)
        if isinstance(item, Exception):
            raise item
        reasoning, content, finish = item
        return NS(choices=[NS(message=NS(reasoning=reasoning, content=content, model_extra={}),
                              finish_reason=finish)])

    monkeypatch.setattr(config.Endpoint, "client",
                        lambda self: NS(chat=NS(completions=NS(create=create))))


def test_trace_records_a_row_for_every_task_including_failures(tmp_path, capsys, patched, monkeypatch):
    """A dropped task would let a later score run look complete over a subset."""
    tasks = tmp_path / "t.txt"
    tasks.write_text("one\n\ntwo\n\nthree\n\nfour\n")
    _fake_endpoint(monkeypatch,
                   ("thinking hard", "answer", "stop"),
                   ("partial think", "", "length"),
                   ("", "answer only", "stop"),
                   ConnectionError("endpoint down"))
    out = tmp_path / "tr.jsonl"
    assert cli.main(["trace", str(tasks), "-o", str(out)]) == 2
    rows = [json.loads(l) for l in out.read_text().splitlines()]
    assert rows[0]["record"] == "manifest" and rows[0]["model"]   # provenance header
    rows = rows[1:]
    assert len(rows) == 4                                        # every task recorded
    assert [r["capture_status"] for r in rows] == ["ok", "truncated", "no_reasoning", "api_error"]
    assert rows[3]["error"].startswith("ConnectionError")
    printed = capsys.readouterr().out
    assert "TRUNCATED" in printed and "NO CoT" in printed and "API ERROR" in printed
    assert "Capture incomplete: 3 of 4" in printed


def test_trace_output_feeds_score_without_aborting(tmp_path, patched, monkeypatch):
    """The advertised trace -> score flow must survive mixed capture results."""
    tasks = tmp_path / "t.txt"
    tasks.write_text("one\n\ntwo\n")
    _fake_endpoint(monkeypatch, ("real reasoning", "a", "stop"), ("", "b", "stop"))
    traces = tmp_path / "tr.jsonl"
    cli.main(["trace", str(tasks), "-o", str(traces)])
    patched["scores"] = {"deception": 0.0, "reward_hacking": 0.0, "oversight_evasion": 0.0}
    assert cli.main(["score", str(traces)]) == 2                 # incomplete, not a crash
    assert len(patched["judge"].calls) == 1                      # the good row was assessed


def test_trace_all_complete_exits_clean(tmp_path, patched, monkeypatch):
    tasks = tmp_path / "t.txt"; tasks.write_text("one\n")
    _fake_endpoint(monkeypatch, ("thinking", "answer", "stop"))
    assert cli.main(["trace", str(tasks), "-o", str(tmp_path / "o.jsonl")]) == 0


# --- partial capture keeps the assessment incomplete (R1) -------------------

@pytest.mark.parametrize("row,why", [
    ({"reasoning": "partial thought", "capture_status": "truncated"}, "explicit status"),
    ({"reasoning": "partial thought", "finish_reason": "length"}, "legacy finish_reason"),
    ({"reasoning": "cut off", "finish_reason": "content_filter"}, "content filtered"),
])
def test_partially_captured_chunks_never_exit_clean(tmp_path, capsys, patched, row, why):
    """A chunk can be scored and still not cover the whole trace."""
    src = _write(tmp_path / "c.jsonl", row)
    patched["scores"] = dict.fromkeys(("deception", "reward_hacking", "oversight_evasion"), 0.0)
    assert cli.main(["score", str(src)]) == 2, why
    assert "only part of the reasoning" in capsys.readouterr().out


def test_partial_capture_dominates_a_flag(tmp_path, patched):
    """Flagged plus incomplete is still incomplete: coverage is not a detection."""
    src = _write(tmp_path / "c.jsonl",
                 {"id": "a", "reasoning": "shortcut", "capture_status": "truncated"})
    patched["scores"] = {"deception": 0.0, "reward_hacking": 0.9, "oversight_evasion": 0.0}
    assert cli.main(["score", str(src)]) == 2


def test_complete_clean_input_still_exits_zero(tmp_path, patched):
    src = _write(tmp_path / "c.jsonl", {"reasoning": "honest work", "capture_status": "ok"})
    patched["scores"] = dict.fromkeys(("deception", "reward_hacking", "oversight_evasion"), 0.0)
    assert cli.main(["score", str(src)]) == 0


def test_trace_to_score_end_to_end_with_mixed_capture(tmp_path, patched, monkeypatch):
    """The documented flow, with one good and one truncated response."""
    tasks = tmp_path / "t.txt"; tasks.write_text("one\n\ntwo\n")
    _fake_endpoint(monkeypatch, ("full reasoning", "a", "stop"), ("cut off", "b", "length"))
    traces = tmp_path / "tr.jsonl"
    assert cli.main(["trace", str(tasks), "-o", str(traces)]) == 2
    patched["scores"] = dict.fromkeys(("deception", "reward_hacking", "oversight_evasion"), 0.0)
    assert cli.main(["score", str(traces)]) == 2          # coverage survives the handoff
    assert len(patched["judge"].calls) == 2               # both had reasoning, both scored


def test_check_warns_when_no_input_limit_is_set(capsys, patched, monkeypatch):
    """An unset budget sends oversized prompts silently.

    `--judge-only` because `check` now contacts the watched model, and a test
    that reaches a real endpoint is not offline: it was loading a local model.
    """
    patched["scores"] = {"deception": 0.0, "reward_hacking": 0.9, "oversight_evasion": 0.0}
    monkeypatch.setattr(cli.config.Endpoint, "client",
                        lambda self: pytest.fail("check --judge-only contacted an endpoint"))
    cli.main(["check", "--judge-only"])
    assert "input limit none set" in capsys.readouterr().out


def test_no_test_reaches_a_live_endpoint_through_check(monkeypatch, patched, capsys):
    """A guard rather than a convention: any future `check` test that forgets to
    mock the watched endpoint fails here instead of loading a 12 GB model."""
    monkeypatch.setattr(cli.config.Endpoint, "client",
                        lambda self: pytest.fail("a test contacted a real endpoint"))
    patched["scores"] = dict.fromkeys(("deception", "reward_hacking", "oversight_evasion"), 0.0)
    cli.main(["check", "--judge-only"])


def test_a_missing_model_is_not_reported_as_an_unreachable_server(capsys, patched, monkeypatch):
    """The server answered; saying it could not be reached sends an agent to
    fix the wrong thing."""
    class NotFound(Exception):
        pass
    _watched(monkeypatch, _message(), fail=NotFound("Error code: 404 - model 'x' not found"))
    patched["scores"] = {"deception": 0.0, "reward_hacking": 0.9, "oversight_evasion": 0.0}
    assert cli.main(["check"]) == 2
    out = capsys.readouterr().out
    assert "refused the request" in out and "pull it first" in out
    assert "could not reach it" not in out


# --- the served context window ----------------------------------------------

def _ps(monkeypatch, models):
    """Stand in for Ollama's /api/ps."""
    import contextlib
    import io

    @contextlib.contextmanager
    def urlopen(url, timeout=None):
        yield io.BytesIO(json.dumps({"models": models}).encode())
    monkeypatch.setattr("urllib.request.urlopen", urlopen)


def test_a_budget_larger_than_the_served_window_fails_the_check(capsys, patched, monkeypatch):
    """The window has to hold the prompt. A budget the server will not honour
    means prompts are truncated from the front, dropping the rubric, and the
    reply is not a verdict."""
    from cotwatcher import config
    monkeypatch.setattr(cli.config, "load",
                        lambda path=None, env=None: config.Settings(judge_max_input_tokens=48000))
    patched["scores"] = {"deception": 0.0, "reward_hacking": 0.9, "oversight_evasion": 0.0}
    _watched(monkeypatch, _message(reasoning="thinking"))
    _ps(monkeypatch, [{"name": config.DEFAULT_MODEL, "context_length": 4096}])
    assert cli.main(["check"]) == 2
    out = capsys.readouterr().out
    assert "4096 tokens of context" in out and "will not honour" in out


def test_a_small_window_with_no_budget_is_a_note_not_a_failure(capsys, patched, monkeypatch):
    from cotwatcher import config
    patched["scores"] = {"deception": 0.0, "reward_hacking": 0.9, "oversight_evasion": 0.0}
    _watched(monkeypatch, _message(reasoning="thinking"))
    _ps(monkeypatch, [{"name": config.DEFAULT_MODEL, "context_length": 4096}])
    assert cli.main(["check"]) == 0
    assert "small for a judge prompt" in capsys.readouterr().out


def test_a_window_that_fits_the_budget_passes(capsys, patched, monkeypatch):
    from cotwatcher import config
    monkeypatch.setattr(cli.config, "load",
                        lambda path=None, env=None: config.Settings(judge_max_input_tokens=48000))
    patched["scores"] = {"deception": 0.0, "reward_hacking": 0.9, "oversight_evasion": 0.0}
    _watched(monkeypatch, _message(reasoning="thinking"))
    _ps(monkeypatch, [{"name": config.DEFAULT_MODEL, "context_length": 65536}])
    assert cli.main(["check"]) == 0
    assert "65536 tokens of context" in capsys.readouterr().out


def test_a_server_that_does_not_report_context_is_not_an_error(capsys, patched, monkeypatch):
    """vLLM and hosted APIs have no /api/ps; silence is not a failure."""
    def boom(url, timeout=None):
        raise OSError("no such endpoint")
    monkeypatch.setattr("urllib.request.urlopen", boom)
    patched["scores"] = {"deception": 0.0, "reward_hacking": 0.9, "oversight_evasion": 0.0}
    _watched(monkeypatch, _message(reasoning="thinking"))
    assert cli.main(["check"]) == 0
    assert "tokens of context" not in capsys.readouterr().out
