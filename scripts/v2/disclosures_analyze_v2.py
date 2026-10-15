"""Lane D (V2): AI-use disclosures as a separate corpus across venues and years.

Usage:
    python3 scripts/v2/disclosures_analyze_v2.py [--data data/v2/disclosures] [--out results/v2/disclosures]

Reads the per-paper extraction (scripts/v2/disclosures_extract_v2.py) and first-page version labels.
Writes aggregates only (no disclosure text beyond <= 25-word excerpts in the labelling files):
  inventory.csv            per venue-year-version: papers, dedicated statement found (clean / suspect),
                           placement (main text vs after the references), length, provisional
                           classifier groups, in-text AI-writing sentence candidates without a section
  reproduction_iclr2027.csv V2 extraction of ICLR 2027 vs the V1.5 extraction summary
  polarity.csv             sentence-level stance per cohort: affirmative use claim, denial, mixed,
                           hypothetical/example, unfilled placeholder, attestation, other
  attribution.csv          token shares: ICLR 2027 policy template / stock (shared 6-grams) / author
  bundles.csv              top 4-gram lexical bundles per cohort (range >= 2% of disclosures)
  frames.csv               top phrase frames (w1 w2 * w4) per cohort with filler variability
  keyness.csv              log-odds (informative Dirichlet prior) between cohort pairs, unigrams-trigrams
  boilerplate.csv          per cohort: share of statements that are mostly template/stock wording,
                           near-copies, and the author-token distribution (substantive content)
Polarity rules are new in V2 (provisional, validated against Bobby's labels when available). They reuse
the clause splitter and negation test of mlngrams.disclosure_classify v2.
"""
from __future__ import annotations

import argparse
import collections
import glob
import hashlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "disclosures"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from mlngrams import disclosure_classify as dc  # noqa: E402
from mlngrams.load import V2_REVISION  # noqa: E402
from mlngrams.tokenize import tokenize  # noqa: E402
from phrases import cover, log_odds, minhash_clusters, template_ngrams  # noqa: E402

COHORTS = ["iclr-2026", "iclr-2027", "colm-2026", "icml-2026"]  # cohorts with enough statements for phrase work
PLACEHOLDER = re.compile(r"\[(?:tasks?|other tasks|the rest|elaborate)|<\s*tasks?|\[elaborate|\(this (?:section|statement) is (?:required|recommended)|see the iclr 20\d\d ai policy|should not be more than 1 page", re.I)
HYPO = re.compile(r"\b(?:for example|for instance|e\.g\.|such as [\"“]|if (?:we|the authors?|authors|any|llms?|ai)|would|could|might|in the event|should (?:we|the authors))\b", re.I)
PAST_USE = re.compile(r"\b(?:we|i|the authors?)\s+(?:also\s+|have\s+|only\s+)?(?:used|employed|utili[sz]ed|leveraged|relied)\b|\b(?:were|was|has been|have been)\s+(?:\w+\s+)?used\b|\bassisted\b", re.I)
ATTEST = re.compile(r"\bresponsib|\baccountab|\b(?:reviewed|verified|checked|validated|inspected|edited by the authors)\b|\bauthors['’]? own\b", re.I)
STOCK_RATE = 50 / 39351


def sentence_stance(s: str) -> str:
    if PLACEHOLDER.search(s):
        return "placeholder"
    s2 = dc._META.sub(" ", s)
    if not dc._AI_ANY.search(s2) and not dc._USE_VERB.search(s2):
        return "attestation" if ATTEST.search(s2) else "other"
    cl = dc._clauses(s2)
    aff = any(a and dc._USE_VERB.search(c) and dc._AI_ANY.search(c) and not (dc._OVERSIGHT.search(c) and not dc._USE_BYPASS.search(c)) for c, a in cl)
    neg = any((not a) and (dc._USE_VERB.search(c) or dc._AI_ANY.search(c)) for c, a in cl)
    if HYPO.search(s2) and not PAST_USE.search(s2):
        return "hypothetical"
    if aff and neg:
        return "mixed"
    if aff:
        return "affirmative"
    if neg:
        return "denial"
    if ATTEST.search(s2):
        return "attestation"
    return "other"


def stances(text: str) -> list[str]:
    return [sentence_stance(s) for s in dc._SENT.split(text or "") if s.strip()]


def paper_stance(st: list[str]) -> str:
    """affirmative (some use claimed, no denial), denial_only, mixed (claims and denials), placeholder_only,
    no_claim (attestations / other only)."""
    s = set(st)
    a = bool(s & {"affirmative", "mixed"})
    d = bool(s & {"denial", "mixed"})
    if a and d:
        return "use_and_denial"
    if a:
        return "use_only"
    if d:
        return "denial_only"
    if s and s <= {"placeholder", "hypothetical", "other", "attestation"} and "placeholder" in s:
        return "placeholder_only"
    if "hypothetical" in s:
        return "hypothetical_only"
    return "no_claim"


def load(data):
    rows = []
    for f in sorted(glob.glob(os.path.join(data, "*.parquet"))):
        rows.append(pd.read_parquet(f))
    d = pd.concat(rows, ignore_index=True)
    vers = []
    for f in glob.glob(os.path.join(ROOT, "data", "v2", "version", V2_REVISION[:7], "*.parquet")):
        venue, year = os.path.basename(f)[:-8].rsplit("-", 1)
        v = pd.read_parquet(f, columns=["paper_id", "version"]).rename(columns={"paper_id": "doc_id"})
        v["venue"], v["year"] = venue, int(year)
        vers.append(v)
    v = pd.concat(vers).drop_duplicates(["venue", "year", "doc_id"])
    d = d.merge(v, on=["venue", "year", "doc_id"], how="left")
    d["version"] = d.version.fillna("unknown")
    d["cohort"] = d.venue + "-" + d.year.astype(str)
    d["tier_v2"] = tier_v2(d)
    return d


def tier_v2(d: pd.DataFrame) -> pd.Series:
    """V2 sensitivity tier. V1.5 treats a statement that runs to the end of the text as suspect, which
    fits ICLR 2027 (statements in the main text) but not ICLR 2026, where most statements are the last
    appendix section. Such a statement is accepted here if it holds no omission marker (no figure,
    table or equation was swallowed), is at most 3,000 characters and has no bibliography residue."""
    eot = (d.end_reason == "end_of_text") & d.form.isin(["line", "run_in"]) & ~d.bibliography_residue.fillna(False).astype(bool)
    eot &= ~d.text.fillna("").str.contains("⟦", regex=False) & (d.n_chars <= 3000)
    return np.where(d.found.fillna(False).astype(bool) & ((d.tier == "clean") | eot), "clean", np.where(d.found.fillna(False).astype(bool), "suspect", None))


def inventory(d):
    rows = []
    for stratum in ("all", "submission", "published"):
        sel = d if stratum == "all" else d[d.version == stratum]
        for (v, y), g in sel.groupby(["venue", "year"]):
            f = g[g.found == True]  # noqa: E712
            c = f[f.tier_v2 == "clean"]
            nf = g[g.found != True]  # noqa: E712
            r = {"venue": v, "year": y, "stratum": stratum, "papers": len(g), "found": len(f),
                 "found_pct": 100 * len(f) / max(1, len(g)), "clean_v15": int((f.tier == "clean").sum()), "clean": len(c), "clean_pct": 100 * len(c) / max(1, len(g)),
                 "found_after_references_pct": 100 * (~f.in_body.astype(bool)).mean() if len(f) else np.nan,
                 "toc_skipped": int((g.toc_skips > 0).sum()),
                 "words_p25": c.n_words.quantile(.25) if len(c) else np.nan, "words_p50": c.n_words.median() if len(c) else np.nan,
                 "words_p75": c.n_words.quantile(.75) if len(c) else np.nan,
                 "inline_candidate_pct_no_section": 100 * (nf.inline_n > 0).mean() if len(nf) else np.nan}
            for grp in ("drafting", "polish_only", "other_use", "none", "unknown"):
                r[f"clean_{grp}_pct"] = 100 * (c.cls_group == grp).mean() if len(c) else np.nan
            rows.append(r)
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(ROOT, "data", "v2", "disclosures"))
    ap.add_argument("--out", default=os.path.join(ROOT, "results", "v2", "disclosures"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    d = load(a.data)
    inv = inventory(d)
    inv.insert(0, "corpus_revision", V2_REVISION)
    inv.to_csv(os.path.join(a.out, "inventory.csv"), index=False, float_format="%.4g")

    # ICLR 2027 reproduction against V1.5
    v15 = pd.read_csv(os.path.join(ROOT, "results", "disclosures", "extraction_summary.csv"))
    g = d[d.cohort == "iclr-2027"]
    f = g[g.found == True]  # noqa: E712
    mine = {"papers": len(g), "disclosure_found": len(f), "tier_clean": int((f.tier == "clean").sum()),
            "tier_suspect": int((f.tier == "suspect").sum()), "toc_skipped": int((g.toc_skips > 0).sum())}
    rep = v15[v15.measure.isin(mine)].assign(v2=lambda x: x.measure.map(mine))
    rep = pd.concat([rep, pd.DataFrame([{"measure": "toc_skipped", "value": None, "v2": mine["toc_skipped"]}])])
    grp_v15 = {"drafting": 11766, "other_use": 21437, "polish_only": 5358, "unknown": 537, "none": 253}  # docs/ai-disclosures.md §6
    c27 = f[f.tier == "clean"]
    rep = pd.concat([rep, pd.DataFrame([{"measure": f"group_{k}", "value": v, "v2": int((c27.cls_group == k).sum())} for k, v in grp_v15.items()])])
    rep.rename(columns={"value": "v1_5"}).to_csv(os.path.join(a.out, "reproduction_iclr2027.csv"), index=False)

    # Sentence stance and paper stance, clean tier, cohorts with >= 50 clean statements
    clean = d[d.tier_v2 == "clean"].copy()
    big = clean.cohort.value_counts()
    big = big[big >= 50].index.tolist()
    clean = clean[clean.cohort.isin(big)]
    clean["stances"] = clean.text_clean.map(stances)
    clean["paper_stance"] = clean.stances.map(paper_stance)
    pol = []
    for coh, g in clean.groupby("cohort"):
        allst = collections.Counter(s for st in g.stances for s in st)
        tot = sum(allst.values())
        r = {"cohort": coh, "statements": len(g), "sentences": tot}
        for k in ("affirmative", "denial", "mixed", "hypothetical", "placeholder", "attestation", "other"):
            r[f"sent_{k}_pct"] = 100 * allst[k] / max(1, tot)
        for k in ("use_only", "use_and_denial", "denial_only", "placeholder_only", "hypothetical_only", "no_claim"):
            r[f"paper_{k}_pct"] = 100 * (g.paper_stance == k).mean()
        r["paper_any_denial_pct"] = 100 * g.stances.map(lambda s: bool({"denial", "mixed"} & set(s))).mean()
        r["paper_any_attestation_pct"] = 100 * g.stances.map(lambda s: "attestation" in s).mean()
        pol.append(r)
    pd.DataFrame(pol).to_csv(os.path.join(a.out, "polarity.csv"), index=False, float_format="%.4g")
    clean[["cohort", "doc_id", "paper_stance", "cls_group"]].to_parquet(os.path.join(a.data, "..", "disclosure_stance.parquet"), index=False)
    # agreement of the stance rules with the frozen classifier's "none" group (consistency, not validation)
    xt = pd.crosstab([clean.cohort, clean.cls_group], clean.paper_stance)
    xt.to_csv(os.path.join(a.out, "stance_vs_classifier_group.csv"))

    # Attribution, bundles, frames, near-copies per cohort
    tmpl = template_ngrams(4)
    att, bund, frames, boil = [], [], [], []
    toks_by = {}
    for coh in [c for c in COHORTS if c in big]:
        g = clean[clean.cohort == coh].reset_index(drop=True)
        docs = [tokenize(t) for t in g.text]
        n = len(docs)
        sdf = max(5, round(STOCK_RATE * n))
        df6 = collections.Counter()
        for segs in docs:
            df6.update({tuple(s[i:i + 6]) for s in segs for i in range(len(s) - 5)})
        stock6 = {k for k, c in df6.items() if c >= sdf}
        tt = st = at = 0
        per_auth, per_share, shingles = [], [], []
        c4, df4, fr = collections.Counter(), collections.Counter(), collections.defaultdict(collections.Counter)
        uni = collections.Counter()
        for segs in docs:
            ntok = nt = ns = 0
            seen4, sh = set(), set()
            for s in segs:
                ct = cover(s, tmpl, 4)
                cs = cover(s, stock6, 6) & ~ct
                ntok += len(s)
                nt += int(ct.sum())
                ns += int(cs.sum())
                uni.update(tuple(s[i:i + k]) for k in (1, 2, 3) for i in range(len(s) - k + 1))
                for i in range(len(s) - 3):
                    q = tuple(s[i:i + 4])
                    c4[q] += 1
                    seen4.add(q)
                    fr[(q[0], q[1], "*", q[3])][q[2]] += 1
                for j in range(len(s) - 4):
                    sh.add(int.from_bytes(hashlib.blake2b(" ".join(s[j:j + 5]).encode(), digest_size=7).digest(), "little"))
            df4.update(seen4)
            tt += ntok
            st += nt + ns
            at += ntok - nt - ns
            att.append({"cohort": coh, "doc_tokens": ntok, "template": nt, "stock": ns})
            per_auth.append(ntok - nt - ns)
            per_share.append((nt + ns) / max(1, ntok))
            shingles.append(sh)
        toks_by[coh] = uni
        cl = minhash_clusters(shingles)
        cs_ = collections.Counter(cl)
        near = np.array([cs_[c] > 1 for c in cl])
        exact = g.text_clean.str.lower().str.replace(r"\W+", " ", regex=True).duplicated(keep=False).to_numpy()
        per_auth, per_share = np.array(per_auth), np.array(per_share)
        boil.append({"cohort": coh, "statements": n, "stock_df": sdf,
                     "share_ge50pct_template_or_stock": (per_share >= .5).mean(),
                     "share_ge90pct_template_or_stock": (per_share >= .9).mean(),
                     "share_exact_copy": exact.mean(), "share_in_near_copy_cluster": near.mean(),
                     "author_tokens_p25": np.percentile(per_auth, 25), "author_tokens_p50": np.median(per_auth),
                     "author_tokens_p75": np.percentile(per_auth, 75),
                     "share_ge20_author_tokens": (per_auth >= 20).mean(),
                     "boilerplate_share": ((per_share >= .5) | near).mean()})
        for q, c in c4.most_common():
            if df4[q] < 0.02 * n:
                continue
            bund.append({"cohort": coh, "bundle": " ".join(q), "count": c, "docs": df4[q], "range_pct": 100 * df4[q] / n,
                         "per_10k_tokens": 1e4 * c / max(1, tt)})
            if sum(1 for b in bund if b["cohort"] == coh) >= 60:
                break
        top = sorted(fr.items(), key=lambda kv: -sum(kv[1].values()))[:40]
        for k, fills in top:
            tot = sum(fills.values())
            frames.append({"cohort": coh, "frame": " ".join(k), "count": tot, "distinct_fillers": len(fills),
                           "type_token": len(fills) / tot, "top_fillers": "; ".join(f"{w} {100 * c / tot:.0f}%" for w, c in fills.most_common(5))})
    a_ = pd.DataFrame(att).groupby("cohort")[["doc_tokens", "template", "stock"]].sum()
    a_["template_pct"] = 100 * a_.template / a_.doc_tokens
    a_["stock_pct"] = 100 * a_.stock / a_.doc_tokens
    a_["author_pct"] = 100 - a_.template_pct - a_.stock_pct
    a_.reset_index().to_csv(os.path.join(a.out, "attribution.csv"), index=False, float_format="%.4g")
    pd.DataFrame(bund).to_csv(os.path.join(a.out, "bundles.csv"), index=False, float_format="%.4g")
    pd.DataFrame(frames).to_csv(os.path.join(a.out, "frames.csv"), index=False, float_format="%.4g")
    pd.DataFrame(boil).to_csv(os.path.join(a.out, "boilerplate.csv"), index=False, float_format="%.4g")

    # Keyness between cohorts (Monroe et al. log-odds with informative Dirichlet prior)
    kw = []
    pairs = [("iclr-2026", "iclr-2027"), ("colm-2026", "iclr-2027"), ("icml-2026", "iclr-2027"), ("colm-2026", "iclr-2026")]
    for x, y in pairs:
        if x not in toks_by or y not in toks_by:
            continue
        prior = toks_by[x] + toks_by[y]
        lo = log_odds(toks_by[x], toks_by[y], prior).rename(columns={"count_use": "count_x", "count_nonuse": "count_y"})
        lo = lo[(lo.count_x + lo.count_y) >= 20]
        for side, part in (("more_in_" + x, lo.nlargest(40, "z")), ("more_in_" + y, lo.nsmallest(40, "z"))):
            for _, r in part.iterrows():
                kw.append({"pair": f"{x} vs {y}", "side": side, **r.to_dict()})
    pd.DataFrame(kw).to_csv(os.path.join(a.out, "keyness.csv"), index=False, float_format="%.4g")
    print(inv[inv.stratum == "all"].to_string())
    print(pd.DataFrame(pol).round(1).to_string())
    print(pd.DataFrame(boil).round(3).to_string())
    print(a_.round(1).to_string())


if __name__ == "__main__":
    main()
