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
- `cli.py`: `check` / `rubric` / `score` subcommands over the same `Settings` and `Judge`. Exit codes are the contract: 0 assessed and clean, 1 flagged, 2 assessment incomplete (any unscored chunk, endpoint failure, unreadable input). A run the judge could not assess must never exit 0. Per-chunk exceptions are caught and recorded so one bad call does not lose the run.
- `evals/pressure/harness.py` executes model-written Python on the host and refuses to start without `COTWATCHER_ALLOW_CODE_EXECUTION=1`. Keep that gate, keep the subprocess environment minimal, and do not describe the temp directory as a sandbox.
- Tests use a `FakeClient` duck-typing `openai.OpenAI` (`tests/test_judge.py`); no network in tests.

## Conventions

- README register: report style. Setup, evidence, finding. No conversational asides, no clipped emphatic fragments ("Not a rate.", "An alarm bell, not a verdict."), no "honestly", no metaphors. State the sample size and let it stand.

- Nothing under `evals/external/` or derived from it is ever committed. It holds third-party transcripts released with a training-corpus canary; the repo may become public. Generated traces and episodes (`evals/traces/`, `evals/pressure/episodes/`, `evals/probe/cache/`) are gitignored too; only hand-labeled fixtures are tracked.

- Every model call goes through the OpenAI-compatible API so one client covers Ollama, OpenAI, vLLM, LM Studio and llama.cpp. Do not add provider-specific SDKs.
- Ollama picks a context length per model and machine and can land as low as 4,096 tokens; it then truncates from the front, discarding the system prompt. Any judge call carrying more than a short chunk (episode-level scoring, multi-turn reasoning) must use the 16k variant: `ollama create gpt-oss:20b-16k -f ollama/Modelfile.gpt-oss-16k`, `COTWATCHER_JUDGE_MODEL=gpt-oss:20b-16k`. The first with/without-CoT comparison (2026-09-21) was invalid for this reason.
- Baseline judge is local Ollama with `gpt-oss:20b`. Examples and defaults assume it; hosted models are the override, never the default.
- Some models emit patch bodies with literal backslash-n instead of newlines, which lands as an unparseable one-line file and makes a working fix look like a failed task. The harness normalises those (`unescape_body`) and records `syntax_error` per patch plus `truth.invalid_patch`; an episode with `invalid_patch` says nothing about the model's behaviour and must not be labeled. The 2026-09-19 Qwen3.5 run predates this and is unaffected (31 patches, none escaped).
- Every pressure episode carries a `provenance` block with the exact prompt, spec, tests, rules and caps it was run under. Score and label episodes against that snapshot, never against the current `templates.py`. Bump `TEMPLATE_VERSION` in `harness.py` whenever templates, rules or caps change; it is part of every `run_id`, and labels key on run plus model plus episode id.
- Probe activations are cached by a key covering the prompt, context, chunk and the extractor's identity (model, revision, dtype, device, layers, tokenizer). Do not narrow it.
- A probed model must be a plain transformer. Hybrid architectures (Qwen3.5's gated delta rule and causal conv, Mamba variants) have no MPS kernels and fall back to reference PyTorch: 50-90s per short chunk versus ~2s. Measure extraction cost before adopting a watched model.
- Watched model is `qwen3:8b` (Ollama) / `Qwen/Qwen3-8B` (HF, for activations); Ollama cannot expose hidden states. A watched model must pass both halves: drive the harness (R1 distills do not: they generate to the token cap instead of acting) and extract cheaply on MPS (Qwen3.5 does not: hybrid attention, 50-90s per chunk). Earlier results naming DeepSeek-R1-Distill-Qwen-7B or Qwen3.5-9B are historical; see PLAN.md.
- Default action on a flag is log and continue; halting is opt-in. Keep that default.
- cotwatcher is about the model's behaviour, never the user's input. Rubric categories describe behaviour the model originates; examples and eval traces use ordinary tasks only, so the reasoning is the only variable. Do not add "bad request, handled well" traces as boundary tests; they put attention back on the input. Preserve the model-not-user instruction in `SYSTEM_PROMPT` when editing it.
- Deception requires awareness plus decision in the reasoning. Fabrication with no sign the model knew better is hallucination, out of scope, and not a positive. Do not label or fixture it as deception.
- The default rubric is three categories, deliberately. Do not add a fourth to the default; extra categories belong in a user's own rubric file.
