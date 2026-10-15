"""Gate 1: V1 -> V2 change in per-venue-year descriptive estimates, split by source.

Because the update is purely additive (docs/v2-corpus-inventory.md), for any per-paper quantity x
    V2 mean = (n_r * mean_r + n_a * mean_a) / (n_r + n_a)
and V1 mean = mean_r exactly, so
    delta = V2 - V1 = share_added * (mean_a - mean_r)          (added-records term)
with the modified-records term and the methodology term both identically zero. Medians do
not decompose additively; they are reported side by side.

Inputs: data/v2/structure/2c0dd19/*.parquet, data/v2/version/2c0dd19/*.parquet,
        results/v2/inventory/membership.csv.gz
Outputs: results/v2/diff/structure_by_status.csv, structure_by_status_version.csv, v1_v2_structure_delta.csv,
         results/v2/diff/fig_v1_v2_shift.png
"""
import glob
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
OUT = os.path.join(ROOT, "results", "v2", "diff")
os.makedirs(OUT, exist_ok=True)
mem = pd.read_csv(os.path.join(ROOT, "results", "v2", "inventory", "membership.csv.gz"))

parts = []
for f in glob.glob(os.path.join(ROOT, "data", "v2", "structure", "2c0dd19", "*.parquet")):
    venue, year = os.path.basename(f)[:-8].rsplit("-", 1)
    s = pd.read_parquet(f)
    v = pd.read_parquet(f.replace("/structure/", "/version/"))[["pdf_sha256", "version"]]
    s = s.merge(v, on="pdf_sha256", how="left")
    s["venue"], s["year"] = venue, int(year)
    parts.append(s)
d = pd.concat(parts, ignore_index=True)
d = d.merge(mem, on=["venue", "year", "paper_id"], how="left")
d["status"] = d.status.fillna("retained")
d = d.drop_duplicates(["venue", "year", "pdf_sha256"])
d = d[d.chars >= 2000]  # V1 exclusion rule for short/placeholder texts
d["post_share"] = d.post_chars / d.chars
d["published"] = (d.version == "published").astype(float)
d["submission"] = (d.version == "submission").astype(float)

METRICS = ["chars", "body_chars", "post_chars", "post_share", "pages", "published"]
g = d.groupby(["venue", "year", "status"])
prof = g[METRICS].mean().add_suffix("_mean").join(g[["chars", "body_chars", "post_share", "pages"]].median()
                                                  .add_suffix("_median")).join(g.size().rename("n")).reset_index()
prof.round(4).to_csv(os.path.join(OUT, "structure_by_status.csv"), index=False)

rows = []
for (venue, year), gg in d.groupby(["venue", "year"]):
    r, a = gg[gg.status == "retained"], gg[gg.status == "added"]
    for m in METRICS:
        v2 = gg[m].mean()
        v1 = r[m].mean() if len(r) else float("nan")
        rows.append(dict(venue=venue, year=year, metric=m, n_v1=len(r), n_added=len(a),
                         v1=v1, v2=v2, delta=v2 - v1,
                         added_term=(len(a) / len(gg)) * (a[m].mean() - r[m].mean()) if len(a) and len(r) else float("nan"),
                         modified_term=0.0, methodology_term=0.0,
                         rel_change_pct=100 * (v2 - v1) / v1 if len(r) and v1 else float("nan")))
w = pd.DataFrame(rows)
w.round(5).to_csv(os.path.join(OUT, "v1_v2_structure_delta.csv"), index=False)

# Figure: V1 vs V2 means for venue-years that changed, by metric (one panel per metric).
ch = w[(w.n_added > 0) & (w.n_v1 > 0)].copy()
ch["label"] = ch.venue.str.upper().str.replace("NEURIPS", "NeurIPS") + " " + ch.year.astype(str)
show = ["body_chars", "post_share", "published"]
titles = {"body_chars": "Main-body characters (mean)", "post_share": "Post-reference share of text (mean)",
          "published": "Camera-ready share"}
fig, axes = plt.subplots(1, 3, figsize=(13, 5), dpi=150, sharey=True)
labels = sorted(ch.label.unique(), key=lambda s: (s.split()[0], s.split()[1]))
for ax, m in zip(axes, show):
    sub = ch[(ch.metric == m) & (ch.n_v1 > 0)].set_index("label").reindex(labels)
    y = range(len(labels))
    ax.hlines(y, sub.v1, sub.v2, color="#9aa5b1", linewidth=2)
    ax.scatter(sub.v1, y, s=36, color="#9aa5b1", label="V1 records (cb5553e)", zorder=3)
    ax.scatter(sub.v2, y, s=36, color="#1f5aa6", label="all V2 records (2c0dd19)", zorder=3)
    ax.set_title(titles[m], fontsize=9, loc="left")
    ax.tick_params(labelsize=8)
    ax.grid(axis="x", color="#e5e7eb", linewidth=0.8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
axes[0].set_yticks(range(len(labels)), labels)
axes[0].invert_yaxis()
fig.legend(*axes[0].get_legend_handles_labels(), fontsize=8, frameon=False, loc="upper right", ncol=2)
fig.suptitle("Venue-years that gained records: V1 estimate vs V2 estimate (difference = added records only)",
             fontsize=10, x=0.01, ha="left")
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig_v1_v2_shift.png"))
print(w[(w.n_added > 0) & (w.n_v1 > 0) & w.metric.isin(["body_chars", "post_share", "published"])]
      [["venue", "year", "metric", "v1", "v2", "rel_change_pct"]].round(3).to_string())

# Same profile within version strata (are added camera-ready papers like V1's camera-ready papers?).
sv = d[d.version.isin(["published", "submission"])].groupby(["venue", "year", "status", "version"])
sv = sv.agg(n=("paper_id", "size"), body_med=("body_chars", "median"),
            post_share_med=("post_share", "median"), pages=("pages", "median")).reset_index()
sv = sv[sv.set_index(["venue", "year"]).index.isin(w[(w.n_added > 0) & (w.n_v1 > 0)].set_index(["venue", "year"]).index)]
sv.round(3).to_csv(os.path.join(OUT, "structure_by_status_version.csv"), index=False)
