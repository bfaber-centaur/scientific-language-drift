"""Lane D (V2): per-paper appendix decomposition on the V2 pin, every venue-year in the dataset.

Runs the unchanged V1.5 scanner (`scripts/appendix_scan.py` scan v1, `analyse()`) on revision
2c0dd19 instead of cb5553e, over the V2 venue list (ICML 2023-26, COLM 2026, CoRL 2025 added). The
scanner itself is not modified, so per-paper rows for V1 records must equal the V1.5 scan exactly
(all V1 records are byte-identical in V2; docs/v2-corpus-inventory.md).

Adds three id-level columns the V1 analysis took from results/paper_flags_iclr.csv, computed with
the same rules (scripts/paper_flags.py, scripts/recon.py): `short` (< 2,000 chars), `template`
(unmodified ICLR LaTeX template in the first 300 chars), `id_stratum`.

Usage:
    python3 scripts/v2/appendix_scan_v2.py --out data/v2/appendix [--venues iclr icml] [--years 2026]

Outputs (git-ignored): <out>/papers.parquet, <out>/sections.parquet, <out>/run.json. No paper text.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "..", "src"))

import pandas as pd  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

import appendix_scan as scan  # noqa: E402
import recon  # noqa: E402
from mlngrams.load import V2_REVISION, fetch  # noqa: E402
from mlngrams.tokenize import TOKENIZER_VERSION  # noqa: E402

VENUES = {
    "iclr": list(range(2017, 2028)),
    "icml": [2023, 2024, 2025, 2026],
    "neurips": [2021, 2022, 2023, 2024, 2025],
    "tmlr": [2022, 2023, 2024, 2025, 2026],
    "colm": [2024, 2025, 2026],
    "corl": [2021, 2022, 2023, 2024, 2025],
    "emnlp": [2023],
}


def analyse(args):
    venue, year, doc_id, text = args
    r, s = scan.analyse(args)
    t = text or ""
    r["short"] = len(t) < recon.SHORT
    r["template"] = bool(recon._TEMPLATE.search(t[:300]))
    r["id_stratum"] = recon.id_stratum(doc_id)
    return r, s


def iter_rows(venue, year, revision):
    pf = pq.ParquetFile(fetch("omissions", venue, year, revision=revision))
    for b in pf.iter_batches(batch_size=128, columns=["paper_id", "text"]):
        for row in b.to_pylist():
            yield venue, year, row["paper_id"], row["text"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--venues", nargs="*", default=list(VENUES))
    ap.add_argument("--years", nargs="*", type=int)
    ap.add_argument("--out", required=True)
    ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--revision", default=V2_REVISION)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    papers, sections = [], []
    with Pool(a.procs) as pool:
        for venue in a.venues:
            for year in VENUES[venue]:
                if a.years and year not in a.years:
                    continue
                k = 0
                for r, s in pool.imap(analyse, iter_rows(venue, year, a.revision), chunksize=16):
                    papers.append(r)
                    sections.extend(s)
                    k += 1
                print(f"{venue} {year}: {k} papers", flush=True)
    pd.DataFrame(papers).to_parquet(os.path.join(a.out, "papers.parquet"), index=False)
    pd.DataFrame(sections).to_parquet(os.path.join(a.out, "sections.parquet"), index=False)
    with open(os.path.join(a.out, "run.json"), "w") as f:
        json.dump({"revision": a.revision, "config": "omissions", "scan_version": scan.SCAN_VERSION,
                   "tokenizer": TOKENIZER_VERSION, "venues": a.venues, "years": a.years}, f, indent=1)


if __name__ == "__main__":
    main()
