"""Lane E E7: would a word-dropping extraction artifact explain the fall of "of"? If "of" tokens were
being lost, phrases where "of" is obligatory would surface without it ("one the", "most the").
Counts, per million tokens (our tokenizer), "X of the" vs ungrammatical "X the" for quantifier X.
Usage: python3 -I of_deletion_test.py REC STORE OUT.csv iclr-2023 iclr-2027 ..."""
import os, re, sys
import pandas as pd, pyarrow.parquet as pq
MARK = re.compile(r"⟦[^⟧]{0,80}⟧"); HY = re.compile(r"([A-Za-z])-\n\s*([a-z])")
Q = ["one", "some", "each", "most", "all", "many", "none", "part", "number", "both", "any"]
rec, store, dst = sys.argv[1:4]
L = pd.read_csv(os.path.join(rec, "listing.csv")); L = L[L.rev.str.startswith("2c0dd19")]
rows = []
for stem in sys.argv[4:]:
    lfs = L[L.path == f"omissions/{stem}.parquet"].lfs.iloc[0]
    c = {f"{q} of the": 0 for q in Q} | {f"{q} the": 0 for q in Q}; n = 0
    for b in pq.ParquetFile(os.path.join(store, lfs + ".parquet")).iter_batches(256, columns=["text"]):
        for t in b.column(0).to_pylist():
            t = t or ""; i = t.find("⟦references omitted⟧"); t = t if i < 0 else t[:i]
            toks = re.findall(r"[a-z]+", HY.sub(r"\1\2", MARK.sub(" ", t)).lower()); n += len(toks)
            for k in range(len(toks) - 2):
                if toks[k] in Q:
                    if toks[k + 1] == "of" and toks[k + 2] == "the": c[f"{toks[k]} of the"] += 1
                    elif toks[k + 1] == "the": c[f"{toks[k]} the"] += 1
    for q in Q:
        rows.append(dict(file=stem, q=q, of_the_pm=round(1e6 * c[f"{q} of the"] / n, 1), bare_the_pm=round(1e6 * c[f"{q} the"] / n, 1)))
    print(stem, flush=True)
pd.DataFrame(rows).to_csv(dst, index=False)
