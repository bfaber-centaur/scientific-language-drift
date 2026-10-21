"""V2 disclosures: draw the larger judge sample (300 statements) for the model-reader comparison.

Clean-tier (V2 tier) statements from the 2026-written cohorts, excluding papers already in the 45-item
labelling sample, seed 20261021. Quotas: ICLR 2027 100, ICLR 2026 100, COLM 2026 40, ICML 2026 40,
TMLR 2026 20. The text shown is `text_clean`, cut to 3,000 characters.

Usage: python3 scripts/v2/judge_sample.py [data/v2/disclosures]

Writes results/v2/disclosures/judges/sample.csv (ids and machine labels, no text) and
data/v2/judges/items.json (item texts; git-ignored).
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts", "disclosures"))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pandas as pd  # noqa: E402

from disclosures_analyze_v2 import paper_stance, stances, tier_v2  # noqa: E402

SEED = 20261021
QUOTA = {"iclr-2027": 100, "iclr-2026": 100, "colm-2026": 40, "icml-2026": 40, "tmlr-2026": 20}


def main():
    data = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data", "v2", "disclosures")
    prev = set(pd.read_csv(os.path.join(ROOT, "results", "v2", "disclosures", "labelling", "sample.csv")).doc_id)
    parts = []
    for cohort, k in QUOTA.items():
        d = pd.read_parquet(os.path.join(data, f"{cohort}.parquet"))
        d["cohort"] = cohort
        d["tier_v2"] = tier_v2(d)
        c = d[(d.tier_v2 == "clean") & ~d.doc_id.isin(prev)]
        parts.append(c.sample(k, random_state=SEED))
    s = pd.concat(parts, ignore_index=True).sample(frac=1, random_state=SEED).reset_index(drop=True)
    s["item"] = [f"J{i + 1:03d}" for i in range(len(s))]
    s["text_shown"] = s.text_clean.str.slice(0, 3000)
    s["truncated"] = s.text_clean.str.len() > 3000
    s["stance_v2"] = [paper_stance(stances(t)) for t in s.text_shown]
    s["part"] = "J"
    out = os.path.join(ROOT, "results", "v2", "disclosures", "judges")
    os.makedirs(out, exist_ok=True)
    s[["item", "part", "cohort", "doc_id", "cls_group", "cls_labels", "stance_v2", "n_words", "truncated"]].to_csv(
        os.path.join(out, "sample.csv"), index=False)
    items = os.path.join(ROOT, "data", "v2", "judges")
    os.makedirs(items, exist_ok=True)
    venue = {"iclr": "ICLR", "colm": "COLM", "icml": "ICML", "tmlr": "TMLR"}
    rows = [{"item": r.item, "venue": venue[r.cohort.split("-")[0]], "year": int(r.cohort.split("-")[1]),
             "kind": "statement", "text": r.text_shown} for r in s.itertuples()]
    json.dump(rows, open(os.path.join(items, "items.json"), "w"), indent=1, ensure_ascii=False)
    print(s.groupby("cohort").size().to_string(), "\ntruncated", int(s.truncated.sum()))


if __name__ == "__main__":
    main()
