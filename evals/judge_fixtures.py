"""Score the transfer fixtures with the text judge, for the side-by-side with probes.

    .venv/bin/python evals/judge_fixtures.py evals/probe/fixtures.jsonl

Reports AUROC per category using the judge's score for that category as the
ranking, on exactly the chunks the probe transfer test used.
"""

import json
import sys
from collections import defaultdict

from sklearn.metrics import roc_auc_score

import cotwatcher


def main() -> int:
    recs = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
    judge = cotwatcher.load().make_judge()
    by_cat = defaultdict(lambda: ([], []))
    for i, r in enumerate(recs):
        s = judge.score(r["reasoning"], task=r.get("prompt", ""))
        y, p = by_cat[r["category"]]
        y.append(r["label"]); p.append(s.scores[r["category"]])
        print(f"{i+1:>2}/{len(recs)} {r['id']:<40} label={r['label']} {r['category']}={s.scores[r['category']]:.2f}", flush=True)
    print(f"\n{'category':<18} {'n':>3}  AUROC")
    for cat, (y, p) in sorted(by_cat.items()):
        print(f"{cat:<18} {len(y):>3}  {roc_auc_score(y, p):.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
