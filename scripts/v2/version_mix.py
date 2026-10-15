"""Gate 0/1: per-record document version (camera-ready vs submission) from the raw first page.

Streams the `direct` config row group by row group over HTTP (only `pdf_sha256` and `text`
columns), looks at the first page (text before the first form feed, whitespace collapsed),
and records which venue header or footer it carries. Paper text is never written out; the
output holds ids, hashes and a matched-marker label only.

Usage:
    python3 scripts/v2/version_mix.py --revision 2c0dd192a3d3ba6605ed3f5ed5df145dddbdcb27 \
        --out data/v2/version [--files icml-2026 colm-2026 ...]

Output: <out>/<rev7>/<venue>-<year>.parquet with columns
    pdf_sha256, paper_id, version (published | submission | preprint | unknown), marker
and results/v2/inventory/version_mix.csv (counts per venue-year, revision).

Rules (first match wins, submission markers checked first because NeurIPS and CoRL
submissions carry the conference name too):
  submission: "submitted to ...", "under review ...", "anonymous author(s)",
              "paper under double-blind review", "anonymous <venue> submission"
  published:  "published as a conference paper at", "published in transactions on machine
              learning research", "proceedings of the <n>th international conference on
              machine learning", "<n>th conference on neural information processing systems
              (neurips <yyyy>)", "conference on robot learning (corl <yyyy>)",
              "proceedings of the <yyyy> conference on empirical methods"
  submission: also >= 30 bare three-digit margin line numbers on page 1 (ACL review format)
  preprint:   "preprint" header with neither of the above
For ICLR this matches V1's header rule (docs/corpus.md) except that V1 searched the whole
direct text; first-page only is stricter about in-text mentions.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import pyarrow.parquet as pq
from huggingface_hub import HfApi, HfFileSystem

REPO_ID = "woog/open-text-detector-papers"
ROOT = os.path.join(os.path.dirname(__file__), "..", "..")

SUBMISSION = [
    ("submitted_to", re.compile(r"\bsubmitted to (the )?\d+\s*\w*\s*(annual )?conference on (neural|robot)", re.I)),
    ("under_review", re.compile(r"\bunder review (as|by|at|for)\b", re.I)),
    ("double_blind", re.compile(r"paper under double-blind review", re.I)),
    ("anonymous_submission", re.compile(r"anonymous (emnlp|acl|naacl|corl|colm|icml|neurips) submission", re.I)),
    ("anonymous_authors", re.compile(r"\banonymous authors?\b|\banonymous author\(s\)", re.I)),
]
PUBLISHED = [
    ("published_conference", re.compile(r"published as a conference paper at (iclr|colm)", re.I)),
    ("published_tmlr", re.compile(r"published in transactions on machine learning research", re.I)),
    ("icml_proceedings", re.compile(r"proceedings of the .{0,14}international conference on machine\s*learning", re.I)),
    ("neurips_camera_ready", re.compile(r"conference on neural information processing systems \(neurips \d{4}\)", re.I)),
    ("corl_camera_ready", re.compile(r"conference on robot learning \(corl \d{4}\)", re.I)),
    ("emnlp_proceedings", re.compile(r"proceedings of the \d{4} conference on empirical methods", re.I)),
]
PREPRINT = re.compile(r"\bpreprint\b", re.I)


LINE_NO = re.compile(r"^\s*\d{3}\s*$", re.M)


def classify(first_page: str) -> tuple[str, str]:
    t = " ".join(first_page.split())
    for name, rx in SUBMISSION:
        if rx.search(t):
            return "submission", name
    # ACL-style review copies carry three-digit line numbers in the margin (000, 001, ...).
    if len(LINE_NO.findall(first_page)) >= 30:
        return "submission", "acl_line_numbers"
    for name, rx in PUBLISHED:
        if rx.search(t):
            return "published", name
    if PREPRINT.search(t[:600]):
        return "preprint", "preprint"
    return "unknown", ""


def scan(fs: HfFileSystem, sha: str, path: str, out: str) -> pd.DataFrame:
    dst = os.path.join(out, sha[:7], os.path.basename(path))
    if os.path.exists(dst):
        return pd.read_parquet(dst)
    rows = []
    with fs.open(f"datasets/{REPO_ID}@{sha}/{path}", block_size=8 << 20) as fh:
        pf = pq.ParquetFile(fh)
        for i in range(pf.num_row_groups):
            rg = pf.read_row_group(i, columns=["pdf_sha256", "paper_id", "text"])
            for h, pid, text in zip(*(rg.column(c).to_pylist() for c in ("pdf_sha256", "paper_id", "text"))):
                v, m = classify((text or "").split("\f", 1)[0])
                rows.append({"pdf_sha256": h, "paper_id": pid, "version": v, "marker": m})
    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    df.to_parquet(dst + ".part")
    os.replace(dst + ".part", dst)
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--revision", required=True)
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "v2", "version"))
    ap.add_argument("--files", nargs="*", help="venue-year stems; default: every direct file")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    sha = HfApi().dataset_info(REPO_ID, revision=a.revision).sha
    fs = HfFileSystem()
    paths = sorted(p for p in HfApi().list_repo_files(REPO_ID, repo_type="dataset", revision=sha)
                   if p.startswith("direct/") and p.endswith(".parquet"))
    if a.files:
        paths = [p for p in paths if os.path.basename(p)[:-8] in a.files]
    # Biggest first so the long ones overlap.
    sizes = {s.rfilename: s.size for s in HfApi().dataset_info(REPO_ID, revision=sha, files_metadata=True).siblings}
    paths.sort(key=lambda p: -sizes[p])
    summary = []

    def run(p):
        df = scan(fs, sha, p, a.out)
        print(p, len(df), df.version.value_counts().to_dict(), flush=True)
        stem = os.path.basename(p)[:-8]
        venue, year = stem.rsplit("-", 1)
        c = df.version.value_counts()
        return {"revision": sha, "venue": venue, "year": int(year), "rows": len(df),
                **{k: int(c.get(k, 0)) for k in ("published", "submission", "preprint", "unknown")}}

    with ThreadPoolExecutor(a.workers) as ex:
        summary = list(ex.map(run, paths))
    s = pd.DataFrame(summary).sort_values(["venue", "year"])
    for k in ("published", "submission", "preprint", "unknown"):
        s[k + "_pct"] = (100 * s[k] / s["rows"]).round(1)
    os.makedirs(os.path.join(ROOT, "results", "v2", "inventory"), exist_ok=True)
    dst = os.path.join(ROOT, "results", "v2", "inventory", "version_mix.csv")
    if a.files and os.path.exists(dst):
        old = pd.read_csv(dst)
        old = old[~old.set_index(["revision", "venue", "year"]).index.isin(s.set_index(["revision", "venue", "year"]).index)]
        s = pd.concat([old, s]).sort_values(["venue", "year"])
    s.to_csv(dst, index=False)
    print("wrote", dst)


if __name__ == "__main__":
    sys.exit(main())
