"""Gate 1: coarse document structure of V2 records (main body vs post-reference text).

Streams the `omissions` text column row group by row group over HTTP, never writes text.
Per record: pages (form feeds + 1), body_chars (before the first references marker, i.e.
mlngrams.load.main_body), post_chars (after the last references marker), ref_pages (number of
reference markers), has_refs. Character counts of omissions text, so tables, equations and
figure text are already excluded as markers. This is deliberately cruder than
scripts/appendix_scan.py (statements and checklists are not cut): it is a provenance check
of whether added records differ structurally from V1 records, not the appendix analysis.

Usage:
    python3 scripts/v2/structure_scan.py [--files iclr-2026 ...] [--workers 4]
Output: data/v2/structure/2c0dd19/<venue>-<year>.parquet (git-ignored).
"""
from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import pyarrow.parquet as pq
from huggingface_hub import HfApi, HfFileSystem

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from mlngrams.load import REPO_ID, V2_REVISION  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
REF = "⟦references omitted⟧"


def profile(text: str) -> dict:
    text = text or ""
    i, j = text.find(REF), text.rfind(REF)
    return {"pages": text.count("\f") + 1, "chars": len(text),
            "body_chars": len(text) if i < 0 else i,
            "post_chars": 0 if j < 0 else len(text) - j - len(REF),
            "ref_pages": text.count(REF), "has_refs": i >= 0}


def scan(fs, path, out):
    dst = os.path.join(out, os.path.basename(path))
    if os.path.exists(dst):
        return path, len(pd.read_parquet(dst))
    rows = []
    with fs.open(f"datasets/{REPO_ID}@{V2_REVISION}/{path}", block_size=8 << 20) as fh:
        pf = pq.ParquetFile(fh)
        for k in range(pf.num_row_groups):
            rg = pf.read_row_group(k, columns=["paper_id", "pdf_sha256", "text"])
            for pid, h, t in zip(*(rg.column(c).to_pylist() for c in ("paper_id", "pdf_sha256", "text"))):
                rows.append({"paper_id": pid, "pdf_sha256": h, **profile(t)})
    df = pd.DataFrame(rows)
    df.to_parquet(dst + ".part")
    os.replace(dst + ".part", dst)
    return path, len(df)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", nargs="*")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    out = os.path.join(ROOT, "data", "v2", "structure", V2_REVISION[:7])
    os.makedirs(out, exist_ok=True)
    info = HfApi().dataset_info(REPO_ID, revision=V2_REVISION, files_metadata=True)
    paths = [s for s in info.siblings if s.rfilename.startswith("omissions/") and s.rfilename.endswith(".parquet")]
    if a.files:
        paths = [s for s in paths if os.path.basename(s.rfilename)[:-8] in a.files]
    paths = [s.rfilename for s in sorted(paths, key=lambda s: -s.size)]
    fs = HfFileSystem()
    with ThreadPoolExecutor(a.workers) as ex:
        for p, n in ex.map(lambda p: scan(fs, p, out), paths):
            print(p, n, flush=True)


if __name__ == "__main__":
    main()
