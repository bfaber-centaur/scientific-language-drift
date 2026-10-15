"""Lane C (V2): cohort rates, V1/added decomposition, per-paper distributions, cross-venue tables.

Input: per-paper counts from scripts/v2/lane_c_count.py (data/v2/lane_c/counts/*.csv.gz), Gate 0's
membership table and version labels (data/v2/version/2c0dd19/*.parquet, scripts/v2/version_mix.py),
and titles read from the clean parquet files. Output: results/v2/function_words/*.csv.
The ICLR-overlap flag (non-ICLR papers that also appear at ICLR) is the union of exact normalized-title
matches and Lane E's text-matched pairs (docs/v2-adversarial-review.md D3).

Exclusions (V1 rules, docs/corpus.md): texts under 2,000 characters, exact duplicate text_sha256
(first paper_id kept), and the ICLR 2025 title-slug stratum (paper_id containing "-" or longer than 12
characters; Gate 0 item 4 and "Coverage limitations").

Rates are pooled: occurrences per million alphabetic tokens, summed over papers. 95% intervals are
percentile intervals from 400 Poisson-weighted paper bootstraps (the paper is the unit).
"""
from __future__ import annotations

import glob
import os
import re
import sys

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lane_c_fetch import fetch, expected, V2  # noqa: E402
from lane_c_count import WORDS, BIGRAMS  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "results/v2/function_words")
HEAD = ["of", "in", "we", "and"]
BIG = ["_".join(b) for b in BIGRAMS]
CONS = ["sentences", "comma_and", "we_initial", "passive", "hyph_compound", "possessive", "the_x_of", "em_dash", "chars_alpha_tok"]
B = 400


def norm_title(t):
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(t).lower()).split())


def load() -> pd.DataFrame:
    df = pd.concat([pd.read_csv(p) for p in sorted(glob.glob(os.path.join(ROOT, "data/v2/lane_c/counts/*.csv.gz")))],
                   ignore_index=True)
    df = df.rename(columns={"conference": "venue"})
    mem = pd.read_csv(os.path.join(ROOT, "results/v2/inventory/membership.csv.gz"))
    df = df.merge(mem, on=["venue", "year", "paper_id"], how="left")
    ver = pd.concat([pd.read_parquet(p) for p in glob.glob(os.path.join(ROOT, "data/v2/version/2c0dd19/*.parquet"))])
    df = df.merge(ver[["pdf_sha256", "version"]].drop_duplicates("pdf_sha256"), on="pdf_sha256", how="left")
    titles = []
    for p in sorted(x for x in expected(V2) if x.startswith("clean/")):
        t = pq.read_table(fetch(p), columns=["paper_id", "conference", "year", "title"]).to_pandas()
        titles.append(t.rename(columns={"conference": "venue"}))
    titles = pd.concat(titles)
    titles["ntitle"] = titles.title.map(lambda t: norm_title(t) if isinstance(t, str) else None)
    df = df.merge(titles[["paper_id", "venue", "year", "ntitle"]], on=["paper_id", "venue", "year"], how="left")
    # exclusions
    allrow = df[df.region == "all"].sort_values("paper_id")
    keep = allrow[allrow.text_chars >= 2000].drop_duplicates("text_sha256")
    keep = keep[~((keep.venue == "iclr") & (keep.year == 2025) &
                  (keep.paper_id.str.contains("-") | (keep.paper_id.str.len() > 12)))]
    df = df[df.pdf_sha256.isin(set(keep.pdf_sha256))].copy()
    df["version"] = df.version.fillna("unknown")
    # cross-venue overlap flag: a title that also appears in another venue-year (titles >= 25 chars)
    t = titles.dropna(subset=["ntitle"])
    t = t[t.ntitle.str.len() >= 25]
    t["vy"] = t.venue + "-" + t.year.astype(str)
    multi = t.groupby("ntitle").vy.nunique()
    shared = set(multi[multi > 1].index)
    df["iclr_overlap"] = False
    iclr_titles = set(t[t.venue == "iclr"].ntitle)
    df.loc[(df.venue != "iclr") & df.ntitle.isin(iclr_titles), "iclr_overlap"] = True
    df["cross_overlap"] = df.ntitle.isin(shared)
    # Lane E D3: exact titles miss about a fifth of the overlap; add Lane E's text-matched pairs
    # (results/v2/review/e4_textpairs_*.csv) so the exclusion is the union of title and text matches.
    text_ids = set()
    for f in glob.glob(os.path.join(ROOT, "results/v2/review/e4_textpairs_*.csv")):
        a, b = os.path.basename(f)[len("e4_textpairs_"):-4].split("_")
        e = pd.read_csv(f)
        for stem, col in ((a, "a_id"), (b, "b_id")):
            if not stem.startswith("iclr"):
                v, y = stem.split("-")
                text_ids |= {(v, int(y), i) for i in e[col]}
    key = list(zip(df.venue, df.year, df.paper_id))
    df.loc[[k in text_ids for k in key], "iclr_overlap"] = True
    return df


def pooled(g: pd.DataFrame, cols, rng) -> dict:
    tok = g.tokens.to_numpy(float)
    X = g[cols].to_numpy(float)
    est = X.sum(0) / tok.sum() * 1e6
    W = rng.poisson(1.0, size=(B, len(g))).astype(float)
    bs = (W @ X) / (W @ tok)[:, None] * 1e6
    lo, hi = np.percentile(bs, [2.5, 97.5], axis=0)
    return est, lo, hi, bs


def cohort_table(df, by, cols, rng, stratum=""):
    rows = []
    for key, g in df.groupby(by):
        if len(g) < 30:
            continue
        est, lo, hi, _ = pooled(g, cols, rng)
        r = dict(zip(by, key if isinstance(key, tuple) else (key,)))
        r.update(stratum=stratum, n_papers=len(g), tokens=int(g.tokens.sum()))
        for i, c in enumerate(cols):
            r[c] = round(est[i], 1)
            if c in HEAD:
                r[c + "_lo"], r[c + "_hi"] = round(lo[i], 1), round(hi[i], 1)
        r["paper_median_of"] = round((g["of"] / g.tokens * 1e6).median(), 1)
        rows.append(r)
    return pd.DataFrame(rows)


def main():
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(20261015)
    df = load()
    df.to_pickle(os.path.join(ROOT, "data/v2/lane_c/merged.pkl"))
    cols = WORDS + BIG + CONS
    by = ["venue", "year", "version", "region"]

    # 1. every venue-year-version-region (the master table)
    t = cohort_table(df, by, cols, rng, "all_records")
    t2 = cohort_table(df, ["venue", "year", "region"], cols, rng, "all_versions")
    t2["version"] = "all"
    master = pd.concat([t, t2], ignore_index=True)
    master.to_csv(os.path.join(OUT, "rates_by_cohort.csv"), index=False)

    # 2. ICLR 2024-2026: V1 records vs added records (P4)
    ic = df[(df.venue == "iclr") & df.year.between(2024, 2027)]
    parts = []
    for name, sub in (("all", ic), ("v1_retained", ic[ic.status == "retained"]), ("added", ic[ic.status == "added"])):
        x = cohort_table(sub, ["year", "region"], HEAD + ["the", "a", "to"], rng, name)
        y = cohort_table(sub[sub.version == "submission"], ["year", "region"], HEAD + ["the", "a", "to"], rng, name)
        x["version"], y["version"] = "all", "submission"
        parts += [x, y]
    pd.concat(parts).to_csv(os.path.join(OUT, "iclr_v1_vs_added.csv"), index=False)

    # 3. ICML/TMLR/COLM with and without papers whose title also appears at ICLR
    nonic = df[df.venue.isin(["icml", "tmlr", "colm", "neurips"])]
    parts = []
    for name, sub in (("with_iclr_overlap", nonic), ("without_iclr_overlap", nonic[~nonic.iclr_overlap]),
                      ("iclr_overlap_only", nonic[nonic.iclr_overlap])):
        parts.append(cohort_table(sub, ["venue", "year", "version", "region"], HEAD, rng, name))
    pd.concat(parts).to_csv(os.path.join(OUT, "nonclr_overlap_sensitivity.csv"), index=False)

    # 4. per-paper distributions of the four headline rates (quantiles)
    q = []
    for key, g in df[df.region.isin(["abstract", "intro600", "prose"])].groupby(by):
        if len(g) < 30:
            continue
        g = g[g.tokens >= 50]
        for w in HEAD:
            r = g[w] / g.tokens * 1e6
            q.append(dict(zip(by, key), word=w, n=len(g), **{f"q{int(p*100):02d}": round(r.quantile(p), 1)
                                                         for p in (0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95)},
                          share_zero=round((g[w] == 0).mean(), 4)))
    pd.DataFrame(q).to_csv(os.path.join(OUT, "per_paper_quantiles.csv"), index=False)
    print("done", len(df))


if __name__ == "__main__":
    main()
