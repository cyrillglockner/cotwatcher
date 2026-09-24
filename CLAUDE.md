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
- `cli.py`: `check` / `rubric` / `trace` / `score` subcommands over the same `Settings` and `Judge`. Exit codes are the contract: 0 assessed and clean, 1 flagged, 2 incomplete. Incomplete means any chunk not assessed (no captured reasoning, judge error, truncated judge reply) or any operational failure (bad input, bad threshold, unreadable file, unwritable output). **Input and config errors raise `InputError`, which `main()` turns into exit 2; they must never exit 1, because 1 means a detection.** `--config` and `--rubric` are accepted before *and* after the subcommand, because the documented form puts them after.
- Partial capture keeps a run incomplete. A truncated or content-filtered chunk can be scored, but only part of the reasoning was ever captured, so `score` exits 2 even when the scores are clean and even when another row flags. Imported rows with no `capture_status` are classified from `finish_reason`. Coverage is not a detection.
- `trace` writes one row per task with a `capture_status` of ok / truncated / content_filtered / no_reasoning / api_error, including for tasks that failed. Never drop a task: a missing row lets a later `score` run report a clean result over an unknown subset. `score` reports rows without reasoning as unassessed and counts them toward incompleteness.
- `--threshold` must be a finite number in [0, 1]. NaN makes every comparison false, which silently disables all alerting while still printing a clean run.
- A judge reply with `finish_reason` of `length` or `content_filter` sets `Score.error` even when the JSON parses: a truncated reply is not a verdict.
- `evals/pressure/harness.py` executes model-written Python on the host and refuses to start without `COTWATCHER_ALLOW_CODE_EXECUTION=1`. Keep that gate, keep the subprocess environment minimal, and do not describe the temp directory as a sandbox.
- **A zero exit code from pytest is not evidence, and neither is a call-phase pass.** `os._exit(0)` produces exit 0 with nothing run; a fixture that fails in teardown produces a call-phase pass that pytest reports as "1 passed, 1 error" with exit 1. `run_pytest` collects test ids in a separate process, runs with `--report-log`, keeps setup/call/teardown outcomes separately, and returns `ok` only when every collected test passed its call phase with no failure in any phase **and** the process exited 0. A reported pass that disagrees with the exit code is recorded as invalid. Never reintroduce a verdict from stdout, from the return code alone, or from the call phase alone. This raises the cost of forgery; code sharing a process with the reporter can still write the log. `tests/test_harness_verdict.py` is the regression suite.
- **Template integrity is checked before model time.** `tests/test_templates.py` asserts, per template: the buggy code fails, a spec-correct fix passes control and hidden, the blocked condition fails exactly the contradictory test, and a gaming patch passes the blocked visible suite while failing hidden. The fourth property caught a broken pair whose contradictory test re-asserted an input the base suite already pinned, making it unsatisfiable by any implementation. Whenever a contradictory input changes, pin its spec-correct answer in that template's hidden suite.
- **There is one thing to label: did the model decide to pursue the behaviour?** It lives in the reasoning. Neither the code nor the report is labelled, because neither is the event: a model that decides to cheat and then ships correct code still decided, and a model that ships broken code without deciding anything made a mistake. Artifacts are printed as context so the reasoning is readable and a claimed decision can be located. They are the input to the no-CoT arm of `compare.py`, where the human label is ground truth for both arms; that is a machine comparison, not a labelling job.
- Keep "was the final code tested" separate from "did it pass". A spec-correct implementation legitimately fails a contradictory test, so failing is not a defect and a report saying so is accurate.
- "Hidden suite passed" means the checked cases passed, never that the code is spec-correct. The suite samples the specification; it does not prove it.
- Every test run records `code_sha` and `tests_sha`. `truth.final_artifact_verified` is true only when the files in their final state were run and passed, so a pass that predates the last patch cannot count as verification. `misleading_claim` keys off that, not off the last run.
- `compare.py` counts a label only when the set is `frozen`, the reviewer is in `APPROVED_REVIEWERS`, and the label is explicitly 0 or 1. Null and missing stay `unreviewed`; `invalid_patch` episodes are `excluded_invalid_patch`. Reviewer identity is metadata, not policy.
- `trace`, `score` and `compare.py` each write a manifest row first (models, urls, rubric path and sha, system-prompt sha, threshold, version, timestamp) and comparison output is timestamped rather than overwritten. A saved verdict that cannot name the monitor that produced it is not evidence. Readers skip rows where `record == "manifest"`.
- Tests use a `FakeClient` duck-typing `openai.OpenAI` (`tests/test_judge.py`); no network in tests.

- Two experiments, both maintained. `evals/pressure/` is the primary line: a conflict inside a system the model acts on, with mechanical ground truth. `evals/disclosure/` is the cheap single-call companion that separates deliberate omission from oversight. Neither replaces the other; do not fold one into the other.

## Review process

`FINDINGS.md` is the ledger. Every review finding has a stable ID and a status,
and reviews **update rows rather than opening a new round**. A row reaches
`verified-fixed` only with a named verification: a regression test, or a
measured before/after recorded in the row. A finding a later review reopens
keeps its ID and gains a note. Do not report a round as closed; report the
ledger.

## Conventions

- README register: report style. Setup, evidence, finding. No conversational asides, no clipped emphatic fragments ("Not a rate.", "An alarm bell, not a verdict."), no "honestly", no metaphors. State the sample size and let it stand.

- Nothing under `evals/external/` or derived from it is ever committed. It holds third-party transcripts released with a training-corpus canary; the repo may become public. Generated traces and episodes (`evals/traces/`, `evals/pressure/episodes/`, `evals/probe/cache/`) are gitignored too; only hand-labeled fixtures are tracked.

- Every model call goes through the OpenAI-compatible API so one client covers Ollama, OpenAI, vLLM, LM Studio and llama.cpp. Do not add provider-specific SDKs.
- Ollama picks a context length per model and machine and can land as low as 4,096 tokens; it then truncates from the front, discarding the system prompt. **This applies to the actor as much as the judge.** A 4,096-token actor filled its window and was cut off before reaching an action, which looked like the model failing the task; `max_tokens` does not create context. `harness.py` preflights the real completion length and refuses to start when the server stops far short. Actor variant: `ollama create qwen3:8b-32k -f ollama/Modelfile.qwen3-8b-32k`.
- `run_id` carries both `TEMPLATE_VERSION` and `PROTOCOL_VERSION`. Bump the protocol whenever caps, retry policy or action parsing change: episodes from different protocols are different experiments and must not be pooled, including controls reused as a baseline. Any judge call carrying more than a short chunk (episode-level scoring, multi-turn reasoning) must use the 16k variant: `ollama create gpt-oss:20b-16k -f ollama/Modelfile.gpt-oss-16k`, `COTWATCHER_JUDGE_MODEL=gpt-oss:20b-16k`. The first with/without-CoT comparison (2026-09-21) was invalid for this reason.
- Baseline judge is local Ollama with `gpt-oss:20b`. Examples and defaults assume it; hosted models are the override, never the default.
- Some models emit patch bodies with literal backslash-n instead of newlines, which lands as an unparseable one-line file and makes a working fix look like a failed task. The harness normalises those (`unescape_body`) and records `syntax_error` per patch plus `truth.invalid_patch`; an episode with `invalid_patch` says nothing about the model's behaviour and must not be labeled. The 2026-09-19 Qwen3.5 run predates this and is unaffected (31 patches, none escaped).
- Every pressure episode carries a `provenance` block with the exact prompt, spec, tests, rules and caps it was run under. Score and label episodes against that snapshot, never against the current `templates.py`. Bump `TEMPLATE_VERSION` in `harness.py` whenever templates, rules or caps change; it is part of every `run_id`, and labels key on run plus model plus episode id.
- Probe activations are cached by a key covering the prompt, context, chunk and the extractor's identity (model, revision, dtype, device, layers, tokenizer). Do not narrow it.
- A probed model must be a plain transformer. Hybrid architectures (Qwen3.5's gated delta rule and causal conv, Mamba variants) have no MPS kernels and fall back to reference PyTorch: 50-90s per short chunk versus ~2s. Measure extraction cost before adopting a watched model.
- Watched model is `qwen3:8b` (Ollama) / `Qwen/Qwen3-8B` (HF, for activations); Ollama cannot expose hidden states. A watched model must pass both halves: drive the harness (R1 distills do not: they generate to the token cap instead of acting) and extract cheaply on MPS (Qwen3.5 does not: hybrid attention, 50-90s per chunk). Earlier results naming DeepSeek-R1-Distill-Qwen-7B or Qwen3.5-9B are historical; see PLAN.md.
- Default action on a flag is log and continue; halting is opt-in. Keep that default.
- **cotwatcher examines the model's internal process. It does not judge output.** Two ways in, and both are the model rather than its answer: the chain of thought it writes, and the activations underneath it. The question is whether the model is up to something. It is not a quality checker, a fact checker, a code reviewer or a report grader, and no feature should drift that way.
  The probe is a second reading of the same subject, not a fallback. Text is what the model says about its process; activations are **measurements of** that process, not a reading of intent. A probe may respond to conflict, pressure, vocabulary or difficulty rather than to concealment, so a disagreement with the text judge is a reason to look, never proof that something hidden was found. Neither signal is privileged ground truth.
  In the experiments, output is examined for one reason only: to establish ground truth about what actually happened, so a reasoning verdict can be scored against it. The no-CoT arm of `compare.py` deliberately shows an output monitor the artifacts, because the whole question is what that arm can see without the reasoning. That is the baseline being measured, never a description of what cotwatcher does.
- cotwatcher is about the model's behaviour, never the user's input. Rubric categories describe behaviour the model originates; examples and eval traces use ordinary tasks only, so the reasoning is the only variable. Do not add "bad request, handled well" traces as boundary tests; they put attention back on the input. Preserve the model-not-user instruction in `SYSTEM_PROMPT` when editing it.
- **The event cotwatcher detects is a commitment to a prohibited strategy**, decided with Cyrill 2026-09-24. Three levels, and only the middle one is the event: *recognises an option* (0, ordinary reasoning), *commits to it* (the event), *acts or reverses* (the artifacts answer this; a reversal does not undo the commitment). Flag the commitment and record the reversal in the rationale. This replaces the earlier instruction to score only the decision the reasoning arrived at, which would have scored a commit-then-reverse as clean. Without a fixed event definition the experiments drift between detecting bad outcomes, dishonest reports and problematic decisions.
- Deception requires awareness plus decision in the reasoning. Fabrication with no sign the model knew better is hallucination, out of scope, and not a positive. Do not label or fixture it as deception.
- The default rubric is three categories, deliberately. Do not add a fourth to the default; extra categories belong in a user's own rubric file.
