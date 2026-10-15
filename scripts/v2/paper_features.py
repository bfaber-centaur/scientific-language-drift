"""Lane B (V2 replication): per-paper counts of a fixed target list, every venue, main body.

Usage:
    python3 scripts/v2/paper_features.py [--revision 2c0dd19...] [--out data/v2/replication/features]
                                         [--files icml-2026 ...] [--workers 4]

Same text pipeline as the V1 counts (scripts/count_ngrams.py --body-only): omissions config,
template statement sections cut (sections v2), text before the first ⟦references omitted⟧,
tokenizer v1.3, n-grams never cross segment boundaries. For every record it writes, without text:
    doc_id, pdf_sha256, text_sha256, tokens, stop_tokens, pos1, pos2, pos3, letters, words_alpha
    c:<target>   occurrences of each target n-gram (TARGETS below, exact n-gram match as in V1 tables)
One parquet per venue-year in OUT/<rev7>/. These per-paper rows let Lane B compute prevalence and
per-million rates per (venue, year, version, membership), paper-level bootstrap intervals, and the
V1 cross-venue checks (results/style_shift_checks.csv) on complete V2 cohorts. Not committed (data/).
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pandas as pd  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from mlngrams.filters import STOPWORDS  # noqa: E402
from mlngrams.load import V2_REVISION, fetch, main_body  # noqa: E402
from mlngrams.sections import strip_statements  # noqa: E402
from mlngrams.tokenize import tokenize  # noqa: E402

FUNCTION = ["of", "in", "we", "and", "the", "to", "a", "is", "for", "that", "on", "with", "by", "this",
            "our", "are", "be", "as", "which", "it"]
RHETORICAL = ["delve", "delves", "delving", "underscores", "underscore", "intricate", "pivotal", "showcasing",
              "showcase", "realm", "notably", "furthermore", "additionally", "moreover", "leverage",
              "leverages", "leveraging", "seamlessly", "robust", "meticulous", "meticulously", "commendable",
              "garnered", "noteworthy", "tapestry", "nuanced", "landscape", "crucial", "comprehensive",
              "innovative", "remarkable", "unprecedented", "paramount", "multifaceted", "holistic",
              "streamline", "harness", "elucidate", "foster", "versatile", "insightful", "invaluable"]
TOPICAL = ["transformer", "neural network", "neural networks", "deep learning", "convolutional neural",
           "generative adversarial", "reinforcement learning", "graph neural", "language models",
           "large language", "diffusion models"]
PHRASES = ["of the", "in the", "can be", "we propose", "in this paper", "a novel", "test whether",
           "held fixed", "results support", "percentage points", "across diverse", "crucial role",
           "plays a crucial", "comprehensive analysis", "extensive experiments", "novel approach",
           "delve into", "shed light", "to the best", "it is worth", "state-of-the-art",
           "experimental setup", "we show", "we find", "in order to", "such as", "as well as",
           "in addition", "we also", "this work", "our method", "our approach", "we introduce",
           "we present", "is a", "there is", "it is"]
TARGETS = list(dict.fromkeys(FUNCTION + RHETORICAL + TOPICAL + PHRASES))
BY_N = {n: {t for t in TARGETS if t.count(" ") + 1 == n} for n in (1, 2, 3)}


def features(text: str) -> dict:
    t = main_body(strip_statements(text)[0])
    segs = tokenize(t)
    row = {"tokens": 0, "stop_tokens": 0, "letters": 0, "words_alpha": 0, "pos1": 0, "pos2": 0, "pos3": 0}
    c = Counter()
    for s in segs:
        L = len(s)
        row["tokens"] += L
        row["pos1"] += L
        row["pos2"] += max(0, L - 1)
        row["pos3"] += max(0, L - 2)
        for i, w in enumerate(s):
            if w in STOPWORDS:
                row["stop_tokens"] += 1
            if w.isalpha():
                row["words_alpha"] += 1
                row["letters"] += len(w)
            if w in BY_N[1]:
                c[w] += 1
            if i + 1 < L:
                b = w + " " + s[i + 1]
                if b in BY_N[2]:
                    c[b] += 1
                if i + 2 < L:
                    tg = b + " " + s[i + 2]
                    if tg in BY_N[3]:
                        c[tg] += 1
    for k in TARGETS:
        row["c:" + k] = c.get(k, 0)
    return row


def scan(args):
    venue, year, revision, out = args
    dst = os.path.join(out, revision[:7], f"{venue}-{year}.parquet")
    if os.path.exists(dst):
        return dst
    pf = pq.ParquetFile(fetch("omissions", venue, year, revision))
    rows = []
    for b in pf.iter_batches(batch_size=128, columns=["paper_id", "pdf_sha256", "text_sha256", "text"]):
        for r in b.to_pylist():
            f = features(r["text"] or "")
            f.update({"doc_id": r["paper_id"], "pdf_sha256": r["pdf_sha256"], "text_sha256": r["text_sha256"]})
            rows.append(f)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    df = pd.DataFrame(rows)
    df.insert(0, "year", year)
    df.insert(0, "venue", venue)
    df.to_parquet(dst + ".part", index=False)
    os.replace(dst + ".part", dst)
    print(venue, year, len(df), flush=True)
    return dst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--revision", default=V2_REVISION)
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "v2", "replication", "features"))
    ap.add_argument("--files", nargs="*")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    files = pd.read_csv(os.path.join(ROOT, "results", "v2", "inventory", "files.csv"))
    stems = sorted({p.split("/")[1][:-8] for p in files[files.revision == a.revision].path
                    if p.startswith("omissions/") and p.endswith(".parquet")})
    if a.files:
        stems = [s for s in stems if s in a.files]
    jobs = [(s.rsplit("-", 1)[0], int(s.rsplit("-", 1)[1]), a.revision, a.out) for s in stems]
    jobs.sort(key=lambda j: (j[0] == "iclr" and j[1] == 2027), reverse=True)  # longest first
    with ProcessPoolExecutor(a.workers) as ex:
        list(ex.map(scan, jobs))


if __name__ == "__main__":
    main()
