"""Lane E: summary tables for results/v2/review/ from the scratch outputs of fw_recount.py and
header_audit.py (per-record tables stay outside the repo).

Usage: python3 -I scripts/v2/review/review_tables.py REC_DIR SCRATCH_OUT_DIR results/v2/review
Expects SCRATCH_OUT_DIR/fw_iclr.parquet, fw_other.parquet, headers.parquet.
"""
import os
import sys

import numpy as np
import pandas as pd

rec, so, out = sys.argv[1:4]
W = ["of", "in", "we", "and", "the", "to", "a", "is", "that", "our"]

# V1 membership and exact-duplicate texts, from our own hashes
r2 = pd.read_parquet(os.path.join(rec, "records-2c0dd19-omissions.parquet"),
                     columns=["file", "pdf_sha256", "my_sha256"])
r1 = pd.read_parquet(os.path.join(rec, "records-cb5553e-omissions.parquet"), columns=["file", "pdf_sha256"])
changed, v1keys = set(r1.file), set(zip(r1.file, r1.pdf_sha256))
r2["v1"] = [(f not in changed) or ((f, h) in v1keys) for f, h in zip(r2.file, r2.pdf_sha256)]
r2["dup"] = r2.my_sha256.duplicated(keep="first")
r2["stem"] = r2.file.str.split("/").str[1].str[:-8]

fw = pd.concat([pd.read_parquet(os.path.join(so, f)) for f in ("fw_iclr.parquet", "fw_other.parquet")])
fw = fw.merge(r2[["stem", "pdf_sha256", "v1", "dup"]], left_on=["file", "pdf_sha256"], right_on=["stem", "pdf_sha256"])
fw = fw[~fw.dup]
h = pd.read_parquet(os.path.join(so, "headers.parquet"))
fw = fw.merge(h[["file", "pdf_sha256", "g0_version"]], on=["file", "pdf_sha256"])
fw["venue"] = fw.file.str.rsplit("-", n=1).str[0]
fw["year"] = fw.file.str[-4:].astype(int)


def summ(g):
    d = {"n": len(g)}
    for w in W:
        d[f"{w}_pm"] = round(1e6 * g[w].sum() / g.n_tok.sum())
    for w in ("of", "and", "we"):
        d[f"{w}_per1k_median"] = round(float(np.median(1e3 * g[w] / g.n_tok)), 2)
    return pd.Series(d)


rows = []
for region, mintok in (("body", 300), ("abs", 50)):
    b = fw[(fw.region == region) & (fw.n_tok >= mintok)]
    for keys, label in ((["venue", "year"], "all"), (["venue", "year", "g0_version"], "by_version"),
                        (["venue", "year", "v1"], "by_v1_membership")):
        t = b.groupby(keys).apply(summ).reset_index()
        t.insert(0, "split", label)
        t.insert(0, "region", region)
        rows.append(t)
pd.concat(rows).to_csv(os.path.join(out, "e5_function_words.csv"), index=False)

b = fw[(fw.region == "body") & (fw.n_tok >= 1000) & (fw.venue == "iclr")]
r = 1e3 * b["of"] / b.n_tok
bins = [0, 8, 12, 16, 20, 24, 28, 32, 1000]
pd.crosstab(b.year, pd.cut(r, bins), normalize="index").round(4).to_csv(os.path.join(out, "e5_iclr_of_distribution.csv"))

# header audit
h["venue"] = h.file.str.rsplit("-", n=1).str[0]
h["year"] = h.file.str[-4:].astype(int)
a = h.groupby(["file", "g0_version", "named_kind"]).size().rename("n").reset_index()
a.to_csv(os.path.join(out, "e3_header_audit.csv"), index=False)
t = h[(h.venue == "tmlr") & (h.named_venue == "tmlr") & (h.named_kind == "published")]
pd.crosstab(t.file, t.named_year.astype(int)).to_csv(os.path.join(out, "e3_tmlr_year_vs_header.csv"))
y = h[(h.named_venue == h.venue) & h.named_year.notna() & (h.venue != "tmlr")]
y[y.named_year != y.year].groupby(["file", "named_year", "named_kind"]).size().rename("n").reset_index().to_csv(
    os.path.join(out, "e3_header_year_mismatch.csv"), index=False)
print("ok")
