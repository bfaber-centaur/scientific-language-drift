"""Lane B (V2 replication): V1 vs V2 comparison tables, verdicts, waterfall and figures 2, 6, 7.

Usage:
    python3 scripts/v2/replication_compare.py --views ~/work/views [--v1repro-tables ~/work/v1repro_tables]

Inputs
    --views DIR   one count_ngrams-format directory per view (scripts/v2/replication_views.py):
                  v1repro, add2024, add2026, v2def, v2main, member:v1 -> "member_v1", member:added -> "member_added"
    results/full/{body,longitudinal}        V1 tables (read only)
    results/v2/replication/v2main/longitudinal   V2 longitudinal run (scripts/longitudinal.py)
    results/v2/replication/venues/venue_metrics.csv  (scripts/v2/venue_replication.py)

Outputs in results/v2/replication/ (every table names its corpus revision and view):
    exactness_v1repro.csv      V1 records recounted at the V2 pin vs the committed V1 tables
    series_by_view.csv         per-year count, df, docs, positions, per_million, prevalence of every
                               target n-gram in every view, all versions and under_review only
    contrast_check.csv         this script's cohort log2 on v1repro vs V1's committed log2_cw (formula check)
    findings_v1_vs_v2.csv      each V1 finding's effect in V1 and V2, with the verdict (pre-specified rules)
    rankings_v1_vs_v2.csv      V1 top-100 risers/fallers: V1 vs V2 log2 change; summary in rankings_summary.csv
    waterfall.csv              V1 -> modified records -> added 2024 -> added 2026 -> methodology -> V2
    stability_table.csv        every (target, year) prevalence: V1, V2, difference, material flag
    vocab_rise_reversal.csv    the figure 6 table
    figures/fig_v2_2_stability.png, fig_v2_6_vocab_rise_reversal.png, fig_v2_7_revision_waterfall.png
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "results", "v2", "replication")
V1_BODY = os.path.join(ROOT, "results", "full", "body")
V1_LONG = os.path.join(ROOT, "results", "full", "longitudinal")
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, HERE)

from mlngrams.filters import STOPWORDS  # noqa: E402
from mlngrams.load import V1_REVISION, V2_REVISION  # noqa: E402

K = 5.0
EARLY, RECENT = (2017, 2021), (2025, 2027)
VIEW_DIRS = {"v1repro": "v1repro", "add2024": "add2024", "add2026": "add2026", "v2def": "v2def",
             "v2main": "v2main", "member_v1": "member_v1", "member_added": "member_added"}
RHET = ["delve", "underscores", "intricate", "pivotal", "showcasing", "realm"]
BREAK = ["we propose", "a novel", "test whether", "held fixed", "results support", "percentage points",
         "notably", "leverage", "furthermore", "in this paper"]
FUNC = ["of", "in", "we", "and", "the", "of the", "can be"]
ACROSS = ["across diverse", "across three", "across four", "across five", "performance across"]


# ---------------------------------------------------------------- view access
class View:
    def __init__(self, path: str):
        self.path = path
        self.tot = pd.read_csv(os.path.join(path, "totals.csv"))
        self.tots = pd.read_csv(os.path.join(path, "totals_by_stratum.csv"))
        self._cache: dict = {}

    def table(self, n: int, stratum: str | None = None, ngrams=None) -> pd.DataFrame:
        """Rows of the n-gram table, optionally only for `ngrams` (read with a filter: the full V2
        bigram tables do not fit next to a running count)."""
        key = (n, stratum, None if ngrams is None else tuple(sorted(ngrams)))
        if key not in self._cache:
            filt = [] if ngrams is None else [("ngram", "in", list(ngrams))]
            if stratum is None:
                t = pd.read_parquet(os.path.join(self.path, f"ngrams_n{n}.parquet"),
                                    columns=["year", "ngram", "count", "df"], filters=filt or None)
            else:
                t = pd.read_parquet(os.path.join(self.path, f"ngrams_n{n}_by_stratum.parquet"),
                                    columns=["year", "stratum", "ngram", "count", "df"],
                                    filters=[("stratum", "=", stratum)] + filt).drop(columns="stratum")
            self._cache[key] = t
        return self._cache[key]

    def totals(self, n: int, stratum: str | None = None) -> pd.DataFrame:
        if stratum is None:
            t = self.tot[self.tot.n == n]
        else:
            t = self.tots[(self.tots.n == n) & (self.tots.stratum == stratum)]
        return t.set_index("year")[["docs", "tokens", "positions"]]

    def series(self, ngrams, stratum=None) -> pd.DataFrame:
        out = []
        for n in sorted({g.count(" ") + 1 for g in ngrams}):
            want = [g for g in ngrams if g.count(" ") + 1 == n]
            t = self.table(n, stratum, want)
            tot = self.totals(n, stratum)
            grid = pd.MultiIndex.from_product([tot.index, want], names=["year", "ngram"]).to_frame(index=False)
            g = grid.merge(t, on=["year", "ngram"], how="left").fillna({"count": 0, "df": 0})
            g = g.merge(tot, left_on="year", right_index=True)
            g["per_million"] = 1e6 * g["count"] / g.positions
            g["prevalence"] = g.df / g.docs
            g["n"] = n
            out.append(g)
        return pd.concat(out, ignore_index=True)

    def stop_share(self) -> pd.Series:
        t = self.table(1, None, sorted(STOPWORDS))
        s = t.groupby("year")["count"].sum()
        return s / self.totals(1)["tokens"]

    def contrast(self, ngrams, early=EARLY, recent=RECENT, stratum=None) -> pd.DataFrame:
        s = self.series(ngrams, stratum)
        e = s[s.year.between(*early)].groupby("ngram")[["count", "positions", "df", "docs"]].sum()
        r = s[s.year.between(*recent)].groupby("ngram")[["count", "positions", "df", "docs"]].sum()
        out = pd.DataFrame({
            "log2_cw": np.log2(((r["count"] + K) / r.positions) / ((e["count"] + K) / e.positions)),
            "pp_cw": 100 * (r.df / r.docs - e.df / e.docs),
        })
        return out


# ---------------------------------------------------------------- verdicts (pre-specified)
def verdict(e1: float, e2: float, threshold: float = 0.0) -> str:
    if not np.isfinite(e1) or not np.isfinite(e2) or e1 == 0:
        return "n/a"
    if np.sign(e2) != np.sign(e1):
        return "reversed"
    if abs(e2) < threshold:
        return "disappears"
    r = abs(e2) / abs(e1)
    if r > 1.25:
        return "strengthened"
    if r < 0.75:
        return "weakened"
    return "survives"


def lg(a, b):
    return float(np.log2((a + 1e-4) / (b + 1e-4)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--views", required=True)
    ap.add_argument("--v1repro-tables", default=None, help="make_tables output for v1repro (exactness check)")
    ap.add_argument("--v1repro-alltext-tables", default=None)
    ap.add_argument("--v1repro-long", default=None, help="longitudinal output dir for v1repro")
    a = ap.parse_args()
    figdir = os.path.join(OUT, "figures")
    os.makedirs(figdir, exist_ok=True)
    V = {k: View(os.path.join(os.path.expanduser(a.views), d)) for k, d in VIEW_DIRS.items()
         if os.path.exists(os.path.join(os.path.expanduser(a.views), d, "totals.csv"))}
    rev = {"revision": V2_REVISION[:7]}

    # ---------------- 1. exactness: V1 records recounted at V2 vs committed V1 tables
    ex = []
    pairs = []
    if a.v1repro_tables:
        pairs.append(("body", V1_BODY, a.v1repro_tables))
    if a.v1repro_alltext_tables:
        pairs.append(("alltext", os.path.join(ROOT, "results", "full", "alltext"), a.v1repro_alltext_tables))
    if a.v1repro_long:
        pairs.append(("longitudinal", V1_LONG, a.v1repro_long))
    for kind, v1dir, mine in pairs:
        for f in sorted(glob.glob(os.path.join(v1dir, "*.csv"))):
            name = os.path.basename(f)
            g = os.path.join(os.path.expanduser(mine), name)
            if not os.path.exists(g):
                ex.append({"kind": kind, "table": name, "rows_v1": None, "identical": False, "note": "missing"})
                continue
            x, y = pd.read_csv(f), pd.read_csv(g)
            same_shape = x.shape == y.shape and list(x.columns) == list(y.columns)
            num = x.select_dtypes("number").columns
            ok, mad = False, None
            if same_shape:
                mad = float(np.nanmax(np.abs(x[num].to_numpy(float) - y[num].to_numpy(float)))) if len(num) else 0.0
                ok = x.drop(columns=num).astype(str).equals(y.drop(columns=num).astype(str)) and \
                    np.allclose(x[num].to_numpy(float), y[num].to_numpy(float), rtol=1e-6, atol=1e-9, equal_nan=True)
            rec = {"kind": kind, "table": name, "rows_v1": len(x), "rows_v2": len(y), "identical": bool(ok),
                   "max_abs_diff": mad}
            if {"year", "ngram", "count"} <= set(x.columns):
                mm = x.merge(y, on=["year", "ngram"], how="outer", indicator=True)
                o, t = mm[mm.year != 2027], mm[mm.year == 2027]
                rec["identical_except_2027"] = bool((o._merge == "both").all() and (o.count_x == o.count_y).all()
                                                    and (o.df_x == o.df_y).all())
                rec["max_rel_count_diff_2027"] = float(((t.count_y - t.count_x).abs() / t.count_x).max())
                if "rank_x" in mm:
                    rec["rank_changes"] = int((mm.rank_x != mm.rank_y).sum())
            elif {"year", "n", "docs"} <= set(x.columns):  # totals: distinct_ngrams counts kept n-grams only
                mm = x.merge(y, on=["year", "n"])
                rec["docs_diff"] = ";".join(f"{r.year}:{r.docs_y - r.docs_x:+d}" for r in mm[mm.n == 1].itertuples()
                                            if r.docs_y != r.docs_x)
                rec["tokens_identical_except_2027"] = bool((mm[mm.year != 2027].tokens_x == mm[mm.year != 2027].tokens_y).all())
            ex.append(rec)
    if ex:
        pd.DataFrame(ex).assign(v1_revision=V1_REVISION[:7], v2_revision=V2_REVISION[:7]).to_csv(
            os.path.join(OUT, "exactness_v1repro.csv"), index=False)
        print(pd.DataFrame(ex).groupby("kind").identical.agg(["sum", "count"]))

    # ---------------- 2. series by view
    wl = pd.read_csv(os.path.join(V1_LONG, "watchlist_evaluation.csv"))
    targets = list(dict.fromkeys(RHET + BREAK + FUNC + ACROSS + list(wl.ngram)))
    rows = []
    for k, v in V.items():
        for stratum in (None, "under_review", "published"):
            s = v.series(targets, stratum)
            s.insert(0, "stratum", stratum or "all")
            s.insert(0, "view", k)
            rows.append(s)
        ss = v.stop_share()
        rows.append(pd.DataFrame({"view": k, "stratum": "all", "year": ss.index, "ngram": "<stopword share>",
                                  "prevalence": np.nan, "per_million": ss.values * 1e6, "n": 1}))
    S = pd.concat(rows, ignore_index=True)
    S.insert(0, "revision", V2_REVISION[:7])
    S.to_csv(os.path.join(OUT, "series_by_view.csv"), index=False, float_format="%.6g")

    def val(view, ngram, year, field="prevalence", stratum="all"):
        r = S[(S.view == view) & (S.ngram == ngram) & (S.year == year) & (S.stratum == stratum)]
        return float(r[field].iloc[0]) if len(r) else np.nan

    # ---------------- 3. contrast formula check against V1's committed log2_cw
    v1c = pd.read_csv(os.path.join(V1_LONG, "changes_content_bigrams_main.csv"))
    v1c = v1c.drop_duplicates("ngram").set_index("ngram")
    if "v1repro" in V:
        mine = V["v1repro"].contrast(list(v1c.index))
        chk = v1c[["log2_cw"]].join(mine, rsuffix="_recomputed")
        chk["abs_diff"] = (chk.log2_cw - chk.log2_cw_recomputed).abs()
        chk.reset_index().to_csv(os.path.join(OUT, "contrast_check.csv"), index=False, float_format="%.6g")
        print("contrast check, max abs diff:", chk.abs_diff.max())

    # ---------------- 4. findings: V1 effect vs V2 effect
    F = []

    def add(finding, item, measure, e1, e2, threshold=0.0, v1_detail="", v2_detail=""):
        F.append({"finding": finding, "item": item, "measure": measure, "effect_v1": e1, "effect_v2": e2,
                  "verdict": verdict(e1, e2, threshold), "v1": v1_detail, "v2": v2_detail})

    def fmt(view, ng, years, field="prevalence", stratum="all"):
        f = (lambda x: f"{100 * x:.1f}%") if field == "prevalence" else (lambda x: f"{x:.0f}")
        return " ".join(f"{y % 100:02d}:{f(val(view, ng, y, field, stratum))}" for y in years)

    yrs = range(2022, 2028)
    base = "v1repro"
    for w in RHET:
        p1 = {y: val(base, w, y) for y in range(2017, 2028)}
        p2 = {y: val("v2main", w, y) for y in range(2017, 2028)}
        sd1 = np.std([np.log2((p1[y + 1] + 1e-3) / (p1[y] + 1e-3)) for y in range(2017, 2023)])
        add("F2 2024 burst", w, "log2 prevalence step 2023->2024", lg(p1[2024], p1[2023]), lg(p2[2024], p2[2023]),
            threshold=2 * sd1, v1_detail=fmt(base, w, yrs), v2_detail=fmt("v2main", w, yrs))
        pk1 = max(range(2024, 2027), key=lambda y: p1[y])
        add("F2 fade", w, f"log2 prevalence 2026 vs V1 peak year {pk1}", lg(p1[2026], p1[pk1]), lg(p2[2026], p2[pk1]))
        add("F2 fade", w, "log2 prevalence 2027 vs 2026", lg(p1[2027], p1[2026]), lg(p2[2027], p2[2026]))
    for w in BREAK:
        fld = "per_million" if w == "in this paper" else "prevalence"
        for stratum in ("all", "under_review"):
            a1 = val(base, w, 2027, fld, stratum) - val(base, w, 2026, fld, stratum)
            a2 = val("v2main", w, 2027, fld, stratum) - val("v2main", w, 2026, fld, stratum)
            if fld == "prevalence":
                a1, a2 = 100 * a1, 100 * a2
            add("F3 2027 break" + ("" if stratum == "all" else " (under review)"), w,
                ("pp" if fld == "prevalence" else "per million") + " change 2026->2027", a1, a2,
                v1_detail=fmt(base, w, yrs, fld, stratum), v2_detail=fmt("v2main", w, yrs, fld, stratum))
    for w in ["of the", "can be", "of", "in", "we", "and"]:
        for (y0, y1) in ((2017, 2026), (2024, 2026), (2024, 2027), (2026, 2027)):
            e1 = lg(val(base, w, y1, "per_million"), val(base, w, y0, "per_million"))
            e2 = lg(val("v2main", w, y1, "per_million"), val("v2main", w, y0, "per_million"))
            add("F4 function words", w, f"log2 per-million {y0}->{y1}", e1, e2,
                v1_detail=fmt(base, w, range(2023, 2028), "per_million"),
                v2_detail=fmt("v2main", w, range(2023, 2028), "per_million"))
    st = {k: V[k].stop_share() for k in (base, "v2main") if k in V}
    for (y0, y1) in ((2017, 2024), (2024, 2026), (2026, 2027)):
        add("F4 function words", "stopword share", f"pp change {y0}->{y1}",
            100 * (st[base][y1] - st[base][y0]), 100 * (st["v2main"][y1] - st["v2main"][y0]),
            v1_detail=" ".join(f"{y % 100}:{100 * st[base][y]:.1f}" for y in (2017, 2024, 2025, 2026, 2027)),
            v2_detail=" ".join(f"{y % 100}:{100 * st['v2main'][y]:.1f}" for y in (2017, 2024, 2025, 2026, 2027)))
    for w in ACROSS:
        add("F5 across", w, "pp change 2023->2026", 100 * (val(base, w, 2026) - val(base, w, 2023)),
            100 * (val("v2main", w, 2026) - val("v2main", w, 2023)), v1_detail=fmt(base, w, yrs), v2_detail=fmt("v2main", w, yrs))
        add("F5 across", w, "pp change 2026->2027", 100 * (val(base, w, 2027) - val(base, w, 2026)),
            100 * (val("v2main", w, 2027) - val("v2main", w, 2026)))
    # watchlist: main-contrast log2_cw, V1 vs V2
    if "v2main" in V:
        c1 = V[base].contrast(list(wl.ngram))
        c2 = V["v2main"].contrast(list(wl.ngram))
        for r in wl.itertuples():
            add("Watchlist (" + r.group + ")", r.ngram, f"log2_cw 2017-21 -> 2025-27 (predicted {r.predicted})",
                c1.log2_cw[r.ngram], c2.log2_cw[r.ngram], threshold=0.5 if r.predicted in ("up", "down") else 0)
    Fd = pd.DataFrame(F)
    Fd.insert(0, "revision_v2", V2_REVISION[:7])
    Fd.to_csv(os.path.join(OUT, "findings_v1_vs_v2.csv"), index=False, float_format="%.4g")
    print(Fd.groupby(["finding", "verdict"]).size().unstack(fill_value=0))

    # ---------------- 5. rankings
    v2l = os.path.join(OUT, "v2main", "longitudinal", "changes_content_bigrams_main.csv")
    rk, summ = [], []
    if os.path.exists(v2l) and "v2main" in V:
        v1all = pd.read_csv(os.path.join(V1_LONG, "changes_content_bigrams_main.csv"))
        v2all = pd.read_csv(v2l)
        for lst in ("riser_log2_cw", "faller_log2_cw", "riser_pp_cw"):
            l1 = v1all[v1all.list == lst].sort_values("rank").head(100)
            l2 = v2all[v2all.list == lst].sort_values("rank").head(100)
            c2 = V["v2main"].contrast(list(l1.ngram))
            m = l1[["rank", "ngram", "log2_cw", "pp_cw"]].merge(c2, left_on="ngram", right_index=True,
                                                                  suffixes=("_v1", "_v2"))
            m["rank_v2"] = m.ngram.map(dict(zip(l2.ngram, l2["rank"])))
            m.insert(0, "list", lst)
            rk.append(m)
            col = "pp_cw" if lst.endswith("pp_cw") else "log2_cw"
            top25 = m[m["rank"] <= 25]
            summ.append({"list": lst, "measure": col,
                         "spearman_top100": m[col + "_v1"].rank().corr(m[col + "_v2"].rank()),
                         "sign_flips_top25": int((np.sign(top25[col + "_v1"]) != np.sign(top25[col + "_v2"])).sum()),
                         "top25_in_v2_top100": int(top25.rank_v2.notna().sum()),
                         "top100_overlap": int(m.rank_v2.notna().sum()),
                         "median_abs_diff": float((m[col + "_v1"] - m[col + "_v2"]).abs().median())})
        pd.concat(rk).to_csv(os.path.join(OUT, "rankings_v1_vs_v2.csv"), index=False, float_format="%.4g")
        pd.DataFrame(summ).assign(revision_v2=V2_REVISION[:7]).to_csv(
            os.path.join(OUT, "rankings_summary.csv"), index=False, float_format="%.4g")
        print(pd.DataFrame(summ))

    # ---------------- 6. waterfall
    steps = [("v1repro", "V1 records at V2 pin"), ("add2024", "+ records added to 2024"),
             ("add2026", "+ records added to 2026"), ("v2def", "+ records added to 2025 (0-P: none)"),
             ("v2main", "methodology: whole 2025 minus slug ids")]
    # per-year estimates (V1's tables) and pooled main-contrast estimates ("main" = log2_cw 2017-21 -> 2025-27)
    items = [("delve", 2024, "prevalence"), ("underscores", 2025, "prevalence"), ("test whether", 2026, "prevalence"),
             ("of the", 2026, "per_million"), ("<stopword share>", 2026, "per_million"),
             ("a novel", "main", "log2"), ("we propose", "main", "log2"), ("leverage", "main", "log2"),
             ("intricate", "main", "log2"), ("of the", "main", "log2")]
    W = []
    for ng, y, fld in items:
        prev = None
        for k, label in steps:
            if k not in V:
                continue
            if fld == "log2":
                x = float(V[k].contrast([ng]).log2_cw[ng])
                meas = "log2_cw 2017-21 -> 2025-27"
            else:
                x = val(k, ng, y, fld)
                if ng == "<stopword share>":
                    x, meas = x / 1e4, "percent of tokens"  # stored as per million
                elif fld == "prevalence":
                    x, meas = 100 * x, "% of papers"
                else:
                    meas = "per million positions"
            W.append({"item": ng, "year": y, "measure": meas, "step": label, "view": k, "value": x,
                      "delta": np.nan if prev is None else x - prev})
            prev = x
    W = pd.DataFrame(W)
    W.insert(0, "revision_v2", V2_REVISION[:7])
    W.to_csv(os.path.join(OUT, "waterfall.csv"), index=False, float_format="%.5g")

    # ---------------- 7. stability table (all targets x years, all versions)
    p = S[(S.stratum == "all") & S.view.isin([base, "v2main"]) & (S.ngram != "<stopword share>")]
    st_t = p.pivot_table(index=["ngram", "year"], columns="view", values=["prevalence", "per_million"])
    st_t.columns = [f"{a}_{b}" for a, b in st_t.columns]
    st_t = st_t.reset_index()
    st_t["prev_diff_pp"] = 100 * (st_t.prevalence_v2main - st_t.prevalence_v1repro)
    st_t["prev_rel"] = st_t.prevalence_v2main / st_t.prevalence_v1repro - 1
    st_t["material"] = (st_t.prev_diff_pp.abs() >= 1) & (st_t.prev_rel.abs() >= 0.25)
    st_t.insert(0, "revision_v2", V2_REVISION[:7])
    st_t.to_csv(os.path.join(OUT, "stability_table.csv"), index=False, float_format="%.5g")

    figures(S, Fd, W, st_t, rk, figdir, val)
    json.dump({"v1_revision": V1_REVISION, "v2_revision": V2_REVISION, "views": {k: v.path for k, v in V.items()},
               "k_pseudocounts": K, "early": EARLY, "recent": RECENT},
              open(os.path.join(OUT, "compare_run.json"), "w"), indent=1)


# ---------------------------------------------------------------- figures
INK, INK2, GRID = "#1f1f1c", "#5f5e5a", "#e6e5e0"
C_V1, C_V2, C_UR = "#8a8984", "#2a6fdb", "#e07b39"
NAMES = {"icml": "ICML", "neurips": "NeurIPS", "colm": "COLM", "tmlr": "TMLR"}
VENUE_C = {"icml": "#2a9d8f", "neurips": "#8e5bd0", "colm": "#c2410c", "tmlr": "#b8860b"}


def style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color("#bdbcb6")
    ax.spines["bottom"].set_color("#bdbcb6")
    ax.tick_params(colors=INK2, labelsize=7)
    ax.grid(color=GRID, lw=0.5)
    ax.set_axisbelow(True)


def figures(S, Fd, W, st_t, rk, figdir, val):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.titlesize": 9})
    stamp = f"V1 records: rev {V1_REVISION[:7]} (recounted at {V2_REVISION[:7]}); V2: rev {V2_REVISION[:7]}"

    # ---- figure 2: stability
    fig, axes = plt.subplots(1, 3, figsize=(17, 5.8))
    ax = axes[0]
    if rk:
        R = pd.concat(rk)
        for lst, c in (("riser_log2_cw", C_V2), ("faller_log2_cw", C_UR)):
            r = R[R.list == lst]
            ax.scatter(r.log2_cw_v1, r.log2_cw_v2, s=12, color=c, lw=0, label=lst.replace("_log2_cw", "s") + " (V1 top 100)")
        lim = [min(R.log2_cw_v1.min(), R.log2_cw_v2.min()) - 0.3, max(R.log2_cw_v1.max(), R.log2_cw_v2.max()) + 0.3]
        ax.plot(lim, lim, color=C_V1, lw=0.8, ls="--")
        far = R[R.list != "riser_pp_cw"].assign(d=lambda x: (x.log2_cw_v2 - x.log2_cw_v1).abs()).nlargest(5, "d")
        for r in far.itertuples():
            ax.annotate(r.ngram, (r.log2_cw_v1, r.log2_cw_v2), fontsize=6.5, color=INK2, xytext=(3, 2), textcoords="offset points")
        ax.set_xlabel("V1: log2(2025–27 / 2017–21), corpus-weighted", fontsize=8)
        ax.set_ylabel("V2 (v2main): same contrast", fontsize=8)
        ax.legend(fontsize=7, frameon=False, loc="upper left")
    ax.set_title("a. Top content-bigram risers and fallers", loc="left", fontsize=10)
    style(ax)
    # b. watchlist: corpus-weighted vs year-balanced, V1 vs V2
    ax = axes[1]
    w1 = os.path.join(V1_LONG, "watchlist_evaluation.csv")
    w2 = os.path.join(OUT, "v2main", "longitudinal", "watchlist_evaluation.csv")
    if os.path.exists(w2):
        a1, a2 = pd.read_csv(w1).set_index("ngram"), pd.read_csv(w2).set_index("ngram")
        ax.scatter(a1.log2_cw, a2.log2_cw.reindex(a1.index), s=16, color=C_UR, lw=0,
                   label="corpus-weighted (recent cohort: 81% → 58% ICLR 2027)")
        ax.scatter(a1.log2_yb, a2.log2_yb.reindex(a1.index), s=16, color=C_V2, lw=0, label="year-balanced")
        flip = a1.index[a1.held != a2.held.reindex(a1.index)]
        ax.scatter(a1.log2_cw[flip], a2.log2_cw.reindex(flip), s=46, facecolor="none", edgecolor=INK, lw=0.8,
                   label="pre-registered verdict changes")
        lim = [-4.5, 8.5]
        ax.plot(lim, lim, color=C_V1, lw=0.8, ls="--")
        ax.set_xlabel("V1: log2(2025–27 / 2017–21)", fontsize=8)
        ax.set_ylabel("V2 (v2main): same contrast", fontsize=8)
        ax.legend(fontsize=7, frameon=False, loc="upper left")
    ax.set_title("b. Watchlist: pooled contrasts move, year-balanced do not", loc="left", fontsize=10)
    style(ax)
    ax = axes[2]
    q = st_t[st_t.year.between(2024, 2026) & st_t.prevalence_v1repro.notna()]
    for y, c in ((2024, "#9fc3ef"), (2025, "#2a6fdb"), (2026, "#0b2e6b")):
        r = q[q.year == y]
        ax.scatter(100 * r.prevalence_v1repro, 100 * r.prevalence_v2main, s=14, color=c, lw=0, label=str(y))
    m = q[q.material]
    ax.scatter(100 * m.prevalence_v1repro, 100 * m.prevalence_v2main, s=40, facecolor="none", edgecolor=C_UR, lw=1,
               label="material: |Δ| ≥ 1 pp and ≥ 25%")
    for r in m.head(10).itertuples():
        ax.annotate(f"{r.ngram} {r.year}", (100 * r.prevalence_v1repro, 100 * r.prevalence_v2main), fontsize=6.5,
                    color=INK2, xytext=(3, -8), textcoords="offset points")
    ax.plot([0, 100], [0, 100], color=C_V1, lw=0.8, ls="--")
    ax.set_xscale("symlog", linthresh=1)
    ax.set_yscale("symlog", linthresh=1)
    ax.set_xlabel("V1: % of papers containing it", fontsize=8)
    ax.set_ylabel("V2 (v2main): % of papers", fontsize=8)
    ax.set_title("c. Per-year prevalence, 2024–2026 (tracked n-grams)", loc="left", fontsize=10)
    ax.legend(fontsize=7, frameon=False, loc="upper left")
    style(ax)
    fig.suptitle("Figure 2. Old vs new estimates (ICLR, main body). Only 2024–2026 gained papers.",
                 x=0.01, ha="left", fontsize=11)
    fig.text(0.01, 0.005, stamp + ". Tables: rankings_v1_vs_v2.csv, stability_table.csv.", fontsize=7, color=INK2)
    fig.tight_layout(rect=(0, 0.02, 1, 0.95))
    fig.savefig(os.path.join(figdir, "fig_v2_2_stability.png"), dpi=150)
    plt.close(fig)

    # ---- figure 6: vocabulary rise and reversal
    words = RHET + ["notably", "across diverse"]
    vm_path = os.path.join(OUT, "venues", "venue_metrics.csv")
    vm = pd.read_csv(vm_path) if os.path.exists(vm_path) else None
    rows = []
    fig, axes = plt.subplots(2, 4, figsize=(13, 6), sharex=True)
    for ax, w in zip(axes.flat, words):
        for view, stratum, c, ls, lab in (("v1repro", "all", C_V1, "--", "ICLR V1"),
                                          ("v2main", "all", C_V2, "-", "ICLR V2"),
                                          ("v2main", "under_review", C_UR, ":", "ICLR V2, under review")):
            s = S[(S.view == view) & (S.stratum == stratum) & (S.ngram == w) & (S.year >= 2017)].sort_values("year")
            ax.plot(s.year, 100 * s.prevalence, ls=ls, color=c, lw=1.4 if view == "v2main" and stratum == "all" else 1,
                    marker="o", ms=2.5, label=lab)
            rows += [{"word": w, "series": lab, "venue": "iclr", "year": y, "pct_papers": 100 * p, "lo": np.nan,
                      "hi": np.nan, "papers": d, "revision": V1_REVISION[:7] if view == "v1repro" else V2_REVISION[:7]}
                     for y, p, d in zip(s.year, s.prevalence, s.docs)]
        if vm is not None:
            for venue, c in VENUE_C.items():
                g = vm[(vm.venue == venue) & (vm.group == "published") & (vm.metric == "prev:" + w)].sort_values("year")
                if len(g):
                    ax.errorbar(g.year, 100 * g.value, yerr=[100 * (g.value - g.lo), 100 * (g.hi - g.value)],
                                color=c, lw=1, marker="s", ms=2.5, capsize=1.5, elinewidth=0.6, label=NAMES[venue] + " published")
                    rows += [{"word": w, "series": NAMES[venue] + " published", "venue": venue, "year": y,
                              "pct_papers": 100 * v, "lo": 100 * lo, "hi": 100 * hi, "papers": n,
                              "revision": V2_REVISION[:7]}
                             for y, v, lo, hi, n in zip(g.year, g.value, g.lo, g.hi, g.papers)]
        ax.set_title(w, loc="left", fontsize=9)
        ax.set_ylim(bottom=0)
        style(ax)
    for ax in axes[:, 0]:
        ax.set_ylabel("% of papers (main body)", fontsize=8)
    h, lab = axes.flat[0].get_legend_handles_labels()
    fig.legend(h, lab, fontsize=7, frameon=False, loc="lower center", ncol=7, bbox_to_anchor=(0.5, 0.025))
    fig.suptitle("Figure 6. Vocabulary rise and reversal: ICLR (V1 vs V2) and other venues' published papers "
                 "(95% paper bootstrap)", x=0.01, ha="left", fontsize=11)
    fig.text(0.01, 0.005, stamp + ". Table: vocab_rise_reversal.csv. TMLR year semantics are provisional.",
             fontsize=7, color=INK2)
    fig.tight_layout(rect=(0, 0.07, 1, 0.95))
    fig.savefig(os.path.join(figdir, "fig_v2_6_vocab_rise_reversal.png"), dpi=150)
    plt.close(fig)
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "vocab_rise_reversal.csv"), index=False, float_format="%.5g")

    # ---- figure 7: waterfall
    items = list(dict.fromkeys(zip(W["item"], W["year"])))
    fig, axes = plt.subplots(2, 5, figsize=(15, 5.8))
    for ax, (ng, y) in zip(axes.flat, items):
        w = W[(W["item"] == ng) & (W.year == y)].reset_index(drop=True)
        labels = ["V1"] + ["mod. records"] + ["+2024", "+2026", "+2025", "method"] + ["V2"]
        v1 = w.value.iloc[0]
        deltas = [0.0] + list(w.delta.iloc[1:])
        bottoms, heights, colors = [0], [v1], [C_V1]
        cur = v1
        bottoms.append(cur)
        heights.append(0.0)
        colors.append("#bdbcb6")
        for d in deltas[1:]:
            bottoms.append(cur if d >= 0 else cur + d)
            heights.append(abs(d))
            colors.append("#2a9d8f" if d >= 0 else C_UR)
            cur += d
        bottoms.append(0)
        heights.append(cur)
        colors.append(C_V2)
        x = np.arange(len(heights))
        ax.bar(x, heights, bottom=bottoms, color=colors, width=0.7)
        lo = min(min(bottoms[1:-1]), cur, v1)
        hi = max(max(b + h for b, h in zip(bottoms[1:-1], heights[1:-1])), cur, v1)
        pad = max((hi - lo) * 0.6, abs(hi) * 0.02, 1e-3)
        if y == "main":  # log2 contrasts: keep zero in view so signs read correctly
            lo2, hi2 = min(lo, 0), max(hi, 0)
            pad2 = (hi2 - lo2) * 0.15
            ax.set_ylim(lo2 - pad2, hi2 + pad2 * 2.5)
            ax.axhline(0, color=INK2, lw=0.6)
        else:
            ax.set_ylim(max(0, lo - pad), hi + pad * 0.6)
        ax.set_xticks(x)
        ax.set_xticklabels(labels[:len(x)], rotation=60, fontsize=6.5)
        ax.set_title(f"{ng} " + ("2017–21→2025–27" if y == "main" else str(y)), loc="left", fontsize=9)
        ax.text(0.98, 0.95, f"{w.measure.iloc[0]}\nV1 {v1:.3g} → V2 {cur:.3g}", transform=ax.transAxes, ha="right",
                va="top", fontsize=6.5, color=INK2)
        style(ax)
    fig.suptitle("Figure 7. Corpus revision waterfall: V1 estimate, then each source of change, then V2 "
                 "(y axis truncated)", x=0.01, ha="left", fontsize=11)
    fig.text(0.01, 0.005, stamp + ". 'mod. records' = re-extracted or modified V1 records (none: all V1 records are "
             "byte-identical). Table: waterfall.csv.", fontsize=7, color=INK2)
    fig.tight_layout(rect=(0, 0.02, 1, 0.95))
    fig.savefig(os.path.join(figdir, "fig_v2_7_revision_waterfall.png"), dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
