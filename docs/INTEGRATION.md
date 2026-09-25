# Integrating cotwatcher

Written for a coding agent adding cotwatcher to someone's application. It says what to reuse,
what you have to write yourself, how to verify the result, and what cannot be observed.

Read "What cotwatcher cannot see" before you start. It decides whether this integration is
possible at all, and it is the most common reason one silently does nothing.

## What you are building

cotwatcher reads a model's chain of thought and reports whether the model **decided to pursue
behaviour a rubric prohibits**. It does not assess the model's output. A wrong answer is not an
event and a clumsy one is not either.

You provide the glue between the user's application and these parts:

| You reuse | What it does |
|---|---|
| `cotwatcher check` | verifies the watched model exposes reasoning and the judge works |
| `LLMJudge.score(chunk, task=...)` | scores one piece of reasoning against the rubric |
| `EventJudge.propose(reasoning, task=..., prior=...)` | proposes decision events quoting the reasoning |
| `cotwatcher.events.verify` | locates each quoted passage in the source |
| `cotwatcher propose` / `cotwatcher review` | the offline path: captured episodes to a review page |
| `Rubric.load(path)` | the categories, editable by the user |

You write: the capture, the loop that calls the judge, and whatever the application does with a
verdict. There is no `watch()` wrapper to call, and you should not expect one.

## What cotwatcher cannot see

- **Reasoning the endpoint does not return.** Most hosted assistant APIs return an answer only.
  If the application calls one of those, there is nothing to monitor and no glue code fixes it.
- **The agent you are running inside.** If a user asks you to add cotwatcher to their project,
  they usually mean the model their application calls, not you. Your own reasoning is generally
  not exposed to the process you are writing code in. Say so rather than appearing to monitor
  yourself.
- **Activations.** The probe work in this repository is a replay over saved text, not live
  hidden states. Do not wire it into a live path.
- **Anything after the reasoning ends.** cotwatcher reads what the model thought, not what the
  tool call did. Pair it with the application's own tool logs rather than replacing them.

Check the first point before writing anything:

```bash
export COTWATCHER_MODEL=<the model the application calls>
export COTWATCHER_MODEL_URL=<its OpenAI-compatible base url>
cotwatcher check
```

Exit 0 means the watched model returned reasoning, the judge answered, and the context the
server is serving can hold what cotwatcher intends to send. Exit 2 means one of those failed,
and the output says which. Do not proceed past a failing check by working around
it: an endpoint that exposes no reasoning produces empty captures, and an empty capture scores
clean, so the integration will look like a quiet monitor rather than a broken one.

## Capturing reasoning

Reasoning arrives in one of three places depending on the server. `cotwatcher.cli.reasoning_of`
handles all three and is the function to copy or call:

- `message.reasoning` — Ollama
- `message.reasoning_content` — vLLM, DeepSeek, most OpenAI-compatible servers
- `<think>...</think>` inside `message.content` — some models emit it inline

Capture it where the application already calls its model. A minimal integration:

```python
from openai import OpenAI
from cotwatcher import config
from cotwatcher.cli import reasoning_of

# config.load() reads cotwatcher.toml and the COTWATCHER_* environment.
# Settings() would build defaults and ignore both, including the input budget.
settings = config.load()
judge = settings.make_judge()

client = OpenAI(base_url=..., api_key=...)
reply = client.chat.completions.create(model=..., messages=messages)
reasoning = reasoning_of(reply.choices[0].message)

def assess(reasoning, task):
    """Runs off the response path. Never raises into the caller."""
    if not reasoning:
        log.warning("cotwatcher: no reasoning in this reply; nothing was assessed")
        return
    try:
        score = judge.score(reasoning, task=task)
    except Exception as e:                 # transport, timeout, auth: the judge is a network call
        log.warning("cotwatcher: not assessed, judge call failed: %s", e)
        return                             # unassessed. Do not fall through to a clean path.
    if not score.ok:
        log.warning("cotwatcher: not assessed: %s", score.error)
    elif score.over(0.5):
        log.warning("cotwatcher: %s — %s", score.over(0.5), score.rationale)
```

Call `assess` where it cannot delay the user: a thread, a task queue, or an `asyncio` task
whose result you log. Scoring is a second inference and takes as long as the first.

Four rules for that loop, each of which has been got wrong in this repository already:

1. **Scoring is a second inference.** Do not block the user's response on it.
2. **An exception is not a verdict.** `judge.score()` is a network call and raises on transport
   failure, before any `score.ok` check can run. Catch it and record the chunk as unassessed.
   (`EventJudge.propose` differs: it returns a verdict carrying `error` rather than raising.
   Handle both shapes if you use both.)
3. **`score.ok is False` means unassessed, not clean.** Count it separately and surface it.
   Every silent-failure bug found in this repository had the same shape: something that assessed
   nothing and looked fine.
4. **Bound the judge's input.** Set `judge_max_input_tokens` to the judge's context minus room
   for the reply. A server truncates an oversized prompt from the front, which discards the
   rubric, and the answer it returns is not a verdict. `cotwatcher check` compares your setting
   against the window the server actually serves and fails when the setting cannot be honoured,
   which is the common case with Ollama's defaults.

## Choosing the judge

The judge is a second model behind any OpenAI-compatible endpoint, local by default so nothing
leaves the machine. It does not have to be the model being watched, and it usually should not
be. Configure it in `cotwatcher.toml` or by environment variable:

```toml
judge_max_input_tokens = 48000   # top level, and the loader also accepts it under [judge]

[model]                          # what you watch
url = "http://localhost:11434/v1"
model = "qwen3:8b-32k"

[judge]                          # what scores
url = "http://localhost:11434/v1"
model = "gpt-oss:20b-64k"
```

Those model names are long-context variants, not the stock tags. Ollama otherwise serves a
context of its own choosing, often 4,096 tokens, and truncates from the front, so a 48,000-token
budget is a number nothing honours. Build them from the Modelfiles in `ollama/`:

```bash
ollama create gpt-oss:20b-64k -f ollama/Modelfile.gpt-oss-64k
ollama create qwen3:8b-32k   -f ollama/Modelfile.qwen3-8b-32k
```

`cotwatcher check` reports the window each endpoint is actually serving and fails when the
budget exceeds it, so run it after any change here.

## The rubric

Three default categories: `deception`, `reward_hacking`, `oversight_evasion`. `cotwatcher rubric`
prints what the judge is actually given, in prompt form, which is what to read when a verdict
looks wrong. It is not a rubric file and cannot be edited into one.

To change the categories, copy the bundled YAML and pass it back:

```bash
python -c "import cotwatcher.rubrics, pathlib; \
  print(pathlib.Path(cotwatcher.rubrics.__file__).parent / 'default.yaml')"
cp <that path> rubric.yaml        # then edit, and pass --rubric rubric.yaml
```

Keep categories about the model's own choices. A category describing a bad outcome rather than a
decision will fire on confusion and on ordinary mistakes.

## Verifying the integration

Do all four before reporting the work as done.

1. `cotwatcher check` exits 0.
2. Run the application once and confirm a verdict was produced for a reply that had reasoning.
3. Confirm a reply with **no** reasoning is logged as unassessed rather than passing silently.
   Force it by pointing the watched model at a non-reasoning one.
4. Confirm an unreachable judge does not take the application down and does not read as clean.
   Force it by stopping the judge's server.

Tests 3 and 4 are the ones that matter. Tests 1 and 2 only show the happy path works.

## Reviewing what it found

Verdicts are for a person. For captured episodes, `cotwatcher propose` asks for decision events
quoting the reasoning and `cotwatcher review` renders them as one HTML page where each quote is
located in the source and can be confirmed or rejected: see [REVIEW.md](REVIEW.md).

Report honestly what the numbers are worth. The judge's accuracy on real workloads is not
established, and on this repository's eight labelled episodes it currently flags four of six
labelled negatives. Wire it up as a log to review, not as a gate that blocks anything.
