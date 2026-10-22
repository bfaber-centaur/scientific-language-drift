"""V3: does author count relate to review outcomes at ICLR, and does that relation shift over time?

Input: data/v3/review_meta.parquet (scripts/v3/review_meta.py). All slopes are per doubling of the
author count (log2). Outcomes: rating_z (within-year z of the mean reviewer rating; scales differ by
year), accepted (linear probability, decided papers only: accept vs reject), withdrawn (all papers),
cite_pct (within-year Google Scholar citation percentile, 2017-2025; 2026 has no counts).

Specifications, each fitted per year:
  raw        outcome ~ log2(n_authors)
  common     + log2(max_author_papers by name): the same control in every year
  controls   + log2(max_author_papers) [+ industry 2017-24] [+ primary-area FE 2024-26]
  last_fe    + last-author fixed effects (within-transform; papers whose last author has >= 2
             submissions that year) + log2(max_author_papers)
  first_fe   same with first-author fixed effects
Robust (HC1) standard errors; clustered by the FE author for the FE specs.

Writes results/v3/authors/{bins.csv, slopes.csv, pooled_trend.csv, relative_size.csv, name_collision_check.csv,
citations_within_decision.csv, decision_given_rating.csv,
fig_authors_quality.png}.
"""
from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import statsmodels.formula.api as smf  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
OUT = os.path.join(ROOT, "results", "v3", "authors")
BINS = [0, 1, 2, 3, 4, 5, 6, 8, 11, 1000]
LABELS = ["1", "2", "3", "4", "5", "6", "7-8", "9-11", "12+"]


def load():
    df = pd.read_parquet(os.path.join(ROOT, "data", "v3", "review_meta.parquet"))
    df = df[df.n_authors.notna()].copy()
    df["la"] = np.log2(df.n_authors)
    df["lmax"] = np.log2(df.max_author_papers)
    df["withdrawn"] = (df.decision == "withdraw").astype(float)
    df["industry_f"] = df.industry.astype(float)
    df["nb"] = pd.cut(df.n_authors, BINS, labels=LABELS)
    df["size_pct"] = df.groupby("year").n_authors.rank(pct=True)
    return df


def fit(d, formula, cluster=None):
    d = d.dropna(subset=[c for c in d.columns if c in formula])
    if len(d) < 50:
        return None
    if cluster:
        m = smf.ols(formula, d).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(d[cluster])[0]})
    else:
        m = smf.ols(formula, d).fit(cov_type="HC1")
    return m.params["la"], m.bse["la"], int(m.nobs)


def within(d, y, fe):
    d = d.dropna(subset=[y, "la", "lmax", fe]).copy()
    d = d[d.groupby(fe)[fe].transform("size") >= 2]
    for c in (y, "la", "lmax"):
        d[c] = d[c] - d.groupby(fe)[c].transform("mean")
    return fit(d, f"{y} ~ la + lmax - 1", cluster=fe)


def main():
    os.makedirs(OUT, exist_ok=True)
    df = load()
    dec = df[df.accepted.notna()]

    # Descriptive bins.
    rows = []
    for (y, b), g in df.groupby(["year", "nb"], observed=True):
        gd = g[g.accepted.notna()]
        rows.append({"year": y, "authors": b, "papers": len(g), "share": len(g) / (df.year == y).sum(),
                     "rating_z": g.rating_z.mean(), "accept_rate_decided": gd.accepted.mean(),
                     "decided": len(gd), "withdraw_rate": g.withdrawn.mean(), "cite_pct": g.cite_pct.mean()})
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "bins.csv"), index=False)

    # Per-year slopes.
    out = []
    for y in sorted(df.year.unique()):
        d = df[df.year == y]
        ctrl = "la + lmax"
        if d.industry_f.notna().mean() > 0.8:
            ctrl += " + industry_f"
        if d.primary_area.notna().mean() > 0.8:
            ctrl += " + C(primary_area)"
        for outcome, data in (("rating_z", d), ("accepted", d[d.accepted.notna()]),
                              ("withdrawn", d), ("cite_pct", d)):
            if data[outcome].notna().sum() < 50 or data[outcome].nunique() < 2:
                continue
            for spec, res in (("raw", fit(data, f"{outcome} ~ la")),
                              ("common", fit(data.assign(lmax=np.log2(data.max_author_papers_name)),
                                             f"{outcome} ~ la + lmax")),
                              ("controls", fit(data, f"{outcome} ~ {ctrl}")),
                              ("last_fe", within(data, outcome, "last_author")),
                              ("first_fe", within(data, outcome, "first_author"))):
                if res:
                    out.append({"year": y, "outcome": outcome, "spec": spec, "slope": res[0], "se": res[1],
                                "n": res[2]})
    sl = pd.DataFrame(out)
    sl.to_csv(os.path.join(OUT, "slopes.csv"), index=False)

    # Pooled test for a linear trend in the slope (year centred at 2021.5), 2017-2026.
    tr = []
    for outcome, data in (("rating_z", df), ("accepted", dec), ("withdrawn", df[df.year >= 2018]),
                          ("cite_pct", df)):
        d = data.dropna(subset=[outcome]).copy()
        d["t"] = d.year - 2021.5
        for spec, f in (("raw", f"{outcome} ~ C(year) + la + la:t"),
                        ("controls", f"{outcome} ~ C(year) + la + la:t + lmax + lmax:C(year)")):
            m = smf.ols(f, d).fit(cov_type="HC1")
            tr.append({"outcome": outcome, "spec": spec, "slope_at_2021_5": m.params["la"],
                       "trend_per_year": m.params["la:t"], "trend_se": m.bse["la:t"],
                       "trend_p": m.pvalues["la:t"], "n": int(m.nobs)})
        # LLM-era break: 2025-26 vs 2017-24.
        d["post"] = (d.year >= 2025).astype(float)
        m = smf.ols(f"{outcome} ~ C(year) + la + la:post + lmax + lmax:C(year)", d).fit(cov_type="HC1")
        tr.append({"outcome": outcome, "spec": "controls_post2025_break", "slope_at_2021_5": m.params["la"],
                   "trend_per_year": m.params["la:post"], "trend_se": m.bse["la:post"],
                   "trend_p": m.pvalues["la:post"], "n": int(m.nobs)})
    pd.DataFrame(tr).to_csv(os.path.join(OUT, "pooled_trend.csv"), index=False)

    # Name-collision check (2021-24 carry OpenReview profile ids; 2025-26 names only): refit the
    # controls and last-author FE specs with name-based vs id-based author keys.
    nc = []
    for y in range(2021, 2025):
        d = df[df.year == y].copy()
        d["lmax_name"] = np.log2(d.max_author_papers_name)
        for outcome in ("rating_z", "accepted"):
            dd = d[d[outcome].notna()]
            for key, lm, fe in (("id", "lmax", "last_author_id"), ("name", "lmax_name", "last_author")):
                e = dd.assign(lmax=dd[lm])
                c = fit(e, f"{outcome} ~ la + lmax" + (" + industry_f" if y <= 2024 else ""))
                f = within(e, outcome, fe)
                nc.append({"year": y, "outcome": outcome, "key": key, "controls_slope": c[0], "controls_se": c[1],
                           "last_fe_slope": f[0], "last_fe_se": f[1], "last_fe_n": f[2]})
    pd.DataFrame(nc).to_csv(os.path.join(OUT, "name_collision_check.csv"), index=False)

    # Decision given ratings: among decided papers, does team size predict acceptance beyond the
    # reviewers' scores (flexible spline in the mean rating)? ICLR 2026 ratings are pre-rebuttal: ICLR
    # reset all scores and reassigned area chairs after the 2025-11-27 OpenReview leak.
    dg = []
    for y in sorted(dec.year.unique()):
        d = dec[dec.year == y].dropna(subset=["rating_mean"])
        m = smf.ols("accepted ~ la + bs(rating_mean, df=5)", d).fit(cov_type="HC1")
        m2 = smf.ols("accepted ~ la + lmax + bs(rating_mean, df=5)", d.dropna(subset=["lmax"])).fit(cov_type="HC1")
        dg.append({"year": y, "pp_per_doubling": 100 * m.params["la"], "se_pp": 100 * m.bse["la"],
                   "pp_per_doubling_with_lmax": 100 * m2.params["la"], "se_pp_with_lmax": 100 * m2.bse["la"],
                   "n": int(m.nobs)})
    pd.DataFrame(dg).to_csv(os.path.join(OUT, "decision_given_rating.csv"), index=False)

    # Citations within decision group: does team size predict citations among papers with the same
    # outcome (so not via acceptance)? Percentile recomputed within year x decision.
    cw = []
    for (y, dcs), d in df[df.decision.isin(["accept", "reject", "withdraw"])].groupby(["year", "decision"]):
        d = d.dropna(subset=["gs_citation"])
        if len(d) < 80:
            continue
        d = d.assign(cp=d.gs_citation.rank(pct=True))
        r = fit(d, "cp ~ la")
        c = fit(d, "cp ~ la + lmax" + (" + industry_f" if d.industry_f.notna().mean() > 0.8 else ""))
        cw.append({"year": y, "decision": dcs, "slope_raw": r[0], "se_raw": r[1], "slope_controls": c[0],
                   "se_controls": c[1], "n": r[2]})
    pd.DataFrame(cw).to_csv(os.path.join(OUT, "citations_within_decision.csv"), index=False)

    # Relative team size: is it absolute or relative size that predicts? Per year, both in one model.
    rel = []
    for y, d in df.groupby("year"):
        m = smf.ols("rating_z ~ la + size_pct", d.dropna(subset=["rating_z"])).fit(cov_type="HC1")
        rel.append({"year": y, "slope_log2": m.params["la"], "se_log2": m.bse["la"],
                    "slope_size_pct": m.params["size_pct"], "se_size_pct": m.bse["size_pct"]})
    pd.DataFrame(rel).to_csv(os.path.join(OUT, "relative_size.csv"), index=False)

    # Figure.
    b = pd.read_csv(os.path.join(OUT, "bins.csv"))
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.3))
    cmap = plt.get_cmap("viridis")
    for i, y in enumerate(sorted(b.year.unique())):
        g = b[(b.year == y) & (b.decided >= 30)]
        ax[0].plot(g.authors.astype(str).map(LABELS.index), g.accept_rate_decided, marker="o", ms=3, color=cmap(i / 9), label=y)
    ax[0].set(title="Acceptance rate of decided papers\nby number of authors", xlabel="authors",
              ylabel="accepted / (accepted + rejected)")
    ax[0].set_xticks(range(len(LABELS)), LABELS)
    ax[0].legend(fontsize=7, ncol=2)
    for spec, c in (("raw", "#888"), ("controls", "#1f77b4"), ("last_fe", "#d62728")):
        s = sl[(sl.outcome == "rating_z") & (sl.spec == spec)]
        ax[1].errorbar(s.year + {"raw": -0.15, "controls": 0, "last_fe": 0.15}[spec], s.slope, 1.96 * s.se,
                       fmt="o", ms=4, color=c, capsize=2, label=spec)
    ax[1].axhline(0, color="k", lw=0.6)
    ax[1].set(title="Rating (within-year z) per doubling of authors", xlabel="ICLR year", ylabel="slope, 95% CI")
    ax[1].legend(fontsize=8)
    sh = b.pivot(index="year", columns="authors", values="share")[LABELS]
    sh.plot.area(ax=ax[2], cmap="viridis", lw=0)
    ax[2].set(title="Team-size mix of submissions", xlabel="ICLR year", ylabel="share", ylim=(0, 1))
    ax[2].legend(fontsize=7, ncol=3, title="authors", title_fontsize=7, loc="lower left")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_authors_quality.png"), dpi=150)
    print(sl.pivot_table(index=["outcome", "year"], columns="spec", values="slope").round(3).to_string())
    print(pd.read_csv(os.path.join(OUT, "pooled_trend.csv")).round(4).to_string())
    print(pd.read_csv(os.path.join(OUT, "relative_size.csv")).round(3).to_string())
    print(pd.read_csv(os.path.join(OUT, "name_collision_check.csv")).round(3).to_string())


if __name__ == "__main__":
    main()
