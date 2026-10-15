"""Lane C (V2) sensitivity: do ethics/reproducibility/AI-use statements inside the body move the prose rates?

Seeded sample of 6 row groups per file (ICLR 2026, 2027). Rates with the prose region as counted (a) and
with the body cut at the first statement heading (b). Result recorded in docs/v2-function-words.md.
"""
import sys,random,re,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import pyarrow.parquet as pq
from lane_c_fetch import fetch
from lane_c_count import regions, measure, TOK
H=re.compile(r"^[ \t]*(?:[A-Z]?\d*\.?\s*)?(?:(?:ai|llm|large language models?)\s*(?:use|usage)?\s*(?:statement|disclosure|declaration)|use of (?:ai|large language models|llms)|ethics statement|reproducibility statement|statement on (?:the )?use|llm usage|declaration of (?:llm|ai))\b.*$",re.I|re.M)
for stem in ['iclr-2026','iclr-2027']:
    pf=pq.ParquetFile(fetch(f'clean/{stem}.parquet'))
    rng=random.Random(7); rgs=sorted(rng.sample(range(pf.num_row_groups),min(6,pf.num_row_groups)))
    tot={'a':[0,0,0,0,0],'b':[0,0,0,0,0]}; nh=0;n=0
    for g in rgs:
        for t in pf.read_row_group(g,columns=['text']).column(0).to_pylist():
            b=regions(t)['prose']
            if not b: continue
            n+=1
            body=regions(t)['body']; m=H.search(body)
            cut=body[:m.start()] if m else body
            if m: nh+=1
            # prose filter on cut
            lines=[ln for ln in cut.split('\n') if (lambda ns: ns and sum(c.isalpha() for c in ns)/len(ns)>=0.85)(re.sub(r'\s','',ln)) and len(TOK.findall(ln))>=12]
            for k,txt in (('a',b),('b','\n'.join(lines))):
                mm=measure(txt); 
                for i,w in enumerate(['tokens','of','in','we','and']): tot[k][i]+=mm[w]
    print(stem,n,'with statement heading in body',nh, {k:[round(v[i]/v[0]*1e6) for i in range(1,5)] for k,v in tot.items()})
