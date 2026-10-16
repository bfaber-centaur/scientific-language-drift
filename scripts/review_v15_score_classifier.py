"""Lane D (v1.5 review): score Lane B's frozen disclosure classifier against the reviewer's blind labels.

Usage: python3 scripts/review_v15_score_classifier.py <lane-b-src-dir> <iclr2027.parquet from Lane B extract.py>
Reads results/review/blind_labels_laneb_test30.csv (reviewer labels, fixed in e11ef0e before Lane B labelled
the test set). Prints per-category precision/recall, exact match and each disagreement (ids and labels only).
"""
import sys

import pandas as pd

sys.path.insert(0, sys.argv[1])
from mlngrams.disclosure_classify import CATEGORIES, CLASSIFIER_VERSION, classify  # noqa: E402

rev = pd.read_csv(sys.argv[3] if len(sys.argv) > 3 else "results/review/blind_labels_laneb_test30.csv")
txt = pd.read_parquet(sys.argv[2]).set_index("doc_id").text_clean
rows = []
for _, r in rev.iterrows():
    out = classify(txt[r.doc_id])
    pred = set(out["labels"] if isinstance(out, dict) and "labels" in out else out)
    rows.append((r.doc_id, set(r.reviewer_labels.split()), pred, r.stratum))
print("classifier", CLASSIFIER_VERSION, "items", len(rows))
for c in CATEGORIES:
    tp = sum(c in g and c in p for _, g, p, _ in rows)
    fp = sum(c not in g and c in p for _, g, p, _ in rows)
    fn = sum(c in g and c not in p for _, g, p, _ in rows)
    print(f"{c:11s} support={tp + fn:2d} pred={tp + fp:2d} P={tp / (tp + fp) if tp + fp else float('nan'):.2f} "
          f"R={tp / (tp + fn) if tp + fn else float('nan'):.2f}")
ex = sum(g == p for _, g, p, _ in rows)
print(f"exact match {ex}/{len(rows)}")
for d, g, p, s in rows:
    if g != p:
        print(f"  {d} ({s}) reviewer={sorted(g)} classifier={sorted(p)}")
# Round 2: python3 scripts/review_v15_score_classifier.py <lane-b>/src <extract> results/review/blind_labels_laneb_test2_30.csv
