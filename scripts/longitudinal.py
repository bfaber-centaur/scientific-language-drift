"""Longitudinal analysis of n-gram rates across years (ICLR).

Usage:
    python3 scripts/longitudinal.py ~/work/pilot pilot
    python3 scripts/longitudinal.py ~/work/full_body full --sens ~/work/full --sens-label alltext
        [--k 5] [--tmp ~/work/agent-c]

The primary input for the full analysis is the body-only run (text before the
first reference-list marker), because the appendix share of text grew from ~7%
(2017) to ~47% (2027); the all-text run is the sensitivity input (--sens).
If the input has ngrams_n{n}_by_stratum.parquet / totals_by_stratum.csv, an
under-review-only sensitivity (stratum == "under_review", i.e. submission
versions, in-sample only) is added, because 2027 is ~94% submission versions
while 2017-2026 are ~60-72%.

Reads a count_ngrams.py output directory (totals.csv, ngrams_n{1,2,3}.parquet)
and writes to results/<name>/longitudinal/ (figures in .../figures/).

Outputs
-------
timeseries_top100_content_bigrams.csv, timeseries_top100_raw_bigrams.csv,
timeseries_watchlist.csv
    Long format: set, ngram, n, year, count, df, docs, positions, per_million,
    prevalence, absent_row, tiny_year. "Top 100 pooled" is ranked by the
    YEAR-BALANCED mean per_million over non-tiny years (missing year = 0), so the
    42k-paper 2027 cohort does not dominate the selection.
    absent_row=True: no (year, ngram) row in the input. With tokenizer >= v1.3
    count files (every n-gram with df >= 3 in at least one year, exact rows for
    all other years) this is a true 0. With older files (pruned per year at
    df >= 3) it means 0..2 papers; method.json records which applies.
changes_{content|raw}_bigrams_{contrast}.csv
    Cohort comparisons (contrasts below). Lists (column `list`, top 100 each):
    riser/faller by log2 ratio of corpus-weighted rates (log2_cw), by log2 ratio
    of year-balanced rates (log2_yb) and by change in corpus-weighted
    prevalence in percentage points (pp_cw).
cw_vs_yb_{content|raw}_bigrams_{contrast}.csv
    N-grams in the top 100 risers/fallers under one weighting whose rank under
    the other weighting is > 300, or whose cw and yb log2 ratios differ by >= 1.
denominator_diagnostics.csv
    Per year: share of unigram positions that are <num>, single letters,
    stopwords; per-million of common function bigrams (a baseline: if these
    move, every per-million comparison across those years shares the shift).
    Change tables also carry log2_27_vs_24_26 / spike_2027 (2027 rate >= 8x
    the 2024-2026 rate: 2027-specific text such as a new template statement).
nonmonotonic_n{1,2}.csv
    Peak/trough trajectories over non-tiny years (see find_nonmonotonic).
yoy_jumps.csv
    Biggest year-over-year changes 2023->2024 and 2026->2027 (n=1,2).
prevalence_ci_top30_risers.csv
    Per-year prevalence with 95% Wilson intervals for the top 30 content risers.
watchlist_evaluation.csv
    Pre-registered predictions vs observed cohort change.
timeseries_under_review.csv
    Same long format, stratum == under_review only, for the watchlist and the
    top 30 content risers/fallers (main contrast).
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
prevalence (sum df / sum docs) >= 1% and sum df >= 20 (this is at least as
strict as the QA rule "prevalence >= 1% in at least one cohort, df >= 20 in the
higher cohort"; for fallers it requires the early cohort to clear both).
Single-paper concentration (one paper contributing > 20% of a count) cannot
be checked from aggregates; the df >= 20 floor is the only guard.
Sensitivity columns in change tables: log2_cw_ur (same score, under-review
versions only), log2_cw_<sens-label> (same score on the --sens input) and
share_r_of_<sens-label> (primary recent-cohort count / sens count; for body vs
all text = share of occurrences that are in the body). In yoy_jumps.csv,
holds_in_under_review = the under-review-only log2 change keeps >= 50% of
the all-version log2 change (same sign) and |log2_ur| >= 0.5; 2026->2027 jumps without it are treated as confounded by
the version mix. Tiny years (< 200 docs:
ICLR 2013, 2014) are excluded from all rankings and cohorts; they appear in the
time series flagged tiny_year.

Uncertainty: from aggregate tables a paper-level bootstrap is impossible
(per-paper counts are not stored), so intervals are binomial (Wilson) on
prevalence = df/docs per year. They ignore extraction-coverage selection,
duplicates across venues, and per-paper burstiness of counts, so they are
lower bounds on real uncertainty and say nothing about per_million variance.

Pre-registered watchlist (written before running on the full data; the pilot
watchlist values had not been computed either; predictions were not changed
after the pilot run). Direction = predicted change
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
PARTIAL_YEARS = (2025, 2026)  # 2025: id-stratum subset only; 2026: ~26% extraction
SHADE_YEARS = PARTIAL_YEARS  # figure shading only; --coverage v2 clears it
SUBMISSION_YEAR = 2027  # under review, written in 2026
# Approximate extraction coverage reported by the corpus agent; annotation only.
# 2025: year-level tables hold only the unbiased id stratum (4,781 papers).
LABEL_2025 = "\nid stratum"
COVERAGE = {2017: 0.98, 2018: 0.98, 2019: 0.98, 2020: 0.98, 2021: 0.98, 2022: 0.98,
            2023: 0.97, 2024: 0.83, 2026: 0.26, 2027: 0.998}
MIN_PREV, MIN_DF = 0.01, 20
TOPK = 100
K = 5.0  # pseudo-count default; overwritten by --k


def wilson(x, n, z=1.96):
    x = np.asarray(x, float)
    n = np.asarray(n, float)
    p = np.where(n > 0, x / np.maximum(n, 1), np.nan)
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return np.clip(c - h, 0, 1), np.clip(c + h, 0, 1)


class Data:
    def __init__(self, src, tmp, stratum=None):
        self.src = src
        self.stratum = stratum
        os.makedirs(tmp, exist_ok=True)
        self.con = duckdb.connect(os.path.join(tmp, "longitudinal.duckdb"))
        self.con.execute("SET threads TO 3")
        self.con.execute(f"SET temp_directory='{os.path.join(tmp, 'duck_tmp')}'")
        self.con.execute("SET memory_limit='6GB'")
        if stratum:
            ts = pd.read_csv(os.path.join(src, "totals_by_stratum.csv"))
            self.totals = ts[ts.stratum == stratum].drop(columns="stratum")
        else:
            self.totals = pd.read_csv(os.path.join(src, "totals.csv"))
        self.years = sorted(self.totals.year.unique())
        d1 = self.totals[self.totals.n == 1].set_index("year")["docs"]
        self.tiny = [y for y in self.years if d1[y] < TINY_DOCS]
        self.rank_years = [y for y in self.years if y not in self.tiny]
        run = json.load(open(os.path.join(src, "run.json")))
        self.min_df = run.get("min_df", 3)
        self.run = run
        tv = str(run.get("tokenizer", "v0")).lstrip("v").split(".")
        self.missing_is_zero = tuple(map(int, tv[:2])) >= (1, 3)

    def path(self, n):
        return os.path.join(self.src, f"ngrams_n{n}.parquet")

    def rel(self, n):
        """SQL relation with columns year, ngram, count, df, docs, positions, per_million, prevalence."""
        if not self.stratum:
            return f"'{self.path(n)}'"
        sp = os.path.join(self.src, f"ngrams_n{n}_by_stratum.parquet")
        return (f"(SELECT year, ngram, count, df, docs, positions, 1e6 * count / positions AS per_million, "
                f"df / docs AS prevalence FROM '{sp}' WHERE stratum = '{self.stratum}')")

    def tot(self, n):
        return self.totals[self.totals.n == n].set_index("year")

    def series(self, ngrams, n):
        """Full year grid for given n-grams (missing years filled, absent_row=True)."""
        if not ngrams:
            return pd.DataFrame()
        self.con.register("wanted", pd.DataFrame({"ngram": list(ngrams)}))
        t = self.con.execute(
            f"SELECT g.* FROM {self.rel(n)} g JOIN wanted USING (ngram)").df()
        self.con.unregister("wanted")
        tot = self.tot(n)
        grid = pd.MultiIndex.from_product([list(ngrams), self.years], names=["ngram", "year"]).to_frame(index=False)
        g = grid.merge(t, on=["ngram", "year"], how="left")
        g["absent_row"] = g["count"].isna()
        g["docs"] = g["year"].map(tot["docs"])
        g["positions"] = g["year"].map(tot["positions"])
        for c in ("count", "df"):
            g[c] = g[c].fillna(0).astype(int)
        g["per_million"] = 1e6 * g["count"] / g["positions"]
        g["prevalence"] = g["df"] / g["docs"]
        g["n"] = n
        g["tiny_year"] = g["year"].isin(self.tiny)
        return g[["ngram", "n", "year", "count", "df", "docs", "positions", "per_million",
                  "prevalence", "absent_row", "tiny_year"]]

    def top_pooled(self, n, view, k=TOPK):
        ys = ",".join(map(str, self.rank_years))
        lim = k * 6 if view == "content" else k
        q = (f"SELECT ngram, sum(per_million)/{len(self.rank_years)} AS pm_yb FROM {self.rel(n)} "
             f"WHERE year IN ({ys}) GROUP BY ngram ORDER BY pm_yb DESC LIMIT {lim if view == 'raw' else 20000}")
        t = self.con.execute(q).df()
        if view == "content":
            t = t[t.ngram.map(is_content)]
        return t.head(k).ngram.tolist()

    def cohort_table(self, n, early, recent, wanted=None):
        """Per-ngram cohort aggregates for one contrast (prefiltered: df>=MIN_DF in a
        cohort), or, with `wanted`, exactly those n-grams (no prefilter)."""
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
        if wanted is None:
            q = (f"SELECT ngram, {', '.join(cols)} FROM {self.rel(n)} WHERE year IN ({ys_all}) "
                 f"GROUP BY ngram HAVING df_e >= {MIN_DF} OR df_r >= {MIN_DF}")
        else:
            self.con.register("wanted_c", pd.DataFrame({"ngram": list(wanted)}))
            q = (f"SELECT ngram, {', '.join(cols)} FROM {self.rel(n)} JOIN wanted_c USING (ngram) "
                 f"WHERE year IN ({ys_all}) GROUP BY ngram")
        t = self.con.execute(q).df()
        if wanted is not None:
            self.con.unregister("wanted_c")
            t = pd.DataFrame({"ngram": list(wanted)}).merge(t, on="ngram", how="left").fillna(0)
        return t, info

    def pair_counts(self, n, y0, y1, wanted=None):
        """Counts in two years; prefiltered to df >= MIN_DF in one year unless `wanted`."""
        if y0 not in self.years or y1 not in self.years:
            return None
        if wanted is not None:
            self.con.register("wanted_p", pd.DataFrame({"ngram": list(wanted)}))
            filt = "WHERE ngram IN (SELECT ngram FROM wanted_p)"
        else:
            filt = f"WHERE greatest(coalesce(a.df,0), coalesce(b.df,0)) >= {MIN_DF}"
        q = (f"SELECT ngram, coalesce(a.count,0) c0, coalesce(b.count,0) c1, coalesce(a.df,0) df0, "
             f"coalesce(b.df,0) df1 FROM (SELECT * FROM {self.rel(n)} WHERE year={y0}) a FULL OUTER JOIN "
             f"(SELECT * FROM {self.rel(n)} WHERE year={y1}) b USING (ngram) {filt}")
        t = self.con.execute(q).df()
        if wanted is not None:
            self.con.unregister("wanted_p")
        tot = self.tot(n)
        t["pm0"] = 1e6 * t.c0 / tot.loc[y0, "positions"]
        t["pm1"] = 1e6 * t.c1 / tot.loc[y1, "positions"]
        t["log2"] = np.log2(((t.c1 + K) / tot.loc[y1, "positions"]) / ((t.c0 + K) / tot.loc[y0, "positions"]))
        t["prev0"] = t.df0 / tot.loc[y0, "docs"]
        t["prev1"] = t.df1 / tot.loc[y1, "docs"]
        return t


def sens_log2(D, n, early, recent, wanted, k):
    """log2_cw of `wanted` n-grams on another Data source (same cohorts where present)."""
    e = [y for y in early if y in D.years]
    r = [y for y in recent if y in D.years]
    if not e or not r:
        return None
    t, info = D.cohort_table(n, e, r, wanted=wanted)
    (pe, _), (pr, _) = info["e"], info["r"]
    t["log2"] = np.log2(((t.cnt_r + k) / pr) / ((t.cnt_e + k) / pe))
    return t.set_index("ngram")


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
    lo = [y for y in SHADE_YEARS if y in years]
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


def small_multiples(ts, items, title, path, tiny, years, color, ur=None):
    import matplotlib.pyplot as plt
    ncol = 5
    nrow = math.ceil(len(items) / ncol)
    fig, axes = plt.subplots(nrow, ncol, figsize=(12, 2.0 * nrow + 0.9), squeeze=False)
    for ax, ng in zip(axes.flat, items):
        g = ts[ts.ngram == ng].sort_values("year")
        plot_series(ax, g, "per_million", color, tiny)
        if ur is not None:
            u = ur[(ur.ngram == ng) & (ur.set == "watchlist") & ~ur.year.isin(tiny)].sort_values("year")
            ax.plot(u.year, u.per_million, color=C_INK2, lw=0.9, ls=(0, (3, 2)), zorder=3)
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
             "extraction (2026 ~26%; 2025 = unbiased id stratum only). Open diamond: 2027 (submissions under review). "
             "x: tiny years (<200 papers)." + (" Dashed gray: under-review versions only." if ur is not None else ""),
             fontsize=7, color=C_INK2)
    fig.tight_layout(rect=(0, 0.025, 1, 0.97))
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("name")
    ap.add_argument("--k", type=float, default=5.0)
    ap.add_argument("--sens", default=None, help="optional second count dir (e.g. all-text run) for sensitivity columns")
    ap.add_argument("--sens-label", default="alltext")
    ap.add_argument("--outroot", default=None, help="default: <repo>/results")
    ap.add_argument("--tmp", default=os.path.expanduser("~/work/agent-c"))
    ap.add_argument("--coverage", choices=("v1", "v2"), default="v1",
                    help="figure annotations only: v2 = complete 2024-2026 (V2 pin, docs/v2-corpus-inventory.md)")
    a = ap.parse_args()
    global SHADE_YEARS, LABEL_2025
    if a.coverage == "v2":
        COVERAGE.update({2024: 0.986, 2025: 0.995, 2026: 0.996})
        SHADE_YEARS, LABEL_2025 = (), ""
    out = os.path.join(a.outroot or os.path.join(REPO, "results"), a.name, "longitudinal")
    figdir = os.path.join(out, "figures")
    os.makedirs(figdir, exist_ok=True)
    d = Data(os.path.expanduser(a.src), os.path.join(a.tmp, a.name))
    ds = Data(os.path.expanduser(a.sens), os.path.join(a.tmp, a.name + "_sens")) if a.sens else None
    has_strata = os.path.exists(os.path.join(d.src, "totals_by_stratum.csv"))
    dur = Data(d.src, os.path.join(a.tmp, a.name + "_ur"), stratum="under_review") if has_strata else None
    lab_s = a.sens_label
    global K
    K = k = a.k
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
        sens_cols = []
        # sensitivity only for n-grams that make any top list (cheap); filled after ranking
        listed = set()
        for view in ("content", "raw"):
            v = c[c.content] if view == "content" else c
            for col in ("rise_cw", "rise_yb", "fall_cw", "fall_yb", "rise_pp", "fall_pp"):
                listed |= set(v.nsmallest(TOPK, f"rank_{col}").ngram)
        listed = sorted(listed)
        if 2027 in d.rank_years and any(2024 <= y <= 2026 for y in d.rank_years):
            s27 = sens_log2(d, 2, [y for y in d.rank_years if 2024 <= y <= 2026], [2027], listed, k)
            c["log2_27_vs_24_26"] = c.ngram.map(s27["log2"])
            c["spike_2027"] = c.log2_27_vs_24_26 >= 3
            sens_cols += ["log2_27_vs_24_26", "spike_2027"]
        if dur is not None:
            su = sens_log2(dur, 2, early, recent, listed, k)
            if su is not None:
                c["log2_cw_ur"] = c.ngram.map(su["log2"])
                sens_cols.append("log2_cw_ur")
        if ds is not None:
            ss = sens_log2(ds, 2, early, recent, listed, k)
            if ss is not None:
                c[f"log2_cw_{lab_s}"] = c.ngram.map(ss["log2"])
                c[f"share_r_of_{lab_s}"] = c.cnt_r / c.ngram.map(ss["cnt_r"]).where(lambda x: x > 0)
                sens_cols += [f"log2_cw_{lab_s}", f"share_r_of_{lab_s}"]
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
            keep[-1:-1] = sens_cols
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

    # ---- denominator diagnostics: how much of each year's positions go to
    # numbers, single letters, stopwords and the most common function bigrams
    from mlngrams.filters import STOPWORDS
    sw = ",".join("'" + w.replace("'", "''") + "'" for w in STOPWORDS)
    t1 = d.tot(1)
    dg = d.con.execute(
        f"SELECT year, sum(CASE WHEN ngram = '<num>' THEN count ELSE 0 END) AS num, "
        f"sum(CASE WHEN length(ngram) = 1 THEN count ELSE 0 END) AS single_letter, "
        f"sum(CASE WHEN ngram IN ({sw}) THEN count ELSE 0 END) AS stopword FROM {d.rel(1)} GROUP BY year ORDER BY year").df()
    for c_ in ("num", "single_letter", "stopword"):
        dg[f"share_{c_}"] = dg[c_] / dg.year.map(t1["positions"])
    fb = ["of the", "in the", "to the", "on the", "for the", "and the", "is a", "can be", "we use", "et al"]
    fs = d.series(fb, 2).pivot(index="year", columns="ngram", values="per_million")
    dg = dg.merge(fs.add_prefix("pm_").reset_index(), on="year", how="left")
    dg["docs"] = dg.year.map(t1["docs"])
    dg["tokens_per_doc"] = dg.year.map(t1["tokens"] / t1["docs"])
    dg.to_csv(os.path.join(out, "denominator_diagnostics.csv"), index=False, float_format="%.5g")

    # ---- 3. non-monotonic + year-over-year jumps
    ys = ",".join(map(str, d.rank_years))
    nm_all = []
    for n in (1, 2):
        q = (f"WITH t AS (SELECT * FROM {d.rel(n)} WHERE year IN ({ys})) "
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
        for n in (1, 2):
            t = d.pair_counts(n, y0, y1)
            if t is None:
                continue
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
        Y = pd.concat(yoy).drop(columns="content")
        if dur is not None:
            parts = []
            for (pair, n), g in Y.groupby(["pair", "n"]):
                y0, y1 = map(int, pair.split("->"))
                u = dur.pair_counts(n, y0, y1, wanted=g.ngram.unique().tolist())
                if u is None:
                    continue
                u = u.set_index("ngram")
                g = g.copy()
                g["log2_ur"] = g.ngram.map(u["log2"])
                g["df0_ur"] = g.ngram.map(u["df0"])
                g["df1_ur"] = g.ngram.map(u["df1"])
                parts.append(g)
            Y = pd.concat(parts)
            Y["ur_fraction"] = Y.log2_ur / Y.log2
            Y["holds_in_under_review"] = (Y.ur_fraction >= 0.5) & (Y.log2_ur.abs() >= 0.5)
            Y = Y.sort_values(["pair", "n", "view", "direction", "rank"])
        Y.to_csv(os.path.join(out, "yoy_jumps.csv"), index=False, float_format="%.5g")

    # ---- 4. uncertainty for top 30 content risers (main contrast)
    main_c = allchg[("main", "content")]
    top30 = main_c.nsmallest(30, "rank_rise_cw").ngram.tolist()
    s = d.series(top30, 2)
    s["ci95_lo"], s["ci95_hi"] = wilson(s.df, s.docs)
    s["rise_rank"] = s.ngram.map({g: i + 1 for i, g in enumerate(top30)})
    s.sort_values(["rise_rank", "year"]).to_csv(os.path.join(out, "prevalence_ci_top30_risers.csv"),
                                                 index=False, float_format="%.5g")

    # ---- under-review-only series: watchlist + top 30 content risers/fallers
    fall30 = main_c.nsmallest(30, "rank_fall_cw").ngram.tolist()
    early = [y for y in d.rank_years if 2017 <= y <= 2021]
    recent = [y for y in d.rank_years if 2025 <= y <= 2027]
    wsens = {}
    uts = None
    if dur is not None:
        parts = []
        for setname, items in (("watchlist", wl[["ngram", "n"]].values.tolist()),
                               ("top30_content_risers_main", [(g, 2) for g in top30]),
                               ("top30_content_fallers_main", [(g, 2) for g in fall30])):
            for n in (1, 2, 3):
                ngs = [g for g, nn in items if nn == n]
                if ngs:
                    x = dur.series(ngs, n)
                    x.insert(0, "set", setname)
                    parts.append(x)
        uts = pd.concat(parts)
        uts.insert(1, "stratum", "under_review")
        uts.to_csv(os.path.join(out, "timeseries_under_review.csv"), index=False, float_format="%.6g")
    for lab, D in (("ur", dur), (lab_s, ds)):
        if D is None:
            continue
        col = {}
        for n in (1, 2, 3):
            ngs = wl[wl.n == n].ngram.tolist()
            if D.tot(n).empty:  # order not merged in this input (all-text run: n = 1, 2 only)
                continue
            r = sens_log2(D, n, early, recent, ngs, k)
            if r is not None:
                col.update(r["log2"].to_dict())
        wsens[f"log2_cw_{lab}"] = col
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
    ev = pd.DataFrame(ev)
    for c_, m in wsens.items():
        ev.insert(ev.columns.get_loc("log2_yb") + 1, c_, ev.ngram.map(m))
    ev = ev.sort_values(["group", "log2_cw"], ascending=[False, False])
    ev.to_csv(os.path.join(out, "watchlist_evaluation.csv"), index=False, float_format="%.4g")

    json.dump({"src": a.src, "years": [int(y) for y in d.years], "tiny_years": [int(y) for y in d.tiny],
               "k_pseudocounts": k, "min_prevalence_higher_cohort": MIN_PREV, "min_df_higher_cohort": MIN_DF,
               "contrasts": CONTRASTS, "min_df_input": d.min_df, "missing_row_is_true_zero": d.missing_is_zero,
               "input_run": d.run, "sens_src": a.sens, "sens_label": lab_s,
               "under_review_sensitivity": dur is not None, "filter": FILTER_VERSION,
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
                    os.path.join(figdir, "fig1_watchlist_topical.png"), d.tiny, years, C_BLUE, uts)
    small_multiples(wts, styl, "Watchlist: stylistic / rhetorical phrases",
                    os.path.join(figdir, "fig2_watchlist_stylistic.png"), d.tiny, years, C_ORANGE, uts)

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
    cols = [C_GRAY if y in d.tiny else ("#9fc3ef" if y in SHADE_YEARS else C_BLUE) for y in t1.index]
    ax.bar(t1.index, t1.docs, color=cols, width=0.7)
    for y, v in t1.docs.items():
        lab = f"{v:,}" + (LABEL_2025 if y == 2025 and LABEL_2025 else f"\n{COVERAGE[y]:.0%}" if y in COVERAGE else "")
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
