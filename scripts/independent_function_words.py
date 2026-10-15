#!/usr/bin/env python3
"""Independent source-record recount. Never imports the research pipeline.

Raw token rule: ASCII letter runs OR digit runs; lowercase, no sentence rules,
Unicode normalization, citation removal, dehyphenation, or disclosure removal.
Primary denominator includes both kinds of token. Alphabetic-only rates also saved.
"""
import argparse, collections, hashlib, json, pathlib, platform, random, re
import urllib.request, concurrent.futures
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

REV = 'cb5553e0c192c31c562a2822668c7f4ebbb9437a'
SEED = 20261014
WORDS = 'of in we and the a to for with on by that is are'.split()
# Explicit frozen list; not imported from the project's filter or NLTK.
STOP = set('a an the and or but if while as until because of at by for with about against between into through during before after above below to from up down in out on off over under again further then once here there when where why how all any both each few more most other some such no nor not only own same so than too very s t can will just don should now i me my myself we our ours ourselves you your yours yourself yourselves he him his himself she her hers herself it its itself they them their theirs themselves what which who whom this that these those am is are was were be been being have has had having do does did doing'.split())
TOKEN = re.compile(r'[A-Za-z]+|[0-9]+')

def metrics(text):
    tokens = TOKEN.findall(text.lower()); n = len(tokens)
    alpha = [t for t in tokens if t.isalpha()]; na = len(alpha)
    counts = collections.Counter(tokens)
    out = dict(tokens=n, alphabetic_tokens=na,
               alphabetic_fraction=na/n if n else np.nan,
               mean_token_length=np.mean([len(t) for t in tokens]) if n else np.nan,
               mean_alpha_length=np.mean([len(t) for t in alpha]) if na else np.nan,
               stop_fraction=sum(counts[w] for w in STOP)/n if n else np.nan)
    for w in WORDS:
        out[w+'_count']=counts[w]
        out[w+'_pm']=1e6*counts[w]/n if n else np.nan
        out[w+'_alpha_pm']=1e6*counts[w]/na if na else np.nan
    return out

def boundaries(text):
    # Line-anchored headings only, accepting PDF small caps with spaces.
    def find(pattern,start=0):
        return re.search(pattern,text[start:],re.M|re.I)
    abs_m=find(r'^[ \t]*A\s*B\s*S\s*T\s*R\s*A\s*C\s*T[ \t]*\r?$')
    intro=find(r'^[ \t]*(?:1[. ]*[\r\n \t]*)?I\s*N\s*T\s*R\s*O\s*D\s*U\s*C\s*T\s*I\s*O\s*N[ \t]*\r?$')
    refs=find(r'^[ \t]*(?:[0-9]+[. ]*[\r\n \t]*)?(?:R\s*E\s*F\s*E\s*R\s*E\s*N\s*C\s*E\s*S|BIBLIOGRAPHY)[ \t]*\r?$')
    marker=text.find('⟦references omitted⟧')
    rstart=refs.start() if refs else (marker if marker>=0 else None)
    rend=refs.end() if refs else (marker+len('⟦references omitted⟧') if marker>=0 else None)
    out={'full':(0,len(text))}
    if abs_m and intro and 100 <= intro.start()-abs_m.end() <= 10000:
        out['abstract']=(abs_m.end(),intro.start())
    if intro:
        # Require top-level section 2 and a short heading line, not decimal math.
        tail=text[intro.end():]
        # Do not mistake a contribution list item "2. We ..." for section 2.
        sec=re.search(r'(?m)^[ \t]*2[ \t]*\r?\n[ \t]*([A-Za-z][^\n]{2,100})[ \t]*$|^[ \t]*2[ \t]+([A-Z][A-Z &:/()\-]{2,100})[ \t]*$',tail)
        if sec and 300 <= sec.start() <= 20000:
            out['introduction']=(intro.end(),intro.end()+sec.start())
        # A fixed token window is a separately labelled boundary sensitivity.
        ts=list(TOKEN.finditer(tail))
        if len(ts)>=500:out['intro_first500']=(intro.end(),intro.end()+ts[499].end())
    if rstart is not None and rstart>1000:
        out['pre_reference']=(0,rstart)
        # Post-reference means after the heading/first omission marker, NOT appendix.
        out['post_reference']=(rend,len(text))
        if 'introduction' in out and out['introduction'][1]<rstart:
            out['main_after_intro']=(out['introduction'][1],rstart)
    return out

def fetch(config,year,cache,revision):
    p=cache/revision/config/f'iclr-{year}.parquet'
    u=f'https://huggingface.co/datasets/woog/open-text-detector-papers/resolve/{revision}/{config}/iclr-{year}.parquet'
    p.parent.mkdir(parents=True,exist_ok=True)
    if not p.exists():
        with urllib.request.urlopen(u,timeout=180) as r,open(str(p)+'.part','wb') as f:
            while chunk:=r.read(4*1024*1024):f.write(chunk)
        pathlib.Path(str(p)+'.part').replace(p)
    return p,u

def run(a):
    a.out.mkdir(parents=True,exist_ok=True)
    manifest=dict(source_repository_base='ccfd54fb4d2731d715c0f5f350e02ed2fab9f434',
                  dataset_revision=a.revision,seed=a.seed,n_requested=a.n,
                  sampling='random.Random(seed+year).sample over sorted unique (paper_id,pdf_sha256), no exclusions',
                  token_pattern=TOKEN.pattern,stopwords=sorted(STOP),python=platform.python_version(),
                  files=[],samples=[],regions=[])
    rows=[]
    for year in a.years:
        path,url=fetch('direct',year,a.cache,a.revision)
        ids=pq.read_table(path,columns=['paper_id','pdf_sha256']).to_pylist()
        pairs=sorted(set((r['paper_id'],r['pdf_sha256']) for r in ids))
        selected=random.Random(a.seed+year).sample(pairs,min(a.n,len(pairs)))
        hashes={h for _,h in selected}
        manifest['samples'] += [dict(year=year,paper_id=p,pdf_sha256=h,sample_order=i) for i,(p,h) in enumerate(selected)]
        for config in ['direct','clean','omissions']:
            path,url=fetch(config,year,a.cache,a.revision)
            pf=pq.ParquetFile(path)
            manifest['files'].append(dict(year=year,config=config,url=url,bytes=path.stat().st_size,
                sha256=hashlib.file_digest(open(path,'rb'),'sha256').hexdigest(),rows=pf.metadata.num_rows))
            found=0
            for batch in pf.iter_batches(batch_size=128):
                for r in batch.to_pylist():
                    if r['pdf_sha256'] not in hashes:continue
                    found+=1;t=r.get('text') or ''
                    p=a.cache/'sample_text'/str(year)/config/(r['pdf_sha256']+'.txt')
                    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(t)
                    head=t[:2500].lower()
                    version='under_review' if 'under review as a conference paper' in head else ('published' if 'published as a conference paper' in head else 'unknown')
                    base=dict(year=year,config=config,paper_id=r['paper_id'],pdf_sha256=r['pdf_sha256'],version=version,
                              text_sha256=hashlib.sha256(t.encode()).hexdigest(),source_text_sha256=r.get('text_sha256'),
                              pages=r.get('pages',t.count('\f')+1),method=r.get('method'),title=r.get('title'),
                              marker_count=len(re.findall('⟦[^⟧]*⟧',t)))
                    for region,(lo,hi) in boundaries(t).items():
                        rows.append(dict(**base,region=region,start=lo,end=hi,**metrics(t[lo:hi])))
                    manifest['regions'].append(dict(year=year,config=config,pdf_sha256=r['pdf_sha256'],bounds=boundaries(t)))
            print(year,config,'sample rows',found,flush=True)
            assert found==len(selected),(year,config,found,len(selected))
    pd.DataFrame(rows).to_csv(a.out/'paper_metrics.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    (a.out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    summarize(a)

def summarize(a):
    df=pd.read_csv(a.out/'paper_metrics.csv.gz');out=[]
    measures=[w+'_pm' for w in WORDS]+['tokens','mean_token_length','mean_alpha_length','stop_fraction','alphabetic_fraction']
    for key,g in df.groupby(['year','config','region'],sort=True):
        rng=np.random.default_rng(a.seed+key[0]);idx=rng.integers(0,len(g),size=(2000,len(g)))
        for m in measures:
            v=g[m].to_numpy();vboot=v[idx]
            mean_ci=np.nanquantile(np.nanmean(vboot,axis=1),[.025,.975]);med_ci=np.nanquantile(np.nanmedian(vboot,axis=1),[.025,.975])
            pooled=1e6*g[m.replace('_pm','_count')].sum()/g.tokens.sum() if m.endswith('_pm') else np.nan
            out.append(dict(year=key[0],config=key[1],region=key[2],metric=m,n=len(g),mean=np.nanmean(v),median=np.nanmedian(v),mean_lo=mean_ci[0],mean_hi=mean_ci[1],median_lo=med_ci[0],median_hi=med_ci[1],pooled=pooled))
    pd.DataFrame(out).to_csv(a.out/'summary.csv',index=False)

def resegment(a):
    old=pd.read_csv(a.out/'paper_metrics.csv.gz');rows=[]
    manifest=json.loads((a.out/'manifest.json').read_text());manifest['regions']=[]
    meta=['year','config','paper_id','pdf_sha256','version','text_sha256','source_text_sha256','pages','method','title','marker_count']
    for r in old[old.region=='full'][meta].to_dict('records'):
        t=(a.cache/'sample_text'/str(r['year'])/r['config']/(r['pdf_sha256']+'.txt')).read_text()
        b=boundaries(t)
        for region,(lo,hi) in b.items():rows.append(dict(**r,region=region,start=lo,end=hi,**metrics(t[lo:hi])))
        manifest['regions'].append(dict(year=r['year'],config=r['config'],pdf_sha256=r['pdf_sha256'],bounds=b))
    pd.DataFrame(rows).to_csv(a.out/'paper_metrics.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    (a.out/'manifest.json').write_text(json.dumps(manifest,indent=2));summarize(a)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cache',type=pathlib.Path,default=pathlib.Path('data/independent'))
    p.add_argument('--out',type=pathlib.Path,default=pathlib.Path('results/independent_function_words'))
    p.add_argument('--revision',default=REV);p.add_argument('--seed',type=int,default=SEED)
    p.add_argument('--n',type=int,default=240);p.add_argument('--years',type=int,nargs='+',default=[2024,2026,2027])
    p.add_argument('--summarize-only',action='store_true');p.add_argument('--resegment',action='store_true');a=p.parse_args()
    resegment(a) if a.resegment else (summarize(a) if a.summarize_only else run(a))
