"""Lane D (V2): rerun the preregistered Lane C pipeline (disclosure groups vs paper-body language,
disclosure/body overlap with topic-matched and shuffled controls) on other cohorts.

The Lane C scripts (scripts/disclosures/lane_c_features.py, lane_c_analysis.py) are imported and run
unchanged; only their input/output locations, the omissions file they read, and the stock-wording
threshold are redirected (see results/v2/disclosures/lane_c_v2_prereg.md):
  * input   data/v2/disclosures/<venue>-<year>.parquet (scripts/v2/disclosures_extract_v2.py),
            optionally restricted to one first-page version stratum
  * bodies  the V2 omissions file of the same venue-year
  * stock   a 6-gram is stock wording if it occurs in >= max(5, 50/39,351 of the cohort's clean
            disclosures), the V1.5 rate scaled to the cohort
  * output  results/v2/disclosures/lane_c/<cohort>/ (tables, figures); per-paper data under
            data/v2/lane_c/<cohort>/ (git-ignored)
V1.5 files in results/disclosures/ are never written: the Lane C scripts' ROOT is redirected to a
scratch root under data/v2/lane_c/<cohort>/root/, and its results are copied out.

Usage:
    python3 scripts/v2/lane_c_v2.py --cohort iclr-2026 [--version submission] [--boot 1000] [--perm 2000]
"""
from __future__ import annotations

import argparse
import glob
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "disclosures"))

import pandas as pd  # noqa: E402

from mlngrams.load import V2_REVISION, fetch  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cohort", required=True)
    ap.add_argument("--version", choices=["submission", "published"])
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--perm", type=int, default=2000)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    venue, year = a.cohort.rsplit("-", 1)
    year = int(year)
    name = a.cohort + (f"-{a.version}" if a.version else "")
    data = os.path.join(ROOT, "data", "v2", "lane_c", name)
    fake = os.path.join(data, "root")
    out = os.path.join(ROOT, "results", "v2", "disclosures", "lane_c", name)
    for d in (data, os.path.join(fake, "results", "disclosures"), out):
        os.makedirs(d, exist_ok=True)

    disc = pd.read_parquet(os.path.join(ROOT, "data", "v2", "disclosures", f"{a.cohort}.parquet"))
    if a.version:
        ver = pd.read_parquet(os.path.join(ROOT, "data", "v2", "version", V2_REVISION[:7], f"{a.cohort}.parquet"),
                              columns=["paper_id", "version"]).rename(columns={"paper_id": "doc_id"})
        disc = disc.merge(ver.drop_duplicates("doc_id"), on="doc_id", how="left")
        disc = disc[disc.version == a.version]
    disc.to_parquet(os.path.join(data, "iclr2027.parquet"), index=False)  # file name the Lane C script expects
    n_clean = int(((disc.found == True) & (disc.tier == "clean")).sum())  # noqa: E712

    import lane_c_features as F
    F.DATA = data
    F.ROOT = fake
    F.STOCK_DF = max(5, round(50 * n_clean / 39351))
    F.fetch = lambda config, v, y, revision=None: fetch(config, venue, year, revision=V2_REVISION)
    sys.argv = ["lane_c_features.py", "--workers", str(a.workers)]
    F.main()

    import lane_c_analysis as A
    A.DATA = data
    A.OUT = out
    sys.argv = ["lane_c_analysis.py", "--boot", str(a.boot), "--perm", str(a.perm)]
    A.main()
    for f in glob.glob(os.path.join(fake, "results", "disclosures", "*")):
        shutil.copy(f, out)
    with open(os.path.join(out, "cohort.txt"), "w") as fh:
        fh.write(f"cohort {name}; revision {V2_REVISION}; clean disclosures {n_clean}; stock_df {F.STOCK_DF}\n")


if __name__ == "__main__":
    main()
