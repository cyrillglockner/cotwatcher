"""Extract attributable reasoning from Apollo anti-scheming transcript pages.

    .venv/bin/python evals/external/extract_apollo.py

Reads the saved HTML in `evals/external/apollo/` and writes one JSONL per
transcript beside it. Output stays in `evals/external/`, which is never
committed: the pages carry a training-corpus canary.

**Why this source and not the PDF.** The pages mark roles structurally
(`apollo-message-assistant`, `apollo-message-tool`, `apollo-reasoning`), so the
model's own words can be separated from the system prompt, the user turns and
tool results. The PDF transcript collapsed all of that into running text, which
is why keyword counts over it said nothing about the model's decisions: they
were matching tool output.

**What this material is and is not.** Independently produced, which breaks our
own scenario-design loop. It is not natural or real-world: these are
deliberately constructed evaluations, as much a designed bind as our own
packets, just designed by someone else.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parents[1] / "external" / "apollo"

MESSAGE = re.compile(
    r'<div class="apollo-message apollo-message-(?P<role>[a-z]+)".*?(?=<div class="apollo-message |\Z)',
    re.S)
REASONING = re.compile(r'<div class="apollo-reasoning-content">(.*?)</div>', re.S)
CONTENT = re.compile(r'<div class="apollo-message-content[^"]*">(.*?)</div>\s*(?=<div|\Z)', re.S)


def clean(fragment: str) -> str:
    t = re.sub(r"<br\s*/?>", "\n", fragment)
    t = re.sub(r"</(p|div|li)>", "\n", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def parse(path: Path) -> list[dict]:
    raw = path.read_text(errors="replace")
    title = clean(re.search(r"<h1[^>]*>(.*?)</h1>", raw, re.S).group(1)) if re.search(r"<h1", raw) else path.stem
    out = []
    for n, m in enumerate(MESSAGE.finditer(raw)):
        block, role = m.group(0), m.group("role")
        reasoning = "\n\n".join(clean(x) for x in REASONING.findall(block))
        content = "\n\n".join(clean(x) for x in CONTENT.findall(block))
        out.append({"transcript": path.stem, "title": title, "index": n, "role": role,
                    "reasoning": reasoning, "content": content})
    return out


def main() -> int:
    for f in sorted(HERE.glob("*.html")):
        rows = parse(f)
        dest = f.with_suffix(".jsonl")
        with dest.open("w") as out:
            for r in rows:
                out.write(json.dumps(r) + "\n")
        roles = {}
        for r in rows:
            roles[r["role"]] = roles.get(r["role"], 0) + 1
        chars = sum(len(r["reasoning"]) for r in rows)
        blocks = sum(1 for r in rows if r["reasoning"])
        print(f"{f.stem:<36} {roles}  reasoning: {blocks} blocks, {chars:,} chars")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
