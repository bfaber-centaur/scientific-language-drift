"""Top-k tables from a count_ngrams.py output directory.

Usage: python3 scripts/make_tables.py data/full results/full [--k 100]

Writes, for n in 1, 2, 3:
    top{k}_n{n}_raw_by_year.csv        rank, year, ngram, count, df, per_million, prevalence
    top{k}_n{n}_content_by_year.csv    same, content-bearing filter (filters.is_content)
    top{k}_n{n}_{view}_pooled_cw.csv   all years pooled, ranked by pooled count (corpus-
                                       weighted: dominated by the largest years)
    top{k}_n{n}_{view}_pooled_yb.csv   ranked by year-balanced mean per_million (each
                                       year weighs the same); both files carry both measures
and corpus_totals.csv (copy of totals.csv).

Pooled values sum the per-year tables, which were pruned at df >= min_df per
year; for top-k n-grams this pruning loses nothing material (each has df in
the hundreds), but pooled counts of rare n-grams are lower bounds.
"""
from __future__ import annotations

import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pandas as pd  # noqa: E402

from mlngrams.filters import is_content  # noqa: E402


def pooled(t: pd.DataFrame, totals: pd.DataFrame) -> pd.DataFrame:
    g = t.groupby("ngram").agg(count=("count", "sum"), df=("df", "sum"), years_present=("year", "nunique"))
    g["per_million"] = 1e6 * g["count"] / totals["positions"].sum()
    g["prevalence"] = g["df"] / totals["docs"].sum()
    nyears = len(totals)
    # Year-balanced: each year weighs equally; missing years count as 0.
    g["per_million_year_balanced"] = t.groupby("ngram")["per_million"].sum() / nyears
    g["prevalence_year_balanced"] = t.groupby("ngram")["prevalence"].sum() / nyears
    return g.sort_values("count", ascending=False).reset_index()


def main():
    src, out = sys.argv[1], sys.argv[2]
    k = int(sys.argv[sys.argv.index("--k") + 1]) if "--k" in sys.argv else 100
    os.makedirs(out, exist_ok=True)
    totals = pd.read_csv(os.path.join(src, "totals.csv"))
    shutil.copy(os.path.join(src, "totals.csv"), os.path.join(out, "corpus_totals.csv"))
    cols = ["rank", "year", "ngram", "count", "df", "per_million", "prevalence"]
    for n in (1, 2, 3):
        path = os.path.join(src, f"ngrams_n{n}.parquet")
        if not os.path.exists(path):  # e.g. the all-text run merges n = 1, 2 only (disk)
            continue
        t = pd.read_parquet(path)
        t["content"] = t["ngram"].map(is_content)
        tot_n = totals[totals.n == n]
        for view, sub in (("raw", t), ("content", t[t.content])):
            by_year = sub.sort_values(["year", "count"], ascending=[True, False]).groupby("year").head(k).copy()
            by_year["rank"] = by_year.groupby("year").cumcount() + 1
            by_year[cols].to_csv(os.path.join(out, f"top{k}_n{n}_{view}_by_year.csv"), index=False, float_format="%.4g")
            full = pooled(sub, tot_n)
            for tag, key in (("cw", "count"), ("yb", "per_million_year_balanced")):
                p = full.sort_values(key, ascending=False).head(k).copy()
                p.insert(0, "rank", range(1, len(p) + 1))
                p.to_csv(os.path.join(out, f"top{k}_n{n}_{view}_pooled_{tag}.csv"), index=False, float_format="%.4g")


if __name__ == "__main__":
    main()
