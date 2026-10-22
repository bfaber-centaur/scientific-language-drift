"""V3: per-paper review metadata for ICLR 2017-2026 from Paper Copilot's paperlists.

Source: github.com/papercopilot/paperlists, commit PAPERLISTS_SHA (iclr/iclr<year>.json; 2025-26 are
Git LFS objects). The OpenReview API is behind a browser challenge from this environment, so this is a
third-party scrape of OpenReview, not OpenReview itself. Per-file sha256 is recorded.

Writes data/v3/review_meta.parquet (git-ignored: it carries names and affiliations) and
results/v3/review_meta/{source_files.csv, coverage.csv}. Derived per-paper columns only:
    doc_id, year, status, decision (accept/reject/withdraw/desk_reject/other), accepted (0/1, withdrawn
    and desk-rejected excluded -> NaN), n_authors, n_reviews, rating_mean, rating_z (within-year z of
    rating_mean), rating_pct (within-year percentile), confidence_mean, gs_citation (NaN when -1),
    cite_pct (within-year percentile among papers with a count), primary_area, industry (any author
    affiliation domain or name on a fixed list; known 2021-2024 only, affiliations are empty
    in the 2017-2020 and absent in the 2025-2026 files), max_author_papers (most submissions that year by
    any one author on the paper, by OpenReview profile id when present else by name), first_author,
    last_author (names, used only as fixed effects), max_author_papers_name and last_author_id (for the
    2017-2024 check of how much name collisions matter: 2025-26 have names only, no profile ids).

Usage: python3 scripts/v3/review_meta.py --src ~/ext/paperlists
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import Counter

import numpy as np
import pandas as pd

PAPERLISTS_SHA = "9fcfd1234879a8e5630b5116dde411ec143dd763"
ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
OUT = os.path.join(ROOT, "results", "v3", "review_meta")
YEARS = range(2017, 2027)
ACCEPT = {"poster", "oral", "spotlight", "talk", "top-25%", "top-5%", "iclr 2026 conditionalposter",
          "iclr 2026 conditionaloral"}
INDUSTRY = ("google.com", "deepmind.com", "microsoft.com", "meta.com", "fb.com", "facebook.com", "nvidia.com",
            "amazon.com", "apple.com", "openai.com", "ibm.com", "alibaba-inc.com", "baidu.com", "tencent.com",
            "huawei.com", "bytedance.com", "samsung.com", "intel.com", "salesforce.com", "adobe.com",
            "sony.com", "qualcomm.com", "anthropic.com", "uber.com", "twitter.com", "naver.com", "kakao.com",
            "sensetime.com", "antgroup.com", "jd.com", "kuaishou.com", "xiaomi.com", "netflix.com")

INDUSTRY_NAMES = re.compile(r"\b(?:google|deepmind|microsoft|facebook|meta ai|meta platforms|nvidia|amazon|apple inc|"
                            r"openai|ibm|alibaba|baidu|tencent|huawei|bytedance|samsung|intel corp|intel labs|"
                            r"salesforce|adobe|sony|qualcomm|anthropic|uber|twitter|naver|kakao|sensetime)\b")


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def nums(s):
    out = []
    for x in str(s or "").split(";"):
        try:
            out.append(float(x))
        except ValueError:
            pass
    return out


def decision(status):
    s = (status or "").strip().lower()
    if s in ACCEPT:
        return "accept"
    if s == "reject":
        return "reject"
    if s == "withdraw":
        return "withdraw"
    if s == "desk reject":
        return "desk_reject"
    return "other"  # workshop invitations (2017-18), 'Active'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.expanduser("~/ext/paperlists"))
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(os.path.join(ROOT, "data", "v3"), exist_ok=True)
    files, rows = [], []
    for y in YEARS:
        p = os.path.join(a.src, f"iclr{y}.json")
        files.append({"year": y, "path": f"iclr/iclr{y}.json", "sha256": sha256(p), "bytes": os.path.getsize(p)})
        recs = json.load(open(p))
        recs = [r for r in recs if r.get("track", "main") == "main" and r.get("id")]
        # Author ids: OpenReview profile ids when present, else names.
        def ids(r):
            a_ids = [x for x in str(r.get("authorids") or "").split(";")]
            names = [x.strip() for x in str(r.get("author") or "").split(";") if x.strip()]
            if len(a_ids) == len(names) and all(a_ids):
                return a_ids
            return names
        load = Counter(i for r in recs for i in set(ids(r)))
        load_name = Counter(i.strip() for r in recs for i in set(str(r.get("author") or "").split(";")) if i.strip())
        for r in recs:
            authors = [x.strip() for x in str(r.get("author") or "").split(";") if x.strip()]
            rat = nums(r.get("rating") or r.get("recommendation"))
            conf = nums(r.get("confidence"))
            gs = pd.to_numeric(r.get("gs_citation"), errors="coerce")
            dom = str(r.get("aff_domain") or "").lower().split(";")
            aff = str(r.get("aff") or "").lower()
            rows.append({
                "doc_id": r["id"], "year": y, "status": r.get("status"), "decision": decision(r.get("status")),
                "n_authors": len(authors) or np.nan, "n_reviews": len(rat),
                "rating_mean": np.mean(rat) if rat else np.nan,
                "rating_sd": np.std(rat) if len(rat) > 1 else np.nan,
                "confidence_mean": np.mean(conf) if conf else np.nan,
                "gs_citation": gs if gs is not None and gs >= 0 else np.nan,
                "primary_area": r.get("primary_area") or None,
                "industry": (any(d.strip().endswith(INDUSTRY) for d in dom if d.strip())
                             or bool(INDUSTRY_NAMES.search(aff))
                             if (str(r.get("aff_domain") or "").strip("; ") or aff.strip("; ")) else np.nan),
                "max_author_papers": max((load[i] for i in set(ids(r))), default=np.nan),
                "max_author_papers_name": max((load_name[i] for i in set(authors)), default=np.nan),
                "last_author_id": ids(r)[-1] if r.get("authorids") and ids(r) and ids(r)[-1].startswith("~") else None,
                "first_author": authors[0] if authors else None,
                "last_author": authors[-1] if authors else None,
            })
    df = pd.DataFrame(rows).drop_duplicates("doc_id")
    df["accepted"] = np.where(df.decision == "accept", 1.0, np.where(df.decision == "reject", 0.0, np.nan))
    g = df.groupby("year")
    df["rating_z"] = (df.rating_mean - g.rating_mean.transform("mean")) / g.rating_mean.transform("std")
    df["rating_pct"] = g.rating_mean.rank(pct=True)
    df["cite_pct"] = g.gs_citation.rank(pct=True)
    df.to_parquet(os.path.join(ROOT, "data", "v3", "review_meta.parquet"), index=False)
    pd.DataFrame(files).assign(repo="papercopilot/paperlists", commit=PAPERLISTS_SHA).to_csv(
        os.path.join(OUT, "source_files.csv"), index=False)
    cov = df.groupby("year").agg(papers=("doc_id", "size"), with_rating=("rating_mean", "count"),
                                 with_citations=("gs_citation", "count"), industry_known=("industry", "count"),
                                 accepted=("decision", lambda s: (s == "accept").sum()),
                                 rejected=("decision", lambda s: (s == "reject").sum()),
                                 withdrawn=("decision", lambda s: (s == "withdraw").sum()),
                                 desk_rejected=("decision", lambda s: (s == "desk_reject").sum()),
                                 other=("decision", lambda s: (s == "other").sum()),
                                 mean_authors=("n_authors", "mean"), median_authors=("n_authors", "median"))
    cov.to_csv(os.path.join(OUT, "coverage.csv"))
    print(cov.to_string())


if __name__ == "__main__":
    main()
