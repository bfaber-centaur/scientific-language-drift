"""Lane D (v1.5 review): how much post-reference text is a paper checklist rather than appendix?

Usage: python3 scripts/review_v15_checklist.py

For each venue-year file (omissions config) finds checklist material after the first
references marker in two forms: a checklist heading line ("Paper Checklist",
"Checklist"; NeurIPS 2021-22 style) and answer lines ("Answer: [Yes]", "Justification:";
NeurIPS 2024+ style). Prints the share of papers with each and the checklist share of
post-reference characters. Writes results/review/checklist_share.csv.
"""
from __future__ import annotations

import os
import re
import statistics as st
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pandas as pd  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from mlngrams.load import fetch  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
REF = "⟦references omitted⟧"
HEAD = re.compile(r"^[ \t]*(?:[A-Z]?\d*\.?[ \t]+)?(?:neurips )?(?:paper )?checklist[ \t]*$", re.I | re.M)
ANS = re.compile(r"Justification:|Answer: ?\[(?:Yes|No|NA|N/A)\]", re.I)
FILES = [("neurips", 2022), ("neurips", 2024), ("tmlr", 2024), ("colm", 2025), ("iclr", 2027)]


def main() -> None:
    rows = []
    for v, y in FILES:
        head, ans, share, excl = [], [], [], []
        for b in pq.ParquetFile(fetch("omissions", v, y)).iter_batches(batch_size=256, columns=["text"]):
            for r in b.to_pylist():
                t = r["text"] or ""
                f = t.find(REF)
                if f < 0:
                    continue
                post = len(t) - f
                h = None
                for h in HEAD.finditer(t, f):
                    pass
                a = [m.start() for m in ANS.finditer(t, f)]
                starts = []
                if h is not None:
                    starts.append(h.start())
                if len(a) > 3:
                    starts.append(max(f, a[0] - 1500))  # questions precede the first answer
                ck = len(t) - min(starts) if starts else 0
                head.append(h is not None)
                ans.append(len(a) > 3)
                share.append(ck / post if post else 0.0)
                excl.append((post - ck) / len(t))
        rows.append({"venue": v, "year": y, "checklist_heading": sum(head) / len(head),
                     "checklist_answers": sum(ans) / len(ans), "checklist_share_of_post_mean": st.mean(share),
                     "checklist_share_of_post_median": st.median(share),
                     "post_share_median": None, "post_share_excl_checklist_median": st.median(excl)})
    df = pd.DataFrame(rows)
    os.makedirs(os.path.join(ROOT, "results", "review"), exist_ok=True)
    df.drop(columns="post_share_median").to_csv(os.path.join(ROOT, "results", "review", "checklist_share.csv"),
                                                 index=False, float_format="%.3f")
    print(df.drop(columns="post_share_median").to_string())


if __name__ == "__main__":
    main()
