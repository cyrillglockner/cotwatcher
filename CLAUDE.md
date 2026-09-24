# CLAUDE.md

cotwatcher reads a model's chain of thought and asks whether it decided to pursue behaviour a rubric
describes. Reasons in `PLAN.md`, deferred work in `BACKLOG.md`, review ledger in `FINDINGS.md`.
Setup `uv pip install -e ".[dev]"` (add `[evals]`); tests `.venv/bin/pytest`.

## Scope — check before designing anything

1. **The subject is the model's internal process**: its reasoning and activations, not its answer.
2. **Never judge output.** Does this help decide whether the model was up to something, or assess how
   good the work was? The second is a different tool.
3. **The event is a decision to pursue prohibited behaviour.** Noticing an option is not it;
   following through is not required; a withdrawn decision still counts, with the reversal recorded.
4. **Confusion is not hacking; sloppiness is not deception.** A trace can look bad with no decision.
5. **Eval tasks elicit reasoning**, they are not tests the model passes. Put the bind in the
   situation: models decline announced instructions and read announced rules as tests.

Judge the model, never the user's input. Fabrication with no sign the model knew better is
hallucination, not deception.

## Invariants

- Check `Score.ok` before `scores`; an unscored chunk is never clean, and a truncated reply is not a
  verdict. Bound the judge's input: at 16k, five of six episode prompts came back unparseable.
- Exit codes 0 clean / 1 flagged / 2 incomplete. Input errors never exit 1, which means a detection.
  Partial capture keeps a run incomplete. `--threshold` must be finite in [0, 1]; NaN silences it.
- A pytest exit code is not evidence (`os._exit(0)` exits 0 with nothing run), so `run_pytest`
  requires per-phase evidence. `tests/test_templates.py` checks templates before model time.
- Episodes carry provenance; score against that snapshot, never current templates, and never pool
  across `PROTOCOL_VERSION`. Labels count only when frozen. Probe features are a replay, and
  activations measure computation, not intent.
- Ollama picks a context per model, often 4,096, truncating from the front. It bit the judge, then
  the actor. Use `qwen3:8b-32k` and `gpt-oss:20b-64k` (Modelfiles in `ollama/`).
- The pressure harness runs model-written Python: it needs `COTWATCHER_ALLOW_CODE_EXECUTION=1`, and
  the temp directory is not a sandbox. Nothing under `evals/external/` is ever committed.

## Conventions

Docs register: setup, evidence, finding; no asides, fragments or metaphors. `FINDINGS.md` reviews
update rows rather than opening rounds, and `verified-fixed` needs a named verification. Default
action on a flag is log and continue. Assert on programmatic string replacements: two silent no-ops
shipped bugs.
