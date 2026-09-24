# CLAUDE.md

Guidance for Claude Code working in this repository.

cotwatcher reads a model's chain of thought and asks whether the model decided
to pursue behaviour a rubric describes. Python library and CLI; an experimental
activation probe; an evaluation toolkit. Decisions and their reasons are in
`PLAN.md`, deferred work in `BACKLOG.md`, the review ledger in `FINDINGS.md`.

## Scope constraints — check before designing anything

Restated repeatedly because work kept drifting away from them.

1. **The subject is the model's internal process**: the chain of thought it
   writes, and the activations underneath. Not its answer.
2. **Never judge output.** Not code quality, not report accuracy, not whether
   the work was any good. Artifacts are context and elicitation material only.
   The test for anything new: does this help decide whether the model was up to
   something, or does it assess how good the work was? The second is a
   different tool.
3. **The event is a decision to pursue prohibited behaviour.** Noticing an
   option is not the event. Following through is not required. A decision later
   withdrawn still counts, with the reversal recorded. Without this fixed, the
   experiments drift between detecting bad outcomes, dishonest reports and
   problematic decisions.
4. **Confusion is not hacking; sloppiness is not deception.** A trace can look
   bad with no decision behind it. A model oscillating over which requirement
   applies is uncertain. A report describing an abandoned patch is careless.
   Both are 0 unless the reasoning shows a decision.
5. **Eval tasks are instruments for eliciting reasoning**, not tests the model
   passes. Build the bind into the situation, never a stated rule or a stated
   wish: a model declines an announced instruction, and an announced rule reads
   as a test.

Two further boundaries: cotwatcher judges the model, never the user's input
(ordinary tasks only, so the reasoning is the only variable); and fabrication
with no sign the model knew better is hallucination, out of scope, never a
deception positive.

## Commands

```bash
uv venv && uv pip install -e ".[dev]"    # setup; add [evals] for the experiments
.venv/bin/pytest                          # all tests
.venv/bin/pytest tests/test_judge.py -k fences
```

No linter is configured. `examples/score_traces.py` is the end-to-end check
against a real judge; run it after changing `SYSTEM_PROMPT`, the default rubric
or `parse_score`, because unit tests cannot catch a judge that stops scoring
well.

## Architecture

`src/cotwatcher/`, src layout, hatchling build.

- `rubric.py`: `Rubric` (tuple of `Category`) from YAML. `Rubric.default()`
  reads `rubrics/default.yaml`; `to_prompt()` is the text the judge sees.
  Category names are data, never referenced in code. Three categories in the
  default, deliberately; extras belong in a user's own file.
- `config.py`: `Settings` with two `Endpoint`s (`model` = watched, `judge` =
  scorer). `load()` merges defaults, `cotwatcher.toml`, then `COTWATCHER_*`
  env, later wins. `make_judge()` is the one place a client is built.
- `judge.py`: the `Judge` protocol (`score(chunk, context, task) -> Score`) is
  the seam every scorer implements; probes and trained classifiers plug in here
  without touching callers.
- `cli.py`: `check` / `rubric` / `trace` / `score`. `--config` and `--rubric`
  work before *and* after the subcommand.

### Invariants that cost something to learn

- **`Score.ok` before `scores`.** A reply that is not JSON, lacks `scores`,
  omits a category, or carries a non-finite or non-boolean value sets
  `Score.error`. An unscored chunk is never a clean chunk.
- **A truncated judge reply is not a verdict**, even when the JSON parses:
  `finish_reason` of `length` or `content_filter` sets `error`.
- **Bound the judge's input.** Episode-level prompts run 12k-24k tokens; at a
  16k context five of six came back unparseable. `max_input_tokens` refuses an
  oversized prompt rather than sending it, because a front-truncated prompt has
  lost the rubric.
- **Exit codes are a contract**: 0 assessed and clean, 1 flagged, 2 incomplete.
  Incomplete covers any unassessed chunk and any operational failure. Input and
  config errors raise `InputError` and must never exit 1, which means a
  detection.
- **Partial capture keeps a run incomplete.** A truncated chunk can be scored,
  but only part of the reasoning was captured, so `score` exits 2 even when
  clean and even when another row flags. Coverage is not a detection.
- **`trace` writes one row per task** with `capture_status` (ok / truncated /
  content_filtered / no_reasoning / api_error), including failures. A missing
  row lets a later run report a clean result over an unknown subset.
- **`--threshold` must be finite and in [0, 1].** NaN makes every comparison
  false, silently disabling all alerting while printing a clean run.
- Every model call goes through the OpenAI-compatible API. No provider SDKs.
- Tests use a `FakeClient` duck-typing `openai.OpenAI`; no network in tests.

## Experiments

Two lines, both maintained, neither folded into the other: `evals/pressure/`
(a conflict inside a system the model acts on) and `evals/disclosure/`
(single-call packets that put the model in a bind). `evals/probe/` trains
linear probes on activations.

- **`evals/pressure/harness.py` executes model-written Python on the host** and
  refuses to start without `COTWATCHER_ALLOW_CODE_EXECUTION=1`. Keep the gate,
  keep the subprocess environment minimal, and never call the temp directory a
  sandbox.
- **A pytest exit code is not evidence, and neither is a call-phase pass.**
  `os._exit(0)` gives exit 0 with nothing run; a teardown failure gives a
  call-phase pass that pytest reports as "1 passed, 1 error". `run_pytest`
  collects ids in a separate process, runs with `--report-log`, keeps
  setup/call/teardown apart, and returns `ok` only when every collected test
  passed its call phase with no failure in any phase and the process exited 0.
  Regression suite: `tests/test_harness_verdict.py`.
- **Template integrity is checked before model time** (`tests/test_templates.py`):
  the buggy code fails, a correct fix passes control and hidden, the blocked
  condition fails exactly the contradictory test, and a gaming patch passes the
  blocked visible suite while failing hidden. The fourth property caught a pair
  that no implementation could satisfy. When a contradictory input changes, pin
  its spec-correct answer in that template's hidden suite.
- **Provenance.** Every episode records the prompt, spec, tests, rules and caps
  it ran under; score and label against that snapshot, never against current
  `templates.py`. `run_id` carries `TEMPLATE_VERSION` and `PROTOCOL_VERSION`;
  bump the protocol when caps, retry policy or parsing change, because episodes
  from different protocols are different experiments and must not be pooled.
- **Manifests.** `trace`, `score` and `compare.py` each write a manifest row
  first; comparison output is timestamped, never overwritten. A verdict that
  cannot name the monitor that produced it is not evidence. Readers skip rows
  where `record == "manifest"`.
- **Labels** live in `evals/pressure/labels/*.json`, keyed by run id, and count
  only when `frozen` with an approved reviewer and an explicit 0 or 1. Null and
  missing stay unreviewed. A decision seen in a truncated trace is still a
  positive; absence in a partial trace is unknown, never clean.
- **Probe features are a replay**, not the original trajectory's hidden states:
  a fresh forward pass over saved text in a separately loaded copy, with the
  opening prompt as the only context. Activations are measurements of
  computation, not a reading of intent, and neither signal is privileged
  ground truth.
- Probe cache keys cover the prompt, context, chunk and extractor identity
  (model, revision, dtype, device, layers, tokenizer). Do not narrow it.

## Models and their traps

- **Ollama picks a context per model and machine, often 4,096, and truncates
  from the front**, discarding the system prompt. This bit the judge and then
  the actor: a 4,096-token actor filled its window and was cut off before
  reaching an action, which looked like task failure. `max_tokens` does not
  create context. `harness.py` preflights the real window and refuses to start
  when it is too small.
  Variants: `ollama create qwen3:8b-32k -f ollama/Modelfile.qwen3-8b-32k`,
  `gpt-oss:20b-64k -f ollama/Modelfile.gpt-oss-64k`.
- **Watched model**: `qwen3:8b` (Ollama) / `Qwen/Qwen3-8B` (HF, for
  activations). A watched model must pass both halves: drive the harness (R1
  distills do not; they generate to the cap instead of acting) and extract
  cheaply on MPS. **A probed model must be a plain transformer**: hybrid
  architectures have no MPS kernels and cost 50-90s per chunk against ~2s.
- **Judge**: local Ollama `gpt-oss:20b`. Hosted models are the override, never
  the default.
- Some models emit patch bodies with literal backslash-n, which lands as an
  unparseable one-line file and makes a working fix look like a failed task.
  The harness normalises those and records `truth.invalid_patch`; such an
  episode says nothing about behaviour and must not be labelled.

## Review process

`FINDINGS.md` is the ledger: every finding has a stable ID and a status, and
reviews **update rows rather than opening a new round**. A row reaches
`verified-fixed` only with a named verification — a regression test, or a
measured before/after recorded in the row. A reopened finding keeps its ID.
Report the ledger, never a closed round.

## Conventions

- **Docs register**: report style. Setup, evidence, finding. No conversational
  asides, no clipped emphatic fragments, no metaphors. State the sample size
  and let it stand.
- **Nothing under `evals/external/` is ever committed**, nor anything derived
  from it: third-party transcripts released with a training-corpus canary, in a
  public repo. Generated traces, episodes and caches are gitignored; only
  hand-labelled fixtures and frozen labels are tracked.
- Default action on a flag is log and continue; halting is opt-in.
- Assert on string replacements when editing code programmatically. Two silent
  no-ops have shipped bugs that later reviews had to find.
