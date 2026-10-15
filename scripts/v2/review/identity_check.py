"""Lane E check E1: are all V1 records unchanged in V2? Uses only fetch_hash.py outputs (own text hashes).

Usage: python3 -I scripts/v2/review/identity_check.py REC_DIR OUT_DIR
Writes OUT_DIR/e1_identity.csv (one row per config x file) and prints a summary.
"""
import os
import sys

import pandas as pd

rec, out = sys.argv[1], sys.argv[2]
L = pd.read_csv(os.path.join(rec, "listing.csv"))
V1, V2 = "cb5553e", "2c0dd19"
rows = []
for cfg in ("omissions", "clean", "direct"):
    a = pd.read_parquet(os.path.join(rec, f"records-{V1}-{cfg}.parquet"))  # V1 rows of changed files only
    b = pd.read_parquet(os.path.join(rec, f"records-{V2}-{cfg}.parquet"))
    for name, d in (("v1", a), ("v2", b)):
        bad = (d.text_sha256 != d.my_sha256).sum()
        print(cfg, name, "rows", len(d), "text_sha256 column != recomputed sha256(text):", bad)
    l1 = L[L.rev.str.startswith(V1) & L.path.str.startswith(cfg + "/")].set_index("path")
    l2 = L[L.rev.str.startswith(V2) & L.path.str.startswith(cfg + "/")].set_index("path")
    for p in sorted(l2.index):
        bb = b[b.file == p]
        r = dict(config=cfg, file=p, v2_rows=len(bb), in_v1=p in l1.index)
        r["v2_hash_col_mismatch"] = int((bb.text_sha256 != bb.my_sha256).sum())
        r["v2_dup_paper_id"] = int(bb.paper_id.duplicated().sum())
        r["v2_label_mismatch"] = int(((bb.conference.str.lower() + "-" + bb.year.astype(str)) !=
                                      os.path.basename(p)[:-8]).sum())
        if p in l1.index:
            same = l1.loc[p, "lfs"] == l2.loc[p, "lfs"]
            r["byte_identical"] = same
            if same:
                r.update(v1_rows=len(bb), v1_missing_in_v2=0, v1_changed=0, added=0)
            else:
                aa = a[a.file == p]
                k1 = set(zip(aa.paper_id, aa.pdf_sha256, aa.my_sha256))
                k2 = set(zip(bb.paper_id, bb.pdf_sha256, bb.my_sha256))
                ids2 = set(bb.paper_id)
                r.update(v1_rows=len(aa), v1_missing_in_v2=sum(1 for k in k1 if k[0] not in ids2),
                         v1_changed=sum(1 for k in k1 if k[0] in ids2 and k not in k2),
                         added=len(ids2 - set(aa.paper_id)),
                         v1_hash_col_mismatch=int((aa.text_sha256 != aa.my_sha256).sum()))
        else:
            r.update(byte_identical=False, v1_rows=0, v1_missing_in_v2=0, v1_changed=0, added=len(bb))
        rows.append(r)
df = pd.DataFrame(rows)
df.to_csv(os.path.join(out, "e1_identity.csv"), index=False)
print(df.groupby("config")[["v2_rows", "v1_rows", "added", "v1_missing_in_v2", "v1_changed",
                            "v2_hash_col_mismatch", "v2_dup_paper_id", "v2_label_mismatch"]].sum())
print("byte-identical files per config:", df.groupby("config").byte_identical.sum().to_dict())
# cross-config: the same pdf_sha256 set in every config, per file
keys = {cfg: pd.read_parquet(os.path.join(rec, f"records-{V2}-{cfg}.parquet"), columns=["file", "pdf_sha256", "paper_id"])
        for cfg in ("omissions", "clean", "direct")}
for cfg in ("clean", "direct"):
    x = set(zip(keys["omissions"].file.str.split("/").str[1], keys["omissions"].pdf_sha256, keys["omissions"].paper_id))
    y = set(zip(keys[cfg].file.str.split("/").str[1], keys[cfg].pdf_sha256, keys[cfg].paper_id))
    print(f"omissions vs {cfg}: only-omissions {len(x - y)}, only-{cfg} {len(y - x)}")
