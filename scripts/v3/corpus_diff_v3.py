"""V3 Gate 0: what changed in woog/open-text-detector-papers between the V2 pin and the V3 pin.

Lists every file at both revisions (Hub API, with LFS sha256), and for each changed parquet reads
the non-text columns at both revisions (HfFileSystem + column projection, no text download) to
check that old records are untouched and to list the added ones.

Usage:
    python3 scripts/v3/corpus_diff_v3.py [--old <V2 sha>] [--new <sha or main>]
Writes results/v3/inventory/{files_changed.csv, added_records.csv, summary.json}.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import pandas as pd  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402
from huggingface_hub import HfApi, HfFileSystem  # noqa: E402

from mlngrams.load import REPO_ID, V2_REVISION  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "..", "results", "v3", "inventory")
COLS = ["paper_id", "conference", "year", "pdf_sha256", "text_sha256"]


def listing(api, rev):
    info = api.dataset_info(REPO_ID, revision=rev, files_metadata=True)
    return info.sha, {s.rfilename: (s.size, s.blob_id, s.lfs.sha256 if s.lfs else None) for s in info.siblings}


def meta(fs, sha, path):
    with fs.open(f"datasets/{REPO_ID}@{sha}/{path}") as fh:
        return pq.ParquetFile(fh).read(columns=COLS).to_pandas()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", default=V2_REVISION)
    ap.add_argument("--new", default="main")
    a = ap.parse_args()
    api, fs = HfApi(), HfFileSystem()
    old, fo = listing(api, a.old)
    new, fn = listing(api, a.new)
    commits = []
    for c in api.list_repo_commits(REPO_ID, repo_type="dataset", revision=new):
        if c.commit_id == old:
            break
        commits.append({"commit": c.commit_id, "created_at": str(c.created_at), "title": c.title})
    rows, added, summary = [], [], {"old": old, "new": new, "commits": commits}
    for p in sorted(set(fo) | set(fn)):
        if fo.get(p) == fn.get(p):
            continue
        r = {"path": p, "old_size": (fo.get(p) or [None])[0], "new_size": (fn.get(p) or [None])[0],
             "old_lfs": (fo.get(p) or [None] * 3)[2], "new_lfs": (fn.get(p) or [None] * 3)[2]}
        if p.endswith(".parquet") and p in fo and p in fn:
            mo, mn = meta(fs, old, p), meta(fs, new, p)
            j = mo.merge(mn, on="pdf_sha256", how="left", suffixes=("_o", "_n"), indicator=True)
            r["old_rows"], r["new_rows"] = len(mo), len(mn)
            r["old_missing_in_new"] = int((j["_merge"] != "both").sum())
            both = j[j["_merge"] == "both"]
            r["text_hash_changed"] = int((both["text_sha256_o"] != both["text_sha256_n"]).sum())
            r["paper_id_changed"] = int((both["paper_id_o"] != both["paper_id_n"]).sum())
            new_rows = mn[~mn["pdf_sha256"].isin(mo["pdf_sha256"])]
            r["added_rows"] = len(new_rows)
            r["added_paper_id_already_present"] = int(new_rows["paper_id"].isin(mo["paper_id"]).sum())
            if p.startswith("omissions/"):
                added.append(new_rows.assign(file=p))
        rows.append(r)
    os.makedirs(OUT, exist_ok=True)
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "files_changed.csv"), index=False)
    if added:
        pd.concat(added).to_csv(os.path.join(OUT, "added_records.csv"), index=False)
    summary["files_changed"] = rows
    json.dump(summary, open(os.path.join(OUT, "summary.json"), "w"), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
