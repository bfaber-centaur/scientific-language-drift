"""Lane D (v1.5 review): main-body tokens removed as statement sections, by year (400 seeded papers per year).
Usage: python3 scripts/review_v15_statement_tokens.py (reads ~/.cache/mlngrams/omissions)."""
import sys,random; sys.path.insert(0,"/home/user/scientific-language-drift/src")
import pyarrow.parquet as pq, statistics as st
from mlngrams.load import main_body
from mlngrams.sections import strip_statements
from mlngrams.tokenize import tokenize
for y in [2017,2020,2023,2024,2025,2026,2027]:
    pf=pq.ParquetFile(f"/root/.cache/mlngrams/omissions/iclr-{y}.parquet"); n=pf.metadata.num_rows
    keep=set(random.Random(y).sample(range(n),min(400,n))); i=0; rem=[]; tok_full=[]; tok_cut=[]; pre=[]
    for b in pf.iter_batches(batch_size=256,columns=["text"]):
        for r in b.to_pylist():
            if i in keep:
                body=main_body(r["text"]); cut,k=strip_statements(body)
                a=sum(len(s) for s in tokenize(body)); c=sum(len(s) for s in tokenize(cut))
                tok_full.append(a); tok_cut.append(c); rem.append(a-c)
            i+=1
    print(y, "body tokens med %d | after statement cut %d | removed med %d mean %d | papers with >0 removed %.2f"%(st.median(tok_full),st.median(tok_cut),st.median(rem),st.mean(rem),sum(x>0 for x in rem)/len(rem)))
