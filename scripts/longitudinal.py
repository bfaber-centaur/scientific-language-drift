"""Longitudinal analysis of n-gram rates across years (ICLR).

Usage:
    python3 scripts/longitudinal.py ~/work/pilot pilot
    python3 scripts/longitudinal.py ~/work/full  full  [--k 5] [--tmp ~/work/agent-c]

Reads a count_ngrams.py output directory (totals.csv, ngrams_n{1,2,3}.parquet)
and writes to results/<name>/longitudinal/ (figures in .../figures/).

Outputs
-------
timeseries_top100_content_bigrams.csv, timeseries_top100_raw_bigrams.csv,
timeseries_watchlist.csv
    Long format: set, ngram, n, year, count, df, docs, positions, per_million,
    prevalence, pruned, tiny_year. "Top 100 pooled" is ranked by the
    YEAR-BALANCED mean per_million over non-tiny years (missing year = 0), so the
    42k-paper 2027 cohort does not dominate the selection.
    pruned=True: the n-gram is absent from that year's table, i.e. df < min_df
    (3) in that year; count/df are then written as 0 but are really 0..2 papers.
changes_{content|raw}_bigrams_{contrast}.csv
    Cohort comparisons (contrasts below). Lists (column `list`, top 100 each):
    riser/faller by log2 ratio of corpus-weighted rates (log2_cw), by log2 ratio
    of year-balanced rates (log2_yb) and by change in corpus-weighted
    prevalence in percentage points (pp_cw).
cw_vs_yb_{content|raw}_bigrams_{contrast}.csv
    N-grams in the top 100 risers/fallers under one weighting whose rank under
    the other weighting is > 300, or whose cw and yb log2 ratios differ by >= 1.
nonmonotonic_n{1,2}.csv
    Peak/trough trajectories over non-tiny years (see find_nonmonotonic).
yoy_jumps.csv
    Biggest year-over-year changes 2023->2024 and 2026->2027 (n=1,2).
prevalence_ci_top30_risers.csv
    Per-year prevalence with 95% Wilson intervals for the top 30 content risers.
watchlist_evaluation.csv
    Pre-registered predictions vs observed cohort change.
cohorts.csv, method.json

Method
------
Cohorts (only years present in the input are used):
    main:       early 2017-2021 vs recent 2025-2027
    sens_24_26: early 2017-2021 vs recent 2024-2026 (excludes the 2027
                submission cohort)
    sens_27:    early 2017-2021 vs recent 2027 alone
Corpus-weighted cohort rate = 1e6 * (sum count + k) / sum positions (k = 5
pseudo-counts per cohort, default). Year-balanced rate = mean over cohort years
of per-year per_million (missing year = 0) + 1e6 * k / sum positions, i.e. the
same pseudo-count spread proportionally over years. Ratios are log2(recent /
early). Eligibility: in the cohort where the corpus-weighted rate is higher,
prevalence (sum df / sum docs) >= 1% and sum df >= 20. Tiny years (< 200 docs:
ICLR 2013, 2014) are excluded from all rankings and cohorts; they appear in the
time series flagged tiny_year.

Uncertainty: from aggregate tables a paper-level bootstrap is impossible
(per-paper counts are not stored), so intervals are binomial (Wilson) on
prevalence = df/docs per year. They ignore extraction-coverage selection,
duplicates across venues, and per-paper burstiness of counts, so they are
lower bounds on real uncertainty and say nothing about per_million variance.

Pre-registered watchlist (written before running on the full data; the pilot
watchlist values had not been computed either). Direction = predicted change
of the corpus-weighted per-million rate from the early cohort (2017-2021) to
the recent cohort (2025-2027): "up"  log2 ratio >= +0.5, "down" <= -0.5,
"flat" |log2| < 0.5, "peak" = rises then falls (assessed as: max year is
interior and both ends are <= half of it).
Hypotheses:
  Topical controls (these track research topics, not style):
    neural network(s)        down  (term becomes implicit)
    deep learning            down
    convolutional neural     down
    generative adversarial   peak  (GAN era ~2018-2019)
    reinforcement learning   flat
    graph neural             up
    transformer              up
    language models          up    (strongly)
    large language           up    (strongly; near-zero early)
    diffusion models         up    (strongly; near-zero early)
  Stylistic / rhetorical phrases:
    we propose               flat
    in this paper            down
    state-of-the-art         flat  (tokenized as one hyphenated unigram)
    to the best              flat
    it is worth              flat
    plays a crucial          up
    crucial role             up
    across diverse           up
    comprehensive analysis   up
    extensive experiments    up
    novel approach           flat
    delve into               up
    shed light               flat
    a novel                  flat
    notably                  up
    furthermore              up
    additionally             up
    moreover                 flat
    leverage                 up
    seamlessly               up
    robust                   up
    pivotal                  up
    underscores              up
    intricate                up
  Function-phrase control:
    of the                   flat
These are descriptive hypotheses about frequency change; none implies a cause.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import duckdb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from mlngrams.filters import FILTER_VERSION, is_content  # noqa: E402

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

WATCHLIST = [
    # ngram, group, predicted direction
    ("neural network", "topical", "down"),
    ("neural networks", "topical", "down"),
    ("deep learning", "topical", "down"),
    ("convolutional neural", "topical", "down"),
    ("generative adversarial", "topical", "peak"),
    ("reinforcement learning", "topical", "flat"),
    ("graph neural", "topical", "up"),
    ("transformer", "topical", "up"),
    ("language models", "topical", "up"),
    ("large language", "topical", "up"),
    ("diffusion models", "topical", "up"),
    ("we propose", "stylistic", "flat"),
    ("in this paper", "stylistic", "down"),
    ("state-of-the-art", "stylistic", "flat"),
    ("to the best", "stylistic", "flat"),
    ("it is worth", "stylistic", "flat"),
    ("plays a crucial", "stylistic", "up"),
    ("crucial role", "stylistic", "up"),
    ("across diverse", "stylistic", "up"),
    ("comprehensive analysis", "stylistic", "up"),
    ("extensive experiments", "stylistic", "up"),
    ("novel approach", "stylistic", "flat"),
    ("delve into", "stylistic", "up"),
    ("shed light", "stylistic", "flat"),
    ("a novel", "stylistic", "flat"),
    ("notably", "stylistic", "up"),
    ("furthermore", "stylistic", "up"),
    ("additionally", "stylistic", "up"),
    ("moreover", "stylistic", "flat"),
    ("leverage", "stylistic", "up"),
    ("seamlessly", "stylistic", "up"),
    ("robust", "stylistic", "up"),
    ("pivotal", "stylistic", "up"),
    ("underscores", "stylistic", "up"),
    ("intricate", "stylistic", "up"),
    ("of the", "control", "flat"),
]

CONTRASTS = {
    "main": ((2017, 2021), (2025, 2027)),
    "sens_24_26": ((2017, 2021), (2024, 2026)),
    "sens_27": ((2017, 2021), (2027, 2027)),
}
TINY_DOCS = 200
PARTIAL_YEARS = (2025, 2026)  # extraction coverage ~53% / ~26% (corpus agent)
SUBMISSION_YEAR = 2027  # under review, written in 2026
# Approximate extraction coverage reported by the corpus agent; annotation only.
COVERAGE = {2017: 0.98, 2018: 0.98, 2019: 0.98, 2020: 0.98, 2021: 0.98, 2022: 0.98,
            2023: 0.97, 2024: 0.83, 2025: 0.53, 2026: 0.26, 2027: 0.998}
MIN_PREV, MIN_DF = 0.01, 20
TOPK = 100


def wilson(x, n, z=1.96):
    x = np.asarray(x, float)
    n = np.asarray(n, float)
    p = np.where(n > 0, x / np.maximum(n, 1), np.nan)
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return np.clip(c - h, 0, 1), np.clip(c + h, 0, 1)


class Data:
    def __init__(self, src, tmp):
        self.src = src
        os.makedirs(tmp, exist_ok=True)
        self.con = duckdb.connect(os.path.join(tmp, "longitudinal.duckdb"))
        self.con.execute("SET threads TO 3")
        self.con.execute(f"SET temp_directory='{os.path.join(tmp, 'duck_tmp')}'")
        self.con.execute("SET memory_limit='6GB'")
        self.totals = pd.read_csv(os.path.join(src, "totals.csv"))
        self.years = sorted(self.totals.year.unique())
        d1 = self.totals[self.totals.n == 1].set_index("year")["docs"]
        self.tiny = [y for y in self.years if d1[y] < TINY_DOCS]
        self.rank_years = [y for y in self.years if y not in self.tiny]
        run = json.load(open(os.path.join(src, "run.json")))
        self.min_df = run.get("min_df", 3)

    def path(self, n):
        return os.path.join(self.src, f"ngrams_n{n}.parquet")

    def tot(self, n):
        return self.totals[self.totals.n == n].set_index("year")

    def series(self, ngrams, n):
        """Full year grid for given n-grams (missing years filled, pruned=True)."""
        if not ngrams:
            return pd.DataFrame()
        self.con.register("wanted", pd.DataFrame({"ngram": list(ngrams)}))
        t = self.con.execute(
            f"SELECT g.* FROM '{self.path(n)}' g JOIN wanted USING (ngram)").df()
        self.con.unregister("wanted")
        tot = self.tot(n)
        grid = pd.MultiIndex.from_product([list(ngrams), self.years], names=["ngram", "year"]).to_frame(index=False)
        g = grid.merge(t, on=["ngram", "year"], how="left")
        g["pruned"] = g["count"].isna()
        g["docs"] = g["year"].map(tot["docs"])
        g["positions"] = g["year"].map(tot["positions"])
        for c in ("count", "df"):
            g[c] = g[c].fillna(0).astype(int)
        g["per_million"] = 1e6 * g["count"] / g["positions"]
        g["prevalence"] = g["df"] / g["docs"]
        g["n"] = n
        g["tiny_year"] = g["year"].isin(self.tiny)
        return g[["ngram", "n", "year", "count", "df", "docs", "positions", "per_million",
                  "prevalence", "pruned", "tiny_year"]]

    def top_pooled(self, n, view, k=TOPK):
        ys = ",".join(map(str, self.rank_years))
        lim = k * 6 if view == "content" else k
        q = (f"SELECT ngram, sum(per_million)/{len(self.rank_years)} AS pm_yb FROM '{self.path(n)}' "
             f"WHERE year IN ({ys}) GROUP BY ngram ORDER BY pm_yb DESC LIMIT {lim if view == 'raw' else 20000}")
        t = self.con.execute(q).df()
        if view == "content":
            t = t[t.ngram.map(is_content)]
        return t.head(k).ngram.tolist()

    def cohort_table(self, n, early, recent):
        """Per-ngram cohort aggregates for one contrast (prefiltered: df>=MIN_DF in a cohort)."""
        tot = self.tot(n)
        cols = []
        info = {}
        for lab, yrs in (("e", early), ("r", recent)):
            ys = ",".join(map(str, yrs))
            cols.append(f"""sum(CASE WHEN year IN ({ys}) THEN count ELSE 0 END) AS cnt_{lab},
                sum(CASE WHEN year IN ({ys}) THEN df ELSE 0 END) AS df_{lab},
                sum(CASE WHEN year IN ({ys}) THEN per_million ELSE 0 END)/{len(yrs)} AS pmyb_{lab},
                sum(CASE WHEN year IN ({ys}) THEN prevalence ELSE 0 END)/{len(yrs)} AS prevyb_{lab}""")
            info[lab] = (tot.loc[list(yrs), "positions"].sum(), tot.loc[list(yrs), "docs"].sum())
        ys_all = ",".join(map(str, sorted(set(early) | set(recent))))
        q = (f"SELECT ngram, {', '.join(cols)} FROM '{self.path(n)}' WHERE year IN ({ys_all}) "
             f"GROUP BY ngram HAVING df_e >= {MIN_DF} OR df_r >= {MIN_DF}")
        t = self.con.execute(q).df()
        return t, info


def changes(t, info, k):
    (pe, de), (pr, dr) = info["e"], info["r"]
    t = t.copy()
    t["pm_cw_e"] = 1e6 * (t.cnt_e + k) / pe
    t["pm_cw_r"] = 1e6 * (t.cnt_r + k) / pr
    t["pm_yb_e"] = t.pmyb_e + 1e6 * k / pe
    t["pm_yb_r"] = t.pmyb_r + 1e6 * k / pr
    t["prev_cw_e"] = t.df_e / de
    t["prev_cw_r"] = t.df_r / dr
    t["log2_cw"] = np.log2(t.pm_cw_r / t.pm_cw_e)
    t["log2_yb"] = np.log2(t.pm_yb_r / t.pm_yb_e)
    t["pp_cw"] = 100 * (t.prev_cw_r - t.prev_cw_e)
    t["pp_yb"] = 100 * (t.prevyb_r - t.prevyb_e)
    hi_r = t.pm_cw_r >= t.pm_cw_e
    prev_hi = np.where(hi_r, t.prev_cw_r, t.prev_cw_e)
    df_hi = np.where(hi_r, t.df_r, t.df_e)
    t = t[(prev_hi >= MIN_PREV) & (df_hi >= MIN_DF)].copy()
    t["rank_rise_cw"] = t.log2_cw.rank(ascending=False, method="first").astype(int)
    t["rank_rise_yb"] = t.log2_yb.rank(ascending=False, method="first").astype(int)
    t["rank_fall_cw"] = t.log2_cw.rank(ascending=True, method="first").astype(int)
    t["rank_fall_yb"] = t.log2_yb.rank(ascending=True, method="first").astype(int)
    t["rank_rise_pp"] = t.pp_cw.rank(ascending=False, method="first").astype(int)
    t["rank_fall_pp"] = t.pp_cw.rank(ascending=True, method="first").astype(int)
    return t


def year_strings(d, ngrams, n, field="per_million"):
    s = d.series(ngrams, n)
    s = s[~s.tiny_year]
    fmt = (lambda v: f"{v:.3g}") if field == "per_million" else (lambda v: f"{100 * v:.2g}")
    return s.groupby("ngram").apply(
        lambda g: "|".join(f"{y % 100:02d}:{fmt(v)}" for y, v in zip(g.year, g[field])), include_groups=False)


def find_nonmonotonic(wide, eps=0.002):
    """Peak: interior max year with min(before) and min(after) both <= max/2 (on
    prevalence + eps, eps = 0.2 pp, to damp noise near zero). Trough: interior
    min year with max(before) and max(after) both >= 2 * min."""
    rows = []
    years = list(wide.columns)
    A = wide.values + eps
    for i in range(1, len(years) - 1):
        left, mid, right = A[:, :i], A[:, i], A[:, i + 1:]
        is_max = mid >= A.max(axis=1)
        pk = np.minimum(mid / left.min(axis=1), mid / right.min(axis=1))
        is_min = mid <= A.min(axis=1)
        tr = np.minimum(left.max(axis=1) / mid, right.max(axis=1) / mid)
        for kind, sel, score in (("peak", is_max & (pk >= 2), pk), ("trough", is_min & (tr >= 2), tr)):
            for j in np.where(sel)[0]:
                rows.append({"ngram": wide.index[j], "shape": kind, "turn_year": years[i], "score": score[j]})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------- plotting
C_BLUE, C_ORANGE, C_AQUA, C_GRAY, C_INK, C_INK2 = "#2a78d6", "#eb6834", "#1baf7a", "#8a8984", "#0b0b0b", "#52514e"


def style_axes(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#bdbcb6")
    ax.tick_params(colors=C_INK2, labelsize=7)
    ax.grid(axis="y", color="#e6e5e0", lw=0.6)
    ax.set_axisbelow(True)


def set_year_ticks(ax, years):
    ys = [y for y in years if y >= 2017]
    ticks = ys if len(ys) <= 6 else [y for y in ys if y % 2 == 1]
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"'{y % 100:02d}" for y in ticks])


def mark_years(ax, years, label=False):
    lo = [y for y in PARTIAL_YEARS if y in years]
    if lo:
        ax.axvspan(min(lo) - 0.5, max(lo) + 0.5, color="#ecebe6", zorder=0, lw=0)
    if SUBMISSION_YEAR in years:
        ax.axvline(SUBMISSION_YEAR - 0.5, color=C_GRAY, lw=0.7, ls=(0, (2, 2)), zorder=0)
    if label:
        tr = ax.get_xaxis_transform()
        if lo:
            ax.text(np.mean(lo), 0.98, "partial\nextraction", transform=tr, ha="center", va="top", fontsize=6, color=C_INK2)
        if SUBMISSION_YEAR in years:
            ax.text(SUBMISSION_YEAR, 0.98, "under\nreview", transform=tr, ha="center", va="top", fontsize=6, color=C_INK2)


def plot_series(ax, g, field, color, tiny, ci=None):
    main = g[~g.year.isin(tiny)]
    ax.plot(main.year, main[field], color=color, lw=1.6, zorder=3)
    full = main[main.year != SUBMISSION_YEAR]
    ax.scatter(full.year, full[field], s=12, color=color, zorder=4, edgecolor="white", lw=0.5)
    sub = main[main.year == SUBMISSION_YEAR]
    ax.scatter(sub.year, sub[field], s=22, marker="D", facecolor="white", edgecolor=color, lw=1.2, zorder=5)
    tg = g[g.year.isin(tiny)]
    if len(tg):
        ax.scatter(tg.year, tg[field], s=14, marker="x", color=C_GRAY, lw=0.9, zorder=4)
    if ci is not None:
        lo, hi = ci
        m = ~g.year.isin(tiny).values
        ax.fill_between(g.year[m], lo[m], hi[m], color=color, alpha=0.18, lw=0, zorder=2)


def small_multiples(ts, items, title, path, tiny, years, color):
    import matplotlib.pyplot as plt
    ncol = 5
    nrow = math.ceil(len(items) / ncol)
    fig, axes = plt.subplots(nrow, ncol, figsize=(12, 2.0 * nrow + 0.9), squeeze=False)
    for ax, ng in zip(axes.flat, items):
        g = ts[ts.ngram == ng].sort_values("year")
        plot_series(ax, g, "per_million", color, tiny)
        mark_years(ax, years)
        style_axes(ax)
        ax.set_title(ng, fontsize=9, color=C_INK, loc="left")
        ax.set_ylim(bottom=0)
        set_year_ticks(ax, years)
    for ax in list(axes.flat)[len(items):]:
        ax.axis("off")
    fig.suptitle(title, x=0.01, ha="left", fontsize=11, color=C_INK)
    fig.text(0.01, 0.005,
             "y: occurrences per million n-gram positions (own scale per panel, from 0). Shaded: 2025-2026 partial text "
             "extraction (~53%, ~26%). Open diamond: 2027 submissions under review. x: tiny years (<200 papers).",
             fontsize=7, color=C_INK2)
    fig.tight_layout(rect=(0, 0.025, 1, 0.97))
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("name")
    ap.add_argument("--k", type=float, default=5.0)
    ap.add_argument("--tmp", default=os.path.expanduser("~/work/agent-c"))
    a = ap.parse_args()
    out = os.path.join(REPO, "results", a.name, "longitudinal")
    figdir = os.path.join(out, "figures")
    os.makedirs(figdir, exist_ok=True)
    d = Data(os.path.expanduser(a.src), os.path.join(a.tmp, a.name))
    k = a.k
    print("years", d.years, "tiny", d.tiny)

    # ---- 1. time series
    for view in ("content", "raw"):
        top = d.top_pooled(2, view)
        s = d.series(top, 2)
        s.insert(0, "set", f"top100_pooled_{view}_bigrams")
        s.insert(1, "pooled_rank", s.ngram.map({g: i + 1 for i, g in enumerate(top)}))
        s.to_csv(os.path.join(out, f"timeseries_top100_{view}_bigrams.csv"), index=False, float_format="%.6g")
    wl = pd.DataFrame(WATCHLIST, columns=["ngram", "group", "predicted"])
    wl["n"] = wl.ngram.str.count(" ") + 1
    wts = pd.concat([d.series(wl[wl.n == n].ngram.tolist(), n) for n in (1, 2, 3)])
    wts = wts.merge(wl[["ngram", "group", "predicted"]], on="ngram")
    wts.insert(0, "set", "watchlist")
    wts.to_csv(os.path.join(out, "timeseries_watchlist.csv"), index=False, float_format="%.6g")

    # ---- 2. risers / fallers
    cohort_rows = []
    allchg = {}
    seen_recent = []
    for cname, ((e0, e1), (r0, r1)) in CONTRASTS.items():
        early = [y for y in d.rank_years if e0 <= y <= e1]
        recent = [y for y in d.rank_years if r0 <= y <= r1]
        if not early or not recent or recent in seen_recent:
            continue  # year absent, or identical to an earlier contrast (pilot)
        seen_recent.append(recent)
        t, info = d.cohort_table(2, early, recent)
        t["content"] = t.ngram.map(is_content)
        c = changes(t, info, k)
        for lab, yrs in (("early", early), ("recent", recent)):
            p, dd = info[lab[0]]
            cohort_rows.append({"contrast": cname, "cohort": lab, "years": " ".join(map(str, yrs)),
                                "docs": dd, "positions_n2": p})
        for view in ("content", "raw"):
            v = c[c.content] if view == "content" else c
            v = v.copy()
            for col in ("rise_cw", "rise_yb", "fall_cw", "fall_yb", "rise_pp", "fall_pp"):
                v[f"rank_{col}"] = v[f"rank_{col}"].rank(method="first").astype(int)
            allchg[(cname, view)] = v
            lists = []
            for lab, col in (("riser_log2_cw", "rise_cw"), ("faller_log2_cw", "fall_cw"),
                             ("riser_log2_yb", "rise_yb"), ("faller_log2_yb", "fall_yb"),
                             ("riser_pp_cw", "rise_pp"), ("faller_pp_cw", "fall_pp")):
                x = v.nsmallest(TOPK, f"rank_{col}").copy()
                x.insert(0, "list", lab)
                x.insert(1, "rank", x[f"rank_{col}"])
                lists.append(x)
            L = pd.concat(lists)
            ys = year_strings(d, L.ngram.unique().tolist(), 2)
            L["per_million_by_year"] = L.ngram.map(ys)
            keep = ["list", "rank", "ngram", "cnt_e", "cnt_r", "df_e", "df_r", "pm_cw_e", "pm_cw_r", "pm_yb_e",
                    "pm_yb_r", "prev_cw_e", "prev_cw_r", "log2_cw", "log2_yb", "pp_cw", "pp_yb",
                    "rank_rise_cw", "rank_rise_yb", "rank_fall_cw", "rank_fall_yb", "per_million_by_year"]
            L[keep].to_csv(os.path.join(out, f"changes_{view}_bigrams_{cname}.csv"), index=False, float_format="%.5g")
            # disagreement between weightings
            dis = []
            for a1, a2, lab in (("rise_cw", "rise_yb", "riser"), ("rise_yb", "rise_cw", "riser"),
                                ("fall_cw", "fall_yb", "faller"), ("fall_yb", "fall_cw", "faller")):
                x = v[(v[f"rank_{a1}"] <= TOPK) & ((v[f"rank_{a2}"] > 300) | ((v.log2_cw - v.log2_yb).abs() >= 1))].copy()
                x.insert(0, "list", f"{lab}_top100_by_{a1[-2:]}")
                dis.append(x)
            D = pd.concat(dis)
            D["per_million_by_year"] = D.ngram.map(year_strings(d, D.ngram.unique().tolist(), 2)) if len(D) else ""
            D[["list"] + keep[2:]].to_csv(os.path.join(out, f"cw_vs_yb_{view}_bigrams_{cname}.csv"),
                                          index=False, float_format="%.5g")
    pd.DataFrame(cohort_rows).to_csv(os.path.join(out, "cohorts.csv"), index=False)

    # ---- 3. non-monotonic + year-over-year jumps
    ys = ",".join(map(str, d.rank_years))
    nm_all = []
    for n in (1, 2):
        q = (f"WITH t AS (SELECT * FROM '{d.path(n)}' WHERE year IN ({ys})) "
             f"SELECT t.ngram, year, prevalence, per_million FROM t JOIN "
             f"(SELECT ngram FROM t GROUP BY ngram HAVING max(prevalence) >= 0.02) USING (ngram)")
        t = d.con.execute(q).df()
        wide = t.pivot(index="ngram", columns="year", values="prevalence").reindex(columns=d.rank_years).fillna(0)
        nm = find_nonmonotonic(wide)
        if len(nm):
            no_partial = [y for y in d.rank_years if y not in PARTIAL_YEARS]
            robust = set()
            if len(no_partial) >= 3:
                nm2 = find_nonmonotonic(wide[no_partial])
                robust = set(zip(nm2.ngram, nm2["shape"]))
            nm["robust_without_2025_2026"] = [(g, s) in robust for g, s in zip(nm.ngram, nm["shape"])]
            nm["content"] = nm.ngram.map(is_content)
            nm["n"] = n
            nm["max_prevalence"] = nm.ngram.map(wide.max(axis=1))
            nm["prevalence_pct_by_year"] = nm.ngram.map(
                wide.apply(lambda r: "|".join(f"{y % 100:02d}:{100 * v:.2g}" for y, v in r.items()), axis=1))
            nm = nm.sort_values("score", ascending=False)
            nm.to_csv(os.path.join(out, f"nonmonotonic_n{n}.csv"), index=False, float_format="%.4g")
            nm_all.append(nm)

    yoy = []
    for y0, y1 in ((2023, 2024), (2026, 2027)):
        if y0 not in d.years or y1 not in d.years:
            continue
        for n in (1, 2):
            tot = d.tot(n)
            p0, p1 = tot.loc[y0, "positions"], tot.loc[y1, "positions"]
            q = (f"SELECT ngram, coalesce(a.count,0) c0, coalesce(b.count,0) c1, coalesce(a.df,0) df0, coalesce(b.df,0) df1 "
                 f"FROM (SELECT * FROM '{d.path(n)}' WHERE year={y0}) a FULL OUTER JOIN "
                 f"(SELECT * FROM '{d.path(n)}' WHERE year={y1}) b USING (ngram)")
            t = d.con.execute(q).df()
            t["pm0"] = 1e6 * (t.c0 + k) / p0
            t["pm1"] = 1e6 * (t.c1 + k) / p1
            t["prev0"] = t.df0 / tot.loc[y0, "docs"]
            t["prev1"] = t.df1 / tot.loc[y1, "docs"]
            t["log2"] = np.log2(t.pm1 / t.pm0)
            up = t.pm1 >= t.pm0
            t = t[(np.where(up, t.prev1, t.prev0) >= MIN_PREV) & (np.where(up, t.df1, t.df0) >= MIN_DF)].copy()
            t["content"] = t.ngram.map(is_content)
            for view in ("content", "raw"):
                v = t[t.content] if view == "content" else t
                for dirn, x in (("up", v.nlargest(50, "log2")), ("down", v.nsmallest(50, "log2"))):
                    x = x.copy()
                    x.insert(0, "pair", f"{y0}->{y1}")
                    x.insert(1, "n", n)
                    x.insert(2, "view", view)
                    x.insert(3, "direction", dirn)
                    x.insert(4, "rank", range(1, len(x) + 1))
                    yoy.append(x)
    if yoy:
        pd.concat(yoy).drop(columns="content").to_csv(os.path.join(out, "yoy_jumps.csv"), index=False, float_format="%.5g")

    # ---- 4. uncertainty for top 30 content risers (main contrast)
    main_c = allchg[("main", "content")]
    top30 = main_c.nsmallest(30, "rank_rise_cw").ngram.tolist()
    s = d.series(top30, 2)
    s["ci95_lo"], s["ci95_hi"] = wilson(s.df, s.docs)
    s["rise_rank"] = s.ngram.map({g: i + 1 for i, g in enumerate(top30)})
    s.sort_values(["rise_rank", "year"]).to_csv(os.path.join(out, "prevalence_ci_top30_risers.csv"),
                                                 index=False, float_format="%.5g")

    # ---- watchlist evaluation (main contrast, computed from the series)
    early = [y for y in d.rank_years if 2017 <= y <= 2021]
    recent = [y for y in d.rank_years if 2025 <= y <= 2027]
    ev = []
    for (ng, grp, pred), g in wts.groupby(["ngram", "group", "predicted"]):
        e, r = g[g.year.isin(early)], g[g.year.isin(recent)]
        lcw = math.log2(((r["count"].sum() + k) / r.positions.sum()) / ((e["count"].sum() + k) / e.positions.sum()))
        kk = 1e6 * k
        lyb = math.log2((r.per_million.mean() + kk / r.positions.sum()) / (e.per_million.mean() + kk / e.positions.sum()))
        gm = g[g.year.isin(d.rank_years)].sort_values("year")
        pm = gm.per_million.values
        imax = int(np.argmax(pm))
        peak = 0 < imax < len(pm) - 1 and pm[0] <= pm[imax] / 2 and pm[-1] <= pm[imax] / 2
        obs = "up" if lcw >= 0.5 else "down" if lcw <= -0.5 else "flat"
        held = peak if pred == "peak" else (obs == pred)
        ev.append({"ngram": ng, "group": grp, "predicted": pred, "observed_cw": obs, "held": held,
                   "log2_cw": lcw, "log2_yb": lyb, "peak_shape": peak, "max_year": int(gm.year.values[imax]),
                   "prev_early": e.df.sum() / e.docs.sum(), "prev_recent": r.df.sum() / r.docs.sum(),
                   "per_million_by_year": "|".join(f"{y % 100:02d}:{v:.3g}" for y, v in zip(gm.year, pm))})
    ev = pd.DataFrame(ev).sort_values(["group", "log2_cw"], ascending=[False, False])
    ev.to_csv(os.path.join(out, "watchlist_evaluation.csv"), index=False, float_format="%.4g")

    json.dump({"src": a.src, "years": [int(y) for y in d.years], "tiny_years": [int(y) for y in d.tiny],
               "k_pseudocounts": k, "min_prevalence_higher_cohort": MIN_PREV, "min_df_higher_cohort": MIN_DF,
               "contrasts": CONTRASTS, "min_df_pruning_input": d.min_df, "filter": FILTER_VERSION,
               "coverage_annotation_only": COVERAGE},
              open(os.path.join(out, "method.json"), "w"), indent=1)

    # ---- 5. figures
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.titlesize": 9})
    years = d.years
    topical = [w[0] for w in WATCHLIST if w[1] in ("topical", "control")]
    styl = [w[0] for w in WATCHLIST if w[1] == "stylistic"]
    small_multiples(wts, topical, "Watchlist: topical controls (and 'of the')",
                    os.path.join(figdir, "fig1_watchlist_topical.png"), d.tiny, years, C_BLUE)
    small_multiples(wts, styl, "Watchlist: stylistic / rhetorical phrases",
                    os.path.join(figdir, "fig2_watchlist_stylistic.png"), d.tiny, years, C_ORANGE)

    # fig3: dot plot risers / fallers (content bigrams, main contrast)
    fig, axes = plt.subplots(1, 2, figsize=(11, 6.5))
    for ax, col, title in ((axes[0], "rank_rise_cw", "Top 25 risers"), (axes[1], "rank_fall_cw", "Top 25 fallers")):
        x = main_c.nsmallest(25, col).iloc[::-1]
        yy = np.arange(len(x))
        ax.hlines(yy, x.pm_cw_e, x.pm_cw_r, color="#c9c8c2", lw=1.2, zorder=1)
        ax.scatter(x.pm_cw_e, yy, s=26, color=C_GRAY, label="early " + "-".join(dict.fromkeys(map(str, (early[0], early[-1])))), zorder=3)
        ax.scatter(x.pm_cw_r, yy, s=26, color=C_BLUE, label="recent " + "-".join(dict.fromkeys(map(str, (recent[0], recent[-1])))), zorder=3)
        ax.set_yticks(yy)
        ax.set_yticklabels(x.ngram, fontsize=8)
        ax.set_xscale("log")
        ax.set_xlabel("per million bigram positions (corpus-weighted cohort rate, k=%g, log scale)" % k, fontsize=8)
        ax.set_title(title + " by log2 ratio (content bigrams)", loc="left", fontsize=10)
        style_axes(ax)
        ax.grid(axis="x", color="#e6e5e0", lw=0.6)
        ax.legend(fontsize=8, frameon=False, loc="lower right")
    fig.text(0.01, 0.005, f"Eligible: prevalence >= {MIN_PREV:.0%} and df >= {MIN_DF} in the higher cohort. Recent "
             "cohort includes partial-extraction years and the 2027 submission cohort.", fontsize=7, color=C_INK2)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(os.path.join(figdir, "fig3_risers_fallers.png"), dpi=150)
    plt.close(fig)

    # fig4: corpus-weighted vs year-balanced
    fig, ax = plt.subplots(figsize=(7, 6.5))
    ax.scatter(main_c.log2_cw, main_c.log2_yb, s=4, color="#c9c8c2", lw=0, zorder=1, label="eligible content bigrams")
    top = main_c[(main_c.rank_rise_cw <= TOPK) | (main_c.rank_fall_cw <= TOPK) |
                 (main_c.rank_rise_yb <= TOPK) | (main_c.rank_fall_yb <= TOPK)]
    flag = top[((top.log2_cw - top.log2_yb).abs() >= 1) |
               ((top.rank_rise_cw <= TOPK) & (top.rank_rise_yb > 300)) | ((top.rank_rise_yb <= TOPK) & (top.rank_rise_cw > 300)) |
               ((top.rank_fall_cw <= TOPK) & (top.rank_fall_yb > 300)) | ((top.rank_fall_yb <= TOPK) & (top.rank_fall_cw > 300))]
    ax.scatter(top.log2_cw, top.log2_yb, s=10, color=C_BLUE, lw=0, zorder=2, label="top 100 riser/faller (either)")
    ax.scatter(flag.log2_cw, flag.log2_yb, s=18, facecolor="none", edgecolor=C_ORANGE, lw=1, zorder=3,
               label="flagged: weightings disagree")
    for _, r in flag.reindex((flag.log2_cw - flag.log2_yb).abs().sort_values(ascending=False).index).head(12).iterrows():
        ax.annotate(r.ngram, (r.log2_cw, r.log2_yb), fontsize=6.5, color=C_INK2, xytext=(3, 2), textcoords="offset points")
    lim = [min(main_c.log2_cw.min(), main_c.log2_yb.min()), max(main_c.log2_cw.max(), main_c.log2_yb.max())]
    ax.plot(lim, lim, color=C_GRAY, lw=0.8, ls="--", zorder=0)
    ax.set_xlabel("log2(recent/early), corpus-weighted (pooled counts)")
    ax.set_ylabel("log2(recent/early), year-balanced (mean of per-year rates)")
    ax.set_title("Corpus-weighted vs year-balanced change, content bigrams", loc="left", fontsize=10)
    style_axes(ax)
    ax.legend(fontsize=7, frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(os.path.join(figdir, "fig4_cw_vs_yb.png"), dpi=150)
    plt.close(fig)

    # fig5: prevalence with CIs
    pick = top30[:2] + [w for w in ("language models", "in this paper", "across diverse", "extensive experiments",
                                    "notably", "delve into", "it is worth") if w not in top30[:2]][:6]
    sers = []
    for ng in pick:
        n = ng.count(" ") + 1
        sers.append(d.series([ng], n))
    S = pd.concat(sers)
    fig, axes = plt.subplots(2, 4, figsize=(12, 5.2), squeeze=False)
    for ax, ng in zip(axes.flat, pick):
        g = S[S.ngram == ng].sort_values("year")
        lo, hi = wilson(g.df, g.docs)
        g = g.assign(prevalence=100 * g.prevalence)
        plot_series(ax, g, "prevalence", C_AQUA if ng in top30 else C_BLUE, d.tiny, ci=(100 * lo, 100 * hi))
        mark_years(ax, years)
        style_axes(ax)
        ax.set_ylim(bottom=0)
        ax.set_title(ng + ("  (top riser)" if ng in top30 else ""), fontsize=9, loc="left")
        set_year_ticks(ax, years)
    for ax in axes[:, 0]:
        ax.set_ylabel("% of papers containing it", fontsize=8)
    fig.suptitle("Prevalence by year with 95% binomial (Wilson) intervals", x=0.01, ha="left", fontsize=11)
    fig.text(0.01, 0.005, "Intervals reflect only paper-sampling noise given each year's extracted papers; they do not "
             "cover extraction-coverage bias (2024-2026) or topic mix.", fontsize=7, color=C_INK2)
    fig.tight_layout(rect=(0, 0.025, 1, 0.96))
    fig.savefig(os.path.join(figdir, "fig5_prevalence_ci.png"), dpi=150)
    plt.close(fig)

    # fig6: corpus size context
    t1 = d.tot(1)
    fig, ax = plt.subplots(figsize=(8, 3.2))
    cols = [C_GRAY if y in d.tiny else ("#9fc3ef" if y in PARTIAL_YEARS else C_BLUE) for y in t1.index]
    ax.bar(t1.index, t1.docs, color=cols, width=0.7)
    for y, v in t1.docs.items():
        lab = f"{v:,}" + (f"\n{COVERAGE[y]:.0%}" if y in COVERAGE else "")
        ax.text(y, v, lab, ha="center", va="bottom", fontsize=6.5, color=C_INK2)
    ax.set_yscale("log")
    ax.set_ylabel("papers counted (log scale)", fontsize=8)
    ax.set_title("Papers per year (label: count and approx. extraction coverage)", loc="left", fontsize=10)
    ax.set_xticks(list(t1.index))
    ax.set_xticklabels([str(y) for y in t1.index], fontsize=7)
    style_axes(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(figdir, "fig6_corpus_size.png"), dpi=150)
    plt.close(fig)
    print("wrote", out)


if __name__ == "__main__":
    main()
