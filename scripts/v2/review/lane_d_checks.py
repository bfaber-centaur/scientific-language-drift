"""Lane E E9: independent rough checks of two Lane D headline numbers (no mlngrams, no Lane D code).
(a) median share of `omissions` characters after the first / after the last "⟦references omitted⟧";
(b) share of papers with a heading-like line (<= 90 chars, no sentence-final period) naming an LLM/AI tool
    and a use/disclosure word, anywhere in the text.
Usage: python3 -I lane_d_checks.py REC STORE OUT.csv iclr-2017 iclr-2026 ..."""
import os, re, sys
import numpy as np, pandas as pd, pyarrow.parquet as pq
REF = "⟦references omitted⟧"
HEAD = re.compile(r"^[^\n]{0,90}$", re.M)
TOOL = re.compile(r"\b(llms?|large language models?|generative ai|ai[- ]assist\w*|language models?|ai tools?|chatgpt)\b", re.I)
USE = re.compile(r"\b(use|usage|used|using|disclosure|statement|assistance|declaration|contribution|policy)\b", re.I)
rec, store, dst = sys.argv[1:4]
L = pd.read_csv(os.path.join(rec, "listing.csv")); L = L[L.rev.str.startswith("2c0dd19")]
rows = []
for stem in sys.argv[4:]:
    lfs = L[L.path == f"omissions/{stem}.parquet"].lfs.iloc[0]
    first, last, head, n = [], [], 0, 0
    for b in pq.ParquetFile(os.path.join(store, lfs + ".parquet")).iter_batches(256, columns=["text"]):
        for t in b.column(0).to_pylist():
            t = t or ""
            if len(t) < 2000:
                continue
            n += 1
            i, j = t.find(REF), t.rfind(REF)
            first.append(0.0 if i < 0 else (len(t) - i - len(REF)) / len(t))
            last.append(0.0 if j < 0 else (len(t) - j - len(REF)) / len(t))
            if any(TOOL.search(h) and USE.search(h) and not h.rstrip().endswith(".") and len(h.split()) <= 10
                   for h in HEAD.findall(t)):
                head += 1
    rows.append(dict(file=stem, n=n, median_share_after_first_ref=round(float(np.median(first)), 3),
                     median_share_after_last_ref=round(float(np.median(last)), 3),
                     pct_with_llm_use_heading=round(100 * head / n, 1)))
    print(rows[-1], flush=True)
pd.DataFrame(rows).to_csv(dst, index=False)
