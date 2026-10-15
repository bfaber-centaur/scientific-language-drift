"""Lane B (V2 replication): per-venue trajectories from per-paper features, by version and membership.

Usage:
    python3 scripts/v2/venue_replication.py [--features data/v2/replication/features] [--boot 500]

Inputs: per-paper target counts (scripts/v2/paper_features.py) and flags
(results/v2/replication/flags_v2.csv.gz). Papers flagged short/template are dropped and exact duplicate
texts (same text_sha256) are kept once, first by year, as in count_ngrams.py.

Writes results/v2/replication/venues/:
    venue_metrics.csv   venue, year, group, papers, metric, value, lo, hi (95% paper bootstrap)
        groups: all | published | under_review | v1 (records present in V1) | added |
                published_no_overlap (published, and neither title-matched to an ICLR record of the
                same or previous year nor in Agent E's text-matched pairs, results/v2/review/e4_textpairs_*) | under_review_no_overlap
        metrics: prev:<target> (share of papers containing it), pm:<target> (per million positions,
                pooled), stop_share (pooled), stop_share_mean500 and of_the_pm_mean500 (V1 style-check
                definitions: per-paper means over papers with >= 500 body tokens), mean_word_len
    style_check_v1_vs_v2.csv  V1's results/style_shift_checks.csv rows next to the same statistic on
                the V1 records (complete, not a sample) and on the V2 published cohort
Only aggregates are written.
"""
from __future__ import annotations

import argparse
import glob
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "results", "v2", "replication", "venues")
sys.path.insert(0, HERE)

from paper_features import TARGETS  # noqa: E402

HEADLINE = ["of", "in", "we", "and", "the", "of the", "can be", "delve", "underscores", "intricate", "pivotal",
            "showcasing", "realm", "notably", "furthermore", "leverage", "we propose", "a novel",
            "in this paper", "test whether", "held fixed", "results support", "percentage points",
            "across diverse"]
STYLE_PHRASES = ["delve", "underscores", "showcasing", "pivotal", "we propose", "in this paper", "crucial role",
                 "across diverse", "notably", "furthermore"]


def load(features: str) -> pd.DataFrame:
    fl = pd.read_csv(os.path.join(ROOT, "results", "v2", "replication", "flags_v2.csv.gz"), keep_default_na=False)
    parts = [pd.read_parquet(f) for f in sorted(glob.glob(os.path.join(features, "*", "*.parquet")))]
    d = pd.concat(parts, ignore_index=True)
    d = d.merge(fl[["venue", "year", "doc_id", "version", "member", "iclr_overlap", "exclude", "id_stratum"]],
                on=["venue", "year", "doc_id"], how="left", validate="one_to_one")
    d = d[d.exclude == ""]
    d = d.sort_values(["venue", "year", "doc_id"]).drop_duplicates(["venue", "text_sha256"], keep="first")
    d["iclr_overlap"] = d.iclr_overlap.astype(str) == "True"
    # Agent E (D3): title matching misses about a fifth of the overlap; add the text-matched pairs
    # (results/v2/review/e4_textpairs_iclr-*_<venue>-<year>.csv, column b_id = the non-ICLR record)
    tp = []
    for f in glob.glob(os.path.join(ROOT, "results", "v2", "review", "e4_textpairs_*.csv")):
        a, b = os.path.basename(f)[len("e4_textpairs_"):-4].split("_")
        for side, col in ((a, "a_id"), (b, "b_id")):
            v, y = side.rsplit("-", 1)
            if v != "iclr":
                ids = pd.read_csv(f, usecols=[col])[col]
                tp.append(pd.DataFrame({"venue": v, "year": int(y), "doc_id": ids}))
    if tp:
        tp = pd.concat(tp).drop_duplicates()
        key = set(zip(tp.venue, tp.year, tp.doc_id))
        d["iclr_overlap"] = d.iclr_overlap | np.array([k in key for k in zip(d.venue, d.year, d.doc_id)])
    return d


def groups(d: pd.DataFrame):
    yield "all", d
    yield "published", d[d.version == "published"]
    yield "under_review", d[d.version == "under_review"]
    yield "v1", d[d.member == "v1"]
    yield "added", d[d.member == "added"]
    yield "published_no_overlap", d[(d.version == "published") & ~d.iclr_overlap]
    yield "under_review_no_overlap", d[(d.version == "under_review") & ~d.iclr_overlap]


def pos_col(t: str) -> str:
    return "pos%d" % (t.count(" ") + 1)


def cell(g: pd.DataFrame, boot: int, rng) -> list[dict]:
    n = len(g)
    rows = []
    idx = rng.integers(0, n, size=(boot, n)) if boot and n >= 20 else None

    def add(metric, num, den=None, headline=True):
        num = np.asarray(num, float)
        if den is None:  # mean of per-paper values
            v = num.mean()
            bs = num[idx].mean(1) if (idx is not None and headline) else None
        else:
            den = np.asarray(den, float)
            v = num.sum() / den.sum()
            bs = num[idx].sum(1) / den[idx].sum(1) if (idx is not None and headline) else None
        lo, hi = (np.percentile(bs, [2.5, 97.5]) if bs is not None else (np.nan, np.nan))
        rows.append({"metric": metric, "value": v, "lo": lo, "hi": hi})

    for t in TARGETS:
        hl = t in HEADLINE
        add("prev:" + t, (g["c:" + t] > 0).astype(float), headline=hl)
        add("pm:" + t, 1e6 * g["c:" + t], g[pos_col(t)], headline=hl)
    add("stop_share", g.stop_tokens, g.tokens)
    add("mean_word_len", g.letters, g.words_alpha)
    m = g[g.tokens >= 500]
    if len(m):
        add("stop_share_mean500", m.stop_tokens / m.tokens, headline=False)
        add("of_the_pm_mean500", 1e6 * m["c:of the"] / m.pos2.clip(lower=1), headline=False)
        for p in STYLE_PHRASES:
            add("prev500:" + p, (m["c:" + p] > 0).astype(float), headline=False)
    for r in rows:
        r["papers"] = n
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", default=os.path.join(ROOT, "data", "v2", "replication", "features"))
    ap.add_argument("--boot", type=int, default=500)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    d = load(a.features)
    rng = np.random.default_rng(20261015)
    rows = []
    for (venue, year), vy in d.groupby(["venue", "year"]):
        for gname, g in groups(vy):
            if len(g) == 0:
                continue
            for r in cell(g, a.boot, rng):
                rows.append({"venue": venue, "year": year, "group": gname, **r})
        print(venue, year, len(vy), flush=True)
    m = pd.DataFrame(rows)[["venue", "year", "group", "papers", "metric", "value", "lo", "hi"]]
    m.to_csv(os.path.join(OUT, "venue_metrics.csv"), index=False, float_format="%.6g")

    # V1 cross-venue style checks vs the same statistic on V1 records (all) and V2 published
    sc = pd.read_csv(os.path.join(ROOT, "results", "style_shift_checks.csv"))
    sc = sc[sc.config == "omissions"]
    stat = {"stop_share": "stop_share_mean500", "of_the_pm": "of_the_pm_mean500"}
    stat.update({"prev_" + p.replace(" ", "_"): "prev500:" + p for p in STYLE_PHRASES})
    out = []
    piv = m.set_index(["venue", "year", "group", "metric"])
    for r in sc.itertuples():
        for col, met in stat.items():
            if col not in sc.columns:
                continue
            rec = {"venue": r.venue, "year": r.year, "statistic": col, "v1_sample_papers": r.papers,
                   "v1_sample_value": getattr(r, col)}
            for g in ("v1", "published", "published_no_overlap", "all"):
                k = (r.venue, r.year, g, met)
                rec[g + "_value"] = piv.value.get(k, np.nan)
                rec[g + "_papers"] = piv.papers.get(k, np.nan)
            out.append(rec)
    pd.DataFrame(out).to_csv(os.path.join(OUT, "style_check_v1_vs_v2.csv"), index=False, float_format="%.6g")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
