"""Disclosure phrase inventory with template attribution (Lane B, Gate 2).

Usage: python3 scripts/disclosures/phrases.py [--data data/disclosures/iclr2027.parquet] [--tier clean]

Every disclosure is tokenized with the study tokenizer (v1.3). Each token is then
attributed to one of three sources:
  template   covered by a 4-gram that also occurs in the ICLR 2027 policy text:
             the example disclosure section, its placeholders, and the
             required / recommended task lists (results/disclosures/iclr2027_ai_policy.txt)
  stock      not template, but covered by a 6-gram that occurs in >= STOCK_DF
             disclosures: wording shared across many papers that ICLR did not supply
             ("the authors take full responsibility for")
  author     everything else
An n-gram occurrence is "template" if all its tokens are template, "stock" if
all are template-or-stock and at least one is stock, otherwise "author".

Outputs (results/disclosures/, aggregates only, no disclosure text):
  phrases_n{2,3,4}.csv     top 300 n-grams: count, doc frequency, share of
                           occurrences that are template / stock / author
  frames.csv               4-token phrase frames with one open slot (w1 * w3 w4 and
                           w1 w2 * w4): frequency, distinct fillers, top fillers
  template_coverage.csv    per-disclosure share of template / stock tokens (distribution)
  duplicates.csv           exact and near-duplicate clusters (sizes, example ids)
  length_summary.csv       length distribution and wording variability
  polarity_phrases.csv     n-grams distinguishing affirmative-use sentences from
                           non-use sentences (log-odds ratio, informative Dirichlet prior)
Per-paper attribution shares go to data/disclosures/attribution.parquet (git-ignored).
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from mlngrams.tokenize import TOKENIZER_VERSION, tokenize  # noqa: E402

OUT = os.path.join(ROOT, "results", "disclosures")
STOCK_DF = 50  # a 6-gram shared by >= 50 disclosures (0.12% of papers) is stock wording
TOP = 300
SEED = 20271015

# Sentence-level polarity (descriptive use only; validated on a hand sample in docs/ai-disclosures.md).
NEG = re.compile(
    r"\b(?:not|never|no|none|neither|nor|without)\b|\bn't\b|not applicable|refrain|did not|have not|were not|was not",
    re.I,
)


def template_ngrams(n: int = 4) -> set[tuple[str, ...]]:
    txt = open(os.path.join(OUT, "iclr2027_ai_policy.txt"), encoding="utf-8").read()
    start = txt.index("Example AI disclosure section")
    txt = txt[start:]
    txt = re.sub(r"[<>\[\]]", " ", txt).replace("Required :", "\n\n").replace("Recommended :", "\n\n")
    out = set()
    # Task lists are comma-separated items; authors paste them in any order, so also take each item alone.
    pieces = [txt] + [p for p in re.split(r",|\.", txt) if p.strip()]
    for p in pieces:
        for seg in tokenize(p):
            for i in range(len(seg) - n + 1):
                out.add(tuple(seg[i : i + n]))
    return out


def cover(seg: list[str], grams: set, n: int) -> np.ndarray:
    c = np.zeros(len(seg), dtype=bool)
    for i in range(len(seg) - n + 1):
        if tuple(seg[i : i + n]) in grams:
            c[i : i + n] = True
    return c


def minhash_clusters(shingle_sets: list[set[int]], k: int = 64, bands: int = 16, thresh: float = 0.8):
    """Union-find clusters of documents with estimated 5-gram Jaccard >= thresh."""
    rng = np.random.default_rng(SEED)
    p = (1 << 61) - 1
    a = rng.integers(1, p, k, dtype=np.uint64)
    b = rng.integers(0, p, k, dtype=np.uint64)
    sigs = np.full((len(shingle_sets), k), np.iinfo(np.uint64).max, dtype=np.uint64)
    for i, s in enumerate(shingle_sets):
        if s:
            x = np.fromiter(s, dtype=np.uint64)
            sigs[i] = ((np.outer(x, a) + b) % np.uint64(p)).min(axis=0)
    parent = list(range(len(shingle_sets)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    r = k // bands
    for bnd in range(bands):
        buckets = collections.defaultdict(list)
        for i in range(len(sigs)):
            if shingle_sets[i]:
                buckets[sigs[i, bnd * r : (bnd + 1) * r].tobytes()].append(i)
        for ids in buckets.values():
            for j in ids[1:]:
                if (sigs[ids[0]] == sigs[j]).mean() >= thresh:
                    ra, rb = find(ids[0]), find(j)
                    if ra != rb:
                        parent[rb] = ra
    return [find(i) for i in range(len(shingle_sets))]


def log_odds(c1: collections.Counter, c2: collections.Counter, prior: collections.Counter, a0: float = 1000.0):
    """Monroe et al. (2008) log-odds ratio with informative Dirichlet prior; returns z-scores."""
    n1, n2, n0 = sum(c1.values()), sum(c2.values()), sum(prior.values())
    rows = []
    for w, p in prior.items():
        aw = a0 * p / n0
        y1, y2 = c1.get(w, 0), c2.get(w, 0)
        d = np.log((y1 + aw) / (n1 + a0 - y1 - aw)) - np.log((y2 + aw) / (n2 + a0 - y2 - aw))
        var = 1 / (y1 + aw) + 1 / (y2 + aw)
        rows.append((" ".join(w), y1, y2, d, d / np.sqrt(var)))
    return pd.DataFrame(rows, columns=["ngram", "count_use", "count_nonuse", "log_odds", "z"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(ROOT, "data", "disclosures", "iclr2027.parquet"))
    ap.add_argument("--tier", default="clean", choices=["clean", "all"])
    args = ap.parse_args()
    df = pd.read_parquet(args.data)
    df = df[df.found == True]  # noqa: E712
    if args.tier == "clean":
        df = df[df.tier == "clean"]
    df = df.reset_index(drop=True)
    N = len(df)
    tmpl = template_ngrams(4)
    docs = [tokenize(t) for t in df.text]

    # Stock wording: 6-grams by document frequency, minus template-covered ones.
    df6 = collections.Counter()
    for segs in docs:
        df6.update({tuple(s[i : i + 6]) for s in segs for i in range(len(s) - 5)})
    stock6 = {g for g, c in df6.items() if c >= STOCK_DF}

    counts = {n: collections.Counter() for n in (2, 3, 4)}
    dfreq = {n: collections.Counter() for n in (2, 3, 4)}
    src = {n: {k: collections.Counter() for k in ("template", "stock", "author")} for n in (2, 3, 4)}
    frames = collections.defaultdict(collections.Counter)
    cov_rows, shingles = [], []
    pol = {"use": {n: collections.Counter() for n in (1, 2, 3)}, "nonuse": {n: collections.Counter() for n in (1, 2, 3)}}
    sent_pol = collections.Counter()
    for d, segs in enumerate(docs):
        ntok = ttok = stok = 0
        seen = {n: set() for n in (2, 3, 4)}
        sh = set()
        for s in segs:
            ct = cover(s, tmpl, 4)
            cs = cover(s, stock6, 6) & ~ct
            ntok += len(s)
            ttok += int(ct.sum())
            stok += int(cs.sum())
            for n in (2, 3, 4):
                for i in range(len(s) - n + 1):
                    g = tuple(s[i : i + n])
                    counts[n][g] += 1
                    seen[n].add(g)
                    if ct[i : i + n].all():
                        src[n]["template"][g] += 1
                    elif (ct[i : i + n] | cs[i : i + n]).all():
                        src[n]["stock"][g] += 1
                    else:
                        src[n]["author"][g] += 1
            for i in range(len(s) - 3):
                w = s[i : i + 4]
                frames[(w[0], "*", w[2], w[3])][w[1]] += 1
                frames[(w[0], w[1], "*", w[3])][w[2]] += 1
            for i in range(len(s) - 4):
                sh.add(int.from_bytes(hashlib.blake2b(" ".join(s[i : i + 5]).encode(), digest_size=7).digest(), "little"))
        for n in (2, 3, 4):
            dfreq[n].update(seen[n])
        shingles.append(sh)
        cov_rows.append((df.doc_id[d], ntok, ttok, stok))
        # Polarity: sentences of the cleaned text (segments split only at . ! ? here).
        for sent in re.split(r"(?<=[.!?])\s+", df.text_clean[d]):
            k = "nonuse" if NEG.search(sent) else "use"
            sent_pol[k] += 1
            for seg in tokenize(sent):
                for n in (1, 2, 3):
                    pol[k][n].update(tuple(seg[i : i + n]) for i in range(len(seg) - n + 1))

    # Phrase tables
    for n in (2, 3, 4):
        rows = []
        for g, c in counts[n].most_common(TOP):
            rows.append({
                "ngram": " ".join(g), "count": c, "docs": dfreq[n][g], "doc_pct": round(100 * dfreq[n][g] / N, 2),
                "template_pct": round(100 * src[n]["template"][g] / c, 1), "stock_pct": round(100 * src[n]["stock"][g] / c, 1),
                "author_pct": round(100 * src[n]["author"][g] / c, 1),
            })
        pd.DataFrame(rows).to_csv(os.path.join(OUT, f"phrases_n{n}.csv"), index=False)
        # Author-only view: top n-grams counting only author-attributed occurrences.
        rows = [{"ngram": " ".join(g), "author_count": c, "total_count": counts[n][g]} for g, c in src[n]["author"].most_common(TOP)]
        pd.DataFrame(rows).to_csv(os.path.join(OUT, f"phrases_n{n}_author_only.csv"), index=False)

    fr = []
    for k, fill in frames.items():
        tot = sum(fill.values())
        if tot >= 200 and len(fill) >= 5:
            fr.append({"frame": " ".join(k), "count": tot, "distinct_fillers": len(fill),
                       "top_filler_share": round(fill.most_common(1)[0][1] / tot, 3),
                       "top_fillers": "; ".join(f"{w} ({c})" for w, c in fill.most_common(8))})
    pd.DataFrame(fr).sort_values("count", ascending=False).head(TOP).to_csv(os.path.join(OUT, "frames.csv"), index=False)

    cov = pd.DataFrame(cov_rows, columns=["doc_id", "tokens", "template_tokens", "stock_tokens"])
    cov["template_share"] = cov.template_tokens / cov.tokens.clip(lower=1)
    cov["stock_share"] = cov.stock_tokens / cov.tokens.clip(lower=1)
    cov["author_share"] = 1 - cov.template_share - cov.stock_share
    os.makedirs(os.path.dirname(args.data), exist_ok=True)
    cov.to_parquet(os.path.join(os.path.dirname(args.data), "attribution.parquet"), index=False)
    qs = [0.1, 0.25, 0.5, 0.75, 0.9]
    covsum = pd.DataFrame({
        "measure": ["template_share", "stock_share", "author_share"],
        **{f"p{int(q*100)}": [round(cov[c].quantile(q), 3) for c in ("template_share", "stock_share", "author_share")] for q in qs},
        "mean": [round(cov[c].mean(), 3) for c in ("template_share", "stock_share", "author_share")],
    })
    extra = pd.DataFrame({"measure": ["papers", "token_total", "template_token_pct", "stock_token_pct",
                                      "docs_template_ge_90pct", "docs_template_ge_50pct", "docs_template_zero",
                                      "sentences_use", "sentences_nonuse"],
                          "mean": [N, int(cov.tokens.sum()), round(100 * cov.template_tokens.sum() / cov.tokens.sum(), 2),
                                   round(100 * cov.stock_tokens.sum() / cov.tokens.sum(), 2),
                                   int((cov.template_share >= 0.9).sum()), int((cov.template_share >= 0.5).sum()),
                                   int((cov.template_share == 0).sum()), sent_pol["use"], sent_pol["nonuse"]]})
    pd.concat([covsum, extra]).to_csv(os.path.join(OUT, "template_coverage.csv"), index=False)

    # Duplicates
    norm = [" ".join(t.lower().split()) for t in df.text_clean]
    exact = collections.Counter(norm)
    clusters = minhash_clusters(shingles)
    csize = collections.Counter(clusters)
    dup_rows = []
    by_cluster = collections.defaultdict(list)
    for i, c in enumerate(clusters):
        by_cluster[c].append(i)
    for c, ids in sorted(by_cluster.items(), key=lambda kv: -len(kv[1]))[:50]:
        if len(ids) < 2:
            break
        dup_rows.append({"cluster_size": len(ids), "example_ids": " ".join(df.doc_id[i] for i in ids[:5]),
                         "median_words": int(np.median([df.n_words[i] for i in ids])),
                         "mean_template_share": round(float(cov.template_share[ids].mean()), 3)})
    pd.DataFrame(dup_rows).to_csv(os.path.join(OUT, "duplicates.csv"), index=False)
    lens = df.n_words
    summ = {
        "papers": N, "distinct_exact_texts": len(exact), "papers_in_exact_dup_groups": sum(c for c in exact.values() if c > 1),
        "exact_dup_groups": sum(1 for c in exact.values() if c > 1), "largest_exact_group": max(exact.values()),
        "near_dup_clusters_ge2": sum(1 for c in csize.values() if c > 1),
        "papers_in_near_dup_clusters": sum(c for c in csize.values() if c > 1),
        "distinct_formulations_jaccard08": len(csize), "largest_near_dup_cluster": max(csize.values()),
        **{f"words_p{int(q*100)}": float(lens.quantile(q)) for q in [0.1, 0.25, 0.5, 0.75, 0.9]},
        "words_mean": round(float(lens.mean()), 1), "words_cv": round(float(lens.std() / lens.mean()), 3),
        "type_token_ratio_pooled_unigrams": None,
    }
    uni = collections.Counter(tok for segs in docs for s in segs for tok in s)
    summ["type_token_ratio_pooled_unigrams"] = round(len(uni) / sum(uni.values()), 4)
    summ["vocabulary_size"] = len(uni)
    pd.DataFrame(list(summ.items()), columns=["measure", "value"]).to_csv(os.path.join(OUT, "length_summary.csv"), index=False)

    # Polarity phrases
    pr = []
    for n in (1, 2, 3):
        prior = pol["use"][n] + pol["nonuse"][n]
        prior = collections.Counter({g: c for g, c in prior.items() if c >= 30})
        lo = log_odds(pol["use"][n], pol["nonuse"][n], prior)
        lo["n"] = n
        pr.append(pd.concat([lo.nlargest(60, "z").assign(side="use"), lo.nsmallest(60, "z").assign(side="nonuse")]))
    pd.concat(pr).round(3).to_csv(os.path.join(OUT, "polarity_phrases.csv"), index=False)
    with open(os.path.join(OUT, "phrases_run.json"), "w") as fh:
        json.dump({"tier": args.tier, "papers": N, "tokenizer": TOKENIZER_VERSION, "stock_df": STOCK_DF, "seed": SEED,
                   "template_n": 4, "stock_n": 6, "minhash": {"k": 64, "bands": 16, "thresh": 0.8, "shingle": 5}}, fh, indent=1)
    print(json.dumps(summ, indent=1))
    print(pd.read_csv(os.path.join(OUT, "template_coverage.csv")).to_string())


if __name__ == "__main__":
    main()
