"""Gate 0/1: collect per-record metadata (no paper text) for two dataset revisions.

Reads only non-text columns via HTTP range requests (HfFileSystem + parquet column
projection), so no full parquet is downloaded. Byte-identical files (same git blob id in
both revisions) are read once and shared.

Usage:
    python3 scripts/v2/collect_metadata.py --out data/v2/meta \
        [--old cb5553e0c192c31c562a2822668c7f4ebbb9437a] [--new <sha or main>]

Outputs (git-ignored, under --out):
    files_<rev7>.json             repo file listing with size, blob id, LFS sha256
    <rev7>/<config>/<venue>-<year>.parquet   per-record metadata
Also writes results/v2/inventory/files.csv (one row per file per revision).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import pandas as pd  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402
from huggingface_hub import HfApi, HfFileSystem  # noqa: E402

from mlngrams.load import REPO_ID  # noqa: E402

V1_REVISION = "cb5553e0c192c31c562a2822668c7f4ebbb9437a"
ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
COLS = {
    "omissions": ["paper_id", "openreview_id", "title", "conference", "year", "pdf_sha256", "text_sha256",
                  "source_clean_text_sha256", "omission_counts_json", "chars_clean", "chars_after"],
    "clean": ["paper_id", "conference", "year", "pdf_sha256", "text_sha256", "source_text_sha256",
              "cleanup_version", "flag_count"],
    "direct": ["paper_id", "conference", "year", "pdf_sha256", "text_sha256", "method", "pages"],
}


def listing(api: HfApi, rev: str) -> dict:
    info = api.dataset_info(REPO_ID, revision=rev, files_metadata=True)
    return {
        "sha": info.sha,
        "last_modified": str(info.last_modified),
        "files": [{"path": s.rfilename, "size": s.size, "blob": s.blob_id,
                   "lfs_sha256": s.lfs.sha256 if s.lfs else None} for s in info.siblings],
    }


def read_meta(fs: HfFileSystem, sha: str, path: str) -> pd.DataFrame:
    cfg = path.split("/", 1)[0]
    with fs.open(f"datasets/{REPO_ID}@{sha}/{path}") as fh:
        return pq.ParquetFile(fh).read(columns=COLS[cfg]).to_pandas()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", default=V1_REVISION)
    ap.add_argument("--new", default="main")
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "v2", "meta"))
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    api, fs = HfApi(), HfFileSystem()
    revs = [listing(api, a.old), listing(api, a.new)]
    os.makedirs(a.out, exist_ok=True)
    jobs, done_blob, rows = [], {}, []
    for r in revs:
        json.dump(r, open(os.path.join(a.out, f"files_{r['sha'][:7]}.json"), "w"), indent=1)
        for f in r["files"]:
            rows.append({"revision": r["sha"], **f})
            if f["path"].endswith(".parquet"):
                jobs.append((r["sha"], f))
    print("revisions:", [r["sha"] for r in revs], flush=True)

    def run(job):
        sha, f = job
        dst = os.path.join(a.out, sha[:7], f["path"])
        if os.path.exists(dst):
            return f["path"], len(pd.read_parquet(dst, columns=["paper_id"]))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        df = read_meta(fs, sha, f["path"])
        df.to_parquet(dst + ".part")
        os.replace(dst + ".part", dst)
        return f["path"], len(df)

    # Read each distinct blob once; byte-identical files are copied (hardlinked) afterwards.
    first = {}
    for sha, f in jobs:
        first.setdefault(f["blob"], (sha, f))
    with ThreadPoolExecutor(a.workers) as ex:
        for path, n in ex.map(run, list(first.values())):
            print(f"{path}: {n}", flush=True)
    nrows = {}
    for sha, f in jobs:
        src_sha, src = first[f["blob"]]
        src_p = os.path.join(a.out, src_sha[:7], src["path"])
        dst = os.path.join(a.out, sha[:7], f["path"])
        if not os.path.exists(dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            os.link(src_p, dst)
        nrows[(sha, f["path"])] = pq.ParquetFile(dst).metadata.num_rows
    for r in rows:
        r["rows"] = nrows.get((r["revision"], r["path"]))
    out = os.path.join(ROOT, "results", "v2", "inventory")
    os.makedirs(out, exist_ok=True)
    pd.DataFrame(rows).to_csv(os.path.join(out, "files.csv"), index=False)
    print("wrote", os.path.join(out, "files.csv"))


if __name__ == "__main__":
    main()
