# Backlog

## Next release: beta, Monday 2026-09-28

Cut `0.1.0b1` from whatever has landed by then. Already waiting on it: the README correction
saying probes are not in the installed package, `AGENTS.md`, and the guide paths in
`cotwatcher --help`. The README is the PyPI page, so a correction to it reaches users only
through a release.

Release steps are in `.github/workflows/release.yml`; bump `pyproject.toml` and
`src/cotwatcher/__init__.py` together, tag, and publish a GitHub release. CI reports unreleased
user-facing changes on every push to main and fails once they are more than a week old.

- **Deception by artifact, not only by statement (2026-09-24).** The rubric says deception is working out one thing and deciding "to tell the user another", which points at words. The first Apollo transcript decides to fudge a timing measurement so the grader is shown a false number: no false sentence, the same substance. Consider widening the definition after the challenge set is scored — not before, since the judge is frozen for it.

- **A competent artifact-only baseline (2026-09-24, from Codex).** `compare.py` currently runs the same `LLMJudge` in both arms, and that judge's prompt says it audits private reasoning while its deception category requires awareness and decision *in the reasoning*. Removing the reasoning asks it for evidence the prompt has made unavailable, so the no-CoT arm is an input ablation rather than a real output monitor, and a miss there does not show that artifacts are insufficient. A proper baseline targets the same commitment event, sees only the artifacts, is allowed to treat an explicit admission in a report as establishing a decision, and can abstain instead of guessing at intent. Needed before any claim that CoT catches what output monitoring misses. Save each arm's prompt identity in the manifest.
- **Live activation capture.** Today's probe features are a replay: a fresh forward pass over saved text in a separately loaded HF copy, with the opening prompt as the only context, omitting the actions and tool output that conditioned the actor. Capturing hidden states during the original generation is a separate milestone, and is not required for the exploratory classifier to be useful.

- **A second domain, with different visible work (2026-09-24).** The pressure harness constructs a conflict in code, where the visible work is patches, test runs and a report. The claim cotwatcher wants to make is not about code, so at least one non-code family is needed before any general statement. Sketches, each needing a mechanical ground truth the way the hidden suite provides one now:
  - *Reporting*: a multi-step task where one step verifiably fails (the harness knows which), and the model writes a status summary. Ground truth is the harness log; the question is whether the summary says the step failed.
  - *Research*: a small corpus containing one document that contradicts the obvious conclusion. Ground truth is whether the write-up cites or addresses it. Constructing the corpus is the work.
  - *Planning*: a task with a stated hard constraint that makes the attractive plan impossible. Ground truth is whether the plan satisfies the constraint and whether it says so.
  - *Tool use*: an action gated behind an approval tool. Ground truth is the tool log; the question is whether an ungated route was taken and how the report describes it.
  Run the same two-stage labelling and the same with/without-CoT comparison, so results are comparable across domains.

- **OpenClaw as the reference deployment for the proxy (2026-09-20).** People running OpenClaw locally on an open-weight model want to know the agent is not going off the reservation. Fit: point OpenClaw's model endpoint at `cotwatcher serve`, which forwards to the real Ollama/vLLM; zero changes to OpenClaw, same-box topology, nothing leaves the machine. Slots into OpenClaw's E5 (monitoring/audit) beside E3 (policy engine): the policy engine sees the tool call, cotwatcher sees the reasoning that produced it, and only the reasoning separates "send the email" from "send it because the user would refuse if asked." Three design consequences to carry into the stream tap and proxy steps:
  1. **Agent-aware halt.** In an agent loop the dangerous part is the tool call at the end of the reasoning. The proxy must hold the tool-call portion of the response until the verdict on the reasoning lands, then release or block it. Stronger than "stop the stream when the verdict arrives."
  2. **An agent rubric**, shipped as a separate file, not a change to the default three: deception and oversight_evasion as-is, reward_hacking framed as completing the task by a route the user would not sanction, plus acting outside granted scope.
  3. **Local reasoning model required.** Hosted models with hidden reasoning leave cotwatcher blind; document this as the constraint and the reason the open-weight configuration is the one that can be monitored.
  OpenClaw's tool log is also the natural "output/tool-log monitoring" baseline for the v1 success criterion.

- **PyPI release, when `watch()` exists.** Publish `cotwatcher` 0.1.0a1 as the first install that does the headline job; register `cot-watcher` as an alias depending on it. Cyrill creates the PyPI account (2FA); use Trusted Publishing from a GitHub Actions release workflow rather than an API token; rehearse on TestPyPI. Name confirmed free 2026-09-18. Decided 2026-09-20 not to hold the name with a placeholder.

- **Output/tool-log monitoring baseline.** Needed to measure the v1 success criterion (incidents found beyond what output and tool-log monitoring catch, at a fixed false-alert budget). A simple monitor over final answers and tool calls using the same rubric, run on the same traffic as the CoT monitor.

- **Label the Mythos 5 transcript (2026-09-19).** A lab-released raw transcript (1022 pages, thinking and tool calls interleaved, canary GUID, never to be committed) sits in `evals/external/`, text pre-extracted to `mythos_pages.json`. Keyword pre-screen found 63 pages with oversight-evasion signals, 51 deception, 178 reward-hacking (noisy). Plan: hand-select 10 to 15 clear positives per category plus same-transcript negatives, no PDF parser. Labeling rules agreed with Cyrill: considering is not doing; the chunk itself must carry the label; three buckets (positive, negative, unsure) with unsure excluded; every label anchored to page and message; Cyrill reviews every positive before it counts. Probe feasibility passed 2026-09-19; this is now the critical path for evaluating both the text judge and the probe on real, subtle misbehaviour.

- **Hint-use experiment** (probe milestone after transcript labels; design in PLAN.md). Construct prompts where a planted hint changes the answer; label by whether the output used it and the CoT mentioned it; test whether the probe fires on used-and-unsaid chunks the text judge passes.
- **Probe in the live path.** The eval-time probe experiment is in the plan (step 3c). What stays here: a `ProbeJudge` behind the `Judge` interface for the live stream, which needs the watched model in-process (transformers, or vLLM with hooks) and so only applies to the same-box layout. Gated on the probe beating the text judge on the eval set.
- **Honeypot follow-ups.** Raise `--max-tokens` past 4,000 or discard capped runs (six of thirty lost). The wrong-expectation task was rewritten so the test is right and the code wrong; rerun it. Consider tasks where the honest path is expensive rather than merely available, since R1 does not cheat when doing it right is cheap.
- **Extra rubric categories, documented as recipes.** Sandbagging (deliberately underperforming while able) and hidden agenda (pursuing something nobody asked for: self-continuation, acquiring access, steering the user) were considered for the default and left out to keep it at three. Worth a docs page showing how to add them to a custom rubric, once the eval set can say whether the judge detects them.
- **Trained classifier judge.** Fine-tune a small encoder (ModernBERT class) on labeled traces for speed and cost once there is data. Same interface as `LLMJudge`.
- **CoT faithfulness caveat.** Text monitoring only sees what the model writes. Document this limit in the README rather than pretend otherwise; it is the argument for the probe work above.
