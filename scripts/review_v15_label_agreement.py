"""Lane D (v1.5 review): agreement of the reviewer's 30 blind labels with Lane B coder 1 and coder 2.

Usage: python3 scripts/review_v15_label_agreement.py <lane-b>/results/disclosures/labels
Prints exact label-set agreement and per-category Cohen's kappa for each pair on the reviewer's 30 items, and
coder 1 vs coder 2 on all shared items, plus each item where the three label sets differ (ids and labels only).
"""
import sys

import pandas as pd

LAB = sys.argv[1]
CATS = ["none", "polish", "drafting", "coding", "literature", "other", "ambiguous"]


def sets(df: pd.DataFrame) -> dict:
    return {d: set(v.split(";")) if isinstance(v, str) and v else set() for d, v in df.labels.items()}


def kappa(X: dict, Y: dict, ids: list, c: str) -> float:
    a, b = [c in X[d] for d in ids], [c in Y[d] for d in ids]
    n = len(ids)
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = (sum(a) / n) * (sum(b) / n) + (1 - sum(a) / n) * (1 - sum(b) / n)
    return (po - pe) / (1 - pe) if pe < 1 else float("nan")


rev = pd.read_csv("results/review/blind_labels_laneb_test30.csv").set_index("doc_id")
R = {d: set(v.split()) for d, v in rev.reviewer_labels.items()}
c1 = sets(pd.read_csv(f"{LAB}/test_labels.csv").set_index("doc_id"))
c2 = sets(pd.read_csv(f"{LAB}/test_labels_coder2.csv").set_index("doc_id"))
ids = list(R)
for name, X, Y in [("reviewer-coder1", R, c1), ("reviewer-coder2", R, c2), ("coder1-coder2", c1, c2)]:
    used = [c for c in CATS if any(c in X[d] or c in Y[d] for d in ids)]
    print(name, f"exact {sum(X[d] == Y[d] for d in ids)}/{len(ids)}", " ".join(f"{c}:{kappa(X, Y, ids, c):.2f}" for c in used))
common = [d for d in c1 if d in c2]
print("coder1-coder2 all items", len(common), "exact", sum(c1[d] == c2[d] for d in common))
for d in ids:
    if not R[d] == c1[d] == c2[d]:
        print(" ", d, "reviewer", sorted(R[d]), "coder1", sorted(c1[d]), "coder2", sorted(c2[d]))
