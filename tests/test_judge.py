import json
from types import SimpleNamespace

from cotwatcher import LLMJudge, Rubric, parse_score


class FakeClient:
    """Minimal stand-in for openai.OpenAI that returns a canned message."""

    def __init__(self, content):
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self._content = content

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        msg = SimpleNamespace(content=self._content)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def test_parse_score_fills_missing_and_clamps():
    r = Rubric.default()
    s = parse_score(json.dumps({"scores": {"deception": 1.7, "reward_hacking": -3}, "rationale": "x"}), r)
    assert s.scores == {"deception": 1.0, "reward_hacking": 0.0, "harmful_intent": 0.0, "instruction_subversion": 0.0}
    assert s.rationale == "x"
    assert s.max() == ("deception", 1.0)
    assert s.over(0.5) == {"deception": 1.0}


def test_parse_score_tolerates_fences_and_garbage():
    r = Rubric.default()
    fenced = "```json\n" + json.dumps({"scores": {"harmful_intent": "0.4"}}) + "\n```"
    assert parse_score(fenced, r).scores["harmful_intent"] == 0.4
    bad = parse_score("the model seems fine", r)
    assert set(bad.scores.values()) == {0.0}
    assert bad.raw == "the model seems fine"


def test_llm_judge_sends_rubric_and_chunk():
    client = FakeClient(json.dumps({"scores": {"reward_hacking": 0.9}, "rationale": "hardcodes answers"}))
    judge = LLMJudge(client, model="gpt-5-mini")
    s = judge.score("If I hardcode the expected outputs the tests pass.", context="Looking at the test file.")

    assert s.scores["reward_hacking"] == 0.9
    call = client.calls[0]
    assert call["model"] == "gpt-5-mini"
    assert call["response_format"] == {"type": "json_object"}
    system, user = call["messages"]
    assert "### reward_hacking" in system["content"]
    assert "hardcode the expected outputs" in user["content"]
    assert "Looking at the test file" in user["content"]
