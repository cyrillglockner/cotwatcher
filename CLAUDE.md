# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

cotwatcher watches the chain of thought of open-weight reasoning models and scores it against a user-editable rubric. Python library first, CLI alongside, proxy server later. Plan and decisions in `PLAN.md`, deferred work in `BACKLOG.md`. Read both before proposing architecture.

## Commands

```bash
uv venv && uv pip install -e ".[dev]"   # setup
.venv/bin/pytest                         # all tests
.venv/bin/pytest tests/test_judge.py -k fences   # one test
```

No linter or formatter is configured yet.

`examples/score_traces.py` is the end-to-end check against a real judge (local Ollama `gpt-oss:20b` by default, about 25s per call on this machine). Run it after changing `SYSTEM_PROMPT`, the default rubric, or `parse_score`; the unit tests cannot catch a judge that stops scoring well.

## Architecture

`src/cotwatcher/`, src layout, hatchling build.

- `rubric.py`: `Rubric` (tuple of `Category`) loaded from YAML. `Rubric.default()` reads `rubrics/default.yaml` via `importlib.resources`; `Rubric.to_prompt()` is the text the judge sees. Category names are data, never referenced in code.
- `config.py`: `Settings` with two `Endpoint`s (`model` = the watched reasoning model, `judge` = the scorer), each a URL + key + model name. `load()` merges defaults, `cotwatcher.toml` (cwd or `$COTWATCHER_CONFIG`), then `COTWATCHER_*` env vars, later wins. `Settings.make_judge()` is the one place an `OpenAI` client gets built; callers should go through it. `cotwatcher.example.toml` documents every key.
- `judge.py`: `Judge` protocol (`score(chunk, context, task) -> Score`) is the seam every scorer implements. `LLMJudge` is the only implementation so far: one `chat.completions` call with `response_format=json_object`, parsed by `parse_score`. A reply that is not JSON, lacks `scores`, omits a category, or gives a non-finite or non-numeric value sets `Score.error`; the placeholder scores are 0 and **callers must check `Score.ok` before reading `scores`**. An unscored chunk is never a clean chunk. Trained classifiers and activation probes plug in here later without touching callers.
- Tests use a `FakeClient` duck-typing `openai.OpenAI` (`tests/test_judge.py`); no network in tests.

## Conventions

- Nothing under `evals/external/` or derived from it is ever committed. It holds third-party transcripts released with a training-corpus canary; the repo may become public. Generated traces and episodes (`evals/traces/`, `evals/pressure/episodes/`, `evals/probe/cache/`) are gitignored too; only hand-labeled fixtures are tracked.

- Every model call goes through the OpenAI-compatible API so one client covers Ollama, OpenAI, vLLM, LM Studio and llama.cpp. Do not add provider-specific SDKs.
- Baseline judge is local Ollama with `gpt-oss:20b`. Examples and defaults assume it; hosted models are the override, never the default.
- Watched model for evals is DeepSeek-R1-Distill-Qwen-7B: `deepseek-r1:latest` on Ollama for text, the HF copy in transformers (MPS) when activations are needed. Ollama cannot expose hidden states.
- Default action on a flag is log and continue; halting is opt-in. Keep that default.
- cotwatcher is about the model's behaviour, never the user's input. Rubric categories describe behaviour the model originates; examples and eval traces use ordinary tasks only, so the reasoning is the only variable. Do not add "bad request, handled well" traces as boundary tests; they put attention back on the input. Preserve the model-not-user instruction in `SYSTEM_PROMPT` when editing it.
- Deception requires awareness plus decision in the reasoning. Fabrication with no sign the model knew better is hallucination, out of scope, and not a positive. Do not label or fixture it as deception.
- The default rubric is three categories, deliberately. Do not add a fourth to the default; extra categories belong in a user's own rubric file.
