"""Lane A spot checks that need the text again (docs/appendix-growth.md, "Is the split right?").

Usage: python3 scripts/appendix_checks.py results/appendix/body_tail_residue.csv

Trailing bibliography residue in the main body: reference entries the omissions config left
*before* its first ⟦references omitted⟧ marker are counted as main body. For a seeded sample of
papers per ICLR year, measures the trailing block of bibliography-like lines at the end of the
body (mirror image of appendix_scan.leading_refres) and its share of body characters.
"""
from __future__ import annotations

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from appendix_scan import REF, _REF_LINE  # noqa: E402
from mlngrams.load import fetch  # noqa: E402

SEED, N = 20261015, 500


def trailing_refres(body: str) -> int:
    """Characters of the trailing block of bibliography-like lines (> 20 chars) at the body's end;
    the block stops at three consecutive non-bibliography lines."""
    lines = body.split("\n")
    o, start, miss = len(body), len(body), 0
    for ln in reversed(lines):
        o -= len(ln) + 1
        s = ln.strip()
        if len(s) > 20:
            if _REF_LINE.search(s):
                start, miss = max(o, 0), 0
            else:
                miss += 1
                if miss >= 3:
                    break
    return len(body) - start


def main():
    out = sys.argv[1]
    rows = []
    for year in (2017, 2019, 2021, 2023, 2025, 2026, 2027):
        t = pq.read_table(fetch("omissions", "iclr", year), columns=["paper_id", "text"])
        ids = t.column("paper_id").to_pylist()
        pick = random.Random(SEED + year).sample(range(len(ids)), min(N, len(ids)))
        res, body_chars, hit = 0, 0, 0
        for k in pick:
            x = t.column("text")[k].as_py() or ""
            i = x.find(REF)
            if i < 0:
                continue
            body = x[:i]
            r = trailing_refres(body)
            res += r
            body_chars += len(body)
            hit += r > 0
        rows.append({"year": year, "n": len(pick), "share_papers_with_residue": hit / len(pick),
                     "residue_share_of_body_chars": res / max(1, body_chars)})
        print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(out, index=False, float_format="%.4g")


if __name__ == "__main__":
    main()
