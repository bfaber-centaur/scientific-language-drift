"""V3: trends in corpus-linguistic style features, their relation to review outcomes and team size, and keyness.

Inputs: data/v3/style/*.parquet (scripts/v3/style_features.py), data/v3/review_meta.parquet.
Papers with fewer than 500 body tokens are dropped. ICLR version is held fixed by decision: accepted =
camera-ready; reject / withdraw / desk_reject = submission (results/v3/style/version_proxy_check.csv).

Outputs in results/v3/style/:
  trends.csv               per venue-year x group (iclr_submission, iclr_accepted, iclr2027, icml, neurips)
                           mean and median of each feature
  rating_slopes.csv        per ICLR year, submission versions with a rating: rating_z on the feature
                           (standardised within year), controlling log2 authors and log tokens
  team_slopes.csv          per ICLR year, all papers: feature z on log2 authors (+ log tokens + accepted)
  keyness_*.csv            Dunning log-likelihood G2 and Hardie (2014) Log Ratio, unigrams
  fig_style_trends.png, fig_style_rating.png
"""
from __future__ import annotations

import glob
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import statsmodels.formula.api as smf  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
SRC = os.path.join(ROOT, "data", "v3", "style")
OUT = os.path.join(ROOT, "results", "v3", "style")
FEATS = ["hedge", "booster", "attitude", "self_mention", "engagement", "hype", "llm_marker", "nominal", "passive",
         "mtld", "mattr", "word_len", "sent_len"]
WORDS = ["w_we", "w_our", "w_novel", "w_propose", "w_delve", "w_notably", "w_however", "w_the", "w_of", "w_that",
         "w_which"]


def load():
    st = pd.concat([pd.read_parquet(f) for f in glob.glob(os.path.join(SRC, "[a-z]*-*.parquet"))
                    if not os.path.basename(f).startswith("counts_")])
    st = st[st.tokens >= 500]
    meta = pd.read_parquet(os.path.join(ROOT, "data", "v3", "review_meta.parquet"))
    st = st.merge(meta.drop(columns=["year"]), on="doc_id", how="left")
    st["group"] = np.select(
        [(st.venue == "iclr") & (st.year == 2027),
         (st.venue == "iclr") & (st.decision == "accept"),
         (st.venue == "iclr") & st.decision.isin(["reject", "withdraw", "desk_reject"])],
        ["iclr2027_submission", "iclr_accepted", "iclr_submission"], default=st.venue)
    st["ltok"] = np.log(st.tokens)
    st["la"] = np.log2(st.n_authors)
    return st


def keyness(a: pd.Series, b: pd.Series, min_total=50) -> pd.DataFrame:
    """Dunning G2 and Log Ratio (binary log of the ratio of relative frequencies, +0.5 smoothing)."""
    df = pd.concat([a.rename("a"), b.rename("b")], axis=1).fillna(0)
    df = df[(df.a + df.b) >= min_total]
    na, nb = a.sum(), b.sum()
    ea = (df.a + df.b) * na / (na + nb)
    eb = (df.a + df.b) * nb / (na + nb)
    with np.errstate(divide="ignore", invalid="ignore"):
        g2 = 2 * (np.where(df.a > 0, df.a * np.log(df.a / ea), 0) + np.where(df.b > 0, df.b * np.log(df.b / eb), 0))
    df["per_m_a"] = df.a / na * 1e6
    df["per_m_b"] = df.b / nb * 1e6
    df["log_ratio"] = np.log2(((df.a + 0.5) / na) / ((df.b + 0.5) / nb))
    df["g2"] = g2 * np.sign(df.log_ratio)
    return df.sort_values("g2", ascending=False)


def counts(venue_year, decisions):
    c = pd.read_parquet(os.path.join(SRC, f"counts_{venue_year}.parquet"))
    return c[c.decision.isin(decisions)].groupby("token").n.sum()


def main():
    os.makedirs(OUT, exist_ok=True)
    st = load()
    cols = FEATS + WORDS
    tr = st.groupby(["group", "year"])[cols].agg(["mean", "median"])
    tr.columns = [f"{a}_{b}" for a, b in tr.columns]
    tr.insert(0, "papers", st.groupby(["group", "year"]).size())
    tr.to_csv(os.path.join(OUT, "trends.csv"))

    ic = st[(st.venue == "iclr") & (st.year <= 2026)].copy()
    for f in cols:
        ic[f + "_z"] = ic.groupby("year")[f].transform(lambda s: (s - s.mean()) / s.std())
    rs, ts = [], []
    for y, d in ic.groupby("year"):
        sub = d[d.decision.isin(["reject", "withdraw", "desk_reject"]) & d.rating_z.notna() & d.la.notna()]
        for f in cols:
            m = smf.ols(f"rating_z ~ {f}_z + la + ltok", sub).fit(cov_type="HC1")
            rs.append({"year": y, "feature": f, "slope": m.params[f + "_z"], "se": m.bse[f + "_z"], "n": int(m.nobs)})
            dd = d.dropna(subset=["la"]).assign(acc=(d.decision == "accept").astype(float))
            m2 = smf.ols(f"{f}_z ~ la + ltok + acc", dd).fit(cov_type="HC1")
            ts.append({"year": y, "feature": f, "slope": m2.params["la"], "se": m2.bse["la"], "n": int(m2.nobs)})
    rs, ts = pd.DataFrame(rs), pd.DataFrame(ts)
    rs.to_csv(os.path.join(OUT, "rating_slopes.csv"), index=False)
    ts.to_csv(os.path.join(OUT, "team_slopes.csv"), index=False)

    # Keyness.
    sub = ["reject", "withdraw", "desk_reject"]
    pairs = {
        "keyness_iclr2026sub_vs_2023sub": (("iclr-2026", sub), ("iclr-2023", sub)),
        "keyness_iclr2027_vs_2026sub": (("iclr-2027", ["none"]), ("iclr-2026", sub)),
        "keyness_iclr2026_withdrawn_vs_rejected": (("iclr-2026", ["withdraw"]), ("iclr-2026", ["reject"])),
        "keyness_iclr2026_deskrej_vs_rejected": (("iclr-2026", ["desk_reject"]), ("iclr-2026", ["reject"])),
        "keyness_iclr2023_withdrawn_vs_rejected": (("iclr-2023", ["withdraw"]), ("iclr-2023", ["reject"])),
        "keyness_iclr2026_accepted_vs_rejected": (("iclr-2026", ["accept"]), ("iclr-2026", ["reject"])),
    }
    for name, (a, b) in pairs.items():
        if not all(os.path.exists(os.path.join(SRC, f"counts_{x[0]}.parquet")) for x in (a, b)):
            continue
        k = keyness(counts(*a), counts(*b))
        pd.concat([k.head(150), k.tail(150)]).to_csv(os.path.join(OUT, name + ".csv"))

    # Figures.
    show = ["hedge", "booster", "hype", "llm_marker", "self_mention", "attitude", "nominal", "passive", "mtld",
            "sent_len", "word_len", "engagement"]
    t = tr.reset_index()
    fig, axs = plt.subplots(3, 4, figsize=(16, 10))
    styles = {"iclr_submission": ("#1f77b4", "o", "ICLR submissions (rejected/withdrawn)"),
              "iclr_accepted": ("#2ca02c", "s", "ICLR accepted (camera-ready)"),
              "iclr2027_submission": ("#d62728", "D", "ICLR 2027 submissions"),
              "icml": ("#9467bd", "^", "ICML accepted"), "neurips": ("#8c564b", "v", "NeurIPS accepted")}
    for ax, f in zip(axs.flat, show):
        for g, (c, mk, lab) in styles.items():
            s = t[t.group == g]
            ax.plot(s.year, s[f + "_mean"], marker=mk, ms=4, color=c, label=lab, lw=1.2 if g.startswith("iclr") else 0)
        ax.set_title(f)
        ax.grid(alpha=0.3)
    axs[0, 0].legend(fontsize=7)
    fig.suptitle("Style features per 1,000 body tokens (mtld, mattr, word_len, sent_len in own units), mean per paper")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_style_trends.png"), dpi=130)

    fig, ax = plt.subplots(1, 2, figsize=(14, 4.8))
    for f in ["hedge", "booster", "hype", "llm_marker", "self_mention", "nominal", "mtld", "sent_len"]:
        s = rs[rs.feature == f]
        ax[0].plot(s.year, s.slope, marker="o", ms=3, label=f)
        s = ts[ts.feature == f]
        ax[1].plot(s.year, s.slope, marker="o", ms=3, label=f)
    ax[0].axhline(0, color="k", lw=0.6)
    ax[1].axhline(0, color="k", lw=0.6)
    ax[0].set(title="Rating z per 1 SD of feature (submission versions;\ncontrols: log2 authors, log length)",
              xlabel="ICLR year")
    ax[1].set(title="Feature z per doubling of authors\n(controls: log length, accepted)", xlabel="ICLR year")
    ax[0].legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_style_rating.png"), dpi=130)

    print(rs.pivot(index="feature", columns="year", values="slope").round(3).to_string())
    print(ts.pivot(index="feature", columns="year", values="slope").round(3).to_string())


if __name__ == "__main__":
    main()
