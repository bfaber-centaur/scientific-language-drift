"""Lane D (v1.5 review): appendix growth within submission versions (published vs under review).

Usage: python3 scripts/review_v15_versions.py   (ICLR 2017/2020/2023/2025/2026 all papers; 2027 every 6th batch)
Version flags from results/paper_flags_iclr.csv (v1). Prints medians of PDF pages, main-body pages (page of the
first references marker), pages after the last references marker, and post-reference character share.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from mlngrams.load import fetch  # noqa: E402
import pyarrow.parquet as pq, pandas as pd
REF="⟦references omitted⟧"
fl=pd.read_csv(os.path.join(os.path.dirname(__file__), "..", "results", "paper_flags_iclr.csv")).set_index("pdf_sha256")
rows=[]
for y in [2017,2020,2023,2025,2026,2027]:
    pf=pq.ParquetFile(fetch("omissions", "iclr", y))
    for i,b in enumerate(pf.iter_batches(batch_size=256,columns=["pdf_sha256","text"])):
        if y==2027 and i%6: continue
        for r in b.to_pylist():
            t=r["text"]; f=t.find(REF); l=t.rfind(REF)
            if f<0: continue
            rows.append(dict(year=y,version=fl.version.get(r["pdf_sha256"],"?"),pages=t.count("\x0c")+1,app_pages=t.count("\x0c")-t[:l].count("\x0c"),body_pages=t[:f].count("\x0c")+1,share=1-f/len(t)))
df=pd.DataFrame(rows)
print(df.groupby(["version","year"]).agg(n=("pages","size"),pages=("pages","median"),body_pages=("body_pages","median"),app_pages=("app_pages","median"),share=("share","median")).round(3).to_string())
