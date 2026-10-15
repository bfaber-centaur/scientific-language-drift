"""Lane C (V2): same-paper paired contrasts for the function-word shift.

Pairs are exact normalized-title matches (titles >= 25 characters) between two venue-years, one pair per
title (titles that occur twice in either cohort are dropped), plus Lane E's text-matched pairs under other
titles (results/v2/review/e4_textpairs_*.csv; docs/v2-adversarial-review.md D3) where those exist. For each pair and region the per-paper
counts come from data/v2/lane_c/merged.pkl (scripts/v2/lane_c_analyze.py). The abstract word-sequence
similarity of each pair is computed from the clean text (difflib ratio over lowercase letter tokens) so
lightly edited and rewritten pairs can be separated. Paper text is not written out.

Designs (Gate 0, docs/v2-corpus-inventory.md "Paired designs"):
  P1 iclr-2026 -> icml-2026   submission (by Sep 2025) -> camera-ready finalised in 2026
  P3 iclr-2025 -> icml-2025   the same revision cycle one year earlier (control for P1)
     iclr-2024 -> icml-2024   and two years earlier
  P2 iclr-2026 -> iclr-2027   resubmission, both submissions, same venue
     iclr-2025 -> iclr-2026   the same resubmission design one year earlier (control for P2)
     iclr-2024 -> iclr-2025
  P1b iclr-2026 -> tmlr-2026, colm-2026
Output: results/v2/function_words/pairs_summary.csv, pairs_by_similarity.csv
"""
from __future__ import annotations

import difflib
import os
import sys

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lane_c_fetch import fetch  # noqa: E402
from lane_c_count import regions, TOK  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "results/v2/function_words")
DESIGNS = [("P1", "iclr-2026", "icml-2026"), ("P3", "iclr-2025", "icml-2025"), ("P3", "iclr-2024", "icml-2024"),
           ("P2", "iclr-2026", "iclr-2027"), ("P2ctl", "iclr-2025", "iclr-2026"), ("P2ctl", "iclr-2024", "iclr-2025"),
           ("P1b", "iclr-2026", "tmlr-2026"), ("P1b", "iclr-2026", "colm-2026"), ("P1b", "iclr-2025", "tmlr-2025")]
WORDS = ["of", "in", "we", "and", "the", "a", "to", "for", "with", "on"]
EXTRA = ["hyph_compound", "possessive", "the_x_of", "em_dash"]
REGIONS = ["abstract", "intro600", "prose"]
B = 1000


def abstracts(stem, ids):
    out = {}
    for b in pq.ParquetFile(fetch(f"clean/{stem}.parquet")).iter_batches(batch_size=512, columns=["paper_id", "text"]):
        for pid, text in zip(b.column(0).to_pylist(), b.column(1).to_pylist()):
            if pid in ids:
                out[pid] = regions(text)["abstract"]
    return out


def sim(a, b):
    if not a or not b:
        return np.nan
    x = [w.lower() for w in TOK.findall(a)]
    y = [w.lower() for w in TOK.findall(b)]
    return difflib.SequenceMatcher(None, x, y, autojunk=False).ratio()


def main():
    df = pd.read_pickle(os.path.join(ROOT, "data/v2/lane_c/merged.pkl"))
    df["vy"] = df.venue + "-" + df.year.astype(str)
    allr = df[df.region == "all"]
    rng = np.random.default_rng(20261015)
    summ, bysim, pair_rows = [], [], []
    for design, A, Bc in DESIGNS:
        a = allr[(allr.vy == A) & allr.ntitle.notna() & (allr.ntitle.str.len() >= 25)]
        b = allr[(allr.vy == Bc) & allr.ntitle.notna() & (allr.ntitle.str.len() >= 25)]
        a = a[~a.ntitle.duplicated(keep=False)]
        b = b[~b.ntitle.duplicated(keep=False)]
        a_all, b_all = allr[allr.vy == A], allr[allr.vy == Bc]
        m = a[["ntitle", "paper_id", "version"]].merge(b[["ntitle", "paper_id", "version"]], on="ntitle",
                                                       suffixes=("_a", "_b"))
        m = m[m.paper_id_a != m.paper_id_b]
        m["source"] = "title"
        # Lane E D3: add text-matched pairs (other titles) from results/v2/review/e4_textpairs_*.csv
        for f, flip in ((f"e4_textpairs_{A}_{Bc}.csv", False), (f"e4_textpairs_{Bc}_{A}.csv", True)):
            fp = os.path.join(ROOT, "results/v2/review", f)
            if os.path.exists(fp):
                e = pd.read_csv(fp)
                e = e.rename(columns={"a_id": "paper_id_b", "b_id": "paper_id_a"} if flip else
                             {"a_id": "paper_id_a", "b_id": "paper_id_b"})
                e = e[~e.paper_id_a.isin(m.paper_id_a) & ~e.paper_id_b.isin(m.paper_id_b)]
                va = a_all.set_index("paper_id").version
                vb = b_all.set_index("paper_id").version
                e = e[e.paper_id_a.isin(va.index) & e.paper_id_b.isin(vb.index)]
                m = pd.concat([m, pd.DataFrame({"ntitle": None, "paper_id_a": e.paper_id_a,
                                                "version_a": va.loc[e.paper_id_a].values,
                                                "paper_id_b": e.paper_id_b,
                                                "version_b": vb.loc[e.paper_id_b].values, "source": "text"})],
                              ignore_index=True)
        sa, sb = abstracts(A, set(m.paper_id_a)), abstracts(Bc, set(m.paper_id_b))
        m["abs_sim"] = [sim(sa.get(x), sb.get(y)) for x, y in zip(m.paper_id_a, m.paper_id_b)]
        m["sim_band"] = pd.cut(m.abs_sim, [-0.01, 0.5, 0.8, 0.95, 1.01], labels=["<0.5", "0.5-0.8", "0.8-0.95", ">=0.95"])
        for _, r in m.iterrows():
            pair_rows.append(dict(design=design, a=A, b=Bc, paper_id_a=r.paper_id_a, paper_id_b=r.paper_id_b,
                                  version_a=r.version_a, version_b=r.version_b, source=r.source, abs_sim=round(r.abs_sim, 4)
                                  if r.abs_sim == r.abs_sim else None))
        for reg in REGIONS:
            ra = df[(df.vy == A) & (df.region == reg)].set_index("paper_id")
            rb = df[(df.vy == Bc) & (df.region == reg)].set_index("paper_id")
            mm = m[m.paper_id_a.isin(ra.index) & m.paper_id_b.isin(rb.index)]
            if len(mm) < 20:
                continue
            XA = ra.loc[mm.paper_id_a, ["tokens"] + WORDS + EXTRA].to_numpy(float)
            XB = rb.loc[mm.paper_id_b, ["tokens"] + WORDS + EXTRA].to_numpy(float)

            def change(XA, XB, w=None):
                if w is None:
                    pa, pb = XA.sum(0), XB.sum(0)
                else:
                    pa, pb = w @ XA, w @ XB
                ra_ = pa[..., 1:] / pa[..., :1]
                rb_ = pb[..., 1:] / pb[..., :1]
                return ra_ * 1e6, rb_ * 1e6, (rb_ / ra_ - 1) * 100

            pa, pb, ch = change(XA, XB)
            W = rng.multinomial(len(mm), np.ones(len(mm)) / len(mm), size=B).astype(float)
            _, _, chb = change(XA, XB, W)
            lo, hi = np.percentile(chb, [2.5, 97.5], axis=0)
            # cohort change, all papers, same region (for comparison)
            ca = ra[["tokens"] + WORDS + EXTRA].to_numpy(float).sum(0)
            cb = rb[["tokens"] + WORDS + EXTRA].to_numpy(float).sum(0)
            cch = ((cb[1:] / cb[0]) / (ca[1:] / ca[0]) - 1) * 100
            for i, w in enumerate(WORDS + EXTRA):
                summ.append(dict(design=design, a=A, b=Bc, region=reg, word=w, n_pairs=len(mm),
                                 rate_a=round(pa[i], 1), rate_b=round(pb[i], 1), pair_change_pct=round(ch[i], 1),
                                 lo=round(lo[i], 1), hi=round(hi[i], 1), cohort_change_pct=round(cch[i], 1)))
            for band, g in mm.groupby("sim_band", observed=True):
                if len(g) < 10:
                    continue
                XA_ = ra.loc[g.paper_id_a, ["tokens"] + WORDS].to_numpy(float)
                XB_ = rb.loc[g.paper_id_b, ["tokens"] + WORDS].to_numpy(float)
                pa_, pb_, ch_ = change(XA_, XB_)
                for i, w in enumerate(WORDS[:4]):
                    bysim.append(dict(design=design, a=A, b=Bc, region=reg, sim_band=band, n_pairs=len(g), word=w,
                                      rate_a=round(pa_[i], 1), rate_b=round(pb_[i], 1), pair_change_pct=round(ch_[i], 1)))
        print(design, A, Bc, len(m), "median abs_sim", round(m.abs_sim.median(), 3), flush=True)
    pd.DataFrame(summ).to_csv(os.path.join(OUT, "pairs_summary.csv"), index=False)
    pd.DataFrame(bysim).to_csv(os.path.join(OUT, "pairs_by_similarity.csv"), index=False)
    pd.DataFrame(pair_rows).to_csv(os.path.join(OUT, "pairs.csv.gz"), index=False)


if __name__ == "__main__":
    main()
