"""V4: per-abstract features for every arXiv paper first posted 2018-01 .. 2026-09.

Source: the arXiv metadata snapshot mirrored on Hugging Face, librarian-bots/arxiv-metadata-snapshot at
revision SNAPSHOT_REV (weekly mirror of Cornell's arxiv-metadata-oai-snapshot; synced 2026-10-19).
The abstract is the metadata abstract of the latest version (typed by the submitter, not extracted from
a PDF); the month is the v1 date.

Per paper: field group of the primary (first listed) category, whether any ML category is cross-listed,
author count, version count, tokens, counts of a few function words, the V3 metadiscourse lexicons
(imported unchanged from scripts/v3/style_features.py), nominalisations and multi-label topic tags
(title + abstract: t_*, title only: tt_*).
Writes data/v4/arxiv_features.parquet (git-ignored, ~2M rows) and results/v4/arxiv/source.csv.

Usage: python3 scripts/v4/arxiv_features.py --src ~/.cache/arxiv --jobs 4
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import importlib.util
import os
import re
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import duckdb
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, HERE)
from mlngrams.tokenize import TOKENIZER_VERSION, tokenize  # noqa: E402
from topics import TOPICS, tag  # noqa: E402

_spec = importlib.util.spec_from_file_location("style_v3", os.path.join(ROOT, "scripts", "v3", "style_features.py"))
SV3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(SV3)

SNAPSHOT = "librarian-bots/arxiv-metadata-snapshot"
SNAPSHOT_REV = "d83cc98f9ceba7b7d21cde0245233d48b63a7dbe"
FIRST, LAST = "2018-01", "2026-09"
ML = {"cs.LG", "cs.CL", "cs.CV", "cs.AI", "stat.ML"}
WORDS = ("of", "in", "the", "we", "our", "and", "to", "a", "is", "this", "that", "for", "with", "novel",
         "propose", "delve", "notably", "across", "while", "leverage", "leveraging", "enabling", "thereby")
MATH = re.compile(r"\$\$.*?\$\$|\$[^$]{0,400}\$", re.S)
PHYS = ("astro-ph", "cond-mat", "gr-qc", "hep-", "nucl-", "physics.", "quant-ph", "nlin.", "math-ph")


def group(primary: str) -> str:
    if primary in ML:
        return "ML"
    if primary.startswith("cs."):
        return "CS other"
    if primary.startswith(PHYS):
        return "physics"
    if primary.startswith("math."):
        return "math"
    if primary.startswith("q-bio."):
        return "q-bio"
    if primary.startswith(("q-fin.", "econ.")):
        return "econ/q-fin"
    if primary.startswith("eess."):
        return "eess"
    if primary.startswith("stat."):
        return "stat other"
    return "other"


def features(abstract: str) -> dict:
    text = MATH.sub(" . ", abstract.replace("\n", " "))
    segs = tokenize(text)
    toks = [t for s in segs for t in s if t != "<num>"]
    n = len(toks)
    cnt = Counter(toks)
    joined = " " + " ".join(" ".join(s) for s in segs) + " "

    def c(words, mw=()):
        return sum(cnt[w] for w in words) + sum(joined.count(" " + p + " ") for p in mw)

    f = {"tokens": n, "letters": sum(len(t) for t in toks),
         "hedge": c(SV3.HEDGE, SV3.HEDGE_MW), "booster": c(SV3.BOOSTER, SV3.BOOSTER_MW),
         "attitude": c(SV3.ATTITUDE), "self_mention": c(SV3.SELF), "engagement": c(SV3.ENGAGE, SV3.ENGAGE_MW),
         "hype": c(SV3.HYPE), "llm_marker": c(SV3.LLM),
         "nominal": sum(v for w, v in cnt.items() if SV3.NOMINAL.match(w) and w not in SV3.NOT_NOMINAL),
         "the_x_of": len(re.findall(r" the [a-z][a-z'-]* of ", joined))}
    for w in WORDS:
        f["w_" + w] = cnt[w]
    return f


def load(path: str) -> pd.DataFrame:
    df = duckdb.connect().sql(f"""
        select id, categories, title, abstract, len(authors_parsed) as n_authors, len(versions) as n_versions,
               strftime(strptime(versions[1].created, '%a, %d %b %Y %H:%M:%S %Z'), '%Y-%m') as month
        from read_parquet('{path}')
    """).df()
    df = df[(df.month >= FIRST) & (df.month <= LAST)]
    cats = df.categories.str.split()
    df["primary"] = cats.str[0]
    df["group"] = df.primary.map(group)
    df["ml_cross"] = cats.map(lambda c: any(x in ML for x in c))
    return df.drop(columns=["categories"])


def work(path: str) -> pd.DataFrame:
    """One snapshot shard at a time keeps memory at about 1 GB per worker."""
    chunk = load(path)
    rows = []
    for r in chunk.itertuples(index=False):
        f = features(r.abstract or "")
        f.update(tag((r.title or "") + " . " + (r.abstract or "")))
        f.update(tag(r.title or "", "tt_"))
        rows.append(f)
    return pd.concat([chunk.drop(columns=["abstract", "title"]).reset_index(drop=True), pd.DataFrame(rows)], axis=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.expanduser("~/.cache/arxiv"))
    ap.add_argument("--jobs", type=int, default=4)
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(a.src, "*.parquet")))
    os.makedirs(os.path.join(ROOT, "data", "v4"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "results", "v4", "arxiv"), exist_ok=True)
    src = []
    for p in files:
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            for b in iter(lambda: fh.read(1 << 20), b""):
                h.update(b)
        src.append({"file": os.path.basename(p), "bytes": os.path.getsize(p), "sha256": h.hexdigest()})
    pd.DataFrame(src).assign(dataset=SNAPSHOT, revision=SNAPSHOT_REV).to_csv(
        os.path.join(ROOT, "results", "v4", "arxiv", "source.csv"), index=False)
    with ProcessPoolExecutor(a.jobs) as ex:
        out = pd.concat(list(ex.map(work, files)), ignore_index=True).drop_duplicates("id")
    out.attrs = {}
    out.to_parquet(os.path.join(ROOT, "data", "v4", "arxiv_features.parquet"), index=False)
    print("tokenizer", TOKENIZER_VERSION, "topics", len(TOPICS), "rows", len(out))


if __name__ == "__main__":
    main()
