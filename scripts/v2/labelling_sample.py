"""Lane D (V2): draw the hand-labelling sample of AI-use statements for a human labeller (Bobby).

Usage:
    python3 scripts/v2/labelling_sample.py            # writes the sample and the form data

Sample (seed 20261015), 45 items:
  A  15 ICLR 2027 statements from the held-out test2 set, which already carry Claude coder-1 labels
     (results/disclosures/labels/test2_labels.csv): the overdue human spot check of V1.5 labels.
     Stratified over coder-1 groups (5 drafting, 4 polish_only, 4 other_use, 2 none/unknown).
  B  15 ICLR 2026 statements (V2 tier, random): the classifier has never been checked on 2026 wording.
  C  6 COLM 2026 and 4 ICML 2026 statements (random): other venues.
  D  5 in-text sentences from papers with no statement section (ICLR 2026, COLM 2026, ICML 2026):
     are they author disclosures at all?
Outputs:
  results/v2/disclosures/labelling/sample.csv     ids, part, cohort and the provisional machine labels
                                                  (classifier v2 group, V2 stance) to compare against;
                                                  no statement text
  data/v2/labelling/items.json                    the statement texts for the labelling page (git-ignored)
"""
from __future__ import annotations

import json
import re
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts", "disclosures"))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pandas as pd  # noqa: E402

from disclosures_analyze_v2 import load, paper_stance, stances  # noqa: E402
from eval_groups import group  # noqa: E402

SEED = 20261015


def main():
    d = load(os.path.join(ROOT, "data", "v2", "disclosures"))
    clean = d[d.tier_v2 == "clean"]
    parts = []

    lab = pd.read_csv(os.path.join(ROOT, "results", "disclosures", "labels", "test2_labels.csv"))
    lab["coder1_group"] = lab.labels.fillna("").map(lambda s: group(set(x for x in s.split(";") if x)))
    lab = lab.merge(clean[clean.cohort == "iclr-2027"][["doc_id"]], on="doc_id")
    quota = {"drafting": 5, "polish_only": 4, "other_use": 4}
    a = [lab[lab.coder1_group == g].sample(k, random_state=SEED) for g, k in quota.items()]
    a.append(lab[lab.coder1_group.isin(["none", "unknown"])].sample(2, random_state=SEED))
    a = pd.concat(a)[["doc_id", "labels", "coder1_group"]].rename(columns={"labels": "coder1_labels"})
    a = a.merge(clean[clean.cohort == "iclr-2027"], on="doc_id")
    parts.append(a.assign(part="A"))
    parts.append(clean[clean.cohort == "iclr-2026"].sample(15, random_state=SEED).assign(part="B"))
    parts.append(clean[clean.cohort == "colm-2026"].sample(6, random_state=SEED).assign(part="C"))
    parts.append(clean[clean.cohort == "icml-2026"].sample(4, random_state=SEED).assign(part="C"))
    s = pd.concat(parts, ignore_index=True)
    s["text_shown"] = s.text_clean
    nf = d[(d.found != True) & (d.inline_n > 0) & d.cohort.isin(["iclr-2026", "colm-2026", "icml-2026"])]  # noqa: E712
    dd = nf.sample(5, random_state=SEED).assign(part="D")
    dd["text_shown"] = dd.inline_example
    s = pd.concat([s, dd], ignore_index=True)
    s["stance_v2"] = [paper_stance(stances(t)) if p != "D" else None for t, p in zip(s.text_shown, s.part)]
    s = s.sample(frac=1, random_state=SEED).reset_index(drop=True)  # shuffle so parts are not blocked
    s["item"] = [f"L{i + 1:02d}" for i in range(len(s))]
    out = os.path.join(ROOT, "results", "v2", "disclosures", "labelling")
    os.makedirs(out, exist_ok=True)
    s[["item", "part", "cohort", "doc_id", "version", "cls_group", "cls_labels", "stance_v2", "coder1_labels", "coder1_group"]].to_csv(
        os.path.join(out, "sample.csv"), index=False)
    os.makedirs(os.path.join(ROOT, "data", "v2", "labelling"), exist_ok=True)
    items = [{"item": r.item, "venue": r.cohort.split("-")[0].upper().replace("NEURIPS", "NeurIPS"), "year": int(r.cohort.split("-")[1]),
              "kind": "sentence" if r.part == "D" else "statement", "text": " ".join(re.sub(r"⟦[^⟧]*⟧", " ", str(r.text_shown)).split())} for r in s.itertuples()]
    json.dump(items, open(os.path.join(ROOT, "data", "v2", "labelling", "items.json"), "w"), indent=1, ensure_ascii=False)
    print(s.part.value_counts().to_string())


if __name__ == "__main__":
    main()
