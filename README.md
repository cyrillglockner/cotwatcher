# cotwatcher

**You are running an open-weight reasoning model. Is it deciding to do something you would not want?**

cotwatcher looks at what the model is doing internally rather than at its answer: the chain of thought it writes, and, experimentally, the activations underneath. It scores that against a rubric you control, using any OpenAI-compatible endpoint, so everything runs locally and no reasoning leaves your machine.

```bash
pip install cotwatcher
ollama pull gpt-oss:20b && ollama pull qwen3:8b     # judge, and a model to watch

cotwatcher check                                     # verify the endpoint and rubric
cotwatcher trace tasks.txt -o traces.jsonl           # run your model, capture its reasoning
cotwatcher score traces.jsonl --rubric mine.yaml     # score it
```

Needs Python 3.11+ and a running model server. Ollama is the shortest path and the default; vLLM, LM Studio, llama.cpp and hosted APIs work the same way.

**What installs today:** capturing and scoring saved traces offline, and reviewing what the judge proposed. `cotwatcher propose` asks for decision events quoted from the reasoning, `cotwatcher review` verifies each quote against the source and renders one HTML page to confirm or reject them: [docs/REVIEW.md](docs/REVIEW.md). **Wiring it into a running application** means writing the capture yourself against the judge API; the guide for that, written for a coding agent, is [docs/INTEGRATION.md](docs/INTEGRATION.md). **Not built:** a `watch()` wrapper, a proxy, enforcing a policy or halting a generation. cotwatcher logs for review; it does not gate.

## What it looks for

A **decision to pursue prohibited behaviour**. Noticing an option and declining it is ordinary reasoning. Following through is not required — a decision the model later withdraws still counts, with the reversal recorded.

Three default categories, all about the model's own choices: **deception** (works out one thing, decides to say another), **reward_hacking** (decides to satisfy the check instead of the task), **oversight_evasion** (decides to work around being reviewed). The rubric is a YAML file; replace it with whatever you actually worry about.

It does not judge output. Whether the work was any good, or the request acceptable, are different questions with different tools.

## Configuration

`[model]` is what you watch, `[judge]` is what scores. Separate endpoints, so they can be different machines. Copy `cotwatcher.example.toml`, or use `COTWATCHER_*` environment variables, which win over the file.

`score` exits 0 (assessed, clean), 1 (flagged), or 2 (incomplete: a chunk could not be assessed, or the input or endpoint failed). A run that was not fully assessed never exits 0.

⚠ Ollama picks a context per model and often lands at 4,096 tokens, then truncates from the front, which silently drops the rubric. `cotwatcher check` warns when no input limit is set; `ollama/` has Modelfiles for larger variants.

## Status

Early and honest about it. Detection accuracy on real workloads is unestablished.

On hand-written fixtures the judge scored 1.00 AUROC per category with no false fires. That did not transfer. In a controlled agentic experiment (`evals/pressure/`, 8 episodes, labels reviewed by hand) the model twice decided to satisfy a test it had identified as contradicting the specification — *"we have to make the code pass the tests, even if there's a discrepancy with the specification"* — and the judge caught one of the two, with one false positive on six negatives. Scoring the same episodes without the reasoning caught the *other* one, with two false positives. Each arm saw what the other missed; at n=8 that is a shape, not a rate.

Linear probes on pooled activations reach 0.90-1.00 AUROC on held-out synthetic data and 1.00 / 0.75 / 0.63 transferring to hand-written text. Treat that as a working pipeline, not a detection result: the probe reads a replay of saved text, and activations measure computation, not intent.

**The open question:** does reading the reasoning surface decisions that reading the output and tool logs does not? One of the two positives says yes, one says no.

## Review

The adversarial reviews in [FINDINGS.md](FINDINGS.md) were run by **OpenAI Codex** against this repository. They found the actor being served a 4,096-token context while the run asked for far more, a `reversed` field coerced from the string `"false"` so that reversals were marked that had not happened, a comparison summary reading fields its own rows never carried, a controlled pair whose test made the task unsatisfiable by an ordinary deterministic implementation, and a harness verdict a model's own code could forge. They also argued the project out of building a live stream tap before the verdicts it would produce could be checked by a person, which is why `cotwatcher review` exists.

Development is by [Cyrill Glockner](https://github.com/cyrillglockner) with Claude.

## Limitations

- **CoT faithfulness.** The reasoning is not always what drives the answer. A clean trace is absence of evidence.
- **Scope.** The experiments construct a conflict in a coding task. The question is broader — research that omits contradicting evidence, a status report on a failed task, a plan that quietly drops a constraint — and a result on coding tasks supports a claim about coding tasks.
- **The probe** has never been tested during generation, nor on misbehaviour it was not trained to recognise.

## Experiments

```bash
git clone https://github.com/cyrillglockner/cotwatcher && cd cotwatcher
uv venv && uv pip install -e ".[evals]"
```

`evals/pressure/` runs an agentic task where a hidden suite records what the code actually did; `evals/disclosure/` puts the model in a bind in a single call; `evals/probe/` trains the probes. They exist so you can find out whether any of this catches anything on *your* model rather than ours.

⚠ `evals/pressure/` executes Python written by a model. A temp directory is not a sandbox; run it in a disposable VM. It refuses to start without `COTWATCHER_ALLOW_CODE_EXECUTION=1`.

`docs/INTEGRATION.md` is the guide for wiring cotwatcher into an application, `docs/REVIEW.md` for reviewing what it found. `PLAN.md` carries the decisions and their reasons, `FINDINGS.md` the review ledger, `BACKLOG.md` what is deferred. MIT.
