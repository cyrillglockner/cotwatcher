"""Train linear probes on pooled activations and report held-out AUROC.

    .venv/bin/python evals/probe/train.py --model 1.5b evals/traces/synth_*.jsonl
    .venv/bin/python evals/probe/train.py --model 7b evals/traces/synth_*.jsonl --transfer evals/probe/fixtures.jsonl

For each rubric category: one logistic-regression probe per layer, trained on
that category's labeled chunks (positives vs. their paired negatives), scored
with grouped cross-validation so a pair never straddles train and test, and
also grouped by task so a held-out task tests generalisation across tasks.

--transfer scores a second labeled file with probes trained on all of the
first. That is the check against a probe that only learned the generator's
phrasing: the fixtures were written by hand, the synthetic set by gpt-oss.

Activations are cached in evals/probe/cache/<model>/ keyed by chunk id, so
re-running with different probe settings costs nothing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent))
from evals.probe.activations import MODELS, Extractor  # noqa: E402


def load(paths: list[str]) -> list[dict]:
    recs = []
    for p in paths:
        recs += [json.loads(l) for l in open(p) if l.strip()]
    return recs


def features(recs: list[dict], model_key: str, ex: Extractor | None) -> tuple[dict[int, np.ndarray], Extractor | None]:
    cache = HERE / "cache" / model_key
    cache.mkdir(parents=True, exist_ok=True)
    per_layer: dict[int, list[np.ndarray]] = defaultdict(list)
    layers = None
    for i, r in enumerate(recs):
        key = hashlib.sha1((r["id"] + "|" + r["reasoning"]).encode()).hexdigest()[:16]
        f = cache / f"{key}.npz"
        if f.exists():
            z = np.load(f)
            feats = {int(k): z[k] for k in z.files}
        else:
            if ex is None:
                ex = Extractor(MODELS[model_key])
            feats = ex.pooled(r.get("prompt", ""), r.get("context", ""), r["reasoning"])
            np.savez(f, **{str(k): v for k, v in feats.items()})
        layers = layers or sorted(feats)
        for L in layers:
            per_layer[L].append(feats[L])
        if (i + 1) % 50 == 0:
            print(f"  features {i+1}/{len(recs)}", flush=True)
    return {L: np.stack(v) for L, v in per_layer.items()}, ex


def probe():
    return make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=2000))


def cv_auroc(X, y, groups, n_splits=5) -> float:
    n_splits = min(n_splits, len(set(groups)))
    if n_splits < 2 or len(set(y)) < 2:
        return float("nan")
    scores = np.zeros(len(y))
    for tr, te in GroupKFold(n_splits=n_splits).split(X, y, groups):
        if len(set(y[tr])) < 2:
            return float("nan")
        scores[te] = probe().fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
    return roc_auc_score(y, scores)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("train", nargs="+")
    ap.add_argument("--model", choices=list(MODELS), default="1.5b")
    ap.add_argument("--transfer", help="labeled jsonl scored by probes trained on all of `train`")
    args = ap.parse_args()

    recs = load(args.train)
    print(f"{len(recs)} chunks from {len(args.train)} file(s); model {args.model}")
    X_all, ex = features(recs, args.model, None)
    cats = sorted({r["category"] for r in recs})
    layers = sorted(X_all)

    print(f"\n{'category':<18} {'n':>4}  " + "  ".join(f"L{L:<3}pair  L{L:<3}task" for L in layers))
    for cat in cats:
        idx = np.array([i for i, r in enumerate(recs) if r["category"] == cat])
        y = np.array([recs[i]["label"] for i in idx])
        pair_g = np.array([f"{recs[i]['task_tag']}:{recs[i]['pair']}" for i in idx])
        task_g = np.array([recs[i]["task_tag"] for i in idx])
        row = []
        for L in layers:
            X = X_all[L][idx]
            row.append(f"{cv_auroc(X, y, pair_g):.3f}     {cv_auroc(X, y, task_g):.3f}    ")
        print(f"{cat:<18} {len(idx):>4}  " + "  ".join(row))
    print("\npair = pairs held out together; task = whole tasks held out (generalisation across tasks)")

    if args.transfer:
        trecs = load([args.transfer])
        X_t, _ = features(trecs, args.model, ex)
        print(f"\ntransfer to {args.transfer} ({len(trecs)} chunks)")
        print(f"{'category':<18} {'n+':>3} {'n-':>3}  " + "  ".join(f"L{L:<3}" for L in layers))
        for cat in cats:
            tr = np.array([i for i, r in enumerate(recs) if r["category"] == cat])
            te = np.array([i for i, r in enumerate(trecs) if r["category"] == cat])
            if len(te) == 0:
                continue
            y_tr = np.array([recs[i]["label"] for i in tr])
            y_te = np.array([trecs[i]["label"] for i in te])
            row = []
            for L in layers:
                if len(set(y_te)) < 2:
                    row.append("  nan"); continue
                p = probe().fit(X_all[L][tr], y_tr).predict_proba(X_t[L][te])[:, 1]
                row.append(f"{roc_auc_score(y_te, p):.3f}")
            print(f"{cat:<18} {int(y_te.sum()):>3} {int((1-y_te).sum()):>3}  " + "  ".join(row))
    return 0


if __name__ == "__main__":
    sys.exit(main())
