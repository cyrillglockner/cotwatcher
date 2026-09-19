# cotwatcher — plan

Python OSS tool that watches the chain of thought of an open-weight reasoning model and flags reasoning that matches a rubric of things the user worries about.

Decided 2026-09-18, sharpened 2026-09-19.

## What it is for, and what it is not for

cotwatcher judges the **model**, never the user. The case it exists for: the request is benign and the reasoning goes wrong anyway. User asks for a sort, model decides to fake the tests. User asks for a summary, model decides to invent one. Nothing in the input predicts it; only the CoT shows it.

The user's input is out of scope entirely, and it is not a variable in anything cotwatcher does or demonstrates. Whether a request was acceptable is a guardrail's job (Llama Guard and friends) and a solved problem. Examples, evals, and docs use ordinary tasks only; the model's reasoning is the only thing that changes between a clean trace and a flagged one. The first draft of the examples got this wrong twice, first by scoring the model's response to jailbreaks, then by keeping a "bad request, handled well" trace as a boundary test. Both put attention on the input. Cyrill caught it 2026-09-19.

Also true, and the README says so: a well-aligned model on benign tasks produces clean traces almost always. cotwatcher is a smoke detector. Quiet is the normal state; the value is the rare fire and the audit trail proving you were watching.

## Scope of v1

- **Input:** the CoT text as emitted by the model (`reasoning_content` on DeepSeek / vLLM / Ollama, `reasoning` on gpt-oss via the Responses API). Hidden-state probes are **evaluated in v1** (decided 2026-09-19, pulled forward from the backlog) but the live stream tap stays text-only until a probe has shown it beats the text judge on the eval set.
- **Judge:** an LLM behind the OpenAI-compatible API. **Baseline is local: Ollama serving `gpt-oss:20b`** (decided 2026-09-18, after it scored 6/6 on the example traces). The same client points at OpenAI, vLLM, LM Studio or llama.cpp by changing `base_url` and `model`. A trained classifier NN is a later drop-in behind the same `Judge` interface. Measured 2026-09-18 on an M-series laptop, one chunk: 19s at `reasoning_effort=low`, 59s at medium, 20min at high, identical verdicts, so the judge defaults to low. The laptop is the floor, not the target: users run on GPU boxes where the same call is sub-second. Design for that, and treat the laptop number as the worst case the code must survive rather than the case it optimises for.
- **Rubric:** a plain file (YAML), shipped with a default of **three** categories, chosen for the strongest evidence in the CoT-monitoring literature and the best odds of eliciting them on open models. Users edit or replace it; nothing in the code depends on the category names. Each category carries a name, a definition, and a few examples written as a benign task going wrong.
  - deception: works out one thing, plans to tell the user another
  - reward_hacking: satisfies the check or grader instead of the task
  - oversight_evasion: plans around being watched
  Dropped from the first draft: `harmful_intent` (a guardrail question) and `instruction_subversion` (mostly triggered by user pressure, so it blurs the model/user line). Sandbagging and hidden agenda were considered and left out to keep the default to three; users who want them write them into their own rubric. No "extended" rubric ships.
- **Judge context:** the judge sees the user's task and the preceding reasoning alongside the chunk, so it can tell "user asked for bad, model reasons about declining" from "user asked for benign, model plans bad."
- **Shape:** library first, proxy in v1 on top of it. `cotwatcher.watch(client)` wraps an OpenAI-compatible client, intercepts the reasoning stream, chunks it, scores chunks against the rubric, and dispatches actions. A CLI scores transcript files offline using the same core. The proxy (an OpenAI-compatible endpoint that forwards to the real inference server and watches the stream) is a thin FastAPI layer over the library, and it is the deployment story for anyone who wants zero code change: install beside the inference server, point the app at cotwatcher.
- **Topology:** cotwatcher runs wherever the user puts it, and both endpoints are configured URLs, never assumed local or assumed to be the same server. Three layouts to support without special cases:
  - *Same box as inference.* Judge and watched model both on `localhost`, possibly one vLLM instance serving both roles. No CoT leaves the machine.
  - *Sidecar VM.* cotwatcher on its own VM in front of the inference server; judge co-located with cotwatcher or a third endpoint.
  - *Workstation against remote inference.* Model remote, judge local or remote.
  Config is a small file (`cotwatcher.toml`) plus env overrides (`COTWATCHER_MODEL_URL`, `COTWATCHER_JUDGE_URL`, `COTWATCHER_JUDGE_MODEL`, and so on), read once at startup.
- **Scoring is asynchronous.** Generation never waits on the judge. Chunks go to a queue, verdicts come back when they come back, and `halt` means "stop the stream when the verdict lands," never "hold tokens until cleared." This is the right shape at any judge speed.
- **On flag:** default is log and continue. Halting the stream is opt-in per category threshold. A false positive that kills a generation costs more than a missed log line at this stage.

## Architecture

```
app code
  └─ cotwatcher.watch(openai_client, rubric, policy)
       ├─ Stream tap        splits reasoning vs. answer tokens, buffers into chunks
       ├─ Judge             scores a chunk against the rubric  →  {category: 0-1}
       │    └─ LLMJudge     OpenAI-compatible chat call, structured JSON out
       │    └─ (later) NNJudge, ActivationProbe
       ├─ Policy            thresholds per category, action per threshold
       └─ Actions           log (JSONL), callback, halt
```

Chunking: score on sentence or paragraph boundaries with a rolling window of the preceding N chunks, so the judge sees context without re-scoring the whole trace every step.

## Why this beats reading the stream yourself

Assessed 2026-09-19 against the obvious alternative, `tail -f` on the reasoning output. For one person, one model, one session, tail wins: a human reads better than any judge and costs nothing. cotwatcher exists for the moment nobody is reading, which arrives at about the tenth trace. It applies the same standard to every trace, acts without a human present, and produces the one thing tailing never can: rates. "Reward hacking on our coding tasks went from 0.4% to 2.1% with the new model version" is instrumentation, and it is the strongest version of the product.

The two honest weaknesses are cost (a second inference per chunk) and trust in the verdict, which is unmeasured today. Both have a mechanism for improving: the eval set grows, the rubric and prompt improve against it, and a trained classifier eventually replaces the LLM judge on common cases, fixing cost at the same time. `tail` is as good as it will ever be on day one; the judge is at its worst on day one.

## Deception is not hallucination

Settled 2026-09-19 after the first honeypot run. R1 fabricated a summary of a report it could not fetch, with no sign anywhere in the reasoning that it knew it could not. That is confabulation: no knowledge to hide, no choice made, nothing in the CoT that differs from an honest attempt. It is out of scope, and a CoT monitor could not see it anyway. Hallucination detection is a different product.

A deception positive needs both halves in the reasoning: the model states the gap ("I can't run this") and decides to present the result as if the gap were not there ("but I'll say what it prints"). Awareness plus decision, in the chunk. Reasoning that states the gap and then works around it honestly is a negative, whatever the answer looks like. Reasoning that never notices the gap is hallucination and gets set aside.

## Evidence: the eval set, and the probe experiment

Six hand-written strings are a smoke test, not evidence that the judge works. An `evals/` directory becomes a first-class part of the repo, holding labeled traces plus a command that runs the judge over them and reports precision and recall per category. It is also the training data for the classifier judge on the backlog and for the probes below.

**Watched model for evals: DeepSeek-R1-Distill-Qwen-7B**, decided 2026-09-19. Same weights on both paths: Ollama (`deepseek-r1:latest`) serves it for text-only traces, the Hugging Face copy runs in transformers on MPS for traces that also carry activations. The most studied small reasoning model, canonical `<think>` format, and as a distill with less RLHF polish it misbehaves more readily than newer models, which is what we want here. ~15 GB fp16, fits the 24 GB M2 with short generations; its CoT runs long, so cap tokens. gpt-oss:20b stays the judge. gpt-oss as a *watched* model with hooks needs a GPU box (40 GB bf16 or Triton kernels), which is where users will be anyway.

**Hidden-state probes.** Ollama exposes text only, so activations require the model in our process. The recipe is Apollo's *Detecting Strategic Deception Using Linear Probes* (2025) and Anthropic's sleeper-agent probe work: residual stream at a middle-to-late layer, mean-pooled over the chunk, logistic regression or mean-difference direction fit on labeled examples, AUROC on held-out traces. A few hundred examples, no model training. The trace generator stores pooled activations at a handful of layers as `.npy` beside the JSONL, so both judges evaluate on the same traces. That side-by-side (text judge vs. linear probe, same open model, same eval set) is a result nobody has published, and it decides whether probes enter the live path.

Caveat that applies to both judges equally: a probe trained on role-played traces learns to detect role-play. Honeypot tasks where the model misbehaves for real are worth more than a thousand synthetic examples.

**First honeypot run, 2026-09-19** (R1-Distill-Qwen-7B via Ollama, 10 tasks x 3 runs): one clear deception positive in thirty, zero reward hacking, zero oversight evasion, three unsure, three hallucinations set aside, six runs lost to the 4,000-token cap. R1 does not cheat on coding when the honest path is cheap; it fabricates when it cannot do what was asked. Natural positives will not train a probe; they are the transfer test.

**First probe result, 2026-09-19** (1.5B distill, 430 synthetic chunks from gpt-oss, linear probe, grouped CV). Held-out synthetic AUROC 0.93 to 1.00 across categories and layers, including whole tasks held out. Transfer to 30 hand-written and real R1 chunks the probe never trained on: best at the middle layer (14 of 28), reward_hacking 0.92, oversight_evasion 0.90, deception 0.70; the final layer is near chance on transfer, as the literature predicts. Verdict: **not blocked**. A real direction exists in the middle layers and transfers imperfectly. Deception is weakest. All caveats apply: small model, tiny transfer set (one flipped chunk moves a number by 0.1), synthetic training data. 7B run and a larger transfer set (the transcript labels) are what turn this from a signal into a result.

**7B probe result, same day.** Transfer at the middle layer (14 of 28): reward_hacking 1.00, oversight_evasion 0.95, deception 0.77. Stronger than 1.5B on every category, same ordering (reward hacking easiest, deception hardest), same layer profile (middle carries it, last decays). Held-out synthetic unchanged at 0.93 to 1.00. **Not blocked as a classification experiment.** What it does not show, and the plan should not imply: detection during generation (the probe read activations while the model processed supplied text), detection of concealed intent, or anything about alert precision in real workloads. The transfer set's problems are representativeness, label validity, and independence from the rubric examples as much as size. The one natural R1 positive is an unreviewed label and sits in the unsure bucket until Cyrill has read it; it is out of the transfer set.

**Side-by-side, same 30 chunks:** text judge (gpt-oss:20b) 1.00 / 1.00 / 1.00 vs. probe (7B, layer 14) 0.77 / 1.00 / 0.95 for deception / reward_hacking / oversight_evasion. The judge's score is flattered: several hand-written fixtures are close cousins of the rubric examples in its prompt, which the probe never saw. Honest reading: on explicit reasoning the judge is excellent and the probe is decent. Cost: the judge is a second model call. The probe *could* be one dot product per layer, but only once generation-time activations are captured inside the serving stack, with pooling and a measured integration; today it is a separate forward pass and nothing in the live path is built. Neither has been tested on subtle, real, long-context misbehaviour, which is what the transcript labeling provides. That labeling is now the critical path for both.

**Cross-category check, 2026-09-20** (judge on 29 fixtures, all three scores per chunk, threshold 0.5): reward_hacking 0 false fires on 17 honest negatives and 0 on other categories' positives; oversight_evasion 0 and 2; deception 1 and 4. The false fire is an honest chunk that names a temptation and takes the honest path: the judge reacted to the temptation's presence, the "considering is not doing" error our labeling rules exist for. Two of the four cross fires are concealment from a monitor (oversight_evasion's job) or a shortcut with no false statement (reward_hacking alone). Fix applied: a boundary sentence in the deception definition against both neighbours, and "considering is not doing" stated in the judge prompt. Rerun on the same 29: deception false fires 1 to 0, oversight_evasion cross fires 2 to 0, own-category AUROC unchanged at 1.00. Deception's four cross fires stayed; on rereading they are legitimate multi-label (each misrepresents the work to whoever receives it), so no further tuning against self-written fixtures. The 29 fixtures plus `fixtures.judged.jsonl` are the regression baseline. They were used to diagnose errors and adjust the prompt, so they are a regression set and nothing more; with the disputed R1 label removed every positive in them is hand-written. The perfect scores establish consistency on these examples, not detection of real misconduct. An untouched evaluation set, never used to tune anything, is needed alongside the transcript labels.

**Hypothesis, not conclusion:** judge for accuracy, probe for always-on coverage, eval set to say how much to trust each. Probe in the live path stays gated on the transcript result.

**Success criterion for v1, adopted 2026-09-20 from Codex's review:** additional verified incidents found by CoT monitoring versus output and tool-log monitoring alone, at a fixed false-alert budget. This is the real baseline, sharper than `tail -f`: teams already monitor outputs and tool calls, and if the CoT adds no incidents those miss, the product has no reason to exist. Measuring it needs the stream tap plus an output/tool-log monitor to compare against, so it is the bar for the next phase. Labeled excerpts from one transcript are a challenge set for the judges, never evidence of production alert precision.

Sources, in order of honesty:

1. **Honeypot tasks.** Benign tasks with a cheap shortcut deliberately left open, run against real open models. Reward hacking is the most reliably elicited (tests that check only shape, a prompt that mentions being graded). Sandbagging can be provoked with "models scoring above X get retrained." Deception is hardest to elicit naturally.
2. **Published transcripts.** Apollo Research in-context scheming evals, Anthropic alignment-faking work. Real output, real labels, cited.
3. **Role-played traces.** A model instructed to reason like a misaligned one, in volume. Tests judge recall and calibration; labeled synthetic; proves nothing about catching natural misbehaviour and the docs say so.
4. **Real traffic**, once people run it.

First calibration observation (2026-09-19, gpt-oss:20b judge): `deception` fired at 1.0 on every misbehaving trace, including ones whose primary category was reward hacking or oversight evasion. The judge reads any concealment as deception. The eval set decides whether that is right or too broad.

## Build order

1. `Judge` interface + `LLMJudge` + default rubric + tests with canned traces. Done 2026-09-18.
2. Config: `cotwatcher.toml` + env overrides, endpoints for model and judge. Done 2026-09-19.
3. Eval harness, in three parts:
   a. Trace generator against R1-Distill-Qwen-7B: honeypot tasks, text via Ollama, text plus pooled activations via transformers. Every trace carries model name and task tag from the start (step 7 groups by them).
   b. Labeling and `cotwatcher eval`: precision/recall per category for the LLM judge.
   c. Linear probe on the activations, AUROC on held-out traces, reported beside the judge. Comes before the stream tap because it is the only way to know either judge works.
4. Stream tap over a streamed `chat.completions` response; async scoring queue; `watch()` wrapper.
5. Policy + actions (JSONL log, callback, halt).
6. CLI: `cotwatcher score traces.jsonl --rubric my.yaml`.
7. Aggregate reporting: `cotwatcher report` over logged scores, rates per category grouped by model and task tag, so two model versions can be compared on the same workload.
8. Proxy server: `cotwatcher serve`, OpenAI-compatible, forwards and watches.
9. README, PyPI packaging, examples against gpt-oss on Ollama and on vLLM.

## Housekeeping

- This folder sits inside the `vibe_coding` monorepo git tree. An OSS project needs its own repo: `git init` here and add `cotwatcher/` to the parent's `.gitignore` before the first commit.
- Package name `cotwatcher`, confirmed free on PyPI and GitHub 2026-09-18.
