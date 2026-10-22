"""Streaming loader for woog/open-text-detector-papers at a pinned revision.

Shared data contract: every analysis consumes `iter_docs()`, which yields
dicts with exactly these keys:
    doc_id     : str   OpenReview forum id (`paper_id`)
    venue      : str   lowercase conference, e.g. "iclr"
    year       : int   conference year as labelled in the dataset
    pdf_sha256 : str   row key; joins across configs
    text_sha256: str   hash of the text, for exact-duplicate detection
    text       : str   extracted text of the chosen config
Schema confirmed against revision REVISION (see docs/corpus.md).

Configs: "omissions" (primary for lexical analysis: tables, equations, inline
math, figure text and reference lists replaced by ⟦...⟧ markers), "clean"
(sensitivity check), "direct" (raw text layer, not used).

Files are one parquet per `<venue>-<year>`; they are downloaded once into
CACHE_DIR/<revision>/<config>/ (outside the repo) and read in record batches, so memory
stays bounded by batch size.

Cache safety (V2, 2026-10-15): the V1 loader cached at CACHE_DIR/<config>/<file> with no
revision in the key, so a file cached for one revision was silently returned for another
(MRE: results/independent_function_words/cache_revision_mre.json). The cache is now keyed
by the full 40-character commit sha, and every download is checked against the LFS
SHA-256 that the Hub API reports for that path at that revision. A branch name such as
"main" is resolved to its commit sha before use. Files in the old unkeyed layout are
never read.
"""
from __future__ import annotations

import hashlib
import os
import re
import urllib.request
from typing import Iterator

REPO_ID = "woog/open-text-detector-papers"
# Pinned 2026-10-14. The dataset is actively growing; change only together with docs/corpus.md.
V1_REVISION = "cb5553e0c192c31c562a2822668c7f4ebbb9437a"
# V2 pin (2026-10-15, Gate 0, docs/v2-corpus-inventory.md). V1 analyses keep V1_REVISION.
V2_REVISION = "2c0dd192a3d3ba6605ed3f5ed5df145dddbdcb27"
# V3 pin (2026-10-22, docs/v3-corpus-inventory.md): V2 plus 165 added records (ICLR 2026, TMLR 2023/2026).
V3_REVISION = "b9bfffba0c81927866a747d48c6c259fb42edd76"
REVISION = os.environ.get("MLNGRAMS_REVISION", V1_REVISION)
CACHE_DIR = os.environ.get("MLNGRAMS_CACHE", os.path.expanduser("~/.cache/mlngrams"))

COLUMN_MAP = {  # source column -> contract key (confirmed at REVISION)
    "paper_id": "doc_id",
    "conference": "venue",
    "year": "year",
    "pdf_sha256": "pdf_sha256",
    "text_sha256": "text_sha256",
    "text": "text",
}


def file_name(venue: str, year: int) -> str:
    return f"{venue.lower()}-{year}.parquet"


_SHA = re.compile(r"^[0-9a-f]{40}$")


class CacheIntegrityError(RuntimeError):
    """A downloaded or cached file does not match the hash the Hub reports for its revision."""


def resolve_revision(revision: str) -> str:
    """Full commit sha for `revision`; branch names and tags are resolved through the Hub API."""
    if _SHA.match(revision):
        return revision
    from huggingface_hub import HfApi

    return HfApi().dataset_info(REPO_ID, revision=revision).sha


def cache_path(config: str, venue: str, year: int, revision: str) -> str:
    return os.path.join(CACHE_DIR, revision, config, file_name(venue, year))


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def expected_sha256(rel: str, revision: str) -> str:
    """LFS sha256 of `rel` at `revision`, from the Hub API (authoritative, independent of the download)."""
    from huggingface_hub import HfApi

    (info,) = HfApi().get_paths_info(REPO_ID, [rel], revision=revision, repo_type="dataset")
    if info.lfs is None:
        raise CacheIntegrityError(f"{rel}@{revision}: not an LFS file; no hash to verify against")
    return info.lfs.sha256


def _download(url: str, dst: str) -> None:
    urllib.request.urlretrieve(url, dst)


def fetch(config: str, venue: str, year: int, revision: str = REVISION) -> str:
    """Return a local path to <config>/<venue>-<year>.parquet at `revision`, downloading it if absent.

    The cache key includes the commit sha; a fresh download is verified against the LFS sha256
    the Hub API reports for that path at that revision, and recorded in a `.sha256` sidecar, which later reads re-check cheaply
    (size) and, with MLNGRAMS_VERIFY=1, fully (hash).
    """
    revision = resolve_revision(revision)
    rel = f"{config}/{file_name(venue, year)}"
    path = cache_path(config, venue, year, revision)
    side = path + ".sha256"
    if os.path.exists(path) and os.path.exists(side):
        want, size = open(side).read().split()
        if os.path.getsize(path) != int(size):
            raise CacheIntegrityError(f"{path}: size {os.path.getsize(path)} != recorded {size}")
        if os.environ.get("MLNGRAMS_VERIFY") == "1" and sha256_file(path) != want:
            raise CacheIntegrityError(f"{path}: sha256 differs from recorded {want}")
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    url = f"https://huggingface.co/datasets/{REPO_ID}/resolve/{revision}/{rel}"
    tmp = path + ".part"
    want = expected_sha256(rel, revision)
    _download(url, tmp)
    got = sha256_file(tmp)
    if got != want:
        os.remove(tmp)
        raise CacheIntegrityError(f"{url}: downloaded sha256 {got} != Hub {want}")
    os.replace(tmp, path)
    with open(side, "w") as f:
        f.write(f"{got} {os.path.getsize(path)}\n")
    return path


def iter_docs(
    config: str,
    venue: str,
    year: int,
    revision: str = REVISION,
    batch_size: int = 256,
    with_text: bool = True,
) -> Iterator[dict]:
    import pyarrow.parquet as pq

    pf = pq.ParquetFile(fetch(config, venue, year, revision))
    cols = [c for c in COLUMN_MAP if with_text or c != "text"]
    for batch in pf.iter_batches(batch_size=batch_size, columns=cols):
        for row in batch.to_pylist():
            doc = {COLUMN_MAP[k]: v for k, v in row.items()}
            doc["year"] = int(doc["year"])
            yield doc


def main_body(text: str, marker: str = "⟦references omitted⟧") -> str:
    """Text before the first reference-list marker (drops appendices). Omissions config only."""
    i = text.find(marker)
    return text if i < 0 else text[:i]


def text_hash(text: str) -> str:
    """Hash of whitespace-collapsed lowercase text, for near-exact duplicate detection."""
    return hashlib.sha1(" ".join((text or "").lower().split()).encode()).hexdigest()
