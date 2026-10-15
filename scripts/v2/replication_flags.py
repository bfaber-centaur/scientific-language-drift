"""Lane B (V2 replication): per-paper flags for every V2 record, ids only, no text.

Usage:
    python3 scripts/v2/replication_flags.py [--revision 2c0dd19...] [--workers 4]

Writes results/v2/replication/flags_v2.csv.gz with one row per record of the omissions config:
    venue, year, doc_id, pdf_sha256 (first 16 hex characters)
    member      v1 | added   (results/v2/inventory/membership.csv.gz: "retained" = present in V1)
    version     ICLR: V1's rule, unchanged (scripts/paper_flags.py: "published as a conference paper"
                anywhere in the direct text -> published, else "under review as a conference paper" ->
                under_review, else unknown).
                Other venues: the Gate 0 first-page rule (scripts/v2/version_mix.classify), mapped
                submission -> under_review, published -> published, preprint/unknown -> unknown.
    version_fp  the raw first-page label for every venue (published | submission | preprint | unknown)
    id_stratum  0-P | Q-z_other | nonstandard_id (recon.id_stratum)
    exclude     "" | short (< 2000 chars of omissions text) | template (unmodified ICLR template),
                as in V1's paper_flags.py
    iclr_overlap  non-ICLR records whose normalized title (>= 25 chars) equals the title of an ICLR
                record of the same or the previous year (the Gate 0 resubmission overlap); False for ICLR
    stratum     "<version>|<member>|<id group>" where id group is the id stratum for ICLR 2025 and "-"
                elsewhere. count_ngrams.py uses it directly, so any V1 or V2 view is a sum of strata
                (scripts/v2/replication_views.py).

For V1 records at ICLR this must reproduce results/paper_flags_iclr.csv exactly (checked by --check).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, HERE)

import pandas as pd  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from mlngrams.load import V2_REVISION, fetch  # noqa: E402

OUT = os.path.join(ROOT, "results", "v2", "replication")
SHORT = 2000
_PUB = re.compile(r"published as a conference paper", re.I)  # = recon._PUB
_REV = re.compile(r"under review as a conference paper", re.I)  # = recon._REV
_TEMPLATE = re.compile(r"formatting instructions for iclr", re.I)  # = recon._TEMPLATE
FP_MAP = {"submission": "under_review", "published": "published"}


def id_stratum(pid: str) -> str:  # = recon.id_stratum
    if not re.fullmatch(r"[A-Za-z0-9_-]{9,12}", pid):
        return "nonstandard_id"
    c = pid[0]
    if c.isdigit() or "A" <= c <= "P":
        return "0-P"
    return "Q-z_other"


def norm_title(s):
    if not s:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def scan(args):
    from version_mix import classify

    venue, year, revision = args
    om = pq.ParquetFile(fetch("omissions", venue, year, revision))
    rows = {}
    for b in om.iter_batches(batch_size=256, columns=["paper_id", "pdf_sha256", "text_sha256", "text", "title"]):
        for r in b.to_pylist():
            t = r["text"] or ""
            rows[(r["paper_id"], r["pdf_sha256"])] = {
                "venue": venue, "year": year, "doc_id": r["paper_id"], "pdf_sha256": r["pdf_sha256"],
                "text_sha256": r["text_sha256"],
                "exclude": "short" if len(t) < SHORT else "template" if _TEMPLATE.search(t[:300]) else "",
                "title_norm": norm_title(r["title"]),
            }
    by_sha = {}
    for k in rows:  # one PDF can sit under two forum ids (TMLR 2026), so map a hash to all of them
        by_sha.setdefault(k[1], []).append(k)
    di = pq.ParquetFile(fetch("direct", venue, year, revision))
    for b in di.iter_batches(batch_size=256, columns=["pdf_sha256", "text"]):
        for h, t in zip(b.column("pdf_sha256").to_pylist(), b.column("text").to_pylist()):
            if h not in by_sha:
                continue
            t = t or ""
            fp, _ = classify(t.split("\f", 1)[0])
            if venue == "iclr":
                v = "published" if _PUB.search(t) else "under_review" if _REV.search(t) else "unknown"
            else:
                v = FP_MAP.get(fp, "unknown")
            for k in by_sha[h]:
                rows[k]["version_fp"] = fp
                rows[k]["version"] = v
    out = pd.DataFrame(list(rows.values()))
    for c, v in (("version", "unknown"), ("version_fp", "unknown")):
        out[c] = out[c].fillna(v) if c in out else v
    print(venue, year, len(out), flush=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--revision", default=V2_REVISION)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--check", action="store_true", help="only compare an existing output with V1 flags")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    dst = os.path.join(OUT, "flags_v2.csv.gz")
    if not a.check:
        files = pd.read_csv(os.path.join(ROOT, "results", "v2", "inventory", "files.csv"))
        stems = sorted({p.split("/")[1][:-8] for p in files[files.revision == a.revision].path
                        if p.startswith("omissions/") and p.endswith(".parquet")})
        jobs = [(s.rsplit("-", 1)[0], int(s.rsplit("-", 1)[1]), a.revision) for s in stems]
        jobs.sort(key=lambda j: j[0] == "iclr" and j[1] == 2027, reverse=True)
        with ProcessPoolExecutor(a.workers) as ex:
            df = pd.concat(list(ex.map(scan, jobs)), ignore_index=True)
        mem = pd.read_csv(os.path.join(ROOT, "results", "v2", "inventory", "membership.csv.gz"))
        mem = mem.rename(columns={"paper_id": "doc_id"})
        mem["member"] = mem.status.map({"retained": "v1", "added": "added"})
        df = df.merge(mem[["venue", "year", "doc_id", "member"]], on=["venue", "year", "doc_id"], how="left")
        assert df.member.notna().all(), "record missing from membership.csv.gz"
        df["id_stratum"] = df.doc_id.map(id_stratum)
        # ICLR title overlap: same or previous ICLR year
        ic = df[(df.venue == "iclr") & (df.title_norm.str.len() >= 25)]
        by_year = ic.groupby("year").title_norm.apply(set).to_dict()
        df["iclr_overlap"] = [
            v != "iclr" and len(t) >= 25 and (t in by_year.get(y, ()) or t in by_year.get(y - 1, ()))
            for v, y, t in zip(df.venue, df.year, df.title_norm)
        ]
        idg = [s if (v == "iclr" and y == 2025) else "-" for v, y, s in zip(df.venue, df.year, df.id_stratum)]
        df["stratum"] = df.version + "|" + df.member + "|" + pd.Series(idg, index=df.index)
        # compact: a 16-hex prefix of the PDF hash is enough to join (full hashes: results/v2/inventory)
        df["pdf_sha256"] = df.pdf_sha256.str[:16]
        df = df.drop(columns=["title_norm", "text_sha256"]).sort_values(["venue", "year", "doc_id"])
        df.to_csv(dst, index=False)
        print(df.groupby(["venue", "year", "version"]).size().unstack(fill_value=0))
    df = pd.read_csv(dst, keep_default_na=False)
    v1 = pd.read_csv(os.path.join(ROOT, "results", "paper_flags_iclr.csv"), keep_default_na=False)
    m = v1.merge(df[df.venue == "iclr"], on=["year", "doc_id"], how="left", suffixes=("_v1", "_v2"))
    rep = {
        "v1_records": len(v1),
        "found_in_v2": int(m.member.notna().sum()),
        "member_v1": int((m.member == "v1").sum()),
        "version_equal": int((m.version_v1 == m.version_v2).sum()),
        "exclude_equal": int((m.exclude_v1 == m.exclude_v2).sum()),
        "id_stratum_equal": int((m.id_stratum_v1 == m.id_stratum_v2).sum()),
        "pdf_sha_equal": int((m.pdf_sha256_v1.str[:16] == m.pdf_sha256_v2).sum()),
    }
    pd.Series(rep).to_csv(os.path.join(OUT, "flags_v1_check.csv"), header=["value"])
    print(rep)


if __name__ == "__main__":
    main()
