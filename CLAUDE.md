# CLAUDE.md

cotwatcher reads a model's chain of thought and asks whether it decided to
pursue behaviour a rubric describes. Reasons in `PLAN.md`, deferred work in
`BACKLOG.md`, review ledger in `FINDINGS.md`.

## Scope — check before designing anything

1. **The subject is the model's internal process**: its reasoning and its
   activations. Not its answer.
2. **Never judge output.** Not code quality, not report accuracy. The test for
   anything new: does it help decide whether the model was up to something, or
   assess how good the work was? The second is a different tool.
3. **The event is a decision to pursue prohibited behaviour.** Noticing an
   option is not it. Following through is not required. A withdrawn decision
   still counts, with the reversal recorded.
4. **Confusion is not hacking; sloppiness is not deception.** A trace can look
   bad with no decision behind it.
5. **Eval tasks elicit reasoning**, they are not tests the model passes. Put
   the bind in the situation, never in a stated rule or wish: models decline
   announced instructions and read announced rules as tests.

Also: judge the model, never the user's input. Fabrication with no sign the
model knew better is hallucination, not deception.

## Commands

```bash
uv venv && uv pip install -e ".[dev]"    # add [evals] for the experiments
.venv/bin/pytest
```

`examples/score_traces.py` is the end-to-end check against a real judge. Run it
after changing `SYSTEM_PROMPT`, the default rubric or `parse_score`.

## Architecture

`src/cotwatcher/`: `rubric.py` (YAML, category names are data), `config.py`
(two endpoints; `make_judge()` is the only place a client is built), `judge.py`
(the `Judge` protocol is the seam probes plug into), `cli.py` (`check` /
`rubric` / `trace` / `score`; flags work before and after the subcommand).

Invariants that cost something to learn:

- **Check `Score.ok` before `scores`.** Malformed replies set `error`; an
  unscored chunk is never clean. A reply truncated at the token limit is not a
  verdict even when its JSON parses.
- **Bound the judge's input.** Episode prompts run 12k-24k tokens; at 16k, five
  of six came back unparseable. An oversized prompt is refused, not sent.
- **Exit codes**: 0 clean, 1 flagged, 2 incomplete. Input errors raise
  `InputError` and must never exit 1, which means a detection.
- **Partial capture keeps a run incomplete**, even when scores are clean.
  Coverage is not a detection. `trace` writes one row per task, failures
  included, with a `capture_status`.
- **`--threshold` must be finite and in [0, 1].** NaN disables all alerting
  while printing a clean run.
- OpenAI-compatible API only, no provider SDKs. No network in tests.

## Experiments

`evals/pressure/` (conflict inside a system the model acts on) and
`evals/disclosure/` (single-call binds) are both maintained; neither folds into
the other. `evals/probe/` trains linear probes.

- **The harness executes model-written Python on the host.** It refuses to
  start without `COTWATCHER_ALLOW_CODE_EXECUTION=1`. Never call the temp
  directory a sandbox.
- **A pytest exit code is not evidence**, nor is a call-phase pass:
  `os._exit(0)` exits 0 with nothing run, and a teardown failure reports "1
  passed, 1 error". `run_pytest` collects ids separately, uses `--report-log`,
  keeps phases apart, and requires exit 0. See `tests/test_harness_verdict.py`.
- **Templates are checked before model time** (`tests/test_templates.py`),
  including that a gaming patch passes the visible suite and fails the hidden
  one. When a contradictory input changes, pin its spec-correct answer in that
  template's hidden suite.
- **Provenance**: episodes record what they ran under; score against that
  snapshot. `run_id` carries `TEMPLATE_VERSION` and `PROTOCOL_VERSION` — bump
  the protocol when caps, retries or parsing change, and never pool across
  them. `trace`, `score` and `compare.py` write manifest rows; comparison
  output is timestamped, never overwritten.
- **Labels** live in `labels/*.json`, keyed by run id, counting only when
  frozen with an explicit 0 or 1. A decision seen in a truncated trace is a
  positive; absence in one is unknown, never clean.
- **Probe features are a replay**, not the original hidden states. Activations
  measure computation, not intent; neither signal is privileged ground truth.
  Cache keys cover prompt, context, chunk and extractor identity.

## Models and their traps

- **Ollama picks a context per model, often 4,096, and truncates from the
  front**, discarding the system prompt. It bit the judge, then the actor: a
  4k actor was cut off before it could act, which looked like task failure.
  `max_tokens` does not create context. `harness.py` preflights the window.
  Variants: `qwen3:8b-32k`, `gpt-oss:20b-64k` (Modelfiles in `ollama/`).
- **Watched**: `qwen3:8b` / `Qwen/Qwen3-8B`. It must both drive the harness (R1
  distills do not; they generate to the cap instead of acting) and extract
  cheaply, which needs a plain transformer — hybrids cost 50-90s per chunk
  against ~2s. **Judge**: `gpt-oss:20b` local; hosted is the override.
- Some models emit patch bodies with literal backslash-n, landing as an
  unparseable file. Those episodes carry `truth.invalid_patch` and must not be
  labelled.

## Review process

`FINDINGS.md` is the ledger. Reviews **update rows, they do not open rounds**.
`verified-fixed` needs a named verification: a regression test or a measured
before/after. A reopened finding keeps its ID. Report the ledger, never a
closed round.

## Conventions

- **Docs register**: setup, evidence, finding. No conversational asides, no
  emphatic fragments, no metaphors. State the sample size and stop.
- **Nothing under `evals/external/` is ever committed**, nor derived from it:
  canaried third-party transcripts in a public repo. Generated data is
  gitignored; only hand-labelled fixtures and frozen labels are tracked.
- Default action on a flag is log and continue; halting is opt-in.
- Assert on programmatic string replacements. Two silent no-ops shipped bugs.
