"""Draw the stratified labelling sample (dev and held-out test sets), fixed seed.

Usage: python3 scripts/disclosures/sample_labels.py [--round 2]
Round 2 draws a fresh held-out set ("test2", 150 statements, seed + 2) excluding
every round-1 id; it validates classifier v2, which was developed on round 1.
Writes results/disclosures/labels/sample.csv (doc_id, set, stratum; no text) and
data/disclosures/label_sheet_{dev,test}.csv (with text, git-ignored) for reading.
Strata are defined by surface features only (no classifier output), so the sample
does not depend on the classifier being evaluated.
"""
from __future__ import annotations

import os
import re

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SEED = 20271015
STRATA = {  # stratum: (test n, dev n)
    "template_heavy": (15, 5), "negation_heavy": (20, 6), "short": (15, 5), "long": (15, 5),
    "drafting_cue": (20, 6), "coding_cue": (15, 5), "literature_cue": (15, 5), "global_none": (15, 6),
    "tool_named": (10, 4), "suspect_tier": (10, 3), "random": (30, 10),
}


ROUND2 = {  # stratum: test2 n
    "template_heavy": 12, "negation_heavy": 16, "short": 12, "long": 12, "drafting_cue": 18, "coding_cue": 12,
    "literature_cue": 12, "global_none": 15, "tool_named": 8, "suspect_tier": 8, "random": 25,
}


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--round", type=int, default=1)
    rnd = ap.parse_args().round
    df = pd.read_parquet(os.path.join(ROOT, "data", "disclosures", "iclr2027.parquet"))
    df = df[df.found == True].reset_index(drop=True)  # noqa: E712
    att = pd.read_parquet(os.path.join(ROOT, "data", "disclosures", "attribution.parquet"))
    df = df.merge(att[["doc_id", "template_share"]], on="doc_id", how="left")
    t = df.text_clean.str.lower()
    neg_sent = t.apply(lambda s: sum(bool(re.search(r"\bnot\b|not applicable|\bno\b", x)) for x in re.split(r"(?<=[.!?])\s+", s)))
    clean = df.tier == "clean"
    masks = {
        "template_heavy": clean & (df.template_share >= 0.5),
        "negation_heavy": clean & (neg_sent >= 2),
        "short": clean & (df.n_words < 35),
        "long": clean & (df.n_words > 200),
        "drafting_cue": clean & t.str.contains(r"draft|rewrit|rephras|wrote|writing of (?:the )?(?:paper|manuscript|sections)|generate (?:the )?text"),
        "coding_cue": clean & t.str.contains(r"\bcode\b|coding|debug|implement|script"),
        "literature_cue": clean & t.str.contains(r"literature|related work|search"),
        "global_none": clean & t.str.contains(r"\bno (?:generative )?(?:ai|llms?|large language)|did not use any|have not used any|were not used in (?:the )?(?:preparation|writing|this)|not use (?:any )?(?:generative )?ai"),
        "tool_named": clean & t.str.contains(r"chatgpt|gpt-?\d|claude|gemini|codex|copilot|cursor|deepseek|qwen"),
        "suspect_tier": df.tier == "suspect",
        "random": clean,
    }
    if rnd == 2:
        prev = pd.read_csv(os.path.join(ROOT, "results", "disclosures", "labels", "sample.csv"))
        taken = set(prev.doc_id)
        rows = []
        for k, n in ROUND2.items():
            pick = df[masks[k] & ~df.doc_id.isin(taken)].sample(n, random_state=SEED + 2)
            taken.update(pick.doc_id)
            rows += [{"doc_id": d, "set": "test2", "stratum": k} for d in pick.doc_id]
        s = pd.DataFrame(rows)
        s.to_csv(os.path.join(ROOT, "results", "disclosures", "labels", "sample_round2.csv"), index=False)
        full = s.merge(df[["doc_id", "text_clean", "n_words", "tier"]], on="doc_id").sample(frac=1, random_state=5)
        full.to_csv(os.path.join(ROOT, "data", "disclosures", "label_sheet_test2.csv"), index=False)
        print(s.stratum.value_counts())
        return
    taken: set[str] = set()
    rows = []
    for which, idx in (("test", 0), ("dev", 1)):
        for k, ns in STRATA.items():
            pool = df[masks[k] & ~df.doc_id.isin(taken)]
            pick = pool.sample(ns[idx], random_state=SEED + idx)
            taken.update(pick.doc_id)
            rows += [{"doc_id": d, "set": which, "stratum": k} for d in pick.doc_id]
    s = pd.DataFrame(rows)
    s.to_csv(os.path.join(ROOT, "results", "disclosures", "labels", "sample.csv"), index=False)
    full = s.merge(df[["doc_id", "text_clean", "n_words", "tier"]], on="doc_id")
    for which in ("dev", "test"):
        full[full.set == which].to_csv(os.path.join(ROOT, "data", "disclosures", f"label_sheet_{which}.csv"), index=False)
    print(s.groupby(["set", "stratum"]).size().unstack(0))


if __name__ == "__main__":
    main()
