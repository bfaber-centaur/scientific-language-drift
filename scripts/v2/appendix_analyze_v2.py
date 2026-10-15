"""Lane D (V2): appendix decomposition on the V2 pin, every venue, stratified by document version.

Usage:
    python3 scripts/v2/appendix_analyze_v2.py data/v2/appendix results/v2/appendices

Inputs: the V2 scan (scripts/v2/appendix_scan_v2.py), first-page version labels
(data/v2/version/2c0dd19/, scripts/v2/version_mix.py), V1 membership
(results/v2/inventory/membership.csv.gz), V1 flags (results/paper_flags_iclr.csv) for the
reproduction check, and titles read from the cached omissions files for the paired designs.

Definitions are V1.5's (scripts/appendix_analyze.py, imported, not copied): main, appendix, raw
post-reference ratio, heading categories. What is new here:
  * version strata for every venue: `submission` / `published` from the first-page header
    (Gate 0); ICLR "under_review" in V1 tables corresponds to `submission`.
  * ICLR V2 population: not short (< 2,000 chars), not the ICLR template, forum-id records only
    (drops the 140 ICLR 2025 title-slug records, Gate 0). ICLR 2025 is no longer restricted to the
    0-P id stratum because the year is now 99.5% complete. This is a definition change, so the V1
    definition on V1 records is reported first and must reproduce V1.5 exactly.
  * paired designs: ICLR 2026 -> ICML 2026 and ICLR 2026 -> ICLR 2027 by exact normalized title.

Outputs: CSV tables (aggregates and ids only) and figures under results/v2/appendices/.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "src"))

import appendix_analyze as a1  # noqa: E402
from mlngrams.load import V2_REVISION, cache_path  # noqa: E402

SEED = 20261015
REV7 = V2_REVISION[:7]
QS = a1.QS
MEASURES = ["main_tokens", "main_tokens_with_statements", "appx_tokens", "total_tokens", "appx_ratio",
            "raw_post_ratio", "raw_body_tokens", "raw_post_tokens", "pages", "main_pages", "appx_pages",
            "ref_pages", "post_pages", "body_tables", "post_tables", "body_equations", "post_equations",
            "body_figures", "post_figures"]
FIG_MEASURES = ["main_tokens", "appx_tokens", "appx_ratio", "raw_post_ratio", "main_pages", "appx_pages", "pages"]
# Supplementary-material conventions that decide whether an appendix can be inside the PDF at all
# (docs/appendix-growth.md "Page limits"; ICML 2026 from icml.cc/Conferences/2026/CallForPapers).
IN_PDF = {
    ("neurips", 2021): "separate file", ("neurips", 2022): "optional in PDF",
    ("corl", 2021): "separate file", ("corl", 2022): "unverified",
}
NORM = re.compile(r"[^a-z0-9]+")


def load_versions() -> pd.DataFrame:
    rows = []
    for f in glob.glob(os.path.join(ROOT, "data", "v2", "version", REV7, "*.parquet")):
        venue, year = os.path.basename(f)[:-8].rsplit("-", 1)
        d = pd.read_parquet(f, columns=["paper_id", "version"])
        d["venue"], d["year"] = venue, int(year)
        rows.append(d)
    v = pd.concat(rows).rename(columns={"paper_id": "doc_id"})
    return v.drop_duplicates(["venue", "year", "doc_id"])


def load_titles(keys) -> pd.DataFrame:
    import pyarrow.parquet as pq
    rows = []
    for venue, year in keys:
        p = cache_path("omissions", venue, year, V2_REVISION)
        t = pq.read_table(p, columns=["paper_id", "title"]).to_pandas()
        t["venue"], t["year"] = venue, year
        rows.append(t)
    t = pd.concat(rows).rename(columns={"paper_id": "doc_id"})
    t["norm"] = t.title.fillna("").str.lower().map(lambda s: NORM.sub(" ", s).strip())
    return t[t.norm.str.len() >= 25]


def qtab(df, keys, measures):
    return a1.qtable(df, keys, measures)


def prevalence(df, keys):
    rows = []
    for k, g in df.groupby(keys):
        k = k if isinstance(k, tuple) else (k,)
        n = len(g)
        rows.append({**dict(zip(keys, k)), "n": n,
                     "share_any_appendix_ge100tok": (g.appx_tokens >= 100).mean(),
                     "share_appendix_ge1000tok": (g.appx_tokens >= 1000).mean(),
                     "share_appendix_ge_main": (g.appx_tokens >= g.main_tokens).mean(),
                     "share_appx_pages_ge10": (g.appx_pages >= 10).mean(),
                     "share_appx_tokens_top10pct": g.appx_tokens.nlargest(max(1, n // 10)).sum() / max(1, g.appx_tokens.sum()),
                     "gini_appx_tokens": a1.gini(g.appx_tokens),
                     "pooled_post_char_share": g.post_chars.sum() / max(1, g.chars.sum()),
                     "median_raw_post_ratio": g.raw_post_ratio.median(),
                     "pooled_appx_token_share": g.appx_tokens.sum() / max(1, g.total_tokens.sum()),
                     "share_post_with_statement": (g.post_stmt_chars > 0).mean(),
                     "share_post_with_checklist": (g.post_checklist_chars > 0).mean(),
                     "post_chars_share_checklist": g.post_checklist_chars.sum() / max(1, g.post_chars.sum()),
                     "post_chars_share_statement": g.post_stmt_chars.sum() / max(1, g.post_chars.sum()),
                     "post_chars_share_refres": g.post_refres_chars.sum() / max(1, g.post_chars.sum()),
                     "share_appendix_before_refs": (g.body_appx_chars > 0).mean(),
                     "mean_main_tokens": g.main_tokens.mean(), "mean_appx_tokens": g.appx_tokens.mean()})
    return pd.DataFrame(rows)


def reproduce_v1(papers: pd.DataFrame, out: str) -> pd.DataFrame:
    """V1.5 definitions on V1 records only; compare with results/appendix/length_quantiles_iclr.csv."""
    flags = pd.read_csv(os.path.join(ROOT, "results", "paper_flags_iclr.csv"))
    mem = pd.read_csv(os.path.join(ROOT, "results", "v2", "inventory", "membership.csv.gz"))
    v1ids = mem[(mem.venue == "iclr") & (mem.status == "retained")][["year", "paper_id"]].rename(columns={"paper_id": "doc_id"})
    iclr = papers[papers.venue == "iclr"].merge(v1ids, on=["year", "doc_id"])
    iclr = iclr.merge(flags[["doc_id", "year", "version", "in_sample", "exclude"]], on=["doc_id", "year"], how="left")
    assert iclr.version.notna().all()
    iclr = iclr[(iclr.exclude.isna() | (iclr.exclude == "")) & iclr.in_sample.astype(bool)].copy()
    strat = pd.concat([iclr.assign(stratum="all"), iclr[iclr.version == "under_review"].assign(stratum="under_review"),
                       iclr[iclr.version == "published"].assign(stratum="published")])
    q = qtab(strat, ["stratum", "year"], ["main_tokens", "main_tokens_with_statements", "appx_tokens", "total_tokens",
                                          "appx_ratio", "raw_post_ratio", "pages", "main_pages", "appx_pages"])
    v1 = pd.read_csv(os.path.join(ROOT, "results", "appendix", "length_quantiles_iclr.csv"))
    m = q.merge(v1, on=["stratum", "year", "measure"], suffixes=("_v2run", "_v1"))
    cols = ["n", "mean"] + [f"p{int(x * 100)}" for x in QS]
    m["max_abs_diff"] = np.max(np.abs(np.column_stack([m[f"{c}_v2run"] - m[f"{c}_v1"] for c in cols])), axis=1)
    # V1 tables are written with 4 significant digits; allow that rounding
    scale = np.max(np.abs(np.column_stack([m[f"{c}_v1"] for c in cols])), axis=1)
    m["within_rounding"] = m.max_abs_diff <= np.maximum(5e-4 * scale, 1e-3)
    m[["stratum", "year", "measure", "n_v1", "n_v2run", "p50_v1", "p50_v2run", "mean_v1", "mean_v2run",
       "max_abs_diff", "within_rounding"]].to_csv(os.path.join(out, "v1_reproduction.csv"), index=False, float_format="%.5g")
    return m


def paired(papers, titles, a, b, out_name, out):
    ta = titles[(titles.venue == a[0]) & (titles.year == a[1])]
    tb = titles[(titles.venue == b[0]) & (titles.year == b[1])]
    ta = ta[~ta.norm.duplicated(keep=False)]
    tb = tb[~tb.norm.duplicated(keep=False)]
    pr = ta.merge(tb, on="norm", suffixes=("_a", "_b"))
    P = papers.set_index(["venue", "year", "doc_id"])
    rows = []
    for _, r in pr.iterrows():
        ka, kb = (a[0], a[1], r.doc_id_a), (b[0], b[1], r.doc_id_b)
        if ka in P.index and kb in P.index:
            x, y = P.loc[ka], P.loc[kb]
            rows.append({"doc_a": r.doc_id_a, "doc_b": r.doc_id_b, "version_a": x.version, "version_b": y.version,
                         "main_a": x.main_tokens, "main_b": y.main_tokens, "appx_a": x.appx_tokens,
                         "appx_b": y.appx_tokens, "main_pages_a": x.main_pages, "main_pages_b": y.main_pages,
                         "appx_pages_a": x.appx_pages, "appx_pages_b": y.appx_pages})
    d = pd.DataFrame(rows)
    d.to_csv(os.path.join(out, out_name), index=False)
    if d.empty:
        return {}
    rng = np.random.default_rng(SEED)
    dm, da = (d.main_b - d.main_a).to_numpy(), (d.appx_b - d.appx_a).to_numpy()
    bs = lambda x: np.percentile([np.median(rng.choice(x, len(x))) for _ in range(1000)], [2.5, 97.5]).tolist()  # noqa: E731
    return {"pair": f"{a[0]}{a[1]}->{b[0]}{b[1]}", "n_pairs": len(d),
            "median_main_change": float(np.median(dm)), "median_main_change_ci": bs(dm),
            "median_appx_change": float(np.median(da)), "median_appx_change_ci": bs(da),
            "share_appx_grew": float((da > 0).mean()), "share_main_grew": float((dm > 0).mean()),
            "median_appx_pages_change": float((d.appx_pages_b - d.appx_pages_a).median()),
            "median_main_pages_change": float((d.main_pages_b - d.main_pages_a).median())}


def main():
    src, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    rng = np.random.default_rng(SEED)
    run = json.load(open(os.path.join(src, "run.json")))
    assert run["revision"] == V2_REVISION, run["revision"]
    papers = a1.derive(pd.read_parquet(os.path.join(src, "papers.parquet")))
    secs = pd.read_parquet(os.path.join(src, "sections.parquet"))
    papers = papers.rename(columns={"body_tokens": "raw_body_tokens", "post_tokens": "raw_post_tokens"})

    # ---- 1. V1 reproduction on V1 records with V1 definitions ----
    rep = reproduce_v1(papers, out)
    print("V1 reproduction:", int(rep.within_rounding.sum()), "/", len(rep), "rows within rounding")

    # ---- 2. V2 population and version strata ----
    ver = load_versions()
    papers = papers.merge(ver, on=["venue", "year", "doc_id"], how="left")
    papers["version"] = papers.version.fillna("unknown")
    mem = pd.read_csv(os.path.join(ROOT, "results", "v2", "inventory", "membership.csv.gz")).rename(columns={"paper_id": "doc_id"})
    papers = papers.merge(mem, on=["venue", "year", "doc_id"], how="left")
    keep = ~papers.short & ~papers.template
    keep &= ~((papers.venue == "iclr") & (papers.id_stratum == "nonstandard_id") & (papers.year >= 2024))
    pop = papers[keep].copy()
    pop["stratum"] = "all"
    strat = pd.concat([pop, pop[pop.version == "submission"].assign(stratum="submission"),
                       pop[pop.version == "published"].assign(stratum="published")])
    pd.DataFrame([{"venue": v, "year": y, "rows": len(g), "short": int(g.short.sum()), "template": int(g.template.sum()),
                   "iclr_slug_dropped": int(((g.venue == "iclr") & (g.id_stratum == "nonstandard_id") & (g.year >= 2024)).sum()),
                   "kept": int(keep[g.index].sum()),
                   "submission": int(((g.version == "submission") & keep[g.index]).sum()),
                   "published": int(((g.version == "published") & keep[g.index]).sum())}
                  for (v, y), g in papers.groupby(["venue", "year"])]).to_csv(os.path.join(out, "population.csv"), index=False)

    q = qtab(strat, ["venue", "stratum", "year"], MEASURES)
    q.to_csv(os.path.join(out, "length_quantiles.csv"), index=False, float_format="%.4g")
    prev = prevalence(strat, ["venue", "stratum", "year"])
    prev.to_csv(os.path.join(out, "prevalence.csv"), index=False, float_format="%.4g")

    # Figure 5 table: the decomposition, with percentile bands, every venue and stratum
    f5 = q[q.measure.isin(FIG_MEASURES)].copy()
    f5.insert(0, "corpus_revision", V2_REVISION)
    f5.to_csv(os.path.join(out, "fig5_appendix_decomposition.csv"), index=False, float_format="%.4g")

    # ---- 3. ICLR: added vs retained records (population effect only; no record changed) ----
    ic = strat[(strat.venue == "iclr") & strat.year.between(2024, 2026)]
    avr = qtab(ic.assign(status=ic.status.fillna("added")), ["stratum", "year", "status"],
               ["main_tokens", "appx_tokens", "appx_ratio", "raw_post_ratio", "appx_pages"])
    avr.to_csv(os.path.join(out, "iclr_added_vs_retained.csv"), index=False, float_format="%.4g")

    # ---- 4. year-over-year median changes with bootstrap CIs, per venue and stratum ----
    yoy = []
    for (v, s), sel in strat.groupby(["venue", "stratum"]):
        ys = sorted(sel.year.unique())
        for y0, y1 in zip(ys, ys[1:]):
            A, B = sel[sel.year == y0], sel[sel.year == y1]
            if len(A) < 100 or len(B) < 100:
                continue
            for m in ("main_tokens", "appx_tokens"):
                d, lo, hi = a1.boot_median_diff(A[m], B[m], rng, reps=500)
                yoy.append({"venue": v, "stratum": s, "from": y0, "to": y1, "measure": m, "n_from": len(A),
                            "n_to": len(B), "median_diff": d, "ci_lo": lo, "ci_hi": hi})
    pd.DataFrame(yoy).to_csv(os.path.join(out, "yoy_median_change.csv"), index=False, float_format="%.4g")

    # ---- 5. growth decomposition (mean tokens): how much of the change is appendix ----
    dec = []
    spans = {"iclr": [(2017, 2027), (2017, 2026), (2024, 2026), (2026, 2027)], "icml": [(2023, 2026), (2025, 2026)],
             "neurips": [(2023, 2025)], "tmlr": [(2022, 2026), (2024, 2026)], "colm": [(2024, 2026)], "corl": [(2023, 2025)]}
    for (v, s), sel in strat.groupby(["venue", "stratum"]):
        for y0, y1 in spans.get(v, []):
            A, B = sel[sel.year == y0], sel[sel.year == y1]
            if len(A) < 50 or len(B) < 50:
                continue
            dmain, dappx = B.main_tokens.mean() - A.main_tokens.mean(), B.appx_tokens.mean() - A.appx_tokens.mean()
            dec.append({"venue": v, "stratum": s, "from": y0, "to": y1, "n_from": len(A), "n_to": len(B),
                        "mean_total_from": A.total_tokens.mean(), "mean_total_to": B.total_tokens.mean(),
                        "delta_mean_main": dmain, "delta_mean_appx": dappx,
                        "share_of_growth_from_appendix": dappx / (dmain + dappx) if dmain + dappx else np.nan,
                        "median_pages_from": A.pages.median(), "median_pages_to": B.pages.median(),
                        "median_main_pages_from": A.main_pages.median(), "median_main_pages_to": B.main_pages.median(),
                        "median_appx_pages_from": A.appx_pages.median(), "median_appx_pages_to": B.appx_pages.median()})
    pd.DataFrame(dec).to_csv(os.path.join(out, "growth_decomposition.csv"), index=False, float_format="%.4g")

    # ---- 6. composition by heading category (all venues; V1.5 taxonomy, unchanged) ----
    per, top = a1.composition(papers, secs)
    per = per.reset_index().merge(pop[["venue", "year", "doc_id", "version"]], on=["venue", "year", "doc_id"])
    comp = []
    for stratum in ("all", "submission", "published"):
        sel = per if stratum == "all" else per[per.version == stratum]
        for (v, y), g in sel.groupby(["venue", "year"]):
            if len(g) < 50:
                continue
            tot = g[a1.CAT_ORDER].to_numpy().sum()
            for c in a1.CAT_ORDER:
                comp.append({"venue": v, "stratum": stratum, "year": y, "category": c, "n_papers": len(g),
                             "mean_chars_per_paper": g[c].mean(), "share_of_post_chars": g[c].sum() / max(1, tot),
                             "share_papers_with": (g[c] > 0).mean()})
    comp = pd.DataFrame(comp)
    comp.to_csv(os.path.join(out, "composition.csv"), index=False, float_format="%.4g")

    # ---- 7. paired designs (same title in two venue-years) ----
    titles = load_titles([("iclr", 2025), ("iclr", 2026), ("iclr", 2027), ("icml", 2025), ("icml", 2026)])
    P = pop.copy()
    pairs = [paired(P, titles, ("iclr", 2026), ("icml", 2026), "pairs_iclr2026_icml2026.csv", out),
             paired(P, titles, ("iclr", 2025), ("icml", 2025), "pairs_iclr2025_icml2025.csv", out),
             paired(P, titles, ("iclr", 2026), ("iclr", 2027), "pairs_iclr2026_iclr2027.csv", out),
             paired(P, titles, ("iclr", 2025), ("iclr", 2026), "pairs_iclr2025_iclr2026.csv", out)]
    pd.DataFrame([p for p in pairs if p]).to_csv(os.path.join(out, "pairs_summary.csv"), index=False, float_format="%.4g")

    with open(os.path.join(out, "method.json"), "w") as f:
        json.dump({**run, "analysis": "scripts/v2/appendix_analyze_v2.py v1 (definitions from scripts/appendix_analyze.py v1)",
                   "seed": SEED, "version_labels": f"data/v2/version/{REV7} (scripts/v2/version_mix.py)",
                   "population": "not short, not template; ICLR 2024+ forum-id records only; strata all/submission/published",
                   "in_pdf_notes": {f"{k[0]}-{k[1]}": v for k, v in IN_PDF.items()}}, f, indent=1, default=str)
    figures(q, strat, comp, prev, out)


# ------------------------------------------------------------------ figures
VEN_COL = {"iclr": "#2a78d6", "icml": "#eb6834", "neurips": "#1baf7a", "tmlr": "#8c5fd3", "colm": "#d6a10f", "corl": "#d2457f"}
VEN_NAME = {"iclr": "ICLR", "icml": "ICML", "neurips": "NeurIPS", "tmlr": "TMLR", "colm": "COLM", "corl": "CoRL", "emnlp": "EMNLP"}


def figures(q, strat, comp, prev, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.titlesize": 9})
    figdir = os.path.join(out, "figures")
    os.makedirs(figdir, exist_ok=True)
    foot = f"woog/open-text-detector-papers @ {V2_REVISION[:7]} (V2), omissions config. Tokens: tokenizer v1.3, prose only."

    # Fig 5: main body vs appendix, median with P25-P75 and P10-P90 bands.
    panels = [("iclr", "submission", "ICLR, submissions"), ("iclr", "published", "ICLR, camera-ready"),
              ("icml", "published", "ICML, camera-ready"), ("neurips", "published", "NeurIPS, camera-ready"),
              ("tmlr", "published", "TMLR, published"), ("colm", "published", "COLM, camera-ready")]
    fig, axes = plt.subplots(2, 3, figsize=(10.5, 6.2), sharey=True)
    for ax, (v, s, title) in zip(axes.flat, panels):
        for m, col, lab in (("main_tokens", a1.C_BLUE, "main body"), ("appx_tokens", a1.C_ORANGE, "post-reference appendix")):
            d = q[(q.venue == v) & (q.stratum == s) & (q.measure == m) & (q.n >= 50)].sort_values("year")
            ax.fill_between(d.year, d.p10, d.p90, color=col, alpha=0.08, lw=0)
            ax.fill_between(d.year, d.p25, d.p75, color=col, alpha=0.2, lw=0)
            ax.plot(d.year, d.p50, color=col, lw=2, marker="o", ms=3.5, label=f"{lab}: median, P25–P75, P10–P90")
        ys = sorted(q[(q.venue == v) & (q.stratum == s) & (q.n >= 50)].year.unique())
        a1._style(ax)
        ax.set_xticks(ys)
        ax.set_xticklabels([f"'{str(y)[2:]}" for y in ys], fontsize=7)
        ax.set_title(title, loc="left", color=a1.C_INK)
        ax.set_ylim(0, 14000)
        if v == "neurips":
            ax.axvspan(2020.6, 2022.5, color="#e6e5e0", alpha=0.6, lw=0)
            ax.text(2021.5, 13000, "appendix in a\nseparate file", fontsize=6, ha="center", color=a1.C_INK2, va="top")
    for ax in axes[:, 0]:
        ax.set_ylabel("tokens per paper", fontsize=7, color=a1.C_INK2)
    h, l = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, l, fontsize=7, frameon=False, loc="lower center", ncol=2, bbox_to_anchor=(0.5, 0.035))
    fig.text(0.01, 0.01, foot + " Only cohorts with >= 50 papers. Version from the first-page header. Table: fig5_appendix_decomposition.csv",
             fontsize=6, color=a1.C_INK2)
    fig.suptitle("Fig 5. Main body vs post-reference appendix per paper, by venue and version", x=0.01, ha="left", fontsize=10)
    fig.tight_layout(rect=(0, 0.08, 1, 0.97))
    fig.savefig(os.path.join(figdir, "fig5_appendix_decomposition.png"), dpi=170)
    plt.close(fig)

    # Fig 5b: relative share. Median raw post-reference character share and appendix token share.
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6), sharey=True)
    for ax, s in zip(axes, ("submission", "published")):
        for v, col in VEN_COL.items():
            d = q[(q.venue == v) & (q.stratum == s) & (q.measure == "appx_ratio") & (q.n >= 50)].sort_values("year")
            if d.empty:
                continue
            ax.fill_between(d.year, d.p25, d.p75, color=col, alpha=0.12, lw=0)
            ax.plot(d.year, d.p50, color=col, lw=1.8, marker="o", ms=3, label=VEN_NAME[v])
            r = q[(q.venue == v) & (q.stratum == s) & (q.measure == "raw_post_ratio") & (q.n >= 50)].sort_values("year")
            ax.plot(r.year, r.p50, color=col, lw=0.8, ls=(0, (2, 2)))
        a1._style(ax)
        ax.set_xticks(range(2017, 2028))
        ax.set_xticklabels([f"'{str(y)[2:]}" for y in range(2017, 2028)], fontsize=7)
        ax.set_ylim(0, 0.8)
        ax.set_title(f"Appendix share of prose tokens, {'submissions' if s == 'submission' else 'camera-ready / published'}",
                     loc="left", color=a1.C_INK)
    axes[0].set_ylabel("median per paper (band P25–P75)", fontsize=7, color=a1.C_INK2)
    axes[1].legend(fontsize=7, frameon=False, loc="upper left")
    fig.text(0.01, 0.01, foot + " Solid: cleaned appendix token share; dotted: raw share of characters after the last reference marker.",
             fontsize=6, color=a1.C_INK2)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(os.path.join(figdir, "fig5b_appendix_share_by_venue.png"), dpi=170)
    plt.close(fig)

    # Fig 5c: paper-level distribution of appendix tokens, selected cohorts (ECDF)
    fig, ax = plt.subplots(figsize=(7, 3.6))
    cohorts = [("iclr", "submission", 2017, "#9cc3ef"), ("iclr", "submission", 2022, "#5a9bd5"), ("iclr", "submission", 2026, "#2a78d6"),
               ("iclr", "submission", 2027, "#0b3d7a"), ("icml", "published", 2023, "#f5b08f"), ("icml", "published", 2026, "#eb6834")]
    for v, s, y, col in cohorts:
        x = np.sort(strat[(strat.venue == v) & (strat.stratum == s) & (strat.year == y)].appx_tokens.to_numpy())
        if len(x):
            ax.plot(np.r_[0, x], np.r_[0, np.arange(1, len(x) + 1) / len(x)], color=col, lw=1.6,
                    label=f"{VEN_NAME[v]} {y} {'subm.' if s == 'submission' else 'camera-ready'} (n={len(x):,})")
    ax.set_xscale("symlog", linthresh=100)
    ax.set_xlim(0, 60000)
    a1._style(ax)
    ax.set_xlabel("appendix tokens per paper", fontsize=7, color=a1.C_INK2)
    ax.set_ylabel("share of papers at or below", fontsize=7, color=a1.C_INK2)
    ax.set_title("Paper-level distribution of appendix length (ECDF)", loc="left", color=a1.C_INK)
    ax.legend(fontsize=6.5, frameon=False, loc="lower right")
    fig.text(0.01, 0.01, foot, fontsize=6, color=a1.C_INK2)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(os.path.join(figdir, "fig5c_appendix_ecdf.png"), dpi=170)
    plt.close(fig)

    # Fig 5d: composition, ICLR submissions and ICML camera-ready
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.8), sharey=True, gridspec_kw={"width_ratios": [11, 4]})
    for ax, (v, s, title) in zip(axes, (("iclr", "submission", "ICLR submissions"), ("icml", "published", "ICML camera-ready"))):
        c = comp[(comp.venue == v) & (comp.stratum == s)].pivot(index="year", columns="category", values="mean_chars_per_paper")[a1.CAT_ORDER]
        ax.stackplot(c.index, [c[k] / 1000 for k in a1.CAT_ORDER], colors=[a1.CAT_COLORS[k] for k in a1.CAT_ORDER],
                     labels=[k.replace("_", " ") for k in a1.CAT_ORDER], edgecolor="white", lw=0.6)
        a1._style(ax)
        ax.set_xticks(list(c.index))
        ax.set_xticklabels([f"'{str(y)[2:]}" for y in c.index], fontsize=7)
        ax.set_title(f"Post-reference text by heading category, {title}", loc="left", color=a1.C_INK)
    axes[0].set_ylabel("thousand characters per paper (mean)", fontsize=7, color=a1.C_INK2)
    h, l = axes[1].get_legend_handles_labels()
    axes[1].legend(h[::-1], l[::-1], fontsize=6, frameon=False, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    fig.text(0.01, 0.01, foot + " Heading rules: V1.5 taxonomy (85% agreement with hand labels).", fontsize=6, color=a1.C_INK2)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(os.path.join(figdir, "fig5d_composition.png"), dpi=170)
    plt.close(fig)


if __name__ == "__main__":
    main()
