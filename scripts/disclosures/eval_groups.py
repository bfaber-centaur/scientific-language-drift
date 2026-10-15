"""Gate 3 decision: accuracy of the Lane C comparison groups derived from classifier labels.

Usage: python3 scripts/disclosures/eval_groups.py [--set test]

Groups (rubric v1 labels -> one group per statement):
  none          labels == {none}
  polish_only   labels == {polish}           (pure language editing)
  drafting      "drafting" in labels         (any other uses allowed)
  other_use     everything else with a use claim (no drafting, not polish-only)
  unknown       {ambiguous}, or empty labels (writing_unspecified only)
Decision rule, written before this script was run (docs/ai-disclosures.md, Gate 3):
  Lane C may compare drafting vs polish_only only if, on the held-out test set,
  both groups reach precision >= 0.85 and recall >= 0.80. "none" is reported
  but cannot pass with the support available.
Writes results/disclosures/labels/eval_groups_{set}.csv and confusion_groups_{set}.csv.
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd  # noqa: E402

from evaluate import parse, wilson  # noqa: E402
from mlngrams.disclosure_classify import classify  # noqa: E402

GROUPS = ["none", "polish_only", "drafting", "other_use", "unknown"]


def group(labels: set[str]) -> str:
    if labels == {"none"}:
        return "none"
    if not labels or labels == {"ambiguous"}:
        return "unknown"
    if labels == {"polish"}:
        return "polish_only"
    if "drafting" in labels:
        return "drafting"
    return "other_use"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="test")
    args = ap.parse_args()
    lab = pd.read_csv(os.path.join(ROOT, "results", "disclosures", "labels", f"{args.set}_labels.csv"))
    data = pd.read_parquet(os.path.join(ROOT, "data", "disclosures", "iclr2027.parquet"), columns=["doc_id", "text_clean"])
    lab = lab.merge(data, on="doc_id")
    lab["gold"] = lab.labels.map(lambda s: group(parse(s)))
    lab["pred"] = lab.text_clean.map(lambda t: group(classify(t)["labels"]))
    conf = pd.crosstab(lab.gold, lab.pred).reindex(index=GROUPS, columns=GROUPS, fill_value=0)
    conf.to_csv(os.path.join(ROOT, "results", "disclosures", "labels", f"confusion_groups_{args.set}.csv"))
    rows = []
    for g in GROUPS:
        tp = int(((lab.gold == g) & (lab.pred == g)).sum())
        npred, ngold = int((lab.pred == g).sum()), int((lab.gold == g).sum())
        rows.append({"group": g, "support": ngold, "predicted": npred, "tp": tp,
                     "precision": round(tp / npred, 3) if npred else None, "precision_ci": wilson(tp, npred),
                     "recall": round(tp / ngold, 3) if ngold else None, "recall_ci": wilson(tp, ngold)})
    out = pd.DataFrame(rows)
    ok = all(((out.group == g) & (out.precision >= 0.85) & (out.recall >= 0.80)).any() for g in ("drafting", "polish_only"))
    out.to_csv(os.path.join(ROOT, "results", "disclosures", "labels", f"eval_groups_{args.set}.csv"), index=False)
    print(conf.to_string(), "\n", out.to_string(), "\nGate 3 drafting-vs-polish_only:", "PASS" if ok else "FAIL")


if __name__ == "__main__":
    main()
