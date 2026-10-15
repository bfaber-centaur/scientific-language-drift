"""Lane D (v1.5 review): recount median tokens after the last references marker and the share of papers with a
statement heading after the references (600 seeded papers per year). Usage: python3 scripts/review_v15_appendix_recount.py"""
import sys,random,re; sys.path.insert(0,"/home/user/scientific-language-drift/src")
import pyarrow.parquet as pq, statistics as st
from mlngrams.sections import HEADING
from mlngrams.tokenize import tokenize
REF="⟦references omitted⟧"
AI=re.compile(r"\bai\b|llm|language model",re.I)
for y in [2017,2026,2027]:
    pf=pq.ParquetFile(f"/root/.cache/mlngrams/omissions/iclr-{y}.parquet"); n=pf.metadata.num_rows
    keep=set(random.Random(7+y).sample(range(n),min(600,n))); i=0; app=[]; st_after=[]; ai_after=[]
    for b in pf.iter_batches(batch_size=256,columns=["text"]):
        for r in b.to_pylist():
            if i in keep:
                t=r["text"]; l=t.rfind(REF)
                post=t[l+len(REF):] if l>=0 else ""
                app.append(sum(len(s) for s in tokenize(post)))
                hs=[m.group(0) for m in HEADING.finditer(post)]
                st_after.append(bool(hs)); ai_after.append(any(AI.search(h) for h in hs))
            i+=1
    print(y,"median tokens after last marker",st.median(app),"| any statement heading after refs %.3f | AI/LLM heading after refs %.3f"%(sum(st_after)/len(st_after),sum(ai_after)/len(ai_after)))
