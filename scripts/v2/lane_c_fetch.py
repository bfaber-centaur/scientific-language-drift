"""Lane C (V2): download parquet files at a pinned revision, independently of mlngrams.load.

Uses huggingface_hub's blob-addressed cache (keyed by revision and blob), then verifies each
file's SHA-256 against the LFS hash recorded by Gate 0 in results/v2/inventory/files.csv.
Prints one line per file. Usage: lane_c_fetch.py --config clean [--only iclr-2026 ...]
"""
import argparse, hashlib, os, sys
import pandas as pd
from huggingface_hub import hf_hub_download

REPO = "woog/open-text-detector-papers"
V2 = "2c0dd192a3d3ba6605ed3f5ed5df145dddbdcb27"
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE = os.environ.get("LANE_C_CACHE", os.path.expanduser("~/.cache/lane_c_hf"))


def expected(revision):
    f = pd.read_csv(os.path.join(ROOT, "results/v2/inventory/files.csv"))
    f = f[(f.revision == revision) & f.path.str.endswith(".parquet")]
    return dict(zip(f.path, f.lfs_sha256))


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def fetch(path, revision=V2, exp=None):
    exp = exp or expected(revision)
    local = hf_hub_download(REPO, path, repo_type="dataset", revision=revision, cache_dir=CACHE)
    ok = os.path.join(CACHE, "verified", revision, path + ".ok")
    if not os.path.exists(ok):
        got = sha256(local)
        if got != exp[path]:
            raise RuntimeError(f"hash mismatch {path}: {got} != {exp[path]}")
        os.makedirs(os.path.dirname(ok), exist_ok=True)
        open(ok, "w").write(got)
    return local


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="clean")
    ap.add_argument("--revision", default=V2)
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    exp = expected(a.revision)
    paths = sorted(p for p in exp if p.startswith(a.config + "/"))
    if a.only:
        paths = [p for p in paths if any(p.endswith(o + ".parquet") for o in a.only)]
    for p in paths:
        print(p, fetch(p, a.revision, exp), flush=True)
