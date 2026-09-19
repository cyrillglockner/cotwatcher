# cotwatcher — plan

Python OSS tool that watches the chain of thought of an open-weight reasoning model and flags reasoning that matches a rubric of things the user worries about.

Decided 2026-09-18.

## Scope of v1

- **Input:** the CoT text as emitted by the model (`reasoning_content` on DeepSeek / vLLM / Ollama, `reasoning` on gpt-oss via the Responses API). Hidden-state probes are on the backlog, not in v1.
- **Judge:** an LLM behind the OpenAI-compatible API. **Baseline is local: Ollama serving `gpt-oss:20b`** (decided 2026-09-18, after it scored 6/6 on the example traces). The same client points at OpenAI, vLLM, LM Studio or llama.cpp by changing `base_url` and `model`. A trained classifier NN is a later drop-in behind the same `Judge` interface. Measured 2026-09-18 on an M-series laptop, one chunk: 19s at `reasoning_effort=low`, 59s at medium, 20min at high, identical verdicts, so the judge defaults to low. Fine for offline scoring; a live stream tap needs either a smaller non-reasoning judge or the trained classifier on the backlog.
- **Rubric:** a plain file (YAML), shipped with a default of four categories. Users edit or replace it; nothing in the code depends on the category names. Each category carries a name, a one-line definition, and two or three short examples.
  - deception of the user
  - reward hacking / gaming the task
  - harmful intent
  - instruction subversion (planning to ignore the system prompt or tool rules)
- **Shape:** library first. `cotwatcher.watch(client)` wraps an OpenAI-compatible client, intercepts the reasoning stream, chunks it, scores chunks against the rubric, and dispatches actions. A CLI scores transcript files offline using the same core. A proxy server (local OpenAI-compatible endpoint that forwards and watches) is v1.1, a thin FastAPI layer over the library.
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

## Build order

1. `Judge` interface + `LLMJudge` + default rubric + tests with canned traces.
2. Stream tap over a streamed `chat.completions` response; `watch()` wrapper.
3. Policy + actions (JSONL log, callback, halt).
4. CLI: `cotwatcher score traces.jsonl --rubric my.yaml`.
5. README, PyPI packaging, examples against DeepSeek-R1 on Ollama and gpt-oss on vLLM.
6. v1.1: proxy server.

## Housekeeping

- This folder sits inside the `vibe_coding` monorepo git tree. An OSS project needs its own repo: `git init` here and add `cotwatcher/` to the parent's `.gitignore` before the first commit.
- Package name `cotwatcher`, confirmed free on PyPI and GitHub 2026-09-18.
