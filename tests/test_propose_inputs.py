"""Input compatibility, coverage and report identity for the review path.

Each of these was a way for an episode to come back looking assessed when it
was not, or for a review to attach to something it was not made about.
"""

import json

import pytest

from cotwatcher.cli import (_as_episode, _coverage_gaps, _prior_context, _read_episodes,
                            _task_text, main)


def _write(tmp_path, name, rows):
    p = tmp_path / name
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return p


# --- `cotwatcher trace` output is a valid input to `propose` -----------------

TRACE_ROW = {"id": "t1", "task": "sort a list", "reasoning": "I could hardcode the expected output.",
             "answer": "def f(): ...", "finish_reason": "stop", "capture_status": "ok"}


def test_a_trace_row_is_read_as_a_one_turn_episode():
    """`trace` writes reasoning at the top level; `propose` read only `turns`,
    so the documented capture-to-review path rejected its own capture format."""
    ep = _as_episode(dict(TRACE_ROW), 1)
    assert ep["turns"][0]["reasoning"] == TRACE_ROW["reasoning"]
    assert ep["turns"][0]["step"] == 0 and ep["id"] == "t1"


def test_a_trace_file_survives_the_reader(tmp_path):
    path = _write(tmp_path, "traces.jsonl", [{"record": "manifest"}, TRACE_ROW])
    episodes = _read_episodes(path, None)
    assert len(episodes) == 1 and episodes[0]["turns"][0]["reasoning"]


def test_an_episode_file_still_reads_as_before(tmp_path):
    ep = {"id": "e1", "turns": [{"step": 0, "reasoning": "thinking"}]}
    assert _read_episodes(_write(tmp_path, "eps.jsonl", [ep]), None) == [ep]


def test_a_row_that_is_neither_shape_is_skipped(tmp_path):
    from cotwatcher.cli import InputError
    with pytest.raises(InputError):
        _read_episodes(_write(tmp_path, "x.jsonl", [{"id": "n", "notes": "no reasoning here"}]), None)


def test_the_task_itself_is_preferred_over_its_name():
    assert _task_text({"template": "unit_price", "task": "compute a unit price"}) == "compute a unit price"
    assert _task_text({"template": "unit_price"}) == "unit_price"


# --- coverage ---------------------------------------------------------------

def test_an_episode_with_no_reasoning_is_a_gap_not_a_clean_result():
    """It produced zero judge calls and exited clean."""
    gaps = _coverage_gaps({"turns": [{"step": 0, "reasoning": ""}, {"step": 1, "reasoning": "  "}]})
    assert gaps and "nothing was assessed" in gaps[0]


def test_one_empty_turn_among_others_is_named():
    gaps = _coverage_gaps({"turns": [{"step": 0, "reasoning": "x"}, {"step": 1, "reasoning": ""}]})
    assert any("turn(s) 1" in g for g in gaps)


@pytest.mark.parametrize("reason", ["length", "content_filter"])
def test_truncated_capture_is_a_gap(reason):
    """The reasoning that mattered may be the part that was cut."""
    gaps = _coverage_gaps({"turns": [{"step": 0, "reasoning": "x", "finish_reason": reason}]})
    assert any(reason in g for g in gaps)


def test_a_capture_status_other_than_ok_is_a_gap():
    gaps = _coverage_gaps({"turns": [{"step": 0, "reasoning": "x"}], "capture_status": "truncated"})
    assert any("capture_status" in g for g in gaps)


def test_a_complete_episode_has_no_gaps():
    assert _coverage_gaps({"turns": [{"step": 0, "reasoning": "x", "finish_reason": "stop"}]}) == []


# --- context for reversals ---------------------------------------------------

def test_prior_context_is_bounded_and_ends_with_the_most_recent_turn():
    turns = [{"step": i, "reasoning": f"turn {i} " + "x" * 4000} for i in range(3)]
    prior = _prior_context(turns)
    assert len(prior) < 4000
    assert prior.rindex("turn 2") > prior.rindex("turn 1") if "turn 1" in prior else True


def test_no_earlier_turns_gives_no_context():
    assert _prior_context([]) == ""


# --- report identity ---------------------------------------------------------

EPISODE = {"id": "e1", "turns": [{"step": 0, "reasoning": "I will divide by 100 so the test passes."}]}


def _proposal(stance="commits"):
    return {"id": "e1", "summary": "unchanged summary", "schema_version": "events-v1",
            "judge": {"model": "m", "prompt_sha": "p"},
            "events": [{"category": "reward_hacking", "stance": stance,
                        "quote": "I will divide by 100 so the test passes.",
                        "rationale": "decides to satisfy the test", "turn": 0, "error": None,
                        "location": None}]}


def _report_id(tmp_path, stance, name):
    eps = _write(tmp_path, "eps.jsonl", [EPISODE])
    props = _write(tmp_path, f"prop-{name}.jsonl", [_proposal(stance)])
    out = tmp_path / f"{name}.html"
    main(["review", str(eps), "--proposals", str(props), "-o", str(out)])
    html = out.read_text(encoding="utf-8")
    payload = json.loads(html.split("const REPORT = ")[1].split(";")[0])
    return payload["report_id"], html


def test_changing_an_event_changes_the_report_identity(tmp_path):
    """The identity hashed the summaries and the filename, so a commitment
    turned into a withdrawal kept the same report id and the old confirmation
    would have applied to the new event."""
    a, _ = _report_id(tmp_path, "commits", "a")
    b, _ = _report_id(tmp_path, "withdraws", "b")
    assert a != b


def test_the_same_proposals_give_the_same_report_identity(tmp_path):
    a, _ = _report_id(tmp_path, "commits", "a")
    b, _ = _report_id(tmp_path, "commits", "b")
    assert a == b


def test_a_changed_event_does_not_keep_its_review_identity(tmp_path):
    import re
    _, ha = _report_id(tmp_path, "commits", "a")
    _, hb = _report_id(tmp_path, "withdraws", "b")
    assert set(re.findall(r'data-ev="([^"]+)"', ha)) != set(re.findall(r'data-ev="([^"]+)"', hb))


def test_the_constraint_survives_propose_and_review(tmp_path):
    """It was validated on the way in and dropped on the way out: every event
    wrote `constraint: null` while the judge had supplied one."""
    from cotwatcher.cli import _event_row
    from cotwatcher.events import DecisionEvent

    event = DecisionEvent(category="reward_hacking", stance="commits", quote="q" * 30,
                          rationale="r", constraint="the spec says a fraction")
    assert _event_row(event)["constraint"] == "the spec says a fraction"

    proposal = _proposal()
    proposal["events"][0]["constraint"] = "the spec says a fraction"
    eps = _write(tmp_path, "eps.jsonl", [EPISODE])
    props = _write(tmp_path, "prop.jsonl", [proposal])
    out = tmp_path / "r.html"
    main(["review", str(eps), "--proposals", str(props), "-o", str(out)])
    assert "the spec says a fraction" in out.read_text(encoding="utf-8")
