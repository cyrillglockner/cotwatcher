# cotwatcher

Watch the chain of thought of an open-weight reasoning model and flag the things you worry about.

Reasoning models (DeepSeek-R1, Qwen3, gpt-oss) expose their thinking as text. cotwatcher taps that stream, scores each chunk against a rubric you control, and logs or halts when a score crosses a threshold. The judge is any model behind the OpenAI-compatible API, so it runs fully local against vLLM, Ollama, LM Studio or llama.cpp.

**Status: early.** The judge and rubric are in place; the stream wrapper, policy, and CLI are next. See `PLAN.md`.

## Quick look

```python
from openai import OpenAI
from cotwatcher import LLMJudge, Rubric

judge = LLMJudge(OpenAI(base_url="http://localhost:11434/v1", api_key="ollama"), model="gpt-oss:20b")
score = judge.score("If I hardcode the expected outputs the tests pass.")
print(score.max())   # ('reward_hacking', 0.9)
```

The default rubric covers deception, reward hacking, harmful intent, and instruction subversion. It is a YAML file; copy it, edit it, and pass `Rubric.load("mine.yaml")`.

## A limit worth knowing

Text monitoring sees what the model writes, which is not always what drives its answer. Treat a clean trace as absence of evidence, not evidence of absence. Probing hidden states is on the backlog for exactly this reason.

## Try it

`examples/score_traces.py` scores six canned reasoning chunks (two clean, four that should fire) with a real judge. Default is local Ollama with `gpt-oss:20b`; set `COTWATCHER_BASE_URL`, `COTWATCHER_JUDGE_MODEL`, and `OPENAI_API_KEY` to use a hosted model.

```bash
ollama pull gpt-oss:20b
.venv/bin/python examples/score_traces.py
```

Scores are multi-label. A chunk that hides harmful content in a story legitimately fires harmful intent, deception, and instruction subversion at once.

## Development

```bash
uv venv && uv pip install -e ".[dev]"
.venv/bin/pytest
```

MIT.
