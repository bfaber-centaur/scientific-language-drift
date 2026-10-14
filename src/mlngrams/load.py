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
CACHE_DIR/<config>/ (outside the repo) and read in record batches, so memory
stays bounded by batch size.
"""
from __future__ import annotations

import hashlib
import os
import urllib.request
from typing import Iterator

REPO_ID = "woog/open-text-detector-papers"
# Pinned 2026-10-14. The dataset is actively growing; change only together with docs/corpus.md.
REVISION = os.environ.get("MLNGRAMS_REVISION", "cb5553e0c192c31c562a2822668c7f4ebbb9437a")
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


def fetch(config: str, venue: str, year: int, revision: str = REVISION) -> str:
    """Return a local path to <config>/<venue>-<year>.parquet, downloading it if absent."""
    rel = f"{config}/{file_name(venue, year)}"
    path = os.path.join(CACHE_DIR, rel)
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        url = f"https://huggingface.co/datasets/{REPO_ID}/resolve/{revision}/{rel}"
        tmp = path + ".part"
        urllib.request.urlretrieve(url, tmp)
        os.replace(tmp, path)
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
