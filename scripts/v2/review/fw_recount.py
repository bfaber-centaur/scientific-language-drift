"""Lane E check E5: independent per-paper function-word counts on V2 `omissions` (no mlngrams code).

Tokenizer (deliberately simpler than mlngrams v1.3 and written separately): drop ⟦...⟧ markers,
join line-break hyphenation, lowercase, tokens = maximal runs of ASCII letters [a-z]+.
Denominator = all such tokens. Regions:
  all    whole text
  body   text before the first "⟦references omitted⟧" (whole text if absent)
  abs    from the first line that is just "abstract" to the first line starting with
         "1 introduction"/"introduction" (max 400 tokens); missing if either is absent

Usage: python3 -I scripts/v2/review/fw_recount.py REC_DIR STORE OUT.parquet [venue ...]
Output: one row per record: file, paper_id, pdf_sha256, region, n_tok, and a count per word.
"""
import os
import re
import sys

import pandas as pd
import pyarrow.parquet as pq

WORDS = ["the", "of", "and", "in", "to", "a", "we", "is", "that", "for", "our", "this", "with", "on",
         "as", "by", "are", "be", "it", "which", "these", "their", "can", "from", "an", "not"]
MARK = re.compile(r"⟦[^⟧]{0,80}⟧")
HY = re.compile(r"([A-Za-z])-\n\s*([a-z])")
TOK = re.compile(r"[a-z]+")
ABS = re.compile(r"^\s*abstract\s*$", re.I | re.M)
INTRO = re.compile(r"^\s*(1\.?\s*)?introduction\b", re.I | re.M)
REF = "⟦references omitted⟧"


def counts(t):
    toks = TOK.findall(HY.sub(r"\1\2", MARK.sub(" ", t)).lower())
    d = {"n_tok": len(toks)}
    s = set(WORDS)
    c = dict.fromkeys(WORDS, 0)
    for w in toks:
        if w in s:
            c[w] += 1
    d.update(c)
    return d, toks


def regions(t):
    i = t.find(REF)
    out = {"all": t, "body": t if i < 0 else t[:i]}
    m = ABS.search(t[:20000])
    if m:
        n = INTRO.search(t, m.end())
        if n and n.start() - m.end() < 8000:
            out["abs"] = t[m.end():n.start()]
    return out


def main():
    rec, store, dst = sys.argv[1:4]
    venues = set(sys.argv[4:])
    L = pd.read_csv(os.path.join(rec, "listing.csv"))
    L = L[L.rev.str.startswith("2c0dd19") & L.path.str.startswith("omissions/")]
    rows = []
    for _, r in L.iterrows():
        stem = os.path.basename(r.path)[:-8]
        if venues and stem.rsplit("-", 1)[0] not in venues:
            continue
        pf = pq.ParquetFile(os.path.join(store, r.lfs + ".parquet"))
        for b in pf.iter_batches(batch_size=256, columns=["paper_id", "pdf_sha256", "text"]):
            d = b.to_pydict()
            for pid, h, t in zip(d["paper_id"], d["pdf_sha256"], d["text"]):
                for reg, s in regions(t or "").items():
                    c, toks = counts(s)
                    if reg == "abs":
                        if len(toks) > 400 or len(toks) < 50:
                            continue
                    rows.append({"file": stem, "paper_id": pid, "pdf_sha256": h, "region": reg, **c})
        print(stem, flush=True)
    pd.DataFrame(rows).to_parquet(dst)


if __name__ == "__main__":
    main()
