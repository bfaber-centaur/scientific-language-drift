"""Figure: corpus expansion matrix (venue x year), V1 revision cb5553e vs V2 revision 2c0dd19.

Reads results/v2/inventory/matrix.csv; writes results/v2/inventory/fig_corpus_expansion.png.
Cell color = V2 coverage (extracted / card total, single-hue sequential); cell text = V2 rows,
V1 rows in parentheses when they differ; "new" marks venue-years absent in V1.
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
OUT = os.path.join(ROOT, "results", "v2", "inventory")

m = pd.read_csv(os.path.join(OUT, "matrix.csv"))
venues = ["iclr", "icml", "neurips", "tmlr", "colm", "corl", "emnlp"]
years = list(range(2013, 2028))
years = [y for y in years if y in set(m.year)]
cov = np.full((len(venues), len(years)), np.nan)
fig, ax = plt.subplots(figsize=(13, 4.2), dpi=150)
for _, r in m.iterrows():
    i, j = venues.index(r.venue), years.index(r.year)
    if r.rows_new == 0:
        continue
    cov[i, j] = min(r.coverage_new_pct, 100)
im = ax.imshow(cov, cmap="Blues", vmin=0, vmax=100, aspect="auto")
for _, r in m.iterrows():
    if r.rows_new == 0:
        continue
    i, j = venues.index(r.venue), years.index(r.year)
    txt = f"{int(r.rows_new):,}"
    if r.file_status == "added":
        txt += "\nnew"
    elif r.rows_old != r.rows_new:
        txt += f"\n({int(r.rows_old):,})"
    ax.text(j, i, txt, ha="center", va="center", fontsize=7,
            color="white" if cov[i, j] > 60 else "#1a1a1a")
ax.set_xticks(range(len(years)), years, fontsize=8)
ax.set_yticks(range(len(venues)), [{"neurips": "NeurIPS", "corl": "CoRL"}.get(v, v.upper()) for v in venues], fontsize=8)
ax.set_xticks(np.arange(-.5, len(years)), minor=True)
ax.set_yticks(np.arange(-.5, len(venues)), minor=True)
ax.grid(which="minor", color="white", linewidth=2)
ax.tick_params(which="both", length=0)
for s in ax.spines.values():
    s.set_visible(False)
cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01)
cb.set_label("V2 coverage, % of card total", fontsize=8)
cb.ax.tick_params(labelsize=7)
ax.set_title("Papers per venue-year at dataset revision 2c0dd19 (V1 revision cb5553e in parentheses where different; "
             "'new' = absent in V1)", fontsize=9, loc="left")
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig_corpus_expansion.png"))
print("wrote fig_corpus_expansion.png")
