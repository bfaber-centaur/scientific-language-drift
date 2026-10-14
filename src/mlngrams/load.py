"""Streaming loader for woog/open-text-detector-papers at a pinned revision.

Shared data contract: every analysis consumes `iter_docs()`, which yields
dicts with exactly these keys:
    doc_id : str   stable identifier from the dataset
    venue  : str   e.g. "ICLR"
    year   : int   conference year as labelled in the dataset
    text   : str   extracted full text
Column names in the source are mapped in COLUMN_MAP. They are UNCONFIRMED
until the repository has been inspected (scripts/recon.py); update them and
docs/corpus.md together.

Files are fetched with huggingface_hub into a local cache outside the repo and
read in record batches with pyarrow, so memory stays bounded by batch size.
"""
from __future__ import annotations

import hashlib
import os
from typing import Iterator

REPO_ID = "woog/open-text-detector-papers"
REVISION = os.environ.get("MLNGRAMS_REVISION", "UNPINNED")  # set to a commit sha in docs/corpus.md
CACHE_DIR = os.environ.get("MLNGRAMS_CACHE", os.path.expanduser("~/.cache/mlngrams"))

COLUMN_MAP = {  # source column -> contract key (UNCONFIRMED)
    "id": "doc_id",
    "venue": "venue",
    "year": "year",
    "text": "text",
}


def list_data_files(revision: str = REVISION, config: str | None = None) -> list[str]:
    from huggingface_hub import HfApi

    files = HfApi().list_repo_files(REPO_ID, repo_type="dataset", revision=revision)
    files = [f for f in files if f.endswith(".parquet")]
    if config:
        files = [f for f in files if f.split("/")[0] == config or f"/{config}/" in f or f.startswith(f"{config}-")]
    return sorted(files)


def fetch(path: str, revision: str = REVISION) -> str:
    from huggingface_hub import hf_hub_download

    return hf_hub_download(REPO_ID, path, repo_type="dataset", revision=revision, cache_dir=CACHE_DIR)


def iter_docs(
    files: list[str],
    revision: str = REVISION,
    venues: set[str] | None = None,
    years: set[int] | None = None,
    batch_size: int = 256,
) -> Iterator[dict]:
    import pyarrow.parquet as pq

    for f in files:
        pf = pq.ParquetFile(fetch(f, revision))
        cols = [c for c in COLUMN_MAP if c in pf.schema_arrow.names]
        for batch in pf.iter_batches(batch_size=batch_size, columns=cols):
            for row in batch.to_pylist():
                doc = {COLUMN_MAP[k]: v for k, v in row.items()}
                if venues and doc.get("venue") not in venues:
                    continue
                if years and doc.get("year") is not None and int(doc["year"]) not in years:
                    continue
                yield doc


def text_hash(text: str) -> str:
    """Hash of whitespace-collapsed lowercase text, for exact-duplicate detection."""
    return hashlib.sha1(" ".join((text or "").lower().split()).encode()).hexdigest()
