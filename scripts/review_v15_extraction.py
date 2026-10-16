"""Lane D (v1.5 review): is the length growth an extraction artifact? Pages from the raw PDF text layer.

Usage: python3 scripts/review_v15_extraction.py   (ICLR 2017/2020/2023/2025/2026 all papers; 2027 every 6th batch)

Joins omissions and direct configs on pdf_sha256. Per paper: PDF pages (direct `pages`), page of the first and
last references marker in the omissions text (form feeds), main-body / post-reference characters, omission
markers per page, and the omissions/clean character ratio. Writes results/review/extraction_pages_iclr.csv.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from mlngrams.load import fetch  # noqa: E402
import pyarrow.parquet as pq, pandas as pd, json, random
REF="⟦references omitted⟧"
rows=[]
for y in [2017,2020,2023,2025,2026,2027]:
    pf=pq.ParquetFile(fetch("direct", "iclr", y))
    d={}
    for b in pf.iter_batches(batch_size=512,columns=["pdf_sha256","pages","text"]):
        for r in b.to_pylist(): d[r["pdf_sha256"]]=(r["pages"],len(r["text"] or ""))
    pf=pq.ParquetFile(fetch("omissions", "iclr", y))
    for i,b in enumerate(pf.iter_batches(batch_size=256,columns=["pdf_sha256","text","omission_counts_json","chars_clean","chars_after"])):
        if y==2027 and i%6: continue
        for r in b.to_pylist():
            t=r["text"]; f=t.find(REF)
            if f<0: continue
            dp,dc=d.get(r["pdf_sha256"],(None,None))
            oc=json.loads(r["omission_counts_json"] or "{}")
            pre=t[:f]; post=t[f:]
            rows.append(dict(year=y,dpages=dp,dchars=dc,opages=t.count("\x0c")+1,refpage=pre.count("\x0c")+1,lastref=t[:t.rfind(REF)].count("\x0c")+1,
              pre=len(pre),post=len(post),ratio=r["chars_after"]/r["chars_clean"],
              mk_pre=pre.count("⟦")-0, mk_post=post.count("⟦")-post.count(REF),
              tab_pre=pre.count("⟦table omitted⟧"),tab_post=post.count("⟦table omitted⟧")))
df=pd.DataFrame(rows)
df["page_agree"]=df.dpages==df.opages
df["post_pages"]=df.dpages-df.refpage; df["ref_pages"]=df.lastref-df.refpage+1; df["app_pages"]=df.dpages-df.lastref
df["pre_cpp"]=df.pre/df.refpage
df["post_cpp"]=df.post/df.post_pages.where(df.post_pages>0)
g=df.groupby("year")
out=pd.DataFrame({"n":g.size(),"page_agree":g.page_agree.mean(),"dpages_med":g.dpages.median(),"refpage_med":g.refpage.median(),
 "post_pages_med":g.post_pages.median(),"ref_pages_med":g.ref_pages.median(),"app_pages_med":g.app_pages.median(),"app_pages_p25":g.app_pages.quantile(.25),"app_pages_p75":g.app_pages.quantile(.75),"app_pages_p90":g.app_pages.quantile(.9),"post_pages_p90":g.post_pages.quantile(.9),"pre_chars_med":g.pre.median(),"post_chars_med":g.post.median(),
 "pre_chars_per_page":g.pre_cpp.median(),"post_chars_per_page":g.post_cpp.median(),"ratio_med":g.ratio.median(),
 "markers_per_postpage":(g.mk_post.sum()/g.post_pages.sum()),"markers_per_prepage":(g.mk_pre.sum()/g.refpage.sum()),
 "tables_post_per_paper":g.tab_post.mean()})
pd.set_option("display.width",250); print(out.round(3).T.to_string())
out.round(4).to_csv(os.path.join(os.path.dirname(__file__), "..", "results", "review", "extraction_pages_iclr.csv"))
