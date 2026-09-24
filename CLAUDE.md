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

## Traps no test catches

- **Ollama picks a context per model, often 4,096, and truncates from the front**, discarding the
  system prompt. It bit the judge, then the actor. Use `qwen3:8b-32k` and `gpt-oss:20b-64k`
  (Modelfiles in `ollama/`), and set `judge_max_input_tokens`: it defaults to off, so an oversized
  prompt is sent silently. At 16k, five of six episode prompts came back unparseable.
- **Never pool episodes across `PROTOCOL_VERSION`**, including controls reused as a baseline: caps,
  retry policy and parsing changes make them different experiments.
- **Probe features are a replay** over saved text, not the original hidden states.

Everything else worth knowing is enforced by tests. If a rule can be a test, write the test instead.

## Conventions

Docs register: setup, evidence, finding; no asides, fragments or metaphors. `FINDINGS.md` reviews
update rows rather than opening rounds, and `verified-fixed` needs a named verification. Default
action on a flag is log and continue. Assert on programmatic string replacements: two silent no-ops
shipped bugs.
