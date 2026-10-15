"""Lane E: independent download + record hashing of woog/open-text-detector-papers at two revisions.

Deliberately does not import mlngrams. Files are listed with the Hub API at each revision, downloaded
with plain HTTP into a content-addressed store (<store>/<lfs_sha256>.parquet), and verified by
recomputing SHA-256 of the bytes. For every row we recompute SHA-256 of the UTF-8 text ourselves, so
that "unchanged record" claims do not rest on the dataset's own text_sha256 column.

Output (no paper text): <out>/records-<rev7>-<config>.parquet with
    file, row, paper_id, conference, year, pdf_sha256, text_sha256 (column), my_sha256, n_chars, n_ff

Usage: python3 -I scripts/v2/review/fetch_hash.py --store DIR --out DIR [--keep omissions direct]
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import pyarrow.parquet as pq
from huggingface_hub import HfApi

REPO = "woog/open-text-detector-papers"
V1 = "cb5553e0c192c31c562a2822668c7f4ebbb9437a"
V2 = "2c0dd192a3d3ba6605ed3f5ed5df145dddbdcb27"


def listing(rev: str) -> pd.DataFrame:
    info = HfApi().dataset_info(REPO, revision=rev, files_metadata=True)
    assert info.sha == rev, (info.sha, rev)
    rows = []
    for s in info.siblings:
        if s.rfilename.endswith(".parquet"):
            rows.append({"rev": rev, "path": s.rfilename, "size": s.size, "lfs": s.lfs.sha256 if s.lfs else None,
                         "blob": s.blob_id})
    return pd.DataFrame(rows)


def get(store: str, rev: str, path: str, lfs: str, tries: int = 3) -> str:
    for k in range(tries):
        try:
            return _get(store, rev, path, lfs)
        except Exception as e:  # a short or corrupted transfer is caught by the hash check
            print(f"retry {k + 1}: {e}", flush=True)
    return _get(store, rev, path, lfs)


def _get(store: str, rev: str, path: str, lfs: str) -> str:
    dst = os.path.join(store, lfs + ".parquet")
    if os.path.exists(dst):
        return dst
    url = f"https://huggingface.co/datasets/{REPO}/resolve/{rev}/{path}"
    tmp = dst + f".{os.getpid()}.part"
    h = hashlib.sha256()
    with urllib.request.urlopen(url) as r, open(tmp, "wb") as f:
        for chunk in iter(lambda: r.read(1 << 22), b""):
            h.update(chunk)
            f.write(chunk)
    if h.hexdigest() != lfs:
        os.remove(tmp)
        raise RuntimeError(f"{path}@{rev[:7]}: bytes sha {h.hexdigest()} != listed LFS {lfs}")
    os.replace(tmp, dst)
    return dst


def hash_file(fp: str, path: str) -> pd.DataFrame:
    pf = pq.ParquetFile(fp)
    out, i = [], 0
    cols = ["paper_id", "conference", "year", "pdf_sha256", "text_sha256", "text"]
    for b in pf.iter_batches(batch_size=512, columns=cols):
        d = b.to_pydict()
        for k in range(len(d["text"])):
            t = d["text"][k] or ""
            out.append({"file": path, "row": i, "paper_id": d["paper_id"][k], "conference": d["conference"][k],
                        "year": d["year"][k], "pdf_sha256": d["pdf_sha256"][k], "text_sha256": d["text_sha256"][k],
                        "my_sha256": hashlib.sha256(t.encode("utf-8")).hexdigest(), "n_chars": len(t),
                        "n_ff": t.count("\f")})
            i += 1
    return pd.DataFrame(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--keep", nargs="*", default=["omissions", "direct"], help="V2 configs to keep on disk")
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    os.makedirs(a.store, exist_ok=True)
    os.makedirs(a.out, exist_ok=True)
    L = pd.concat([listing(V1), listing(V2)])
    L.to_csv(os.path.join(a.out, "listing.csv"), index=False)
    v1 = L[L.rev == V1].set_index("path")
    jobs = []
    for _, r in L.iterrows():
        if r.rev == V1 and r.path in set(L[L.rev == V2].path) and \
                L[(L.rev == V2) & (L.path == r.path)].lfs.iloc[0] == r.lfs:
            continue  # byte-identical to the V2 file: hashing V2 covers it
        jobs.append(r)
    print(len(jobs), "files to hash", flush=True)

    def run(r):
        cfg = r.path.split("/")[0]
        dst = os.path.join(a.out, "parts", r.rev[:7], r.path.replace("/", "__"))
        if os.path.exists(dst):
            return
        fp = get(a.store, r.rev, r.path, r.lfs)
        df = hash_file(fp, r.path)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        df.to_parquet(dst)
        keep = r.rev == V2 and cfg in a.keep
        if not keep:
            os.remove(fp)
        print(r.rev[:7], r.path, len(df), "kept" if keep else "deleted", flush=True)

    with ThreadPoolExecutor(a.workers) as ex:
        list(ex.map(run, jobs))
    for rev in (V1, V2):
        for cfg in ("omissions", "clean", "direct"):
            d = os.path.join(a.out, "parts", rev[:7])
            fs = [os.path.join(d, f) for f in sorted(os.listdir(d)) if f.startswith(cfg + "__")]
            pd.concat([pd.read_parquet(f) for f in fs]).to_parquet(
                os.path.join(a.out, f"records-{rev[:7]}-{cfg}.parquet"))
    print("done", flush=True)


if __name__ == "__main__":
    sys.exit(main())
