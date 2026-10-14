"""Cheap cross-checks for the 2024–2027 style shifts seen in the ICLR tables.

Usage: python3 scripts/check_style_shift.py [--sample 800]

For a random sample of papers per (venue, year, config), computes on the main body
(text before the first reference-list marker; for `direct`, before a line
"References"), with the same tokenizer as the main pipeline:
    stop_share     share of tokens that are NLTK stopwords
    of_the_pm      "of the" per million bigram positions
    mean_tok_len   mean token length (letters)
    prev_<w>       share of papers containing the word/phrase <w>
Writes results/style_shift_checks.csv. Two questions it answers:
  1. Is the ICLR 2026/2027 function-word drop present in the raw `direct` text layer
     too (i.e. not produced by the dataset's cleanup)?
  2. Do other venues show the same shifts in the same years?
Only aggregates are written; the sample is drawn with a fixed seed.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from mlngrams.count import ngrams_of  # noqa: E402
from mlngrams.filters import STOPWORDS  # noqa: E402
from mlngrams.load import fetch, main_body  # noqa: E402
from mlngrams.sections import strip_statements  # noqa: E402
from mlngrams.tokenize import tokenize  # noqa: E402

PHRASES = ["delve", "underscores", "showcasing", "pivotal", "we propose", "in this paper",
           "crucial role", "across diverse", "notably", "furthermore"]
TARGETS = (
    [("iclr", y, "omissions") for y in (2017, 2019, 2021, 2023, 2024, 2025, 2026, 2027)]
    + [("iclr", y, "direct") for y in (2023, 2024, 2026, 2027)]
    + [("neurips", y, "omissions") for y in (2021, 2022, 2023, 2024, 2025)]
    + [("tmlr", y, "omissions") for y in (2022, 2023, 2024, 2025, 2026)]
    + [("colm", y, "omissions") for y in (2024, 2025)]
    + [("icml", 2025, "omissions"), ("emnlp", 2023, "omissions")]
)
_DIRECT_REFS = re.compile(r"^\s*references\s*$", re.I | re.M)


def body(text: str, config: str) -> str:
    if config == "direct":
        m = _DIRECT_REFS.search(text)
        text = text[: m.start()] if m else text
    else:
        text = main_body(text)
    return strip_statements(text)[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=800)
    a = ap.parse_args()
    rows = []
    for venue, year, config in TARGETS:
        pf = pq.ParquetFile(fetch(config, venue, year))
        n = pf.metadata.num_rows
        rng = np.random.default_rng(year)
        pick = set(rng.choice(n, size=min(a.sample, n), replace=False).tolist())
        i, stats = 0, []
        for b in pf.iter_batches(batch_size=500, columns=["text"]):
            for r in b.to_pylist():
                if i in pick and r["text"] and len(r["text"]) >= 2000:
                    t = body(r["text"], config)
                    segs = tokenize(t)
                    toks = [w for s in segs for w in s]
                    if len(toks) < 500:
                        i += 1
                        continue
                    bis = list(ngrams_of(segs, 2))
                    low = " ".join(" ".join(s) for s in segs)
                    st = {
                        "stop_share": sum(w in STOPWORDS for w in toks) / len(toks),
                        "of_the_pm": 1e6 * bis.count("of the") / max(1, len(bis)),
                        "mean_tok_len": np.mean([len(w) for w in toks if w != "<num>"]),
                    }
                    for p in PHRASES:
                        st["prev_" + p.replace(" ", "_")] = f" {p} " in f" {low} "
                    stats.append(st)
                i += 1
        df = pd.DataFrame(stats)
        row = {"venue": venue, "year": year, "config": config, "papers": len(df)}
        row.update(df.mean().round(4).to_dict())
        rows.append(row)
        print(row, flush=True)
    out = os.path.join(os.path.dirname(__file__), "..", "results", "style_shift_checks.csv")
    pd.DataFrame(rows).to_csv(out, index=False)


if __name__ == "__main__":
    main()
