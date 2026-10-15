"""Lane E E4b: for exact-title pairs, shingle Jaccard (as title_pairs.py) plus bag-of-words cosine of
the first 1,500 body tokens, to tell rewritten same manuscripts (high cosine) from different papers
sharing a title (low cosine). Usage: python3 -I title_pairs_low.py REC STORE OUT.csv a:b ..."""
import os, re, sys
from collections import Counter
import numpy as np, pandas as pd, pyarrow.parquet as pq
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from title_pairs import mh, norm, MARK, TOK

def toks(t):
    i = t.find("⟦references omitted⟧")
    return TOK.findall(MARK.sub(" ", t if i < 0 else t[:i]).lower())[:1500]

def cos(a, b):
    ca, cb = Counter(a), Counter(b)
    num = sum(v * cb[k] for k, v in ca.items())
    return num / (np.sqrt(sum(v*v for v in ca.values())) * np.sqrt(sum(v*v for v in cb.values())) or 1)

rec, store, dst = sys.argv[1:4]
L = pd.read_csv(os.path.join(rec, "listing.csv")); L = L[L.rev.str.startswith("2c0dd19")]
def load(stem):
    lfs = L[L.path == f"omissions/{stem}.parquet"].lfs.iloc[0]
    return pq.read_table(os.path.join(store, lfs + ".parquet"), columns=["paper_id", "title", "text"]).to_pandas()
rows = []
for pair in sys.argv[4:]:
    a, b = pair.split(":"); da, db = load(a), load(b)
    da["t"], db["t"] = da.title.map(norm), db.title.map(norm)
    ia = {t: i for i, t in enumerate(da.t) if len(t) >= 25}
    for j, t in enumerate(db.t):
        if len(t) >= 25 and t in ia:
            i = ia[t]; x, y = da.text[i] or "", db.text[j] or ""
            tx, ty = toks(x), toks(y)
            rows.append(dict(pair=pair, a_id=da.paper_id[i], b_id=db.paper_id[j], title=da.title[i],
                             jaccard=float((mh(x) == mh(y)).mean()), bow_cos=cos(tx, ty), a_tok=len(tx), b_tok=len(ty)))
    # random-pair cosine baseline
    rng = np.random.default_rng(1)
    for _ in range(300):
        i, j = rng.integers(len(da)), rng.integers(len(db))
        rows.append(dict(pair=pair + ":random", jaccard=np.nan, bow_cos=cos(toks(da.text[i] or ""), toks(db.text[j] or ""))))
    print(pair, flush=True)
pd.DataFrame(rows).to_csv(dst, index=False)
