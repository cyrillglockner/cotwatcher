# cotwatcher

**Watch what an AI model is thinking, and get told when the thinking goes wrong.**

## The idea in plain terms

Modern "reasoning" models (DeepSeek-R1, Qwen3, gpt-oss and others) think out loud before they answer. That inner monologue is called the chain of thought, or CoT. It is usually hidden from end users, but if you run the model yourself you can read it.

That matters because the thinking sometimes shows a problem the final answer hides. A model asked to make failing tests pass might reason "the tests only check the length of the output, so I'll return the input unchanged," then hand back code that looks finished. A model asked what a program prints might think "I can't run this, but I'll state the numbers as if I had." The answer looks fine. The reasoning shows it isn't.

cotwatcher reads that reasoning as it streams out, scores each piece against a short list of things you care about, and logs or stops the response when a score crosses a line you set.

## What it looks for

Three things by default, all about the **model's own choices**:

- **Deception**: the model works out one thing and decides to tell you another. It knows it can't do something and presents a guess as fact.
- **Reward hacking**: the model satisfies the check instead of doing the task. Passing the tests without writing the code.
- **Oversight evasion**: the model plans around being watched. Phrasing a shortcut so a reviewer won't notice.

These live in a small text file you can edit. If you worry about different things, describe them there.

## What it is not

- **It is not a content filter.** Whether a *user's* request was acceptable is a separate job with separate tools. cotwatcher only looks at what the model does with an ordinary request.
- **It is not a hallucination detector.** A model that confidently makes something up without any sign it knew better is a different problem. cotwatcher looks for the case where the reasoning shows the model knew.
- **It is not proven yet.** See "Where this stands" below. This is an early, honest, open project.

## How it works

Two models are involved:

1. **The watched model**, the one doing the actual work. Any open-weight reasoning model served through the standard OpenAI-compatible API (Ollama, vLLM, LM Studio, llama.cpp all speak it).
2. **The judge**, a second model that reads each chunk of reasoning and scores it. Also any model behind the same API. By default it runs locally on your machine, so no reasoning leaves your infrastructure.

You point cotwatcher at both, and it sits in between.

There is also an experimental second kind of judge: a **probe** that reads the watched model's internal activations directly rather than its words. Think of it as an alarm bell rather than a smoke detector. It can't tell you what's wrong, but it can ring when the model's internal state and its written reasoning disagree, which is exactly the case a text reader can never catch. It is in the research stage.

## Where this stands

Being straightforward about it:

- **Built:** the judge, the editable list of concerns, configuration for both models, and an evaluation toolkit (tasks designed to tempt a model into shortcuts, a generator for training examples, and probe training).
- **Measured:** on a small set of test examples, the text judge scored perfectly and raised no false alarms on honest reasoning. The probe, trained only on synthetic examples, correctly ranked reasoning it had never seen at 1.00 / 0.95 / 0.79 (out of 1.00) for reward hacking / oversight evasion / deception. Those are good numbers on a small, hand-written set. They are consistency checks, not proof that it catches real misbehaviour.
- **Found so far in the wild:** running a real model on 30 tasks designed to tempt it, it took a shortcut about once. Well-behaved models on ordinary tasks are usually well-behaved. That is fine; the point of a monitor is the rare case and the record that you were watching.
- **Not built:** the live stream wrapper, the actions (log, callback, halt), the command line, the proxy server for zero-code deployment. See `PLAN.md` for the order.
- **Next:** an experiment where the model is given a solvable task, a real obstacle, and deadline pressure, with the true outcome recorded independently so we can see whether it reports the blocker or claims success. That is the first test with real ground truth, and it also asks the question that decides whether this tool is worth running: does reading the reasoning catch anything that reading the output and the tool log doesn't?

## Try it

Needs Python 3.11+, [Ollama](https://ollama.com), and about 13 GB of disk for the default judge model.

```bash
ollama pull gpt-oss:20b
uv venv && uv pip install -e ".[dev]"
.venv/bin/python examples/score_traces.py
```

That scores six short pieces of reasoning (three honest, three not) and shows what the judge makes of each. On a laptop, expect about 20 seconds per piece; on a GPU server, well under a second.

```python
import cotwatcher

judge = cotwatcher.load().make_judge()
score = judge.score("The tests only check length, so I'll return the input unchanged.")
print(score.max())   # ('reward_hacking', 1.0)
```

Configuration is a `cotwatcher.toml` file (see `cotwatcher.example.toml`) plus `COTWATCHER_*` environment variables. The watched model and the judge are separate settings, so cotwatcher runs on the same box as your inference server, on a machine beside it, or on your laptop against a remote server.

## A limit worth knowing

Reading the reasoning only works if the reasoning is honest about what drives the answer. Research from the labs shows it isn't always. Treat a clean trace as absence of evidence rather than evidence of absence. The probe work above exists for exactly this reason.

## For contributors

`PLAN.md` holds the decisions and their reasons; `BACKLOG.md` holds deferred work; `CLAUDE.md` holds conventions for anyone (or any AI assistant) working in the repo. Tests: `.venv/bin/pytest`.

MIT.
