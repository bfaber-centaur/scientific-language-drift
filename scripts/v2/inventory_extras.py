"""Gate 0 supplementary tables (run after collect_metadata.py, version_mix.py, corpus_diff.py).

Writes to results/v2/inventory/:
    version_mix_by_status.csv       published/submission share of V1-retained vs V2-added records
    extraction_provenance.csv       cleanup version, extraction method, pages, flags: retained vs added
    cross_venue_title_overlap.csv   venue-year pairs sharing exact normalized titles (>= 25 chars)
    v1_cache_consistency.csv        V1's committed coverage tables vs the cb5553e metadata
"""
import glob
import json
import os

import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
OUT = os.path.join(ROOT, "results", "v2", "inventory")
META = os.path.join(ROOT, "data", "v2", "meta")
NEW, OLD = "2c0dd19", "cb5553e"


def stem(f):
    v, y = os.path.basename(f)[:-8].rsplit("-", 1)
    return v, int(y)


def norm_title(s):
    return s.str.lower().str.replace(r"[^a-z0-9]+", " ", regex=True).str.strip()


mem = pd.read_csv(os.path.join(OUT, "membership.csv.gz"))
added = set(map(tuple, mem[mem.status == "added"][["venue", "year", "paper_id"]].values))


def status(v, y, ids):
    return ["added" if (v, y, p) in added else "retained" for p in ids]


# version mix by status
rows = []
for f in sorted(glob.glob(os.path.join(ROOT, "data", "v2", "version", NEW, "*.parquet"))):
    v, y = stem(f)
    d = pd.read_parquet(f)
    d["status"] = status(v, y, d.paper_id)
    for s, g in d.groupby("status"):
        rows.append(dict(venue=v, year=y, status=s, n=len(g),
                         published_pct=round(100 * (g.version == "published").mean(), 1),
                         submission_pct=round(100 * (g.version == "submission").mean(), 1)))
pd.DataFrame(rows).sort_values(["venue", "year", "status"]).to_csv(
    os.path.join(OUT, "version_mix_by_status.csv"), index=False)

# extraction provenance
rows = []
for f in sorted(glob.glob(os.path.join(META, NEW, "clean", "*.parquet"))):
    v, y = stem(f)
    c = pd.read_parquet(f).merge(pd.read_parquet(f.replace("/clean/", "/direct/"))[["pdf_sha256", "method", "pages"]],
                                 on="pdf_sha256")
    c["status"] = status(v, y, c.paper_id)
    for s, g in c.groupby("status"):
        rows.append(dict(venue=v, year=y, status=s, n=len(g),
                         cleanup_versions=";".join(f"{k}:{n}" for k, n in g.cleanup_version.value_counts().items()),
                         methods=";".join(f"{k}:{n}" for k, n in g.method.value_counts().items()),
                         pages_median=g.pages.median(), flag_mean=round(g.flag_count.mean(), 2)))
pd.DataFrame(rows).to_csv(os.path.join(OUT, "extraction_provenance.csv"), index=False)

# cross-venue exact-title overlap
meta = pd.concat([pd.read_parquet(f, columns=["title", "conference", "year"])
                  for f in glob.glob(os.path.join(META, NEW, "omissions", "*.parquet"))])
meta = meta[meta.title.notna()].copy()
meta["t"] = norm_title(meta.title)
meta = meta[meta.t.str.len() >= 25]
meta["vy"] = meta.conference + "-" + meta.year.astype(str)
sizes = meta.groupby("vy").size()
pairs = {}
for vs in meta.groupby("t").vy.apply(lambda s: sorted(set(s))):
    for i in range(len(vs)):
        for j in range(i + 1, len(vs)):
            pairs[(vs[i], vs[j])] = pairs.get((vs[i], vs[j]), 0) + 1
df = pd.DataFrame([dict(a=a, b=b, shared_titles=n) for (a, b), n in pairs.items()])
df["pct_of_a"] = (100 * df.shared_titles / df.a.map(sizes)).round(2)
df["pct_of_b"] = (100 * df.shared_titles / df.b.map(sizes)).round(2)
df.sort_values("shared_titles", ascending=False).to_csv(os.path.join(OUT, "cross_venue_title_overlap.csv"), index=False)

# V1 committed coverage tables vs cb5553e metadata
v1 = pd.concat([pd.read_csv(os.path.join(ROOT, "results", "coverage_iclr.csv")),
                pd.read_csv(os.path.join(ROOT, "results", "coverage_venues.csv"))])
rows = []
for f in glob.glob(os.path.join(META, OLD, "omissions", "*.parquet")):
    v, y = stem(f)
    d = pd.read_parquet(f)
    oc = d.omission_counts_json.map(json.loads)
    rows.append(dict(venue=v, year=y, rows_meta=len(d), chars_median_meta=d.chars_after.median(),
                     chars_p95_meta=d.chars_after.quantile(.95),
                     mean_refs_meta=oc.map(lambda x: x.get("references", 0)).mean(),
                     mean_table_meta=oc.map(lambda x: x.get("table", 0)).mean()))
m = pd.DataFrame(rows).merge(v1[["venue", "year", "rows", "chars_median", "chars_p95", "mean_references", "mean_table"]],
                             on=["venue", "year"], how="outer")
m["ok"] = ((m.rows == m.rows_meta) & ((m.chars_median - m.chars_median_meta).abs() < 1)
           & ((m.chars_p95 - m.chars_p95_meta).abs() < 1) & ((m.mean_references - m.mean_refs_meta).abs() < 1e-3)
           & ((m.mean_table - m.mean_table_meta).abs() < 1e-3))
m.sort_values(["venue", "year"]).to_csv(os.path.join(OUT, "v1_cache_consistency.csv"), index=False)
print("v1 consistency:", int(m.ok.sum()), "/", len(m))
