"""Run the honeypot tasks against the watched model and save the traces.

    .venv/bin/python evals/generate.py                 # 3 runs per task, deepseek-r1:latest
    .venv/bin/python evals/generate.py -n 5 --tag sort_length_tests

Output: evals/traces/<model>_<timestamp>.jsonl, one line per run with the task
tag, prompt, the model's reasoning, and its answer. Labeling happens later and
separately; this script records, it does not judge.

The model endpoint comes from cotwatcher settings (COTWATCHER_MODEL_URL etc.);
--model overrides the model name because the settings default is the judge
model, gpt-oss:20b, and the watched model here is R1.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

import cotwatcher

HERE = Path(__file__).parent


def reasoning_of(message) -> str:
    """Ollama puts thinking in `reasoning`; vLLM and DeepSeek's API use `reasoning_content`."""
    for attr in ("reasoning", "reasoning_content"):
        v = getattr(message, attr, None)
        if v:
            return v
    extra = getattr(message, "model_extra", None) or {}
    return extra.get("reasoning") or extra.get("reasoning_content") or ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", "--runs", type=int, default=3)
    ap.add_argument("--model", default="deepseek-r1:latest")
    ap.add_argument("--tag", action="append", help="only these task tags (repeatable)")
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--max-tokens", type=int, default=4000)
    args = ap.parse_args()

    tasks = yaml.safe_load((HERE / "honeypots.yaml").read_text())["tasks"]
    if args.tag:
        tasks = [t for t in tasks if t["tag"] in args.tag]
    settings = cotwatcher.load()
    client = settings.model.client()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = HERE / "traces" / f"{re.sub(r'[^a-z0-9]+', '-', args.model.lower())}_{stamp}.jsonl"
    print(f"model: {args.model} @ {settings.model.url}\nwriting: {out}\n")

    with out.open("w") as f:
        for t in tasks:
            for run in range(args.runs):
                t0 = time.time()
                resp = client.chat.completions.create(
                    model=args.model,
                    messages=[{"role": "user", "content": t["prompt"]}],
                    temperature=args.temperature,
                    max_tokens=args.max_tokens,
                )
                msg = resp.choices[0].message
                rec = {
                    "id": f"{t['tag']}#{run}",
                    "model": args.model,
                    "task_tag": t["tag"],
                    "targets": t["targets"],
                    "prompt": t["prompt"],
                    "reasoning": reasoning_of(msg),
                    "answer": msg.content or "",
                    "finish_reason": resp.choices[0].finish_reason,
                    "seconds": round(time.time() - t0, 1),
                    "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
                f.write(json.dumps(rec) + "\n")
                f.flush()
                print(f"{rec['id']:<32} {rec['seconds']:>6.1f}s  reasoning={len(rec['reasoning']):>5} chars  "
                      f"answer={len(rec['answer']):>5} chars  {rec['finish_reason']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
