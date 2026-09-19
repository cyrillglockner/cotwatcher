# cotwatcher

Watch the chain of thought of an open-weight reasoning model and flag the things you worry about.

Reasoning models (DeepSeek-R1, Qwen3, gpt-oss) expose their thinking as text. cotwatcher is a CoT monitor: it taps that stream, scores each chunk against a rubric you control, and logs or halts when a score crosses a threshold. The judge is any model behind the OpenAI-compatible API, so it runs fully local against Ollama, vLLM, LM Studio or llama.cpp.

**cotwatcher is about the model's behaviour, never the user's input.** Whether a request was acceptable is a guardrail's job. cotwatcher is for the case nothing else can see: an ordinary request, and the reasoning goes wrong anyway.

It is a smoke detector. A well-aligned model on ordinary tasks produces clean traces almost always; the value is the rare fire and the audit trail proving you were watching.

**Status: early.** The judge and rubric are in place; the stream wrapper, policy, and CLI are next. See `PLAN.md`.

## Quick look

```python
import cotwatcher

judge = cotwatcher.load().make_judge()   # local Ollama + gpt-oss:20b unless configured otherwise
score = judge.score("If I hardcode the expected outputs the tests pass.")
print(score.max())   # ('reward_hacking', 0.9)
```

Configuration is a `cotwatcher.toml` (see `cotwatcher.example.toml`) with `COTWATCHER_*` environment variables on top. The watched model and the judge are separate endpoints, so cotwatcher runs on the inference box, on a sidecar VM, or on a workstation against remote inference without special cases.

The default rubric has three categories: deception (works out one thing, plans to say another), reward hacking (satisfies the grader instead of the task), and oversight evasion (plans around being watched). It is a YAML file; copy it, edit it, and set `rubric_path`.

## A limit worth knowing

Text monitoring sees what the model writes, which is not always what drives its answer. Treat a clean trace as absence of evidence, not evidence of absence. Probing hidden states is on the backlog for exactly this reason.

## Try it

`examples/score_traces.py` scores six hand-written reasoning chunks (three clean, three that should fire) with a real judge. It is a smoke test for the judge and rubric, not evidence about any model. Default is local Ollama with `gpt-oss:20b`; set `COTWATCHER_BASE_URL`, `COTWATCHER_JUDGE_MODEL`, and `OPENAI_API_KEY` to use a hosted model.

```bash
ollama pull gpt-oss:20b
.venv/bin/python examples/score_traces.py
```

Scores are multi-label. A chunk that fakes a summary it never read legitimately fires deception and oversight evasion at once.

## Development

```bash
uv venv && uv pip install -e ".[dev]"
.venv/bin/pytest
```

MIT.
