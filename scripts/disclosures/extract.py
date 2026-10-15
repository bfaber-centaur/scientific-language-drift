"""Recover ICLR 2027 AI-use disclosures from the pinned dataset (Lane B, step 1).

Usage: python3 scripts/disclosures/extract.py [--out data/disclosures]

Reads the `omissions` config of iclr-2027 at the pinned revision, applies
mlngrams.disclosures.extract (extractor v1) to every paper and writes
  data/disclosures/iclr2027.parquet   per paper: doc_id, title, form, heading,
      end_reason, text (raw), text_clean, n_chars, n_words, flags. Git-ignored:
      it holds the full disclosure text and must not be committed.
  results/disclosures/extraction_summary.csv   aggregate counts only.
  results/disclosures/extraction_leakage.csv   how many recovered disclosures
      sit in the main body and were NOT cut by statement removal v2.

Quality tiers:
  clean     heading on its own line or run-in, ended at a heading, an inline
            heading, a blank line or the reference marker, no bibliography residue
  suspect   heading_after / headless forms, or ended at max_chars / end of text,
            or bibliography residue; kept for sensitivity, excluded from primary tables
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pandas as pd  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from mlngrams.disclosures import EXTRACTOR_VERSION, clean, extract, looks_like_bibliography  # noqa: E402
from mlngrams.load import REVISION, fetch  # noqa: E402
from mlngrams.sections import HEADING, SECTIONS_VERSION  # noqa: E402

REF = "⟦references omitted⟧"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "disclosures"))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    path = fetch("omissions", "iclr", 2027)
    pf = pq.ParquetFile(path)
    flags = pd.read_csv(os.path.join(ROOT, "results", "paper_flags_iclr.csv"), usecols=["doc_id", "year", "version", "exclude"])
    flags = flags[flags.year == 2027].drop(columns="year").drop_duplicates("doc_id")
    rows = []
    for b in pf.iter_batches(batch_size=256, columns=["paper_id", "title", "pdf_sha256", "text"]):
        for r in b.to_pylist():
            t = r["text"] or ""
            d = extract(t)
            row = {"doc_id": r["paper_id"], "pdf_sha256": r["pdf_sha256"], "title": r["title"], "paper_chars": len(t)}
            if d is None:
                row["found"] = False
                rows.append(row)
                continue
            ref = t.find(REF)
            line_start = t.rfind("\n", 0, d.start) + 1
            cut_v2 = bool(HEADING.match(t, line_start)) and d.form in ("line",)
            bib = looks_like_bibliography(d.text)
            suspect = d.form in ("heading_after", "headless") or d.end_reason in ("max_chars", "end_of_text") or bib
            tc = clean(d.text)
            row.update(
                found=True, form=d.form, heading=d.heading, end_reason=d.end_reason, n_candidates=d.n_candidates,
                text=d.text, text_clean=tc, n_chars=len(tc), n_words=len(tc.split()),
                rel_pos=d.start / max(1, len(t)), in_body=(ref < 0 or d.start < ref), cut_by_v2=cut_v2,
                bibliography_residue=bib, tier="suspect" if suspect else "clean",
            )
            rows.append(row)
    df = pd.DataFrame(rows).merge(flags, on="doc_id", how="left")
    df.to_parquet(os.path.join(args.out, "iclr2027.parquet"), index=False)

    f = df[df.found == True]  # noqa: E712
    summ = [
        ("papers", len(df)),
        ("disclosure_found", len(f)),
        ("disclosure_found_pct", round(100 * len(f) / len(df), 2)),
        ("tier_clean", int((f.tier == "clean").sum())),
        ("tier_suspect", int((f.tier == "suspect").sum())),
    ]
    summ += [(f"form_{k}", int(v)) for k, v in f.form.value_counts().items()]
    summ += [(f"end_{k}", int(v)) for k, v in f.end_reason.value_counts().items()]
    summ += [("bibliography_residue", int(f.bibliography_residue.sum())), ("multiple_candidates", int((f.n_candidates > 1).sum()))]
    for q in (10, 25, 50, 75, 90):
        summ.append((f"words_p{q}_clean", float(f[f.tier == "clean"].n_words.quantile(q / 100))))
    for v in ("under_review", "published"):
        sub = df[df.version == v]
        summ.append((f"found_pct_{v}", round(100 * sub.found.mean(), 2) if len(sub) else None))
    pd.DataFrame(summ, columns=["measure", "value"]).to_csv(os.path.join(ROOT, "results", "disclosures", "extraction_summary.csv"), index=False)

    leak = f[f.in_body].groupby(["form", "cut_by_v2"]).size().rename("papers").reset_index()
    leak.to_csv(os.path.join(ROOT, "results", "disclosures", "extraction_leakage.csv"), index=False)
    with open(os.path.join(ROOT, "results", "disclosures", "run.json"), "w") as fh:
        json.dump({"revision": REVISION, "config": "omissions", "venue_year": "iclr-2027", "extractor": EXTRACTOR_VERSION,
                   "sections": SECTIONS_VERSION}, fh, indent=1)
    print(pd.DataFrame(summ).to_string(), "\n", leak.to_string())


if __name__ == "__main__":
    main()
