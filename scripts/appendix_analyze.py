"""Lane A, step 2: what grew in the "appendix explosion" (docs/appendix-growth.md).

Usage:
    python3 scripts/appendix_analyze.py data/appendix results/appendix

Reads the per-paper scan (scripts/appendix_scan.py) and results/paper_flags_iclr.csv; writes
compact tables (aggregates, ids and short section headings only) and figures.

Definitions (per paper, tokenizer v1.3 tokens unless stated):
    main     body before the first references marker, minus statement sections (ethics,
             reproducibility, AI/LLM use, acknowledgments; sections.py v2), minus any lettered
             appendix placed before the references (body_appx).
    appendix post-reference text plus body_appx, minus post-reference statement sections,
             NeurIPS-style checklists and bibliography-like lines (reference residue).
             Removals are measured in characters and converted at the post region's own
             tokens-per-character rate.
    raw_*    the earlier study's split: body_tokens (all text before the first marker) and
             post_tokens (all text after the last marker).
Population (ICLR): paper_flags exclude == "" and in_sample (2025 restricted to the 0-P id stratum).
"""
from __future__ import annotations

import json
import os
import re
import sys

import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
QS = [0.10, 0.25, 0.50, 0.75, 0.90]
SEED = 20261015
EARLY, RECENT = (2017, 2018, 2019), (2025, 2026, 2027)

# ---- appendix heading taxonomy (first match wins; checked by hand in heading_audit.csv) ----
CATEGORIES = [
    ("statement", r"\b(llms?|large language models?|ai|generative ai)\b.*\b(use|usage|assist|disclos|statement)|"
                  r"ethic|reproducibility statement|broader impact|societal impact|impact statement|"
                  r"acknowledg|author contribution|usage of llm|use of llm"),
    ("checklist", r"checklist"),
    ("container", r"^(technical |online |supplementary |supplemental )?(appendix|appendices)( for .*)?$|"
                  r"^supplementa(ry|l)( materials?| information)?$|^appendix:?\s*$|^table of contents"),
    ("proofs_theory", r"complexity|proof|theorem|lemma|proposition|corollar|derivation|theoretical|theory|deferred|"
                      r"omitted (details|proofs)|convergence|regret|bound|technical (details|results)|"
                      r"auxiliary results|mathematical"),
    ("ablation", r"ablation|sensitivity|effect of|impact of|influence of|robustness"),
    ("examples_prompts", r"prompt|example|qualitative|case stud|visuali[sz]|samples|generated|generation results|"
                         r"failure (case|mode)|showcase|illustrat|demonstration|transcript|conversation"),
    ("related_work", r"related work|literature|prior work|previous work|comparison (to|with) (prior|existing|related)"),
    ("background_notation", r"notation|preliminar|background|definition|glossary|symbols|problem (setup|formulation)"),
    ("limitations_discussion", r"limitation|future work|discussion|broader|conclusion"),
    ("algorithm", r"algorithm|pseudo|pseudocode"),
    ("data_benchmarks", r"dataset|data|benchmark|task|environment|metric|annotation|human (eval|study)|"
                        r"user study|baseline"),
    ("implementation", r"implementation|hyper-?parameter|training|experiment(al)? (details|setup|settings?|"
                       r"protocol|configuration)|setup|setting|architecture|model details|configuration|"
                       r"compute|computational|resource|runtime|run time|cost|efficiency|reproduc|code|details"),
    ("additional_results", r"additional|more|further|extra|supplementary|extended|full|complete|detailed|"
                           r"results|experiment|evaluation|comparison|performance|analysis|analyses|study|"
                           r"plots|tables|figures|curves"),
]
CAT_RE = [(c, re.compile(p, re.I)) for c, p in CATEGORIES]
CAT_ORDER = ["proofs_theory", "additional_results", "ablation", "implementation", "data_benchmarks",
             "examples_prompts", "algorithm", "related_work", "background_notation",
             "limitations_discussion", "statement", "other_math", "other_tables_figures", "other_prose",
             "unsectioned"]
# Headings that name only the paper's own topic ("ORTHOGONAL BASIS") fall back to marker density:
# display/inline math markers per 1,000 characters (proof sections: median 8.3, other headed
# categories: median <= 2) and table/figure markers per 1,000 characters.
EQ_DENSE, TF_DENSE = 3.0, 0.5


def fallback(row) -> str:
    k = max(row.chars, 1) / 1000
    if (row.n_eq + row.n_math) / k >= EQ_DENSE:
        return "other_math"
    if (row.n_tab + row.n_fig) / k >= TF_DENSE:
        return "other_tables_figures"
    return "other_prose"


def label(df) -> pd.Series:
    cat = df.title.map(classify)
    oth = cat == "other"
    if oth.any():
        cat[oth] = df[oth].apply(fallback, axis=1)
    return cat


def classify(title: str) -> str:
    t = re.sub(r"\s+", " ", title).strip()
    for c, rx in CAT_RE:
        if rx.search(t):
            return c
    return "other"


def qtable(df, keys, measures):
    rows = []
    for k, g in df.groupby(keys):
        k = k if isinstance(k, tuple) else (k,)
        for m in measures:
            x = g[m].dropna()
            rows.append({**dict(zip(keys, k)), "measure": m, "n": len(x), "mean": x.mean(),
                         **{f"p{int(q * 100)}": x.quantile(q) for q in QS}})
    return pd.DataFrame(rows)


def derive(p: pd.DataFrame) -> pd.DataFrame:
    p = p.copy()
    tpc = (p.post_tokens / p.post_chars.where(p.post_chars > 0)).fillna(0)
    removed_chars = (p.post_stmt_chars + p.post_checklist_chars + p.post_refres_chars).clip(upper=p.post_chars)
    p["post_removed_tokens"] = (removed_chars * tpc).round()
    p["main_tokens"] = p.body_tokens_nostmt - p.body_appx_tokens
    # with statement sections kept: main pages include them, and ICLR 2027 requires one in the main text
    p["main_tokens_with_statements"] = p.body_tokens - p.body_appx_tokens
    p["appx_tokens"] = (p.post_tokens - p.post_removed_tokens).clip(lower=0) + p.body_appx_tokens
    p["main_chars"] = p.body_chars - p.body_stmt_chars - p.body_appx_chars
    p["appx_chars"] = (p.post_chars - removed_chars).clip(lower=0) + p.body_appx_chars
    p["total_tokens"] = p.main_tokens + p.appx_tokens
    p["main_pages"] = p.body_pages - p.body_appx_pages
    p["appx_pages"] = (p.post_pages - p.post_checklist_pages).clip(lower=0) + p.body_appx_pages
    p["appx_ratio"] = p.appx_tokens / p.total_tokens.where(p.total_tokens > 0)
    p["raw_post_ratio"] = p.post_chars / p.chars.where(p.chars > 0)  # the earlier study's measure
    p["post_tables"] = p.post_tab
    p["post_figures"] = p.post_fig
    p["post_equations"] = p.post_eq
    p["body_tables"], p["body_figures"], p["body_equations"] = p.body_tab, p.body_fig, p.body_eq
    return p


def gini(x):
    x = np.sort(np.asarray(x, float))
    if x.sum() == 0:
        return np.nan
    n = len(x)
    return (2 * np.arange(1, n + 1) - n - 1).dot(x) / (n * x.sum())


def hinge_fits(years, y):
    """Linear vs one-hinge (slope change) vs one-step (level shift) fits of y on year.
    Returns rows per candidate break with SSE and BIC (Gaussian, k params)."""
    t = np.asarray(years, float)
    y = np.asarray(y, float)
    n = len(t)

    def fit(X):
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        sse = float(((y - X @ beta) ** 2).sum())
        return sse, beta

    base = np.c_[np.ones(n), t - t.min()]
    sse0, _ = fit(base)
    rows = [{"model": "linear", "break": None, "sse": sse0, "k": 2}]
    for b in range(int(t.min()) + 2, int(t.max()) - 1):
        sse, beta = fit(np.c_[base, np.maximum(0, t - b)])
        rows.append({"model": "hinge", "break": b, "sse": sse, "k": 3, "slope_before": beta[1],
                     "slope_after": beta[1] + beta[2]})
        sse, beta = fit(np.c_[base, (t >= b).astype(float)])
        rows.append({"model": "step", "break": b, "sse": sse, "k": 3, "step": beta[2]})
    out = pd.DataFrame(rows)
    out["bic"] = n * np.log(out.sse / n) + out.k * np.log(n)
    return out


def boot_median_diff(a, b, rng, reps=1000):
    a, b = np.asarray(a), np.asarray(b)
    d = [np.median(rng.choice(b, len(b))) - np.median(rng.choice(a, len(a))) for _ in range(reps)]
    return np.median(b) - np.median(a), np.percentile(d, 2.5), np.percentile(d, 97.5)


def composition(papers: pd.DataFrame, secs: pd.DataFrame):
    """Per paper and category: characters of post-reference appendix text. Generic container
    sections ("APPENDIX") are replaced by their subsections; text outside any detected
    section is 'unsectioned'. Statement/checklist sections are reported but are not appendix."""
    top = secs[secs.num == 0].copy()
    top["cat"] = label(top)
    sub = secs[secs.num > 0].copy()
    sub["cat"] = label(sub)
    sub = sub.merge(top[["doc_id", "venue", "year", "letter", "cat"]].rename(columns={"cat": "parent_cat"}),
                    on=["venue", "year", "doc_id", "letter"])
    cont = top[top.cat == "container"]
    sub_c = sub[sub.parent_cat == "container"]
    # container text before its first subsection stays in the container (counted as unsectioned)
    sub_sum = sub_c.groupby(["venue", "year", "doc_id", "letter"]).chars.sum().rename("subchars")
    cont = cont.join(sub_sum, on=["venue", "year", "doc_id", "letter"])
    cont["rest"] = (cont.chars - cont.subchars.fillna(0)).clip(lower=0)
    sub_c = sub_c.assign(cat=sub_c.cat.replace({"container": "other_prose"}))
    parts = pd.concat([
        top[top.cat != "container"][["venue", "year", "doc_id", "cat", "chars"]],
        sub_c[["venue", "year", "doc_id", "cat", "chars"]],
        cont.assign(cat="unsectioned", chars=cont.rest)[["venue", "year", "doc_id", "cat", "chars"]],
    ])
    parts["cat"] = parts.cat.replace({"checklist": "statement"})
    per = parts.groupby(["venue", "year", "doc_id", "cat"]).chars.sum().unstack(fill_value=0)
    per = per.reindex(papers.set_index(["venue", "year", "doc_id"]).index, fill_value=0)
    covered = per.sum(axis=1)
    post = papers.set_index(["venue", "year", "doc_id"]).post_chars
    per["unsectioned"] = per.get("unsectioned", 0) + (post - covered).clip(lower=0)
    for c in CAT_ORDER:
        if c not in per:
            per[c] = 0
    return per[CAT_ORDER], top


def main():
    src, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    figdir = os.path.join(out, "figures")
    os.makedirs(figdir, exist_ok=True)
    rng = np.random.default_rng(SEED)
    run = json.load(open(os.path.join(src, "run.json")))
    papers = pd.read_parquet(os.path.join(src, "papers.parquet"))
    secs = pd.read_parquet(os.path.join(src, "sections.parquet"))
    papers = derive(papers)

    flags = pd.read_csv(os.path.join(ROOT, "results", "paper_flags_iclr.csv"))
    iclr = papers[papers.venue == "iclr"].merge(flags[["doc_id", "year", "version", "in_sample", "exclude"]],
                                                on=["doc_id", "year"], how="left")
    assert iclr.version.notna().all(), "ICLR papers missing from paper_flags_iclr.csv"
    iclr = iclr[(iclr.exclude.isna() | (iclr.exclude == "")) & iclr.in_sample.astype(bool)].copy()
    iclr["stratum"] = "all"
    strat = pd.concat([iclr, iclr[iclr.version == "under_review"].assign(stratum="under_review"),
                       iclr[iclr.version == "published"].assign(stratum="published")])

    measures = ["main_tokens", "main_tokens_with_statements", "appx_tokens", "total_tokens", "raw_body_tokens", "raw_post_tokens",
                "appx_ratio", "raw_post_ratio", "main_chars", "appx_chars", "pages", "body_pages",
                "ref_pages", "post_pages", "main_pages", "appx_pages", "body_tables", "post_tables", "body_figures", "post_figures",
                "body_equations", "post_equations", "post_n_sections"]
    strat = strat.rename(columns={"body_tokens": "raw_body_tokens", "post_tokens": "raw_post_tokens"})
    iclr = iclr.rename(columns={"body_tokens": "raw_body_tokens", "post_tokens": "raw_post_tokens"})
    q = qtable(strat, ["stratum", "year"], measures)
    q.to_csv(os.path.join(out, "length_quantiles_iclr.csv"), index=False, float_format="%.4g")

    # ---- prevalence and diagnostics per year ----
    rows = []
    for (s, y), g in strat.groupby(["stratum", "year"]):
        n = len(g)
        tot_post = g.post_chars.sum()
        rows.append({
            "stratum": s, "year": y, "n": n,
            "share_has_ref_marker": g.has_ref.mean(),
            "share_any_appendix_ge100tok": (g.appx_tokens >= 100).mean(),
            "share_appendix_ge1000tok": (g.appx_tokens >= 1000).mean(),
            "share_appendix_ge_main": (g.appx_tokens >= g.main_tokens).mean(),
            "share_post_ge1page": (g.post_pages >= 1).mean(),
            "share_post_ge10pages": (g.post_pages >= 10).mean(),
            "share_appendix_before_refs": (g.body_appx_chars > 0).mean(),
            "share_post_with_statement": (g.post_stmt_chars > 0).mean(),
            "share_post_with_checklist": (g.post_checklist_chars > 0).mean(),
            "post_chars_share_statement": g.post_stmt_chars.sum() / tot_post if tot_post else np.nan,
            "post_chars_share_checklist": g.post_checklist_chars.sum() / tot_post if tot_post else np.nan,
            "post_chars_share_refres": g.post_refres_chars.sum() / tot_post if tot_post else np.nan,
            "post_chars_share_in_sections": None,  # filled below
            "body_tail_refres_share": g.body_tail_refres_lines.sum() / max(1, g.body_tail_lines.sum()),
            "refzone_chars_median": g.refzone_chars.median(),
            "share_appx_tokens_top10pct": g.appx_tokens.nlargest(max(1, n // 10)).sum() / max(1, g.appx_tokens.sum()),
            "share_appx_tokens_top1pct": g.appx_tokens.nlargest(max(1, n // 100)).sum() / max(1, g.appx_tokens.sum()),
            "gini_appx_tokens": gini(g.appx_tokens),
            "mean_main_tokens": g.main_tokens.mean(), "mean_appx_tokens": g.appx_tokens.mean(),
            "median_main_tokens": g.main_tokens.median(), "median_appx_tokens": g.appx_tokens.median(),
        })
    prev = pd.DataFrame(rows)

    # ---- composition from section headings ----
    per, top = composition(papers, secs)
    per_i = per.loc["iclr"].reset_index()
    per_i = per_i.merge(iclr[["doc_id", "year", "version"]], on=["doc_id", "year"])
    cover = {y: 1 - g.unsectioned.sum() / max(1, g[CAT_ORDER].to_numpy().sum()) for y, g in per_i.groupby("year")}
    prev.loc[prev.stratum == "all", "post_chars_share_in_sections"] = prev[prev.stratum == "all"].year.map(cover)
    prev.to_csv(os.path.join(out, "prevalence_iclr.csv"), index=False, float_format="%.4g")

    comp_rows = []
    for (stratum, sel) in (("all", per_i), ("under_review", per_i[per_i.version == "under_review"])):
        for y, g in sel.groupby("year"):
            tot = g[CAT_ORDER].to_numpy().sum()
            for c in CAT_ORDER:
                comp_rows.append({"stratum": stratum, "year": y, "category": c, "n_papers": len(g),
                                  "mean_chars_per_paper": g[c].mean(), "share_of_post_chars": g[c].sum() / tot,
                                  "share_papers_with": (g[c] > 0).mean()})
    comp = pd.DataFrame(comp_rows)
    comp.to_csv(os.path.join(out, "composition_iclr.csv"), index=False, float_format="%.4g")

    # heading frequency (top-level, ICLR, normalized), compact
    ti = top[top.venue == "iclr"].merge(iclr[["doc_id", "year"]], on=["doc_id", "year"])
    ti["norm"] = ti.title.str.upper().str.replace(r"\s+", " ", regex=True).str.strip()
    ti["cohort"] = np.where(ti.year.isin(EARLY), "2017-2019", np.where(ti.year.isin(RECENT), "2025-2027", "2020-2024"))
    hf = ti.groupby(["cohort", "norm"]).agg(papers=("doc_id", "nunique"), category=("cat", "first")).reset_index()
    ncoh = iclr.assign(cohort=np.where(iclr.year.isin(EARLY), "2017-2019",
                                       np.where(iclr.year.isin(RECENT), "2025-2027", "2020-2024"))).groupby("cohort").size()
    hf["share_papers"] = hf.papers / hf.cohort.map(ncoh)
    hf = hf.sort_values(["cohort", "papers"], ascending=[True, False]).groupby("cohort").head(40)
    hf.to_csv(os.path.join(out, "top_headings_iclr.csv"), index=False, float_format="%.4g")

    # heading audit sample (labelled by hand afterwards in heading_audit.csv)
    samp = pd.concat([g.sample(min(len(g), 14), random_state=SEED) for _, g in ti.groupby("year")])
    samp = samp[["doc_id", "year", "letter", "title", "cat"]].rename(columns={"cat": "rule_label"})
    audit_path = os.path.join(out, "heading_audit.csv")
    if not os.path.exists(audit_path):
        samp.assign(manual_label="").to_csv(audit_path, index=False)
    else:  # hand labels present: agreement and per-class precision/recall of the heading rules
        au = pd.read_csv(audit_path)
        au["rule_eff"] = np.where(au.rule_label.str.startswith("other_"), "topic_only", au.rule_label)
        rows = [{"class": "ALL", "n_manual": len(au), "n_rule": len(au),
                 "agreement": (au.rule_eff == au.manual_label).mean()}]
        for c in sorted(set(au.manual_label) | set(au.rule_eff)):
            tp = ((au.rule_eff == c) & (au.manual_label == c)).sum()
            rows.append({"class": c, "n_manual": int((au.manual_label == c).sum()),
                         "n_rule": int((au.rule_eff == c).sum()),
                         "precision": tp / max(1, (au.rule_eff == c).sum()),
                         "recall": tp / max(1, (au.manual_label == c).sum())})
        pd.DataFrame(rows).to_csv(os.path.join(out, "heading_audit_summary.csv"), index=False, float_format="%.3g")

    # ---- change points on yearly medians (log tokens), submission versions and all papers ----
    cp = []
    for stratum in ("all", "under_review"):
        for m in ("main_tokens", "appx_tokens", "total_tokens"):
            s = q[(q.stratum == stratum) & (q.measure == m)].sort_values("year")
            f = hinge_fits(s.year, np.log(s.p50.clip(lower=1)))
            f.insert(0, "measure", m)
            f.insert(0, "stratum", stratum)
            cp.append(f)
    cp = pd.concat(cp)
    cp.to_csv(os.path.join(out, "changepoints_iclr.csv"), index=False, float_format="%.4g")

    yoy = []
    for stratum, sel in (("all", iclr), ("under_review", iclr[iclr.version == "under_review"])):
        ys = sorted(sel.year.unique())
        for a, b in zip(ys, ys[1:]):
            for m in ("main_tokens", "appx_tokens"):
                d, lo, hi = boot_median_diff(sel[sel.year == a][m], sel[sel.year == b][m], rng)
                yoy.append({"stratum": stratum, "from": a, "to": b, "measure": m, "median_diff": d,
                            "ci_lo": lo, "ci_hi": hi})
    pd.DataFrame(yoy).to_csv(os.path.join(out, "yoy_median_change_iclr.csv"), index=False, float_format="%.4g")

    # ---- within-paper change: cross-year resubmissions (near-duplicate pairs, docs/corpus.md) ----
    dup = pd.read_csv(os.path.join(ROOT, "results", "duplicates_iclr.csv"))
    dup = dup[(dup.year_b > dup.year_a)].drop_duplicates(["paper_id_a", "paper_id_b"])
    allp = papers[papers.venue == "iclr"].set_index("doc_id")
    pr = []
    for _, d in dup.iterrows():
        if d.paper_id_a in allp.index and d.paper_id_b in allp.index:
            a, b = allp.loc[d.paper_id_a], allp.loc[d.paper_id_b]
            pr.append({"year_a": d.year_a, "year_b": d.year_b, "doc_a": d.paper_id_a, "doc_b": d.paper_id_b,
                       "main_a": a.main_tokens, "main_b": b.main_tokens,
                       "appx_a": a.appx_tokens, "appx_b": b.appx_tokens,
                       "pages_a": a.pages, "pages_b": b.pages})
    pr = pd.DataFrame(pr)
    pr.to_csv(os.path.join(out, "resubmission_lengths_iclr.csv"), index=False)
    pairs_summary = {} if pr.empty else {
        "n_pairs": len(pr),
        "median_main_change": float((pr.main_b - pr.main_a).median()),
        "median_appx_change": float((pr.appx_b - pr.appx_a).median()),
        "share_appx_grew": float((pr.appx_b > pr.appx_a).mean()),
        "share_main_grew": float((pr.main_b > pr.main_a).mean()),
        "median_main_ratio": float((pr.main_b / pr.main_a.clip(lower=1)).median()),
        "median_appx_ratio_where_a_pos": float((pr.appx_b / pr.appx_a)[pr.appx_a > 100].median()),
    }

    # ---- other venues ----
    ven = papers.rename(columns={"body_tokens": "raw_body_tokens", "post_tokens": "raw_post_tokens"})
    ven = ven[ven.chars >= 2000]
    vq = qtable(ven, ["venue", "year"], ["main_tokens", "appx_tokens", "appx_ratio", "raw_post_ratio",
                                          "pages", "body_pages", "post_pages", "main_pages", "appx_pages"])
    vq.to_csv(os.path.join(out, "length_quantiles_venues.csv"), index=False, float_format="%.4g")
    vd = pd.DataFrame([{"venue": k[0], "year": k[1], **{
        "n": len(g),
        "share_post_with_checklist": (g.post_checklist_chars > 0).mean(),
        "median_checklist_pages": g.post_checklist_pages[g.post_checklist_pages > 0].median(),
        "post_chars_share_checklist": g.post_checklist_chars.sum() / max(1, g.post_chars.sum()),
        "post_chars_share_statement": g.post_stmt_chars.sum() / max(1, g.post_chars.sum()),
        "share_appendix_ge1000tok": (g.appx_tokens >= 1000).mean(),
        "share_appendix_before_refs": (g.body_appx_chars > 0).mean(),
    }} for k, g in ven.groupby(["venue", "year"])])
    vd.to_csv(os.path.join(out, "diagnostics_venues.csv"), index=False, float_format="%.4g")
    vcomp = per.reset_index()
    vcomp = vcomp[vcomp.venue != "iclr"].groupby(["venue", "year"])[CAT_ORDER].mean().reset_index()
    vcomp.to_csv(os.path.join(out, "composition_venues.csv"), index=False, float_format="%.4g")

    # ---- decomposition of growth in mean and median length, early vs recent cohort ----
    dec = []
    for stratum, sel in (("all", iclr), ("under_review", iclr[iclr.version == "under_review"])):
        for (y0, y1) in ((2017, 2027), (2017, 2026), (2018, 2024), (2024, 2027)):
            a, b = sel[sel.year == y0], sel[sel.year == y1]
            dmain = b.main_tokens.mean() - a.main_tokens.mean()
            dappx = b.appx_tokens.mean() - a.appx_tokens.mean()
            dec.append({"stratum": stratum, "from": y0, "to": y1,
                        "mean_total_from": a.total_tokens.mean(), "mean_total_to": b.total_tokens.mean(),
                        "delta_mean_main": dmain, "delta_mean_appx": dappx,
                        "share_of_growth_from_appendix": dappx / (dmain + dappx),
                        "median_main_from": a.main_tokens.median(), "median_main_to": b.main_tokens.median(),
                        "median_appx_from": a.appx_tokens.median(), "median_appx_to": b.appx_tokens.median(),
                        "median_pages_from": a.pages.median(), "median_pages_to": b.pages.median(),
                        "median_body_pages_from": a.body_pages.median(), "median_body_pages_to": b.body_pages.median(),
                        "median_post_pages_from": a.post_pages.median(), "median_post_pages_to": b.post_pages.median(),
                        "median_main_pages_from": a.main_pages.median(), "median_main_pages_to": b.main_pages.median(),
                        "median_appx_pages_from": a.appx_pages.median(), "median_appx_pages_to": b.appx_pages.median()})
    dec = pd.DataFrame(dec)
    dec.to_csv(os.path.join(out, "growth_decomposition_iclr.csv"), index=False, float_format="%.4g")

    with open(os.path.join(out, "method.json"), "w") as f:
        json.dump({**run, "analysis": "scripts/appendix_analyze.py v1", "seed": SEED,
                   "population": "ICLR: paper_flags exclude=='' and in_sample; venues: chars>=2000",
                   "early": EARLY, "recent": RECENT, "resubmission_pairs": pairs_summary,
                   "taxonomy": dict(CATEGORIES)}, f, indent=1, default=str)

    figures(q, prev, comp, iclr, vq, figdir)
    print(json.dumps(pairs_summary, indent=1))
    print(dec.to_string())


# ------------------------------------------------------------------ figures
C_BLUE, C_ORANGE, C_AQUA, C_GRAY, C_INK, C_INK2 = "#2a78d6", "#eb6834", "#1baf7a", "#8a8984", "#0b0b0b", "#52514e"
CAT_COLORS = {  # categorical slots in fixed order; small categories fold into gray
    "proofs_theory": "#2a78d6", "additional_results": "#eb6834", "ablation": "#1baf7a",
    "implementation": "#8c5fd3", "data_benchmarks": "#d6a10f", "examples_prompts": "#d2457f",
    "related_work": "#5a9bd5", "background_notation": "#9bbf5a", "limitations_discussion": "#b07a4f",
    "algorithm": "#4fb3bf", "statement": "#bdbcb6", "other_math": "#7f7e79", "other_tables_figures": "#a5a49f",
    "other_prose": "#c4c3be", "unsectioned": "#e4e3de",
}


def _style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#bdbcb6")
    ax.tick_params(colors=C_INK2, labelsize=7)
    ax.grid(axis="y", color="#e6e5e0", lw=0.6)
    ax.set_axisbelow(True)


def figures(q, prev, comp, iclr, vq, figdir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.titlesize": 9})

    # Fig 1: main body vs appendix tokens, median with P25-P75 band; submissions dashed
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4), sharey=False)
    for ax, (unit, mm, aa) in zip(axes, (("tokens", "main_tokens", "appx_tokens"),
                                          ("pages", "main_pages", "appx_pages"))):
        for m, col, lab in ((mm, C_BLUE, "main body"), (aa, C_ORANGE, "appendix")):
            s = q[(q.stratum == "all") & (q.measure == m)].sort_values("year")
            ax.fill_between(s.year, s.p25, s.p75, color=col, alpha=0.15, lw=0)
            ax.plot(s.year, s.p50, color=col, lw=2, marker="o", ms=4, label=f"{lab}, median (band P25–P75)")
            u = q[(q.stratum == "under_review") & (q.measure == m)].sort_values("year")
            ax.plot(u.year, u.p50, color=col, lw=1, ls=(0, (3, 2)), label=f"{lab}, submissions only")
        _style(ax)
        ax.set_xticks(range(2017, 2028))
        ax.set_xticklabels([str(y)[2:] for y in range(2017, 2028)])
        ax.set_title(f"Per-paper length, {unit} (ICLR)", loc="left", color=C_INK)
        ax.set_ylim(bottom=0)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, fontsize=6.5, frameon=False, loc="lower center", ncol=4, bbox_to_anchor=(0.5, 0.05))
    fig.text(0.01, 0.01, "Main body excludes statement sections and pre-reference appendices; appendix excludes "
             "statements, checklists and reference residue. Tokens: tokenizer v1.3 on prose (tables/equations omitted).",
             fontsize=6, color=C_INK2)
    fig.tight_layout(rect=(0, 0.12, 1, 1))
    fig.savefig(os.path.join(figdir, "fig1_main_vs_appendix.png"), dpi=170)
    plt.close(fig)

    # Fig 2: distribution of appendix-to-document ratio by year (quantile ribbons + box per year)
    fig, ax = plt.subplots(figsize=(7, 3.4))
    data = [iclr[iclr.year == y].appx_ratio.dropna().to_numpy() for y in range(2017, 2028)]
    bp = ax.boxplot(data, positions=range(2017, 2028), widths=0.55, whis=(10, 90), showfliers=False,
                    patch_artist=True, medianprops={"color": C_INK, "lw": 1.5})
    for b in bp["boxes"]:
        b.set(facecolor="#f7c9b5", edgecolor=C_ORANGE, lw=0.8)
    for w in bp["whiskers"] + bp["caps"]:
        w.set(color=C_ORANGE, lw=0.8)
    _style(ax)
    ax.set_xticks(range(2017, 2028))
    ax.set_xticklabels([str(y) for y in range(2017, 2028)], fontsize=7)
    ax.set_ylim(0, 1)
    ax.set_ylabel("appendix tokens / (main + appendix)", fontsize=7, color=C_INK2)
    ax.set_title("Appendix share of each paper's prose, ICLR (box P25–P75, whiskers P10–P90)", loc="left", color=C_INK)
    fig.tight_layout()
    fig.savefig(os.path.join(figdir, "fig2_appendix_ratio_by_year.png"), dpi=170)
    plt.close(fig)

    # Fig 3: main vs appendix per paper, early vs recent cohort (2D histograms on log axes)
    fig, axes = plt.subplots(1, 2, figsize=(8.5, 3.8), sharex=True, sharey=True)
    bins_x = np.logspace(np.log10(1500), np.log10(20000), 40)
    bins_y = np.r_[0, np.logspace(1, np.log10(150000), 45)]
    for ax, years, lab in zip(axes, (EARLY, RECENT), ("2017–2019", "2025–2027")):
        g = iclr[iclr.year.isin(years)]
        h = ax.hist2d(g.main_tokens.clip(1500, 20000), g.appx_tokens.clip(0, 150000) + 10,
                      bins=[bins_x, bins_y + 10], cmap="Blues", weights=np.full(len(g), 100 / len(g)),
                      cmin=1e-9, vmin=0, vmax=1.5)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xticks([2000, 3000, 5000, 10000, 20000], ["2k", "3k", "5k", "10k", "20k"])
        ax.set_xticks([], minor=True)
        ax.set_yticks([10, 110, 1010, 10010, 100010], ["0", "100", "1k", "10k", "100k"])
        ax.set_yticks([], minor=True)
        x = np.array([1500, 20000])
        ax.plot(x, x, color=C_GRAY, lw=0.8, ls=(0, (3, 2)))
        ax.text(15000, 17000, "appendix = main", fontsize=6, color=C_INK2, rotation=30)
        mm, ma = g.main_tokens.median(), g.appx_tokens.median()
        ax.scatter([mm], [ma + 10], s=40, marker="D", color=C_ORANGE, edgecolor="white", zorder=5)
        ax.set_title(f"{lab} (n = {len(g):,}); ◆ = medians", loc="left", color=C_INK)
        ax.set_xlabel("main-body tokens", fontsize=7, color=C_INK2)
        _style(ax)
    axes[0].set_ylabel("appendix tokens (log scale; bottom row = none)", fontsize=7, color=C_INK2)
    fig.colorbar(h[3], ax=axes, shrink=0.8, label="% of the cohort's papers per cell", extend="max")
    fig.savefig(os.path.join(figdir, "fig3_main_vs_appendix_scatter.png"), dpi=170, bbox_inches="tight")
    plt.close(fig)

    # Fig 4: composition of appendix text by heading category (mean characters per paper)
    c = comp[comp.stratum == "all"].pivot(index="year", columns="category", values="mean_chars_per_paper")[CAT_ORDER]
    fig, ax = plt.subplots(figsize=(8, 3.8))
    ax.stackplot(c.index, [c[k] / 1000 for k in CAT_ORDER], colors=[CAT_COLORS[k] for k in CAT_ORDER],
                 labels=[k.replace("_", " ") for k in CAT_ORDER], edgecolor="white", lw=0.6)
    _style(ax)
    ax.set_xticks(range(2017, 2028))
    ax.set_ylabel("thousand characters per paper (mean)", fontsize=7, color=C_INK2)
    ax.set_title("What fills the post-reference pages: appendix text by section-heading category, ICLR",
                 loc="left", color=C_INK)
    h, l = ax.get_legend_handles_labels()
    ax.legend(h[::-1], l[::-1], fontsize=6.5, frameon=False, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    fig.tight_layout()
    fig.savefig(os.path.join(figdir, "fig4_appendix_composition.png"), dpi=170)
    plt.close(fig)

    # Fig 5: venues, median main vs appendix tokens
    fig, ax = plt.subplots(figsize=(8, 3.6))
    vcol = {"iclr": C_INK, "neurips": C_BLUE, "tmlr": C_ORANGE, "colm": C_AQUA, "corl": "#8c5fd3",
            "icml": "#d6a10f", "emnlp": "#d2457f"}
    for v, col in vcol.items():
        if v == "iclr":
            s = q[(q.stratum == "all")]
        else:
            s = vq[vq.venue == v]
        for m, ls in (("main_tokens", "-"), ("appx_tokens", (0, (3, 2)))):
            t = s[s.measure == m].sort_values("year")
            ax.plot(t.year, t.p50, color=col, ls=ls, lw=1.6, marker="o", ms=3.5,
                    label=f"{v.upper()} {'main' if m == 'main_tokens' else 'appendix'}")
    _style(ax)
    ax.set_xticks(range(2017, 2028))
    ax.set_ylabel("median tokens per paper", fontsize=7, color=C_INK2)
    ax.set_title("Main body (solid) and appendix (dashed) by venue; NeurIPS/CoRL 2021–22 kept appendices in "
                 "separate files", loc="left", color=C_INK, fontsize=8)
    ax.legend(fontsize=6, frameon=False, ncol=2, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    fig.tight_layout()
    fig.savefig(os.path.join(figdir, "fig5_venues.png"), dpi=170)
    plt.close(fig)


if __name__ == "__main__":
    main()
