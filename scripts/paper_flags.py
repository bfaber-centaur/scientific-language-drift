"""Per-paper flags used by count_ngrams.py (ids only, no text).

Usage: python3 scripts/paper_flags.py      # needs omissions + direct ICLR files (fetched if absent)

Writes results/paper_flags_iclr.csv with one row per ICLR paper:
    doc_id, year, pdf_sha256
    version    published | under_review | unknown, from the running header in the
               `direct` text layer ("Published as a conference paper ..." wins if both)
    id_stratum 0-P | Q-z_other | nonstandard_id (see recon.id_stratum)
    in_sample  False for ICLR 2025 papers outside the 0-P id stratum: that part of 2025
               was extracted only partially and is biased toward accepted papers
               (docs/corpus.md). They are kept in the stratified tables only.
    exclude    "" or a reason the paper is not counted at all: short (<2000 chars of
               omissions text) or template (unmodified ICLR LaTeX template).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd  # noqa: E402

import recon  # noqa: E402

YEARS = recon.ICLR_YEARS


def main():
    rows = []
    for year in YEARS:
        direct = recon.scan_direct("iclr", year, allow_fetch=True)
        for r in recon.scan_omissions("iclr", year, keep_keys=False):
            d = direct.get(r["pdf_sha256"], {})
            version = "published" if d.get("pub") else "under_review" if d.get("rev") else "unknown"
            stratum = recon.id_stratum(r["paper_id"])
            exclude = "short" if r["chars"] < recon.SHORT else "template" if r["template"] else ""
            rows.append(
                {
                    "doc_id": r["paper_id"],
                    "year": year,
                    "pdf_sha256": r["pdf_sha256"],
                    "version": version,
                    "id_stratum": stratum,
                    "in_sample": not (year == 2025 and stratum != "0-P"),
                    "exclude": exclude,
                }
            )
        print(year, "done", flush=True)
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(recon.ROOT, "results", "paper_flags_iclr.csv"), index=False)
    print(out.groupby(["year", "version"]).size().unstack(fill_value=0))
    print(out[out.exclude != ""].groupby(["year", "exclude"]).size())


if __name__ == "__main__":
    main()
