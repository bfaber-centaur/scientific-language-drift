"""Lane E check E3: audit the Gate 0 first-page version labels against what the header itself says.

For every V2 `direct` record: re-run the Gate 0 classifier (imported from scripts/v2/version_mix.py
only to reproduce its label), and separately parse the venue and year *named* in the first-page
header/footer with our own patterns. A camera-ready ICML 2026 paper should say "Proceedings of the
43rd International Conference on Machine Learning"; a TMLR paper says "Published in Transactions on
Machine Learning Research (MM/YYYY)". Mismatches between the named year and the file label reveal
mislabelled or out-of-cohort records and test the undocumented TMLR year semantics.

Usage: python3 -I scripts/v2/review/header_audit.py REC_DIR STORE OUT.parquet
Output (no text): file, paper_id, pdf_sha256, has_ff, g0_version, g0_marker, named_venue, named_year,
named_kind (published|submission|other), tmlr_month
"""
import importlib.util
import os
import re
import sys

import pandas as pd
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("vm", os.path.join(HERE, "..", "version_mix.py"))
vm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vm)

ORD = r"(\d{1,2})(?:st|nd|rd|th)"
PATS = [
    ("iclr", "published", re.compile(r"published as a conference paper at iclr\s*(\d{4})", re.I)),
    ("iclr", "submission", re.compile(r"under review as a conference paper at iclr\s*(\d{4})", re.I)),
    ("colm", "published", re.compile(r"published as a conference paper at colm\s*(\d{4})", re.I)),
    ("colm", "submission", re.compile(r"under review as a conference paper at colm\s*(\d{4})", re.I)),
    ("tmlr", "published", re.compile(r"published in transactions on machine learning research \((\d{1,2})\s*/\s*(\d{4})\)", re.I)),
    ("tmlr", "submission", re.compile(r"under review as submission to tmlr", re.I)),
    ("icml", "published", re.compile(r"proceedings of the " + ORD + r" international conference on machine\s*learning", re.I)),
    ("icml", "submission", re.compile(r"under review by the international conference on machine learning \(icml\)", re.I)),
    # submission first: the NeurIPS submission footer contains the camera-ready phrase
    ("neurips", "submission", re.compile(r"submitted to " + ORD + r" conference on neural information processing systems", re.I)),
    ("neurips", "published", re.compile(ORD + r" conference on neural information processing systems \(neurips (\d{4})\)", re.I)),
    ("corl", "published", re.compile(ORD + r" conference on robot learning \(corl (\d{4})\)", re.I)),
]
# ICML n-th edition -> year: 40th = 2023. NeurIPS: 37th = 2023. CoRL: 7th = 2023.
BASE = {"icml": 1983, "neurips": 1986, "corl": 2016}


def parse(page):
    t = " ".join(page.split())
    for venue, kind, rx in PATS:
        m = rx.search(t)
        if not m:
            continue
        g = m.groups()
        month, year = None, None
        if venue in ("iclr", "colm") and g:
            year = int(g[0])
        elif venue == "tmlr" and kind == "published":
            month, year = int(g[0]), int(g[1])
        elif venue in BASE and g:
            year = int(g[-1]) if len(g) == 2 else BASE[venue] + int(g[0])
        return venue, year, kind, month
    return None, None, "other", None


def main():
    rec, store, dst = sys.argv[1:4]
    L = pd.read_csv(os.path.join(rec, "listing.csv"))
    L = L[L.rev.str.startswith("2c0dd19") & L.path.str.startswith("direct/")]
    rows = []
    for _, r in L.iterrows():
        stem = os.path.basename(r.path)[:-8]
        pf = pq.ParquetFile(os.path.join(store, r.lfs + ".parquet"))
        for b in pf.iter_batches(batch_size=256, columns=["paper_id", "pdf_sha256", "text"]):
            d = b.to_pydict()
            for pid, h, t in zip(d["paper_id"], d["pdf_sha256"], d["text"]):
                t = t or ""
                first = t.split("\f", 1)[0]
                v, mk = vm.classify(first)
                nv, ny, nk, mo = parse(first)
                rows.append(dict(file=stem, paper_id=pid, pdf_sha256=h, has_ff="\f" in t,
                                 first_page_chars=len(first), g0_version=v, g0_marker=mk, named_venue=nv,
                                 named_year=ny, named_kind=nk, tmlr_month=mo))
        print(stem, flush=True)
    pd.DataFrame(rows).to_parquet(dst)


if __name__ == "__main__":
    main()
