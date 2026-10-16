"""Gate 5: cross-venue heatmap of stylistic markers (directive visualization 4, marker half).

Reads Lane B's `results/v2/replication/venues/venue_metrics.csv` (V2 pin 2c0dd19, main body) and
writes `results/v2/integration/fig4c_marker_heatmap.{png,csv}`. No new counting: every value is a
Lane B estimate. Cell colour is the change from the cohort series' baseline year (percentage points
of papers; for "of", percent change of the per-million rate), the annotation is the level. Read
along rows of one venue: levels are not comparable across formats (Gate 0 item 9).
"""
import pathlib
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "results/v2/replication/venues/venue_metrics.csv"
OUT = ROOT / "results/v2/integration"
REVISION = "2c0dd192a3d3ba6605ed3f5ed5df145dddbdcb27"

# (label, venue, group, years, baseline year); groups follow Lane B's venue table.
SERIES = [
    ("ICLR submissions", "iclr", "under_review", [2023, 2024, 2025, 2026, 2027], 2023),
    ("ICML camera-ready, no ICLR overlap", "icml", "published_no_overlap", [2023, 2024, 2025, 2026], 2023),
    ("NeurIPS camera-ready", "neurips", "published", [2023, 2024, 2025], 2023),
    ("COLM camera-ready", "colm", "published", [2024, 2025, 2026], 2024),
    ("TMLR published", "tmlr", "published", [2023, 2024, 2025, 2026], 2023),
    ("TMLR submissions", "tmlr", "under_review", [2023, 2024, 2025, 2026], 2023),
    ("CoRL camera-ready", "corl", "published", [2023, 2024, 2025], 2023),
]
MARKERS = [  # (column label, metric, kind)
    ("delve", "prev:delve", "pp"),
    ("underscores", "prev:underscores", "pp"),
    ("a novel", "prev:a novel", "pp"),
    ("we propose", "prev:we propose", "pp"),
    ("notably", "prev:notably", "pp"),
    ("test whether", "prev:test whether", "pp"),
    ("held fixed", "prev:held fixed", "pp"),
    ("percentage points", "prev:percentage points", "pp"),
    ('"of" per million', "pm:of", "pct"),
]


def main() -> int:
    vm = pd.read_csv(SRC)
    rows = []
    for label, venue, group, years, base in SERIES:
        sub = vm[(vm.venue == venue) & (vm.group == group)]
        for year in years:
            for col, metric, kind in MARKERS:
                cell = sub[(sub.year == year) & (sub.metric == metric)]
                ref = sub[(sub.year == base) & (sub.metric == metric)]
                if cell.empty or ref.empty:
                    continue
                v, b = float(cell.value.iloc[0]), float(ref.value.iloc[0])
                change = (v - b) * 100 if kind == "pp" else (v / b - 1) * 100
                level = v * 100 if kind == "pp" else v
                rows.append(dict(series=label, venue=venue, group=group, year=year,
                                 papers=int(cell.papers.iloc[0]), marker=col, metric=metric,
                                 level=level, level_unit="% of papers" if kind == "pp" else "per million",
                                 baseline_year=base,
                                 change=change, change_unit="pp" if kind == "pp" else "% change",
                                 revision=REVISION))
    t = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    t.to_csv(OUT / "fig4c_marker_heatmap.csv", index=False, float_format="%.4g")

    t["row"] = t.series + " " + t.year.astype(str) + " (n " + t.papers.map("{:,}".format) + ")"
    order = list(dict.fromkeys(t.row))
    cols = [m[0] for m in MARKERS]
    chg = t.pivot(index="row", columns="marker", values="change").reindex(index=order, columns=cols)
    lvl = t.pivot(index="row", columns="marker", values="level").reindex(index=order, columns=cols)
    scaled = chg / chg.abs().max()  # each column on its own scale

    fig, ax = plt.subplots(figsize=(11.5, 0.36 * len(order) + 1.8))
    ax.imshow(scaled.values, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
    for i in range(len(order)):
        for j, c in enumerate(cols):
            v = lvl.iloc[i, j]
            if np.isnan(v):
                continue
            txt = f"{v/1000:.1f}k" if c.startswith('"of"') else f"{v:.1f}"
            ax.text(j, i, txt, ha="center", va="center", fontsize=7.5,
                    color="white" if abs(scaled.iloc[i, j]) > 0.6 else "black")
    ax.set_xticks(range(len(cols)), cols, rotation=30, ha="right", fontsize=9)
    ax.set_yticks(range(len(order)), order, fontsize=8)
    prev = None
    for i, r in enumerate(order):
        s = t[t.row == r].series.iloc[0]
        if prev is not None and s != prev:
            ax.axhline(i - 0.5, color="black", lw=0.8)
        prev = s
    ax.set_title("Stylistic markers by venue and year, main body (V2 @ 2c0dd19)\n"
                 "number = level (% of papers; \"of\" per million)\n"
                 "colour = change from the series' first year, each column on its own scale (red up, blue down)", fontsize=9.5)
    fig.tight_layout()
    fig.savefig(OUT / "fig4c_marker_heatmap.png", dpi=150)
    print(f"wrote {len(t)} cells, {len(order)} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
