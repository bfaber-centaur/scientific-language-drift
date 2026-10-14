"""QA audit of a count_ngrams.py run (Agent D). Prints aggregate diagnostics only (no paper text).

    python3 scripts/qa_audit.py --run ~/work/pilot --out /tmp/qa   [--years 2018 2026]

Sections:
  recompute     per-doc tokens/positions in docs.parquet vs fresh tokenization (sample)
  contamination top-K raw/content bigrams per year, rule-based artifact classes, per-million mass
  denominators  share of bigram positions that are number/single-letter residue; appendix share
  rising        2018 vs 2026 risers under several rankings, with document bootstrap + concentration
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from collections import Counter

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from mlngrams import tokenize as tk  # noqa: E402
from mlngrams.count import ngrams_of  # noqa: E402
from mlngrams.filters import is_content  # noqa: E402
from mlngrams.load import iter_docs, main_body  # noqa: E402

CITE = {"et", "al", "arxiv", "preprint", "proceedings", "conference", "international", "journal", "ieee",
        "pp", "vol", "neurips", "icml", "iclr", "cvpr", "acl", "emnlp", "aaai", "openreview"}
CITE_BIGRAMS = {"information processing", "neural information", "processing systems", "learning representations",
                "machine learning", "computer vision", "pattern recognition"}  # second-tier: only flagged in refs check
HEADER = {"conference paper", "under review", "workshop track", "track iclr", "paper under", "double-blind review",
          "anonymous authors", "published as", "paper at", "at iclr"}
TEMPLATE = {"reproducibility statement", "ethics statement", "llm usage", "use of", "of llms", "usage of",
            "impact statement", "broader impact", "broader impacts", "code of", "of ethics", "large language"}
TEMPLATE_STRICT = {"reproducibility statement", "ethics statement", "llm usage", "impact statement",
                   "broader impact", "broader impacts", "code of", "of ethics", "usage of", "llms usage"}
XREF = {"see appendix", "see figure", "see table", "see section", "see fig", "in appendix", "please refer",
        "main text", "main paper", "supplementary material", "additional results", "implementation details",
        "experimental details", "experimental setup", "related work", "related works", "future work",
        "experimental settings", "additional experiments", "next section", "previous section"}
HEADINGS = {"abstract", "introduction", "conclusion", "conclusions", "background", "experiments", "appendix",
            "acknowledgments", "acknowledgements", "discussion", "method", "methods", "results"}
# LLM-era prompt/template furniture (appendix prompt listings)
PROMPT = {"system prompt", "final answer", "output format", "prompt template", "user prompt", "correct answer"}


def classify(ng: str, acr: set[str]) -> str:
    toks = ng.split(" ")
    if ng in HEADER:
        return "header"
    if ng in TEMPLATE_STRICT:
        return "template_statement"
    if any(t in CITE for t in toks) or ng in {"information processing", "neural information", "processing systems"}:
        return "citation_residue"
    if "<num>" in toks:
        return "number_table"
    if any(len(t) == 1 and t not in {"a"} for t in toks):
        return "math_letter"
    if len(toks) == 2 and is_content(ng) and toks[1] in acr and toks[1].rstrip("s")[-1:] == toks[0][:1]:
        return "paren_acronym"
    if ng in XREF:
        return "xref_section"
    if ng in PROMPT:
        return "prompt_furniture"
    return "prose"


def acronyms(sample_texts) -> set[str]:
    c = Counter(m.lower() for t in sample_texts for m in re.findall(r"\(([A-Z][A-Za-z]{1,6})\)", t))
    return {a for a, k in c.items() if k >= 3}


def load_year_texts(config, year, ids=None):
    for d in iter_docs(config, "iclr", year):
        if ids is None or d["doc_id"] in ids:
            yield d


def recompute(run, docs, cfg, out):
    rows = []
    for y, g in docs.groupby("year"):
        s = g.sample(min(60, len(g)), random_state=1).set_index("doc_id")
        for d in load_year_texts(cfg["config"], y, set(s.index)):
            text = main_body(d["text"]) if cfg["body_only"] else d["text"]
            segs = tk.tokenize(text)
            r = s.loc[d["doc_id"]]
            rows.append({
                "year": y, "doc_id": d["doc_id"],
                "tok_ok": sum(map(len, segs)) == r["tokens"],
                **{f"pos{n}_ok": sum(max(0, len(x) - n + 1) for x in segs) == r[f"positions_{n}"] for n in (1, 2, 3)},
                "chars_ok": len(text) == r["chars"],
            })
    df = pd.DataFrame(rows)
    print("== recompute (sampled docs) ==")
    print(df.groupby("year")[[c for c in df if c.endswith("_ok")]].mean().to_string())
    totals = pd.read_csv(os.path.join(run, "totals.csv"))
    agg = docs.groupby("year").agg(docs=("doc_id", "size"), tokens=("tokens", "sum"),
                                   p1=("positions_1", "sum"), p2=("positions_2", "sum"), p3=("positions_3", "sum"))
    for n in (1, 2, 3):
        t = totals[totals.n == n].set_index("year")
        assert (t["positions"] == agg[f"p{n}"]).all() and (t["docs"] == agg["docs"]).all(), "totals != docs.parquet"
    print("totals.csv consistent with docs.parquet sums: OK")


def contamination(run, years, acr, k, out):
    n2 = pd.read_parquet(os.path.join(run, "ngrams_n2.parquet"))
    n2 = n2[n2.year.isin(years)]
    recs = []
    for view in ("raw", "content"):
        for y in years:
            t = n2[n2.year == y]
            if view == "content":
                t = t[t.ngram.map(is_content)]
            t = t.head(k).copy()
            t["cls"] = t.ngram.map(lambda g: classify(g, acr))
            t["view"] = view
            recs.append(t)
    r = pd.concat(recs)
    r.to_csv(os.path.join(out, "contamination_top.csv"), index=False)
    mass = r.pivot_table(index=["view", "cls"], columns="year", values="per_million", aggfunc="sum").fillna(0).round(0)
    cnt = r.pivot_table(index=["view", "cls"], columns="year", values="ngram", aggfunc="count").fillna(0).astype(int)
    print(f"== contamination: per-million mass (sum) of top-{k} bigrams by class ==")
    print(mass.to_string())
    print("-- number of n-grams by class --")
    print(cnt.to_string())
    # Whole-table (not just top-K) share of bigram positions by class
    whole = n2.copy()
    whole["cls"] = whole.ngram.map(lambda g: classify(g, acr))
    share = whole.groupby(["year", "cls"])["count"].sum() / whole.groupby("year")["positions"].first()
    print("== share of ALL bigram positions by class (df>=3 table) ==")
    print((100 * share.unstack(0)).round(2).to_string())
    # Which non-prose classes enter/leave content top-K between first and last year
    a, b = years[0], years[-1]
    ca = set(r[(r.view == "content") & (r.year == a)].ngram)
    cb = r[(r.view == "content") & (r.year == b)]
    new = cb[~cb.ngram.isin(ca)]
    print(f"== content top-{k}: {len(new)} bigrams new in {b} vs {a}; classes: {new.cls.value_counts().to_dict()}")
    print("   non-prose newcomers:", ", ".join(f"{g}({c})" for g, c in zip(new.ngram, new.cls) if c != "prose"))
    # heading fusion: bigrams whose first token is a section heading word followed by prose
    h = n2[n2.ngram.str.split(" ").str[0].isin(HEADINGS)]
    hs = h.groupby("year")["count"].sum() / n2.groupby("year")["positions"].first() * 1e6
    print("== heading-word-initial bigrams per million (proxy for heading/prose fusion) ==", hs.round(0).to_dict())
    tops = h[h.ngram.str.startswith(("abstract ", "introduction "))].groupby("year").head(5)
    print("   e.g.", ", ".join(f"{y}:{g}" for y, g in zip(tops.year, tops.ngram)))


def template_prevalence(run, years):
    n2 = pd.read_parquet(os.path.join(run, "ngrams_n2.parquet"))
    n3 = pd.read_parquet(os.path.join(run, "ngrams_n3.parquet"))
    want2 = ["reproducibility statement", "ethics statement", "llm usage", "impact statement", "workshop track",
             "broader impact", "main text", "see appendix", "in appendix", "system prompt", "final answer",
             "models llms", "information processing", "international conference"]
    want3 = ["use of llms", "large language models", "the use of", "workshop track iclr", "code of ethics",
             "neural information processing", "in the appendix"]
    print("== template / furniture prevalence (share of papers) ==")
    for tab, want in ((n2, want2), (n3, want3)):
        t = tab[tab.ngram.isin(want) & tab.year.isin(years)]
        print(t.pivot_table(index="ngram", columns="year", values="prevalence").round(3).fillna(0).to_string())


def denominators(run, docs, years, cfg):
    print("== length / appendix ==")
    g = docs[docs.year.isin(years)].groupby("year")
    print(pd.DataFrame({"median_tokens": g.tokens.median(), "p90_tokens": g.tokens.quantile(.9),
                        "mean_tokens": g.tokens.mean().round(0)}).to_string())
    rows = []
    for y in years:
        for i, d in enumerate(load_year_texts(cfg["config"], y)):
            if i >= 300:
                break
            full = sum(map(len, tk.tokenize(d["text"])))
            body = sum(map(len, tk.tokenize(main_body(d["text"]))))
            rows.append({"year": y, "body_share": body / max(full, 1)})
    b = pd.DataFrame(rows).groupby("year").body_share.describe()[["mean", "25%", "50%"]]
    print("token share before first ⟦references omitted⟧ (first 300 docs/yr):")
    print(b.round(3).to_string())


def per_doc_counts(cfg, year, cands, body_only):
    """doc -> Counter of candidate bigrams; plus per-doc positions."""
    out, pos = [], []
    for d in load_year_texts(cfg["config"], year):
        text = main_body(d["text"]) if body_only else d["text"]
        segs = tk.tokenize(text)
        c = Counter(g for g in ngrams_of(segs, 2) if g in cands)
        out.append(c)
        pos.append(sum(max(0, len(s) - 1) for s in segs))
    return out, np.array(pos)


def rising(run, a, b, cfg, out, k_smooth=5, min_prev=0.01, B=200):
    n2 = pd.read_parquet(os.path.join(run, "ngrams_n2.parquet"))
    A = n2[n2.year == a].set_index("ngram")
    Bt = n2[n2.year == b].set_index("ngram")
    PA, PB = A.positions.iloc[0], Bt.positions.iloc[0]
    DA, DB = A.docs.iloc[0], Bt.docs.iloc[0]
    j = pd.DataFrame({"cA": A["count"], "cB": Bt["count"], "dfA": A["df"], "dfB": Bt["df"]}).fillna(0)
    j = j[j.index.map(is_content)]
    j["pmA"], j["pmB"] = 1e6 * j.cA / PA, 1e6 * j.cB / PB
    j["prevA"], j["prevB"] = j.dfA / DA, j.dfB / DB
    # naive: per-million ratio with tiny pseudo-count (what a quick analysis would do)
    j["naive"] = np.log2((j.cB / PB + 1e-9) / (j.cA / PA + 1e-9))
    # smoothed: k pseudo-counts on each side (Bayesian-ish; shrinks low counts toward 0)
    j["smooth"] = np.log2(((j.cB + k_smooth) / PB) / ((j.cA + k_smooth) / PA))
    # prevalence-based: log2 of smoothed prevalence ratio, requires min prevalence in later year
    j["prev_lr"] = np.log2(((j.dfB + 1) / (DB + 2)) / ((j.dfA + 1) / (DA + 2)))
    j["absentA"] = j.dfA == 0  # absent from pruned table: true df in {0,1,2}, count unknown
    robust = j[(j.prevB >= min_prev) | (j.prevA >= min_prev)]
    top_naive = j.sort_values("naive", ascending=False).head(40)
    top_smooth = robust.sort_values("smooth", ascending=False).head(40)
    top_prev = robust[robust.dfB >= 30].sort_values("prev_lr", ascending=False).head(40)
    fall_smooth = robust.sort_values("smooth").head(40)
    cands = set(top_naive.index) | set(top_smooth.index) | set(top_prev.index) | set(fall_smooth.index)
    # bootstrap over documents
    ca, pa = per_doc_counts(cfg, a, cands, cfg["body_only"])
    cb, pb = per_doc_counts(cfg, b, cands, cfg["body_only"])
    rng = np.random.default_rng(0)
    cl = sorted(cands)
    MA = np.array([[c[g] for g in cl] for c in ca], dtype=float)
    MB = np.array([[c[g] for g in cl] for c in cb], dtype=float)
    # sanity: per-doc counts sum to table counts (for n-grams present in both tables)
    chk = pd.Series(MB.sum(0), index=cl)
    present = [g for g in cl if g in Bt.index]
    assert (chk[present] == Bt.loc[present, "count"]).all(), "per-doc recount != table count"
    lrs = []
    for _ in range(B):
        ia = rng.integers(0, len(ca), len(ca))
        ib = rng.integers(0, len(cb), len(cb))
        sa = MA[ia].sum(0) + k_smooth
        sb = MB[ib].sum(0) + k_smooth
        lrs.append(np.log2((sb / pb[ib].sum()) / (sa / pa[ia].sum())))
    lrs = np.array(lrs)
    st = pd.DataFrame({"lo": np.percentile(lrs, 2.5, 0), "hi": np.percentile(lrs, 97.5, 0),
                       "maxdoc_shareB": MB.max(0) / np.maximum(MB.sum(0), 1),
                       "maxdoc_shareA": MA.max(0) / np.maximum(MA.sum(0), 1),
                       # macro (mean of per-doc rates): length-robust check of pooled per-million
                       "macro_lr": np.log2(((MB / pb[:, None]).mean(0) + 1e-7) / ((MA / pa[:, None]).mean(0) + 1e-7))},
                      index=cl)
    res = j.loc[cl].join(st)
    res.to_csv(os.path.join(out, f"risers_{a}_{b}.csv"))

    def show(name, idx):
        t = res.loc[idx, ["cA", "cB", "dfA", "dfB", "naive", "smooth", "lo", "hi", "macro_lr", "maxdoc_shareB"]]
        print(f"-- {name} --")
        print(t.round(2).head(25).to_string())
        fragile = t[(t.lo <= 1) | (t.maxdoc_shareB > 0.2) | (t.dfB < 10)]
        print(f"   fragile (CI lower <= 1 bit, or one paper >20% of {b} count, or dfB<10): {len(fragile)}/{len(t)}")

    print(f"== risers {a}->{b} (content bigrams; log2 ratios; bootstrap 95% CI on smoothed k={k_smooth}) ==")
    show("naive per-million ratio, df>=3 table (UNSAFE)", top_naive.index)
    show(f"smoothed k={k_smooth}, prevalence>={min_prev} in either year", top_smooth.index)
    show("prevalence ratio, dfB>=30", top_prev.index)
    show(f"fallers smoothed k={k_smooth}", fall_smooth.index)
    print("naive top-40 that are absent from the pruned earlier-year table:", int(top_naive.absentA.sum()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--years", nargs="+", type=int, default=[2018, 2020, 2024, 2026])
    ap.add_argument("--k", type=int, default=300)
    ap.add_argument("--skip", nargs="*", default=[])
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    import json
    cfg = json.load(open(os.path.join(a.run, "run.json")))
    print("run:", {k: cfg[k] for k in ("tokenizer", "filter", "config", "body_only", "min_df", "docs")},
          "| code:", tk.TOKENIZER_VERSION)
    docs = pd.read_parquet(os.path.join(a.run, "docs.parquet"))
    samp = [d["text"] for i, d in zip(range(400), load_year_texts(cfg["config"], a.years[-1]))]
    acr = acronyms(samp)
    if "recompute" not in a.skip:
        recompute(a.run, docs, cfg, a.out)
    if "contamination" not in a.skip:
        contamination(a.run, a.years, acr, a.k, a.out)
        template_prevalence(a.run, a.years)
    if "denominators" not in a.skip:
        denominators(a.run, docs, a.years, cfg)
    if "rising" not in a.skip:
        rising(a.run, a.years[0], a.years[-1], cfg, a.out)


if __name__ == "__main__":
    main()
