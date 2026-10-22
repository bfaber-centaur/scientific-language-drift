"""V4: ICLR 2017-2026 sub-areas: size, team size and abstract style per topic and per primary area.

Inputs: Paper Copilot paperlists (same files and commit as V3, scripts/v3/review_meta.py) for title,
abstract, keywords and primary area; data/v3/review_meta.parquet for author counts, decisions and
ratings. Topics are the fixed keyword tags of scripts/v4/topics.py on title + abstract (+ keywords),
the same tags used on arXiv. Abstract features reuse scripts/v4/arxiv_features.features.

Writes results/v4/iclr/{topic_year.csv, area_year.csv, topic_period.csv, topic_change.csv (2017-19 vs 2025-26),
topic_change_2023_2026.csv, area_change.csv (2025 vs 2026; 2024 used a different area list),
topic_style_year.csv}; topic tables also with suffix _title (title-only tags).

Usage: python3 scripts/v4/iclr_subareas.py --src ~/ext/paperlists
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
sys.path.insert(0, HERE)
from arxiv_features import features  # noqa: E402
from topics import TOPICS, tag  # noqa: E402

OUT = os.path.join(ROOT, "results", "v4", "iclr")
STYLE = ["w_of", "w_in", "w_we", "w_our", "w_and", "hype", "llm_marker", "self_mention", "hedge", "nominal"]


def team_stats(g: pd.DataFrame) -> pd.Series:
    a = g.n_authors.dropna()
    dec = g.accepted.dropna()
    return pd.Series({"papers": len(g), "mean_authors": a.mean(), "median_authors": a.median(),
                      "mean_log2_authors": np.log2(a).mean(), "solo_share": (a == 1).mean(),
                      "small_share_le2": (a <= 2).mean(), "big_share_ge9": (a >= 9).mean(),
                      "accept_rate": dec.mean() if len(dec) else np.nan, "rating_z": g.rating_z.mean()})


def change(tab: pd.DataFrame, key: str, y0: int, y1: int) -> pd.DataFrame:
    a = tab[tab.year == y0].set_index(key)
    b = tab[tab.year == y1].set_index(key)
    d = pd.DataFrame({f"share_{y0}": a.share, f"share_{y1}": b.share, f"papers_{y1}": b.papers,
                      f"rel_log2_authors_{y0}": a.rel_log2_authors, f"rel_log2_authors_{y1}": b.rel_log2_authors,
                      f"solo_{y0}": a.solo_share, f"solo_{y1}": b.solo_share,
                      f"big9_{y0}": a.big_share_ge9, f"big9_{y1}": b.big_share_ge9})
    d["share_ratio"] = d[f"share_{y1}"] / d[f"share_{y0}"]
    d["rel_team_change"] = d[f"rel_log2_authors_{y1}"] - d[f"rel_log2_authors_{y0}"]
    return d.sort_values("share_ratio", ascending=False).reset_index()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.expanduser("~/ext/paperlists"))
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    meta = pd.read_parquet(os.path.join(ROOT, "data", "v3", "review_meta.parquet"))
    rows = []
    for y in range(2017, 2027):
        for r in json.load(open(os.path.join(a.src, f"iclr{y}.json"))):
            if r.get("track", "main") != "main" or not r.get("id"):
                continue
            txt = (r.get("title") or "") + " . " + (r.get("keywords") or "").replace(";", " , ") + " . " + \
                  (r.get("abstract") or "")
            d = {"doc_id": r["id"], **tag(txt), **tag(r.get("title") or "", "tt_")}
            d.update(features(r.get("abstract") or ""))
            rows.append(d)
    t = pd.DataFrame(rows).drop_duplicates("doc_id").merge(meta, on="doc_id", how="inner")
    t = t[t.n_authors.notna()]
    # topic tags: title + keywords + abstract ("mentions X"), and title only (suffix _title, "is about X")
    for prefix, sfx in (("t_", ""), ("tt_", "_title")):
        yr = t.groupby("year").apply(team_stats, include_groups=False)
        out = []
        for k in TOPICS:
            s = t[t[prefix + k]].groupby("year").apply(team_stats, include_groups=False).reset_index()
            s["topic"] = k
            out.append(s)
        s = yr.reset_index()
        s["topic"] = "ALL"
        tab = pd.concat(out + [s], ignore_index=True)
        tab["share"] = tab.papers / tab.year.map(yr.papers)
        tab["rel_log2_authors"] = tab.mean_log2_authors - tab.year.map(yr.mean_log2_authors)
        tab.to_csv(os.path.join(OUT, f"topic_year{sfx}.csv"), index=False)

        # periods pool the small early years (ICLR 2017 has 489 papers); year column holds the period start
        if "period" not in t:
            t["period"] = pd.cut(t.year, [2016, 2019, 2022, 2024, 2026], labels=[2017, 2020, 2023, 2025]).astype(int)
        py = t.groupby("period").apply(team_stats, include_groups=False)
        out = []
        for k in ["ALL"] + list(TOPICS):
            g = t if k == "ALL" else t[t[prefix + k]]
            s = g.groupby("period").apply(team_stats, include_groups=False).reset_index()
            s["topic"] = k
            out.append(s)
        per = pd.concat(out, ignore_index=True).rename(columns={"period": "year"})
        per["share"] = per.papers / per.year.map(py.papers)
        per["rel_log2_authors"] = per.mean_log2_authors - per.year.map(py.mean_log2_authors)
        per.to_csv(os.path.join(OUT, f"topic_period{sfx}.csv"), index=False)
        change(per, "topic", 2017, 2025).to_csv(os.path.join(OUT, f"topic_change{sfx}.csv"), index=False)
        change(tab, "topic", 2023, 2026).to_csv(os.path.join(OUT, f"topic_change_2023_2026{sfx}.csv"), index=False)

    ar = t[t.primary_area.notna() & (t.year >= 2024)]
    at = ar.groupby(["year", "primary_area"]).apply(team_stats, include_groups=False).reset_index()
    ay = ar.groupby("year").apply(team_stats, include_groups=False)
    at["share"] = at.papers / at.year.map(ay.papers)
    at["rel_log2_authors"] = at.mean_log2_authors - at.year.map(ay.mean_log2_authors)
    at.to_csv(os.path.join(OUT, "area_year.csv"), index=False)
    change(at, "primary_area", 2025, 2026).to_csv(os.path.join(OUT, "area_change.csv"), index=False)

    # pooled abstract rates per topic and year (per 1,000 tokens), abstracts >= 50 tokens
    st = t[t.tokens >= 50]
    srows = []
    for k in ["ALL"] + list(TOPICS):
        g = st if k == "ALL" else st[st["t_" + k]]
        for y, gg in g.groupby("year"):
            d = {"topic": k, "year": y, "papers": len(gg), "tokens": gg.tokens.sum()}
            d.update({c: gg[c].sum() * 1000 / gg.tokens.sum() for c in STYLE})
            srows.append(d)
    pd.DataFrame(srows).to_csv(os.path.join(OUT, "topic_style_year.csv"), index=False)
    print(per[per.topic == "ALL"][["year", "papers", "mean_authors", "solo_share"]])


if __name__ == "__main__":
    main()
