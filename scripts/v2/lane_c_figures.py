"""Lane C (V2): visualization 3 (function-word trajectories) and 4 (cross-venue heatmap).

Reads results/v2/function_words/rates_by_cohort.csv (scripts/v2/lane_c_analyze.py) and writes
fig3_trajectories.{png,svg} with fig3_trajectories.csv and fig4_heatmap.{png,svg} with fig4_heatmap.csv.
Corpus: woog/open-text-detector-papers @ 2c0dd192a3d3ba6605ed3f5ed5df145dddbdcb27, clean config.
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "results/v2/function_words")
REV = "2c0dd19"
COHORTS = [  # label, venue, version, colour, marker
    ("ICLR submissions", "iclr", "submission", "#0072B2", "o"),
    ("ICLR camera-ready", "iclr", "published", "#56B4E9", "s"),
    ("ICML camera-ready", "icml", "published", "#D55E00", "D"),
    ("NeurIPS camera-ready", "neurips", "published", "#009E73", "^"),
    ("TMLR published", "tmlr", "published", "#CC79A7", "v"),
    ("COLM camera-ready", "colm", "published", "#E69F00", "P"),
    ("CoRL camera-ready", "corl", "published", "#999999", "X"),
]
WORDS = ["of", "in", "we", "and"]
MIN_N = 100


def main():
    r = pd.read_csv(os.path.join(OUT, "rates_by_cohort.csv"))
    r = r[r.year >= 2017]
    regions = [("abstract", "Abstract"), ("prose", "Main-body running prose")]
    fig, axes = plt.subplots(2, 4, figsize=(15, 7.2), sharex=True)
    rows = []
    for i, (reg, rlab) in enumerate(regions):
        for j, w in enumerate(WORDS):
            ax = axes[i, j]
            for lab, v, ver, col, mk in COHORTS:
                s = r[(r.venue == v) & (r.version == ver) & (r.region == reg) & (r.n_papers >= MIN_N)].sort_values("year")
                if s.empty:
                    continue
                ax.plot(s.year, s[w] / 1000, color=col, marker=mk, ms=4, lw=1.6, label=lab)
                ax.fill_between(s.year, s[w + "_lo"] / 1000, s[w + "_hi"] / 1000, color=col, alpha=0.15, lw=0)
                for _, x in s.iterrows():
                    rows.append(dict(region=reg, word=w, cohort=lab, venue=v, version=ver, year=x.year,
                                     n_papers=x.n_papers, rate_per_million=x[w], lo=x[w + "_lo"], hi=x[w + "_hi"]))
            ax.set_title(f"“{w}” · {rlab.lower()}", fontsize=10)
            ax.grid(alpha=0.25)
            ax.spines[["top", "right"]].set_visible(False)
            if j == 0:
                ax.set_ylabel("per thousand letter tokens")
    for ax in axes[1]:
        ax.set_xticks(range(2017, 2028, 2))
    axes[0, 0].legend(fontsize=7.5, frameon=False, loc="lower left")
    fig.suptitle("Function-word rates by venue and version, V2 corpus (clean text, letters-only tokens; "
                 f"bands: 95% paper bootstrap; cohorts with ≥{MIN_N} papers)", fontsize=10.5)
    fig.text(0.01, 0.005, f"woog/open-text-detector-papers @ {REV} · Lane C · results/v2/function_words/fig3_trajectories.csv",
             fontsize=7, color="#555")
    fig.tight_layout(rect=(0, 0.02, 1, 0.96))
    for ext in ("png", "svg"):
        fig.savefig(os.path.join(OUT, f"fig3_trajectories.{ext}"), dpi=150)
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "fig3_trajectories.csv"), index=False)

    # fig4: % change vs each cohort's 2023 rate (COLM: 2024), running prose
    cols = ["of", "in", "we", "and", "the", "a", "to", "for", "with", "hyph_compound", "em_dash"]
    labels = ["of", "in", "we", "and", "the", "a", "to", "for", "with", "hyph.\ncompounds", "em\ndash"]
    hm, ylabels = [], []
    base_year = {"colm": 2024}
    for lab, v, ver, _, _ in COHORTS + [("EMNLP 2023", "emnlp", "all", None, None)]:
        s = r[(r.venue == v) & (r.version == ver) & (r.region == "prose") & (r.n_papers >= MIN_N)].set_index("year")
        by = base_year.get(v, 2023)
        if by not in s.index:
            continue
        for y in sorted(s.index):
            if y <= by:
                continue
            hm.append([(s.loc[y, c] / s.loc[by, c] - 1) * 100 for c in cols])
            ylabels.append(f"{lab} {y} vs {by}")
    hm = np.array(hm)
    fig, ax = plt.subplots(figsize=(11, 0.42 * len(ylabels) + 1.8))
    im = ax.imshow(np.clip(hm, -60, 60), cmap="RdBu_r", vmin=-60, vmax=60, aspect="auto")
    ax.set_xticks(range(len(cols)), labels, fontsize=9)
    ax.set_yticks(range(len(ylabels)), ylabels, fontsize=9)
    for a in range(hm.shape[0]):
        for b in range(hm.shape[1]):
            ax.text(b, a, f"{hm[a, b]:+.0f}", ha="center", va="center", fontsize=7.5,
                    color="white" if abs(hm[a, b]) > 35 else "black")
    cb = fig.colorbar(im, ax=ax, shrink=0.8)
    cb.set_label("% change in rate per million letter tokens (clipped at ±60)")
    ax.set_title("Change since 2023 in main-body running prose, by venue and version (COLM: since 2024)", fontsize=10.5)
    fig.text(0.01, 0.005, f"woog/open-text-detector-papers @ {REV} · Lane C · results/v2/function_words/fig4_heatmap.csv",
             fontsize=7, color="#555")
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    for ext in ("png", "svg"):
        fig.savefig(os.path.join(OUT, f"fig4_heatmap.{ext}"), dpi=150)
    pd.DataFrame(hm.round(1), index=ylabels, columns=cols).to_csv(os.path.join(OUT, "fig4_heatmap.csv"))


# Approximate submission deadlines (drafting date) per venue-year, from the venues' usual calendars.
# Not checked per paper; ICLR Y closes in late September of Y-1, ICML Y in late January of Y,
# COLM Y in late March, CoRL Y in late spring, NeurIPS Y in mid-May. TMLR (rolling) is omitted.
DEADLINE = {"iclr": lambda y: y - 1 + 0.73, "icml": lambda y: y + 0.08, "colm": lambda y: y + 0.24,
            "corl": lambda y: y + 0.40, "neurips": lambda y: y + 0.38}


def drafting_figure():
    r = pd.read_csv(os.path.join(OUT, "rates_by_cohort.csv"))
    sel = [c for c in COHORTS if c[1] in DEADLINE and not (c[1] == "iclr" and c[2] == "published")]
    fig, axes = plt.subplots(1, 4, figsize=(15, 3.9), sharex=True)
    rows = []
    for ax, w in zip(axes, WORDS):
        for lab, v, ver, col, mk in sel:
            s = r[(r.venue == v) & (r.version == ver) & (r.region == "prose") & (r.n_papers >= MIN_N) & (r.year >= 2019)]
            s = s.assign(x=s.year.map(DEADLINE[v])).sort_values("x")
            if 2024 not in set(s.year):
                continue
            base = s.loc[s.year == 2024, w].iloc[0]  # each venue indexed to its own 2024 rate (Lane E C1)
            s = s.assign(index=s[w] / base * 100)
            ax.plot(s.x, s["index"], color=col, marker=mk, ms=4.5, lw=1.4, label=lab.replace(" camera-ready", ""))
            for _, x in s.iterrows():
                rows.append(dict(word=w, cohort=lab, year=x.year, approx_deadline=round(x.x, 2), n_papers=x.n_papers,
                                 rate_per_million=x[w], index_2024_eq_100=round(x["index"], 1)))
        ax.set_title(f"“{w}” · main-body running prose", fontsize=10)
        ax.axhline(100, color="#888", lw=0.8)
        ax.grid(alpha=0.25)
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_xlabel("approximate submission deadline")
    axes[0].set_ylabel("rate, own 2024 = 100")
    axes[0].legend(fontsize=7.5, frameon=False, loc="lower left")
    fig.suptitle("Each venue's rate relative to its own 2024 cohort, placed at the approximate submission deadline (levels are not compared across venues)",
                 fontsize=10.5)
    fig.text(0.01, 0.005, f"woog/open-text-detector-papers @ {REV} · Lane C · results/v2/function_words/fig3b_by_drafting_date.csv",
             fontsize=7, color="#555")
    fig.tight_layout(rect=(0, 0.03, 1, 0.94))
    for ext in ("png", "svg"):
        fig.savefig(os.path.join(OUT, f"fig3b_by_drafting_date.{ext}"), dpi=150)
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "fig3b_by_drafting_date.csv"), index=False)


if __name__ == "__main__":
    main()
    drafting_figure()
