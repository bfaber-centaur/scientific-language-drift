"""Lane D (V2): sensitivity of the non-ICLR appendix year-over-year steps to ICLR-overlap papers.

Usage:
    python3 scripts/v2/appendix_overlap_exclusion.py data/v2/appendix results/v2/appendices

Lane E (docs/v2-adversarial-review.md, E4) found that exact-title matching undercounts papers shared
between ICLR and other venues. A paper revised from an ICLR submission for ICML gains ~640 appendix
tokens on its own (pairs_summary.csv), so a venue's step is only independent evidence once those
papers are removed. Excluded here: the non-ICLR side of every pair matched by exact normalized title
(this lane's pairs_*.csv) OR by text (Lane E's results/v2/review/e4_textpairs_*.csv), in every year
where a match file exists. Same population, strata and bootstrap as appendix_analyze_v2.py.

Output: results/v2/appendices/yoy_overlap_excluded.csv
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import appendix_analyze_v2 as a2  # noqa: E402

ROOT, a1 = a2.ROOT, a2.a1
REV = os.path.join(ROOT, "results", "v2", "review")
APX = os.path.join(ROOT, "results", "v2", "appendices")
# (venue, year of the non-ICLR cohort) -> (Lane E file, column holding that venue's id, Lane D pairs file or None)
MATCHES = {
    ("icml", 2024): ("e4_textpairs_iclr-2024_icml-2024.csv", "b_id", None),
    ("icml", 2025): ("e4_textpairs_iclr-2025_icml-2025.csv", "b_id", "pairs_iclr2025_icml2025.csv"),
    ("icml", 2026): ("e4_textpairs_iclr-2026_icml-2026.csv", "b_id", "pairs_iclr2026_icml2026.csv"),
    ("colm", 2026): ("e4_textpairs_colm-2026_iclr-2026.csv", "a_id", None),
    ("tmlr", 2026): ("e4_textpairs_iclr-2026_tmlr-2026.csv", "b_id", None),
}
STEPS = [("icml", 2023, 2024), ("icml", 2024, 2025), ("icml", 2025, 2026), ("colm", 2025, 2026), ("tmlr", 2025, 2026)]


def overlap_ids():
    rows = []
    for (v, y), (ef, col, pf) in MATCHES.items():
        ids = set(pd.read_csv(os.path.join(REV, ef))[col])
        n_text = len(ids)
        if pf:
            ids |= set(pd.read_csv(os.path.join(APX, pf)).doc_b)
        rows += [{"venue": v, "year": y, "doc_id": i} for i in ids]
        print(v, y, "text-matched", n_text, "-> title or text", len(ids))
    return pd.DataFrame(rows).assign(overlap=True)


def main():
    src, out = sys.argv[1], sys.argv[2]
    papers = a1.derive(pd.read_parquet(os.path.join(src, "papers.parquet")))
    papers = papers.merge(a2.load_versions(), on=["venue", "year", "doc_id"], how="left")
    papers["version"] = papers.version.fillna("unknown")
    pop = papers[~papers.short & ~papers.template & papers.venue.isin(["icml", "colm", "tmlr"])]
    pop = pop.merge(overlap_ids(), on=["venue", "year", "doc_id"], how="left")
    pop["overlap"] = pop.overlap.fillna(False).astype(bool)
    rows = []
    for stratum in ("published", "all"):
        sel = pop if stratum == "all" else pop[pop.version == stratum]
        for v, y0, y1 in STEPS:
            for excl in (False, True):
                s = sel[sel.venue == v]
                if excl:
                    s = s[~s.overlap]
                A, B = s[s.year == y0], s[s.year == y1]
                rng = np.random.default_rng(a2.SEED)
                for m in ("main_tokens", "appx_tokens"):
                    d, lo, hi = a1.boot_median_diff(A[m], B[m], rng, reps=1000)
                    rows.append({"venue": v, "stratum": stratum, "from": y0, "to": y1,
                                 "iclr_overlap": "excluded" if excl else "included", "measure": m,
                                 "n_from": len(A), "n_to": len(B),
                                 "n_overlap_dropped_to": int(sel[(sel.venue == v) & (sel.year == y1)].overlap.sum()) if excl else 0,
                                 "median_from": A[m].median(), "median_to": B[m].median(),
                                 "median_diff": d, "ci_lo": lo, "ci_hi": hi})
    t = pd.DataFrame(rows)
    t.to_csv(os.path.join(out, "yoy_overlap_excluded.csv"), index=False, float_format="%.4g")
    print(t[(t.measure == "appx_tokens") & (t.stratum == "published")].to_string(index=False))


if __name__ == "__main__":
    main()
