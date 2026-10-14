"""Corpus reconnaissance: coverage, duplicates and version (camera-ready vs submission) mix.

Usage:
    python3 scripts/recon.py                 # ICLR 2013-2027 + other venues
    python3 scripts/recon.py --no-venues     # ICLR only
    python3 scripts/recon.py --no-direct     # skip header check in the direct config

Reads parquet in record batches (text never fully loaded for large files) and never
prints or saves paper text; outputs contain only ids, hashes and aggregates.

Outputs (results/):
    coverage_iclr.csv        per ICLR year: rows, unique ids/hashes, length stats, omission
                             stats, appendix share, page counts, header (version) mix
    coverage_venues.csv      headline columns for the other venues (omissions config)
    coverage_bias_iclr.csv   per ICLR year: paper_id first-character distribution
                             (chi-square vs uniform) and id-order signals
    coverage_strata_iclr.csv per ICLR year and paper_id stratum (first char 0-P, Q-z,
                             non-OpenReview title-slug ids): n, header (version) mix, length
    duplicates_iclr.csv      one row per duplicate pair found (ids only), with its kind
    duplicates_summary.csv   counts by kind and (year_a, year_b)

Header check: running headers ("Under review as a conference paper at ICLR ...",
"Published as a conference paper at ICLR ...") are removed by the clean cleanup
(rule repeated_review_header) and therefore absent from omissions/clean. The check uses
the `direct` config (raw text layer) where its file is cached or --fetch-direct is given.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pandas as pd  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from mlngrams.load import CACHE_DIR, REVISION, fetch, file_name, text_hash  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
ICLR_YEARS = [2013, 2014] + list(range(2017, 2028))
VENUES = {
    "colm": [2024, 2025],
    "corl": [2021, 2022, 2023, 2024],
    "emnlp": [2023],
    "icml": [2025],
    "neurips": [2021, 2022, 2023, 2024, 2025],
    "tmlr": [2022, 2023, 2024, 2025, 2026],
}
OMISSION_TYPES = ["math_display", "math_inline", "figure", "table", "references", "numeric",
                  "duplicate", "hidden"]
REF = "⟦references omitted⟧"
SHORT = 2000
BATCH = 200

_NORM = re.compile(r"[^a-z0-9]+")
_ABSTRACT = re.compile(r"\babstract\b", re.I)
_PUB = re.compile(r"published as a conference paper", re.I)
_REV = re.compile(r"under review as a conference paper", re.I)
_WORKSHOP = re.compile(r"workshop track|as a workshop paper", re.I)
_TEMPLATE = re.compile(r"formatting instructions for iclr", re.I)
_ANON = re.compile(r"anonymous authors?|paper under double-blind review", re.I)


def norm(s: str) -> str:
    return " ".join(_NORM.sub(" ", s.lower()).split())


def h64(s: str) -> int:
    return int.from_bytes(hashlib.blake2b(s.encode(), digest_size=8).digest(), "little", signed=True)


def abstract_start(text: str) -> int:
    m = _ABSTRACT.search(text[:6000])
    return m.end() if m else 0


def near_keys(text: str):
    """Keys for near-duplicate detection on the abstract onward (skips title/author block,
    which differs between anonymous and camera-ready versions)."""
    body = text[abstract_start(text):]
    body = re.sub(r"⟦[^⟧]{0,80}⟧", " ", body[:4000])
    n = norm(body)
    abs_key = h64(n[:300]) if len(n) >= 200 else None
    words = n[:2000].split()
    sh = {h64(" ".join(words[i:i + 8])) for i in range(max(0, len(words) - 7))}
    return abs_key, sh


def q(xs, p):
    xs = sorted(x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x)))
    if not xs:
        return float("nan")
    k = (len(xs) - 1) * p
    lo, hi = math.floor(k), math.ceil(k)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def scan_omissions(venue: str, year: int, keep_keys: bool):
    """One pass over the omissions file; returns per-paper records (no text)."""
    pf = pq.ParquetFile(fetch("omissions", venue, year))
    cols = ["paper_id", "pdf_sha256", "text", "text_sha256", "omission_counts_json",
            "chars_clean", "chars_after"]
    recs = []
    for b in pf.iter_batches(batch_size=BATCH, columns=cols):
        for r in b.to_pylist():
            t = r["text"] or ""
            n = len(t)
            first = t.find(REF)
            last = t.rfind(REF)
            oc = json.loads(r["omission_counts_json"] or "{}")
            rec = {
                "venue": venue, "year": year, "paper_id": r["paper_id"],
                "pdf_sha256": r["pdf_sha256"], "text_sha256": r["text_sha256"],
                "chars": n,
                "ratio": (r["chars_after"] / r["chars_clean"]) if r["chars_clean"] else float("nan"),
                "has_ref": first >= 0,
                "app_first": (1 - first / n) if first >= 0 else float("nan"),
                "app_last": (1 - (last + len(REF)) / n) if last >= 0 else float("nan"),
                "pages": t.count("\x0c") + 1 if n else 0,
                "pub_om": bool(_PUB.search(t)), "rev_om": bool(_REV.search(t)),
                "norm_hash": text_hash(t) if n else None,
                # unmodified ICLR LaTeX template submitted as the paper (placeholder PDFs)
                "template": bool(_TEMPLATE.search(t[:300])),
            }
            lines = [ln.strip() for ln in t.split("\n") if ln.strip() and ln.strip() != "\x0c"]
            nl = max(1, len(lines))
            # artifact indicators: bare-number lines (line-number columns, page numbers, table
            # cells), and 1-2 character lines (math/figure fragments leaking as tokens)
            rec["digit_line_share"] = sum(ln.isdigit() for ln in lines) / nl
            rec["tiny_line_share"] = sum(len(ln) <= 2 for ln in lines) / nl
            rec["upper_line_share"] = sum(ln.isupper() and len(ln) > 3 for ln in lines) / nl
            for k in OMISSION_TYPES:
                rec["om_" + k] = oc.get(k, 0)
            extra = set(oc) - set(OMISSION_TYPES)
            if extra:
                rec["om_other"] = sum(oc[k] for k in extra)
            if keep_keys and n >= SHORT:
                rec["abs_key"], rec["_sh"] = near_keys(t)
            recs.append(rec)
    return recs


def scan_direct(venue: str, year: int, allow_fetch: bool):
    """Header/version signals from the raw text layer. Returns {pdf_sha256: dict} or None."""
    path = os.path.join(CACHE_DIR, "direct", file_name(venue, year))
    if not os.path.exists(path):
        if not allow_fetch:
            return None
        path = fetch("direct", venue, year)
    pf = pq.ParquetFile(path)
    out = {}
    for b in pf.iter_batches(batch_size=BATCH, columns=["pdf_sha256", "text", "method", "pages"]):
        for r in b.to_pylist():
            t = r["text"] or ""
            head = t[:3000]
            out[r["pdf_sha256"]] = {
                "pub": bool(_PUB.search(t)), "rev": bool(_REV.search(t)),
                "workshop": bool(_WORKSHOP.search(head)), "anon": bool(_ANON.search(head)),
                "ocr": "ocr" in (r["method"] or "").lower(), "method": r["method"],
                "dpages": r["pages"],
            }
    return out


def summarize(recs, direct=None) -> dict:
    df = pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in recs])
    s = {
        "venue": df.venue.iloc[0], "year": int(df.year.iloc[0]),
        "rows": len(df),
        "unique_paper_id": df.paper_id.nunique(),
        "unique_pdf_sha256": df.pdf_sha256.nunique(),
        "unique_text_sha256": df.text_sha256.nunique(),
        "empty": int((df.chars == 0).sum()),
        "short_lt2000": int((df.chars < SHORT).sum()),
        "chars_median": q(df.chars, .5), "chars_p5": q(df.chars, .05), "chars_p95": q(df.chars, .95),
        "ratio_after_clean_median": q(df.ratio, .5),
        "share_with_refs_marker": df.has_ref.mean(),
        "appendix_share_median": q(df.app_first, .5),
        "share_appendix_gt20pct": (df.app_last > 0.2).mean(),
        "pages_median": q(df.pages, .5),
        "digit_line_share_median": q(df.digit_line_share, .5),
        "share_digit_lines_gt10pct": (df.digit_line_share > 0.10).mean(),
        "tiny_line_share_median": q(df.tiny_line_share, .5),
        "upper_line_share_median": q(df.upper_line_share, .5),
        "template_placeholder": int(df.template.sum()),
        "header_in_omissions_text": int((df.pub_om | df.rev_om).sum()),
    }
    for c in df.columns:
        if c.startswith("om_"):
            s["mean_" + c[3:]] = df[c].fillna(0).mean()
    if direct is not None:
        d = pd.DataFrame([direct.get(p, {}) for p in df.pdf_sha256])
        s["direct_matched"] = int(d["pub"].notna().sum())
        pub, rev = d["pub"].fillna(False).astype(bool), d["rev"].fillna(False).astype(bool)
        s["share_published_header"] = pub.mean()
        s["share_under_review_header"] = rev.mean()
        s["share_both_headers"] = (pub & rev).mean()
        s["share_neither_header"] = (~pub & ~rev).mean()
        s["share_workshop_header"] = d["workshop"].fillna(False).astype(bool).mean()
        s["share_anonymous_block"] = d["anon"].fillna(False).astype(bool).mean()
        s["share_ocr_method"] = d["ocr"].fillna(False).astype(bool).mean()
        s["direct_pages_median"] = q(d["dpages"].dropna().tolist(), .5)
        s["methods"] = ";".join(f"{k}:{v}" for k, v in Counter(d["method"].dropna()).most_common())
    return s


def id_bias(recs) -> dict:
    """paper_id first-character distribution vs uniform; a truncated alphabetical crawl
    would concentrate ids at low prefixes."""
    ids = [r["paper_id"] for r in recs]
    c = Counter(i[0] for i in ids)
    n, k = len(ids), len(c)
    alphabet = sorted(set().union(*[set(i[0]) for i in ids]))
    exp = n / max(1, len(alphabet))
    chi2 = sum((c[a] - exp) ** 2 / exp for a in alphabet)
    lens = Counter(len(i) for i in ids)
    srt = sorted(ids)
    return {
        "year": recs[0]["year"], "n": n, "distinct_first_chars": k,
        "chi2_first_char_vs_uniform": round(chi2, 1), "df": len(alphabet) - 1,
        "id_lengths": ";".join(f"{a}:{b}" for a, b in sorted(lens.items())),
        "min_id": srt[0], "median_id": srt[n // 2], "max_id": srt[-1],
        "share_first_char_digit": sum(v for a, v in c.items() if a.isdigit()) / n,
        "share_first_char_upper": sum(v for a, v in c.items() if a.isupper()) / n,
        "share_first_char_lower": sum(v for a, v in c.items() if a.islower()) / n,
        "first_char_counts": ";".join(f"{a}:{c[a]}" for a in alphabet),
    }


def id_stratum(pid: str) -> str:
    """OpenReview forum ids are random; coverage gaps in 2025/2026 follow ASCII id order."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{9,12}", pid):
        return "nonstandard_id"
    c = pid[0]
    if c.isdigit() or "A" <= c <= "P":
        return "0-P"
    return "Q-z_other"


def strata(recs, direct) -> list[dict]:
    out = defaultdict(lambda: Counter())
    for r in recs:
        d = direct.get(r["pdf_sha256"], {}) if direct else {}
        c = out[id_stratum(r["paper_id"])]
        c["n"] += 1
        c["pub"] += bool(d.get("pub"))
        c["rev"] += bool(d.get("rev"))
        c["chars"] += r["chars"]
        c["pages"] += r["pages"]
    return [{"year": recs[0]["year"], "stratum": k, "n": c["n"],
             "share_published_header": c["pub"] / c["n"] if direct else float("nan"),
             "share_under_review_header": c["rev"] / c["n"] if direct else float("nan"),
             "mean_chars": c["chars"] / c["n"], "mean_pages": c["pages"] / c["n"]}
            for k, c in sorted(out.items())]


def duplicates(all_recs):
    rows = []
    by = defaultdict(list)
    for r in all_recs:
        by[("text_sha256", r["text_sha256"])].append(r)
        if r["norm_hash"]:
            by[("norm_text_hash", r["norm_hash"])].append(r)
        by[("paper_id", r["paper_id"])].append(r)
        if r.get("abs_key") is not None:
            by[("abstract_prefix300", r["abs_key"])].append(r)
    seen = set()
    for (kind, _), grp in by.items():
        if len(grp) < 2:
            continue
        for i in range(len(grp)):
            for j in range(i + 1, len(grp)):
                a, b = grp[i], grp[j]
                if (a["year"], a["pdf_sha256"]) > (b["year"], b["pdf_sha256"]):
                    a, b = b, a
                key = (kind, a["pdf_sha256"], b["pdf_sha256"])
                if key in seen or a["pdf_sha256"] == b["pdf_sha256"] and kind != "paper_id":
                    continue
                seen.add(key)
                rows.append({"kind": kind, "year_a": a["year"], "paper_id_a": a["paper_id"],
                             "pdf_a": a["pdf_sha256"][:16], "year_b": b["year"],
                             "paper_id_b": b["paper_id"], "pdf_b": b["pdf_sha256"][:16],
                             "jaccard8": float("nan"),
                             "same_paper_id": a["paper_id"] == b["paper_id"]})
    # shingle Jaccard on the first 2000 normalized chars from the abstract onward
    keyed = [r for r in all_recs if r.get("_sh")]
    inv = defaultdict(list)
    for idx, r in enumerate(keyed):
        for s in r["_sh"]:
            inv[s].append(idx)
    pair_counts = Counter()
    for s, lst in inv.items():
        if 2 <= len(lst) <= 50:  # skip boilerplate shingles shared by many papers
            for i in range(len(lst)):
                for j in range(i + 1, len(lst)):
                    pair_counts[(lst[i], lst[j])] += 1
    for (i, j), c in pair_counts.items():
        a, b = keyed[i], keyed[j]
        if c < 5:
            continue
        jac = len(a["_sh"] & b["_sh"]) / len(a["_sh"] | b["_sh"])
        if jac < 0.3:
            continue
        if (a["year"], a["pdf_sha256"]) > (b["year"], b["pdf_sha256"]):
            a, b = b, a
        rows.append({"kind": "shingle8_j>=0.3", "year_a": a["year"], "paper_id_a": a["paper_id"],
                     "pdf_a": a["pdf_sha256"][:16], "year_b": b["year"],
                     "paper_id_b": b["paper_id"], "pdf_b": b["pdf_sha256"][:16],
                     "jaccard8": round(jac, 3), "same_paper_id": a["paper_id"] == b["paper_id"]})
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-venues", action="store_true")
    ap.add_argument("--no-direct", action="store_true")
    ap.add_argument("--fetch-direct", action="store_true", help="download missing ICLR direct files")
    ap.add_argument("--years", type=int, nargs="*", default=ICLR_YEARS)
    ap.add_argument("--out", default=os.path.join(ROOT, "results"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    all_recs, rows, bias, strat = [], [], [], []
    for y in a.years:
        recs = scan_omissions("iclr", y, keep_keys=True)
        direct = None if a.no_direct else scan_direct("iclr", y, a.fetch_direct)
        s = summarize(recs, direct)
        rows.append(s)
        bias.append(id_bias(recs))
        strat.extend(strata(recs, direct))
        all_recs.extend(recs)
        print(f"iclr {y}: {s['rows']} rows", file=sys.stderr, flush=True)
    cov = pd.DataFrame(rows)
    cov.insert(0, "revision", REVISION[:12])
    cov.to_csv(os.path.join(a.out, "coverage_iclr.csv"), index=False, float_format="%.4f")
    pd.DataFrame(bias).to_csv(os.path.join(a.out, "coverage_bias_iclr.csv"), index=False)
    pd.DataFrame(strat).to_csv(os.path.join(a.out, "coverage_strata_iclr.csv"), index=False,
                               float_format="%.4f")

    dup = duplicates(all_recs)
    dup.to_csv(os.path.join(a.out, "duplicates_iclr.csv"), index=False)
    if len(dup):
        summ = (dup.assign(cross_year=dup.year_a != dup.year_b)
                .groupby(["kind", "year_a", "year_b"]).size().rename("pairs").reset_index())
        summ.to_csv(os.path.join(a.out, "duplicates_summary.csv"), index=False)

    if not a.no_venues:
        vrows = []
        for v, ys in VENUES.items():
            for y in ys:
                s = summarize(scan_omissions(v, y, keep_keys=False))
                vrows.append(s)
                print(f"{v} {y}: {s['rows']} rows", file=sys.stderr, flush=True)
        vc = pd.DataFrame(vrows)
        vc.insert(0, "revision", REVISION[:12])
        vc.to_csv(os.path.join(a.out, "coverage_venues.csv"), index=False, float_format="%.4f")


if __name__ == "__main__":
    main()
