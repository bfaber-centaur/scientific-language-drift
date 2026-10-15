"""Evaluate the disclosure classifier against reference labels (Lane B, Gate 3).

Usage: python3 scripts/disclosures/evaluate.py --set dev|test [--labels FILE] [--show-errors]

Reads reference labels (results/disclosures/labels/{set}_labels.csv: doc_id,
labels as ";"-joined categories) and the disclosure text from
data/disclosures/iclr2027.parquet, runs mlngrams.disclosure_classify, and
writes results/disclosures/labels/eval_{set}.csv: per-category precision, recall,
F1, support, and the 2x2 confusion counts (tp, fp, fn, tn); plus exact-match
rate, mean Jaccard, abstention rate and Wilson 95% intervals.
"""
from __future__ import annotations

import argparse
import math
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pandas as pd  # noqa: E402

from mlngrams.disclosure_classify import CATEGORIES, classify  # noqa: E402


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(c - h, 3), round(c + h, 3))


def parse(s) -> set[str]:
    return {x for x in str(s).split(";") if x and x != "nan"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="dev")
    ap.add_argument("--labels")
    ap.add_argument("--show-errors", action="store_true")
    ap.add_argument("--out")
    args = ap.parse_args()
    lab = pd.read_csv(args.labels or os.path.join(ROOT, "results", "disclosures", "labels", f"{args.set}_labels.csv"))
    data = pd.read_parquet(os.path.join(ROOT, "data", "disclosures", "iclr2027.parquet"), columns=["doc_id", "text_clean"])
    lab = lab.merge(data, on="doc_id", how="left")
    gold, pred, unspec_g, unspec_p = [], [], [], []
    for _, r in lab.iterrows():
        g = parse(r.labels)
        out = classify(r.text_clean)
        p = out["labels"]
        gold.append(g)
        pred.append(p)
        # Flag compared only where it is the sole writing claim (gold has neither polish nor drafting).
        unspec_g.append("writing_unspecified" in parse(r.get("flags", "")) and not g & {"polish", "drafting"})
        unspec_p.append(out["writing_unspecified"])
        if args.show_errors and g != p:
            print(f"{r.doc_id}: gold={sorted(g)} pred={sorted(p)} missing={sorted(g-p)} extra={sorted(p-g)}")
            if "evidence" in out:
                print("   ", [e for e in out["evidence"] if e[0] in (p - g)][:6])
    rows = []
    n = len(lab)
    for c in CATEGORIES:
        tp = sum(c in g and c in p for g, p in zip(gold, pred))
        fp = sum(c not in g and c in p for g, p in zip(gold, pred))
        fn = sum(c in g and c not in p for g, p in zip(gold, pred))
        tn = n - tp - fp - fn
        prec = tp / (tp + fp) if tp + fp else float("nan")
        rec = tp / (tp + fn) if tp + fn else float("nan")
        f1 = 2 * prec * rec / (prec + rec) if tp else 0.0
        rows.append({"category": c, "support": tp + fn, "predicted": tp + fp, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
                     "precision": round(prec, 3), "precision_ci": wilson(tp, tp + fp), "recall": round(rec, 3),
                     "recall_ci": wilson(tp, tp + fn), "f1": round(f1, 3)})
    tp = sum(a and b for a, b in zip(unspec_g, unspec_p))
    rows.append({"category": "writing_unspecified (flag)", "support": sum(unspec_g), "predicted": sum(unspec_p), "tp": tp,
                 "fp": sum(unspec_p) - tp, "fn": sum(unspec_g) - tp, "tn": n - sum(unspec_g) - sum(unspec_p) + tp,
                 "precision": round(tp / sum(unspec_p), 3) if sum(unspec_p) else float("nan"),
                 "recall": round(tp / sum(unspec_g), 3) if sum(unspec_g) else float("nan")})
    exact = sum(g == p for g, p in zip(gold, pred))
    jac = sum(len(g & p) / len(g | p) if g | p else 1 for g, p in zip(gold, pred)) / n
    abst = sum(p == {"ambiguous"} for p in pred)
    rows.append({"category": "ALL: exact match", "support": n, "tp": exact, "precision": round(exact / n, 3), "precision_ci": wilson(exact, n)})
    rows.append({"category": "ALL: mean Jaccard", "support": n, "precision": round(jac, 3)})
    rows.append({"category": "ALL: abstained (ambiguous)", "support": n, "tp": abst, "precision": round(abst / n, 3)})
    df = pd.DataFrame(rows)
    df.to_csv(args.out or os.path.join(ROOT, "results", "disclosures", "labels", f"eval_{args.set}.csv"), index=False)
    print(df.to_string())


if __name__ == "__main__":
    main()
