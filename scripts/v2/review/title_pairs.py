"""Lane E check E4: do Gate 0 exact-title cross-venue pairs point at the same manuscript, and how many
same-manuscript pairs does title matching miss?

For each pair of venue-years, every record gets a MinHash (128 permutations) of its 6-word shingles
from the first 1,500 tokens of the `omissions` body (our own tokenizer, see fw_recount.py). Then:
  - for exact normalized-title pairs (Gate 0's rule: lower, non-alnum -> space, >= 25 chars), the
    estimated Jaccard of the two texts;
  - the same for random cross-venue pairs (baseline);
  - text-matched pairs (estimated Jaccard >= 0.3) found by LSH, whether or not the titles match.

Usage: python3 -I scripts/v2/review/title_pairs.py REC_DIR STORE OUT_DIR iclr-2026:icml-2026 ...
"""
import os
import re
import sys
import zlib

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

MARK = re.compile(r"⟦[^⟧]{0,80}⟧")
TOK = re.compile(r"[a-z]+")
P = (1 << 61) - 1
rng = np.random.default_rng(0)
A = rng.integers(1, P, 128, dtype=np.uint64)
B = rng.integers(0, P, 128, dtype=np.uint64)


def mh(text):
    i = text.find("⟦references omitted⟧")
    toks = TOK.findall(MARK.sub(" ", text if i < 0 else text[:i]).lower())[:1500]
    sh = {zlib.crc32(" ".join(toks[k:k + 6]).encode()) for k in range(max(0, len(toks) - 5))}
    if not sh:
        return np.full(128, np.iinfo(np.uint64).max, dtype=np.uint64)
    x = np.fromiter(sh, dtype=np.uint64)
    # (a*x + b) mod 2^64 is fine as a hash family for estimation purposes here
    return (np.outer(A, x) + B[:, None]).min(axis=1)


def norm(t):
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def load(L, store, stem):
    lfs = L[L.path == f"omissions/{stem}.parquet"].lfs.iloc[0]
    t = pq.read_table(os.path.join(store, lfs + ".parquet"), columns=["paper_id", "title", "text"]).to_pydict()
    sig = np.stack([mh(x or "") for x in t["text"]])
    return pd.DataFrame({"paper_id": t["paper_id"], "title": t["title"]}), sig


def main():
    rec, store, out = sys.argv[1:4]
    L = pd.read_csv(os.path.join(rec, "listing.csv"))
    L = L[L.rev.str.startswith("2c0dd19")]
    summ = []
    for pair in sys.argv[4:]:
        a, b = pair.split(":")
        da, sa = load(L, store, a)
        db, sb = load(L, store, b)
        da["t"], db["t"] = da.title.map(norm), db.title.map(norm)
        ia = {t: i for i, t in enumerate(da.t) if len(t) >= 25}
        tp = [(ia[t], j) for j, t in enumerate(db.t) if len(t) >= 25 and t in ia]
        jt = np.array([(sa[i] == sb[j]).mean() for i, j in tp])
        rr = rng.integers(0, len(da), 2000), rng.integers(0, len(db), 2000)
        jr = (sa[rr[0]] == sb[rr[1]]).mean(axis=1)
        # LSH: 32 bands x 4 rows
        cand = set()
        for band in range(32):
            sl = slice(band * 4, band * 4 + 4)
            buck = {}
            for i, row in enumerate(sa[:, sl]):
                buck.setdefault(row.tobytes(), []).append(i)
            for j, row in enumerate(sb[:, sl]):
                for i in buck.get(row.tobytes(), []):
                    cand.add((i, j))
        txt = [(i, j, (sa[i] == sb[j]).mean()) for i, j in cand]
        txt = [(i, j, s) for i, j, s in txt if s >= 0.3]
        tset = set(tp)
        b_matched_text = {j for _, j, _ in txt}
        b_matched_title = {j for _, j in tp}
        pd.DataFrame([dict(a_id=da.paper_id[i], b_id=db.paper_id[j], jaccard=s, title_match=(i, j) in tset,
                           a_title=da.title[i], b_title=db.title[j]) for i, j, s in txt]).to_csv(
            os.path.join(out, f"e4_textpairs_{a}_{b}.csv"), index=False)
        summ.append(dict(a=a, b=b, n_a=len(da), n_b=len(db), title_pairs=len(tp),
                         title_pairs_j_ge_0_3=int((jt >= 0.3).sum()), title_pairs_j_lt_0_1=int((jt < 0.1).sum()),
                         title_j_median=float(np.median(jt)) if len(jt) else None,
                         random_j_p99=float(np.quantile(jr, .99)), random_j_max=float(jr.max()),
                         text_pairs=len(txt), text_pairs_no_title_match=sum(1 for i, j, _ in txt if (i, j) not in tset),
                         b_with_text_match=len(b_matched_text), b_with_title_match=len(b_matched_title),
                         b_text_match_pct=round(100 * len(b_matched_text) / len(db), 2),
                         b_text_or_title_pct=round(100 * len(b_matched_text | b_matched_title) / len(db), 2)))
        print(summ[-1], flush=True)
    pd.DataFrame(summ).to_csv(os.path.join(out, "e4_title_pairs_summary.csv"), index=False)


if __name__ == "__main__":
    main()
