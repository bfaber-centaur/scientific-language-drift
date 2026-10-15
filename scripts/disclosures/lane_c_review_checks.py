"""Lane C follow-up checks requested by the Lane D review (docs/v1.5-review.md, C1-C4, Gate 3 verdict (c)).

Usage: python3 scripts/disclosures/lane_c_review_checks.py [--boot 500] [--perm 500]

Added after the Lane C results were seen; these are robustness checks, not part of the preregistration.

  C1  overlap with and without disclosures that overran into bibliography / ethics text
      -> results/disclosures/lane_c_overlap_c1.csv
  C2  primary effects corrected for drafting precision between .71 and .86, assuming the false drafting
      labels come from other_use (whose contrast with polish_only is the s1 estimate)
      -> results/disclosures/lane_c_label_error.csv
  C3  drafting / polish_only papers per topic cluster, clusters with < 30 in either group flagged, and the
      primary contrast without them -> results/disclosures/lane_c_topic_cells.csv, lane_c_robustness.csv
  C4  cluster bootstrap that resamples disclosure near-duplicate clusters (MinHash, as in phrases.py) as units
      -> lane_c_robustness.csv
  (c) primary contrast on papers where the classifier and the statement's surface wording agree
      -> lane_c_robustness.csv
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from lane_c_analysis import FEATURES, adj_beta, contrast, dummies, overlap, pooled_sd  # noqa: E402
from mlngrams.disclosures import _BIB_LINE  # noqa: E402
from mlngrams.tokenize import tokenize  # noqa: E402
from phrases import minhash_clusters  # noqa: E402

DATA = os.path.join(ROOT, "data", "disclosures")
OUT = os.path.join(ROOT, "results", "disclosures")
SEED = 20271016
AI_OR_AUTHOR = re.compile(r"\b(?:ai|llms?|language models?|generative|chatgpt|gpt[-\w.]*|claude|gemini|codex|copilot|assist\w*|"
                          r"agents?|tools?|authors?|we|our|us|responsib\w*)\b", re.I)
BIB_INLINE = re.compile(r"arXiv(?: preprint|:\d)|In Proceedings|Conference on [A-Z]|Advances in Neural|\bdoi:", re.I)
DRAFT_CUE = re.compile(r"\bdraft\w*|\brewrit\w*|\bwr(?:ite|iting|itten|ote) (?:parts?|sections?|portions?|paragraphs?|the (?:paper|manuscript|text))", re.I)
POLISH_CUE = re.compile(r"polish|grammar|proofread|readab|language (?:edit|refine|improve)|wording|spelling|typo", re.I)


def overran(text: str, text_clean: str) -> bool:
    if _BIB_LINE.search(text or "") or BIB_INLINE.search(text_clean or ""):
        return True
    sents = [s for s in re.split(r"(?<=[.!?])\s+", text_clean or "") if s.strip()]
    return len(sents) >= 4 and not any(AI_OR_AUTHOR.search(s) for s in sents[-3:])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--boot", type=int, default=500)
    ap.add_argument("--perm", type=int, default=500)
    args = ap.parse_args()
    rng = np.random.default_rng(SEED)
    df = pd.read_parquet(os.path.join(DATA, "lane_c_papers.parquet"))
    for f in FEATURES:
        df[f] = df[f].astype(float)
    disc = pd.read_parquet(os.path.join(DATA, "iclr2027.parquet"), columns=["doc_id", "text", "text_clean"])
    df = df.merge(disc, on="doc_id", how="left")
    z = np.load(os.path.join(DATA, "lane_c_types.npz"))

    # C1
    df["overran"] = [overran(t, c) for t, c in zip(df.text, df.text_clean)]
    print("overran:", int(df.overran.sum()), round(df.overran.mean(), 4), flush=True)
    ov_all = overlap(df, z, rng).assign(subset="all papers")
    ov_keep = overlap(df, z, rng, keep=~df.overran.to_numpy()).assign(subset="overrun disclosures excluded")
    pd.concat([ov_all, ov_keep]).round(5).to_csv(os.path.join(OUT, "lane_c_overlap_c1.csv"), index=False)
    print(pd.concat([ov_all, ov_keep])[["subset", "measure", "group", "papers", "enrichment_own_minus_matched", "ci_lo", "ci_hi"]].round(4).to_string(), flush=True)

    # C2
    c = pd.read_csv(os.path.join(OUT, "lane_c_contrasts.csv"))
    prim = c[c.contrast == "primary"].set_index("feature").d_adj
    s1 = c[c.contrast == "s1"].set_index("feature").d_adj
    rows = []
    for f in FEATURES:
        r = {"feature": f, "d_obs": prim[f], "d_other_vs_polish": s1[f]}
        for P in (0.71, 0.78, 0.86, 1.0):
            r[f"d_true_if_P{P:.2f}"] = (prim[f] - (1 - P) * s1[f]) / P
        rows.append(r)
    pd.DataFrame(rows).round(4).to_csv(os.path.join(OUT, "lane_c_label_error.csv"), index=False)
    print(pd.DataFrame(rows).round(3).to_string(), flush=True)

    # C3
    cells = pd.crosstab(df.topic, df.group)[["drafting", "polish_only"]]
    cells["flag_lt30"] = (cells.min(axis=1) < 30)
    tp = pd.read_csv(os.path.join(OUT, "lane_c_topics.csv")).set_index("topic")
    cells = cells.join(tp.top_terms)
    cells.to_csv(os.path.join(OUT, "lane_c_topic_cells.csv"))
    small = set(cells.index[cells.flag_lt30])
    print("topic clusters with < 30 in a group:", sorted(small), flush=True)

    rob = []

    def add(label, res):
        for _, r in res.iterrows():
            rob.append({"check": label, "feature": r.feature, "n_drafting": r.n_a, "n_polish_only": r.n_b,
                        "d_adj": r.d_adj, "ci_lo": r.d_adj_lo, "ci_hi": r.d_adj_hi, "p_perm": r.p_perm, "q_bh": r.q_bh})

    add("C3: drop topic clusters with < 30 papers in either group",
        contrast(df[~df.topic.isin(small)].reset_index(drop=True), "group", "drafting", "polish_only", args.boot, args.perm, rng, "c3"))

    # (c) surface-cue agreement
    cue = ((df.group == "drafting") & df.text_clean.str.contains(DRAFT_CUE)) | \
          ((df.group == "polish_only") & df.text_clean.str.contains(POLISH_CUE) & ~df.text_clean.str.contains(DRAFT_CUE))
    add("(c): classifier and surface wording agree",
        contrast(df[cue | ~df.group.isin(["drafting", "polish_only"])].reset_index(drop=True), "group", "drafting", "polish_only", args.boot, args.perm, rng, "cue"))

    # C4: cluster bootstrap over disclosure near-duplicate clusters.
    sh = []
    for t in df.text:
        s = set()
        for seg in tokenize(t or ""):
            for j in range(len(seg) - 4):
                s.add(int.from_bytes(hashlib.blake2b(" ".join(seg[j : j + 5]).encode(), digest_size=7).digest(), "little"))
        sh.append(s)
    df["dup_cluster"] = minhash_clusters(sh)
    sub = df[df.group.isin(["drafting", "polish_only"])].reset_index(drop=True)
    x = (sub.group == "drafting").to_numpy(float)
    Y = sub[FEATURES].to_numpy(float)
    D = dummies(sub)
    beta = adj_beta(D, x, Y) / pooled_sd(Y, x)
    groups = sub.groupby("dup_cluster").indices
    keys = list(groups)
    bs = np.empty((args.boot, len(FEATURES)))
    for k in range(args.boot):
        pick = rng.integers(0, len(keys), len(keys))
        i = np.concatenate([groups[keys[j]] for j in pick])
        bs[k] = adj_beta(D[i], x[i], Y[i]) / pooled_sd(Y[i], x[i])
    for j, f in enumerate(FEATURES):
        rob.append({"check": "C4: cluster bootstrap (near-duplicate disclosure clusters as units)", "feature": f,
                    "n_drafting": int(x.sum()), "n_polish_only": int((1 - x).sum()), "d_adj": beta[j],
                    "ci_lo": np.percentile(bs[:, j], 2.5), "ci_hi": np.percentile(bs[:, j], 97.5),
                    "clusters": len(keys)})
    out = pd.DataFrame(rob)
    out.round(5).to_csv(os.path.join(OUT, "lane_c_robustness.csv"), index=False)
    print(out.round(3).to_string(), flush=True)


if __name__ == "__main__":
    main()
