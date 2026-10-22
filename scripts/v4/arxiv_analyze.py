"""V4: arXiv abstracts 2018-01 .. 2026-09: ML against non-ML language, and ML sub-areas.

Reads data/v4/arxiv_features.parquet (scripts/v4/arxiv_features.py). Abstracts under 50 tokens dropped.
"Clean" non-ML groups exclude any paper cross-listed to an ML category (cs.LG, cs.CL, cs.CV, cs.AI,
stat.ML). Rates are pooled (sum of counts / sum of tokens) per 1,000 tokens; standard errors use the
linearised ratio estimator over papers.

Writes results/v4/arxiv/{monthly.csv, period_rates.csv, period_index.csv, ml_standardised.csv,
cat_year.csv, topic_year.csv, topic_year_title.csv, timing.csv, solo_quarterly.csv,
team_style.csv, topic_style_year.csv, fig_monthly.png, fig_subareas.png}.
"""
from __future__ import annotations

import os
import sys

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
sys.path.insert(0, HERE)
from topics import TOPICS  # noqa: E402

OUT = os.path.join(ROOT, "results", "v4", "arxiv")
FEATS = ["w_of", "w_in", "w_the", "w_we", "w_our", "w_and", "the_x_of", "self_mention", "hype", "llm_marker",
         "booster", "hedge", "attitude", "nominal", "w_novel", "w_across", "w_leveraging", "w_notably",
         "w_delve", "letters"]
GROUPS = ["ML", "CS other", "eess", "stat other", "math", "physics", "q-bio", "econ/q-fin"]
PERIODS = [("2018", "2018-01", "2018-12"), ("2020", "2020-01", "2020-12"), ("2022", "2022-01", "2022-12"),
           ("2023", "2023-01", "2023-12"), ("2024", "2024-01", "2024-12"), ("2025", "2025-01", "2025-12"),
           ("2026H1", "2026-01", "2026-06"), ("2026Q3", "2026-07", "2026-09")]


def rates(g: pd.DataFrame, feats=FEATS) -> dict:
    tok = g.tokens.to_numpy(float)
    T = tok.sum()
    d = {"papers": len(g), "tokens": T}
    for f in feats:
        y = g[f].to_numpy(float)
        r = y.sum() / T
        se = np.sqrt(((y - r * tok) ** 2).sum()) / T if len(g) > 1 else np.nan
        k = 1 if f == "letters" else 1000
        d[f] = r * k
        d[f + "_se"] = se * k
    return d


def main():
    os.makedirs(OUT, exist_ok=True)
    df = pd.read_parquet(os.path.join(ROOT, "data", "v4", "arxiv_features.parquet"))
    df = df[df.tokens >= 50]
    df["clean"] = (df.group == "ML") | ~df.ml_cross
    df["year"] = df.month.str[:4].astype(int)
    c = df[df.clean & df.group.isin(GROUPS)]

    # A. monthly series per group
    m = [dict(group=gname, month=mo, **rates(g)) for (gname, mo), g in c.groupby(["group", "month"])]
    pd.DataFrame(m).to_csv(os.path.join(OUT, "monthly.csv"), index=False)

    # B. period rates and index to 2022, all papers and single-version papers (abstract = v1 abstract)
    rows = []
    for sub, d in (("all", c), ("v1_only", c[c.n_versions == 1])):
        for gname, g in d.groupby("group"):
            for lab, a, b in PERIODS:
                gg = g[(g.month >= a) & (g.month <= b)]
                rows.append(dict(sample=sub, group=gname, period=lab, **rates(gg)))
    pr = pd.DataFrame(rows)
    pr.to_csv(os.path.join(OUT, "period_rates.csv"), index=False)
    base = pr[pr.period == "2022"].set_index(["sample", "group"])
    idx = pr[["sample", "group", "period", "papers"]].copy()
    for f in FEATS:
        idx[f] = pr[f].to_numpy() / base.loc[list(zip(pr["sample"], pr.group)), f].to_numpy()
    idx.to_csv(os.path.join(OUT, "period_index.csv"), index=False)

    # C. ML direct standardisation: strata = primary category x LLM tag, weights = 2022 token shares
    ml = df[df.group == "ML"].copy()
    ml["stratum"] = ml.primary + "|" + ml.t_llm.map({True: "llm", False: "nollm"})
    w = ml[ml.year == 2022].groupby("stratum").tokens.sum()
    w = w / w.sum()
    srows = []
    for lab, a, b in PERIODS:
        g = ml[(ml.month >= a) & (ml.month <= b)]
        st = g.groupby("stratum")
        crude = rates(g)
        d = {"period": lab, "papers": len(g), "llm_token_share": g[g.t_llm].tokens.sum() / g.tokens.sum()}
        for f in ["w_of", "w_in", "w_we", "w_our", "the_x_of", "hype", "llm_marker", "self_mention", "nominal"]:
            r = st[f].sum() / st.tokens.sum() * 1000
            d[f + "_crude"] = crude[f]
            d[f + "_std2022mix"] = (r.reindex(w.index) * w).sum()
        srows.append(d)
    pd.DataFrame(srows).to_csv(os.path.join(OUT, "ml_standardised.csv"), index=False)

    # D. sub-areas: primary category and topic tags, counts and team size per year
    def team(g):
        a = g.n_authors.astype(float)
        return pd.Series({"papers": len(g), "mean_authors": a.mean(), "median_authors": a.median(),
                          "mean_log2_authors": np.log2(a.clip(lower=1)).mean(), "solo_share": (a == 1).mean(),
                          "le2_share": (a <= 2).mean(), "ge10_share": (a >= 10).mean()})

    cats = df[df.primary.str.startswith(("cs.", "stat.ML", "eess."))]
    ct = cats.groupby(["primary", "year"]).apply(team, include_groups=False).reset_index()
    yr = cats.groupby("year").apply(team, include_groups=False)
    ct["rel_log2_authors"] = ct.mean_log2_authors - ct.year.map(yr.mean_log2_authors)
    ct.to_csv(os.path.join(OUT, "cat_year.csv"), index=False)

    mlx = df[df.ml_cross]  # every paper with an ML category anywhere
    my = mlx.groupby("year").apply(team, include_groups=False)
    for prefix, sfx in (("t_", ""), ("tt_", "_title")):  # title + abstract, and title only
        trows = []
        for k in ["ALL"] + list(TOPICS):
            g = mlx if k == "ALL" else mlx[mlx[prefix + k]]
            s = g.groupby("year").apply(team, include_groups=False).reset_index()
            s["topic"] = k
            trows.append(s)
        tab = pd.concat(trows, ignore_index=True)
        tab["share"] = tab.papers / tab.year.map(my.papers)
        tab["rel_log2_authors"] = tab.mean_log2_authors - tab.year.map(my.mean_log2_authors)
        tab.to_csv(os.path.join(OUT, f"topic_year{sfx}.csv"), index=False)
        if not sfx:
            tt = tab

    srows = []
    sf = ["w_of", "w_we", "w_our", "self_mention", "hype", "llm_marker", "the_x_of", "nominal"]
    for k in ["ALL"] + list(TOPICS):
        g = mlx if k == "ALL" else mlx[mlx["t_" + k]]
        for lab, a, b in PERIODS:
            gg = g[(g.month >= a) & (g.month <= b)]
            srows.append(dict(topic=k, period=lab, **rates(gg, sf)))
    pd.DataFrame(srows).to_csv(os.path.join(OUT, "topic_style_year.csv"), index=False)

    # E. timing: first month (3-month centred mean) at which each series is 10% beyond its 2022 level,
    # and the month of the peak for the rising-then-falling series
    trows = []
    for gname, g in pd.DataFrame(m).groupby("group"):
        g = g.sort_values("month").set_index("month")
        d = {"group": gname}
        for f in ["w_of", "w_in", "the_x_of", "self_mention"]:
            sm = g[f].rolling(3, center=True, min_periods=1).mean()
            b = g.loc["2022-01":"2022-12", f].mean()
            hit = sm[(sm.index >= "2023-01") & (sm < 0.9 * b)]
            d[f + "_10pct_drop"] = hit.index[0] if len(hit) else None
        for f in ["hype", "llm_marker", "w_novel"]:
            sm = g[f].rolling(3, center=True, min_periods=1).mean()
            d[f + "_peak"] = sm.loc["2022-01":].idxmax()
            d[f + "_peak_value"] = sm.max()
            d[f + "_2026_09_over_2018"] = sm.loc["2026-09"] / g.loc["2018-01":"2018-12", f].mean()
        trows.append(d)
    pd.DataFrame(trows).to_csv(os.path.join(OUT, "timing.csv"), index=False)

    # F. single-author share by quarter and group (all papers, no token filter on authorship),
    # and abstract style by team size
    a = pd.read_parquet(os.path.join(ROOT, "data", "v4", "arxiv_features.parquet"),
                        columns=["group", "month", "n_authors", "ml_cross"])
    a = a[(a.group == "ML") | ~a.ml_cross]
    a["quarter"] = a.month.str[:4] + "Q" + ((a.month.str[5:7].astype(int) - 1) // 3 + 1).astype(str)
    q = a.groupby(["group", "quarter"]).agg(papers=("n_authors", "size"),
                                            solo=("n_authors", lambda x: int((x == 1).sum())),
                                            solo_share=("n_authors", lambda x: (x == 1).mean()),
                                            mean_authors=("n_authors", "mean")).reset_index()
    q.to_csv(os.path.join(OUT, "solo_quarterly.csv"), index=False)
    c2 = c.assign(team=pd.cut(c.n_authors, [0, 1, 4, 9, 10_000], labels=["1", "2-4", "5-9", "10+"]))
    rows = []
    for (gname, tm), g in c2[c2.group.isin(["ML", "CS other", "math", "physics"])].groupby(["group", "team"],
                                                                                         observed=True):
        for lab, a0, b0 in PERIODS:
            gg = g[(g.month >= a0) & (g.month <= b0)]
            rows.append(dict(group=gname, team=tm, period=lab,
                             **rates(gg, ["w_of", "the_x_of", "self_mention", "hype", "llm_marker"])))
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "team_style.csv"), index=False)

    # figures
    mm = pd.DataFrame(m)
    mm["t"] = pd.to_datetime(mm.month)
    show = [("w_of", '"of"'), ("w_we", '"we"'), ("self_mention", "self-mention (we/our/us/I)"),
            ("hype", "hype adjectives"), ("llm_marker", "LLM-excess words"), ("the_x_of", '"the X of"')]
    cols = {"ML": "#c0392b", "CS other": "#e67e22", "eess": "#8e44ad", "stat other": "#16a085",
            "math": "#2c3e50", "physics": "#2980b9", "q-bio": "#27ae60", "econ/q-fin": "#7f8c8d"}
    fig, axs = plt.subplots(2, 3, figsize=(15, 8), sharex=True)
    for ax, (f, lab) in zip(axs.flat, show):
        for gname in GROUPS:
            s = mm[mm.group == gname].sort_values("t")
            ax.plot(s.t, s[f].rolling(3, center=True, min_periods=1).mean(), color=cols[gname],
                    lw=2.2 if gname == "ML" else 1.2, label=gname)
        ax.axvline(pd.Timestamp("2022-11-30"), color="grey", ls=":", lw=1)
        ax.set_title(lab + " per 1,000 abstract tokens")
    axs[0, 0].legend(fontsize=8, ncol=2)
    fig.suptitle("arXiv abstracts by month of first posting (3-month mean); non-ML groups exclude ML cross-lists;"
                 " dotted line = ChatGPT release")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_monthly.png"), dpi=110)

    fig, axs = plt.subplots(1, 2, figsize=(15, 7))
    sel = tt[tt.topic != "ALL"]
    a0, a1 = sel[sel.year == 2019].set_index("topic"), sel[sel.year == 2025].set_index("topic")
    x, y = np.log2(a1.share / a0.share), a1.rel_log2_authors - a0.rel_log2_authors
    axs[0].scatter(x, y, s=np.sqrt(a1.papers) * 2, alpha=.6)
    for k in a1.index:
        axs[0].annotate(k, (x[k], y[k]), fontsize=8)
    axs[0].axhline(0, color="grey", lw=.5)
    axs[0].axvline(0, color="grey", lw=.5)
    axs[0].set_xlabel("log2 change in share of ML arXiv papers, 2019 -> 2025")
    axs[0].set_ylabel("change in team size relative to all ML (mean log2 authors)")
    for k in ["llm", "agents", "alignment_safety", "theory_optimization", "rl", "graph", "self_supervised",
              "classic_nlp", "generative"]:
        s = tt[tt.topic == k]
        axs[1].plot(s.year, s.solo_share, label=k)
    s = tt[tt.topic == "ALL"]
    axs[1].plot(s.year, s.solo_share, "k--", label="all ML")
    axs[1].set_ylabel("single-author share")
    axs[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_subareas.png"), dpi=110)


if __name__ == "__main__":
    main()
