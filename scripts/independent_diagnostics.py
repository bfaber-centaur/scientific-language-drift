#!/usr/bin/env python3
"""Figures and bounded sensitivity checks for the independent recount."""
import collections,hashlib,importlib.util,json,pathlib,re,sys,tempfile
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator,FuncFormatter
from independent_function_words import WORDS,SEED,metrics,boundaries

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'results/independent_function_words'
DATA=ROOT/'data/independent/sample_text'
COLORS=['#0072B2','#D55E00','#009E73'];YEARS=[2024,2026,2027]

def ratio_ci(a,b,pooled=False):
    rng=np.random.default_rng(SEED)
    ia=rng.integers(0,len(a),size=(2000,len(a)));ib=rng.integers(0,len(b),size=(2000,len(b)))
    if pooled:
        av=a[:,0].sum()/a[:,1].sum();bv=b[:,0].sum()/b[:,1].sum()
        rr=(b[ib,0].sum(1)/b[ib,1].sum(1))/(a[ia,0].sum(1)/a[ia,1].sum(1))-1
    else:
        av=np.mean(a);bv=np.mean(b);rr=b[ib].mean(1)/a[ia].mean(1)-1
    return (bv/av-1)*100,*list(np.quantile(rr,[.025,.975])*100)

def save(fig,name):
    fig.savefig(OUT/(name+'.png'),dpi=180,facecolor='white')
    svg=OUT/(name+'.svg');fig.savefig(svg,facecolor='white')
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
    plt.close(fig)

def main():
    d=pd.read_csv(OUT/'paper_metrics.csv.gz');s=pd.read_csv(OUT/'summary.csv')
    full=d[d.region=='full'];versions=full[full.config=='direct'][['year','pdf_sha256','version','method']]
    # Figure 1: all papers, no density smoothing, direct labels and redundant line styles.
    fig,axs=plt.subplots(2,3,figsize=(12,7),layout='constrained')
    for ax,m in zip(axs.flat,['of_pm','in_pm','we_pm','and_pm','stop_fraction','mean_alpha_length']):
        for y,c,ls in zip(YEARS,COLORS,['-','--',':']):
            v=np.sort(d[(d.year==y)&(d.config=='omissions')&(d.region=='pre_reference')][m])
            ax.step(v,np.arange(1,len(v)+1)/len(v),where='post',color=c,ls=ls,label=f'{y} (n={len(v)})')
        ax.set(xlabel=m.replace('_pm',' / million tokens').replace('_',' '),ylabel='Fraction of papers',ylim=(0,1));ax.grid(alpha=.2)
        ax.xaxis.set_major_locator(MaxNLocator(4))
        if m.endswith('_pm'):ax.xaxis.set_major_formatter(FuncFormatter(lambda x,pos:f'{x/1000:g}k'))
    axs[0,0].legend(fontsize=8)
    fig.suptitle('Independent per-paper distributions — supplied omissions text, before references')
    save(fig,'fig1_distributions')
    # Figure 2: comparable regions, means with paper bootstrap intervals.
    regs=['abstract','introduction','main_after_intro','post_reference'];labels=['Abstract','Introduction','After intro / before refs','Post-reference material']
    fig,axs=plt.subplots(1,4,figsize=(13,4.2),layout='constrained',sharey=True)
    for ax,reg,label in zip(axs,regs,labels):
        for j,(y,c,mk) in enumerate(zip(YEARS,COLORS,['o','s','^'])):
            r=s[(s.year==y)&(s.config=='clean')&(s.region==reg)&(s.metric=='of_pm')].iloc[0]
            ax.errorbar(j,r['mean']/1e4,yerr=[[max(0,r['mean']-r.mean_lo)/1e4],[max(0,r.mean_hi-r['mean'])/1e4]],fmt=mk,color=c,capsize=4)
            ax.text(j,r.mean_hi/1e4+.08,f'n={int(r.n)}',ha='center',fontsize=8)
        ax.set(title=label,xticks=range(3),xticklabels=YEARS,ylim=(0,3.3),xlim=(-.4,2.4));ax.grid(axis='y',alpha=.2)
    axs[0].set_ylabel('Mean “of” as % of letter-or-digit tokens')
    fig.suptitle('The shift survives abstracts and introductions (clean corpus text; 95% bootstrap CI)')
    save(fig,'fig2_regions')
    # Figure 3: same-paper intersection, different supplied text configurations / denominators.
    fig,axs=plt.subplots(1,2,figsize=(10,4.3),layout='constrained')
    for ax,m,title in zip(axs,['of_pm','of_alpha_pm'],['Letters + digits denominator','Letters-only denominator']):
        for j,config in enumerate(['direct','clean','omissions']):
            vals=[]
            for y in YEARS:
                sub=d[(d.year==y)&(d.region=='abstract')]
                common=set.intersection(*(set(sub[sub.config==c].pdf_sha256) for c in ['direct','clean','omissions']))
                g=sub[(sub.config==config)&sub.pdf_sha256.isin(common)];vals.append(g[m].mean()/1e4)
            ax.plot(YEARS,vals,marker=['o','s','^'][j],ls=['-','--',':'][j],label=config)
        ax.set(title=title,xticks=YEARS,ylim=(0,3.2),ylabel='Mean abstract “of” (%)');ax.grid(alpha=.2);ax.legend()
    fig.suptitle('Digit dilution is real, but does not explain the decline')
    save(fig,'fig3_config_denominators')
    # Numerical comparisons and sampling CIs, no hypothesis-probability estimates.
    original=pd.read_csv(ROOT/'results/full/body/top100_n1_raw_by_year.csv');comparisons=[]
    for w in WORDS:
        g=d[(d.config=='omissions')&(d.region=='pre_reference')]
        a=g[g.year==2024][[w+'_count','tokens']].to_numpy();b=g[g.year==2027][[w+'_count','tokens']].to_numpy()
        change,lo,hi=ratio_ci(a,b,True)
        o=original[original.ngram==w].set_index('year').per_million
        comparisons.append(dict(word=w,project_2024=o.get(2024),project_2027=o.get(2027),project_change_pct=100*(o.get(2027)/o.get(2024)-1),
            independent_2024=1e6*a[:,0].sum()/a[:,1].sum(),independent_2027=1e6*b[:,0].sum()/b[:,1].sum(),change_pct=change,ci_lo=lo,ci_hi=hi))
    comp=pd.DataFrame(comparisons);comp.to_csv(OUT/'project_comparison.csv',index=False)
    fig,ax=plt.subplots(figsize=(8,5),layout='constrained')
    ax.errorbar(comp.change_pct,np.arange(len(comp)),xerr=[comp.change_pct-comp.ci_lo,comp.ci_hi-comp.change_pct],fmt='o',color='#0072B2',capsize=3,label='Independent sample; 95% paper bootstrap CI')
    ax.scatter(comp.project_change_pct,np.arange(len(comp)),marker='x',color='#D55E00',label='Original project table')
    ax.set(yticks=range(len(comp)),yticklabels=comp.word,xlabel='2024 → 2027 relative change in pooled token frequency (%)');ax.axvline(0,color='gray',lw=1);ax.invert_yaxis();ax.legend(fontsize=8);ax.grid(axis='x',alpha=.2)
    ax.set_title('Independent recount agrees with the project’s main frequency shifts')
    save(fig,'fig4_project_comparison')
    # Exploratory composition checks; no claim these establish exchangeable populations.
    clean=d[d.config=='clean'].drop(columns=['version','method']).merge(versions,on=['year','pdf_sha256'],validate='many_to_one')
    clean['title_language_agent']=clean.title.fillna('').str.contains(r'language|\bllms?\b|reasoning|agent|prompt|retrieval',case=False,regex=True)
    lens=clean[clean.region=='full'][['year','pdf_sha256','tokens']].rename(columns={'tokens':'full_tokens'})
    clean=clean.merge(lens,on=['year','pdf_sha256'],validate='many_to_one')
    sens=[]
    for reg in ['abstract','introduction','pre_reference']:
        g=clean[clean.region==reg]
        masks={'all':np.ones(len(g),bool),'under_review':g.version=='under_review','native_only':g.method=='poppler-bbox-layout',
               'title_language_agent':g.title_language_agent,'other_titles':~g.title_language_agent,
               'full_under_12000_tokens':g.full_tokens<12000,'full_at_least_12000_tokens':g.full_tokens>=12000}
        if reg=='abstract':masks['abstract_150_to_250_tokens']=g.tokens.between(150,250)
        for label,mask in masks.items():
            sub=g[mask]
            for y,h in sub.groupby('year'):
                sens.append(dict(region=reg,control=label,year=y,n=len(h),of_pm=h.of_pm.mean(),in_pm=h.in_pm.mean(),we_pm=h.we_pm.mean(),and_pm=h.and_pm.mean(),tokens=h.tokens.mean()))
    pd.DataFrame(sens).to_csv(OUT/'composition_checks.csv',index=False)
    # Actual line-number and removal diagnostics (counts, not explanations by assertion).
    diag=[]
    for r in full.to_dict('records'):
        t=(DATA/str(r['year'])/r['config']/(r['pdf_sha256']+'.txt')).read_text()
        nonempty=[ln.strip() for ln in t.splitlines() if ln.strip()]
        labels=re.findall(r'⟦([^⟧]*)⟧',t)
        no_markers=re.sub(r'⟦[^⟧]*⟧',' ',t)
        diag.append(dict(year=r['year'],config=r['config'],paper_id=r['paper_id'],pdf_sha256=r['pdf_sha256'],
            standalone_3plus_digit_lines=sum(bool(re.fullmatch(r'\d{3,}',ln)) for ln in nonempty),nonempty_lines=len(nonempty),
            marker_tokens=sum(len(re.findall(r'[A-Za-z]+|[0-9]+',x)) for x in labels),marker_count=len(labels),
            of_pm_without_marker_labels=metrics(no_markers)['of_pm']))
    pd.DataFrame(diag).to_csv(OUT/'extraction_diagnostics.csv',index=False)
    pairs=full.pivot(index=['year','pdf_sha256'],columns='config',values=[w+'_count' for w in WORDS]);ret=[]
    for y in YEARS:
        g=pairs.loc[y]
        for w in WORDS:
            v=g[w+'_count'];ret.append(dict(year=y,word=w,direct=int(v.direct.sum()),clean=int(v.clean.sum()),omissions=int(v.omissions.sum()),clean_to_direct=v.clean.sum()/v.direct.sum(),omissions_to_clean=v.omissions.sum()/v.clean.sum()))
    pd.DataFrame(ret).to_csv(OUT/'word_retention.csv',index=False)
    # Provenance MRE: revision not part of the ORIGINAL loader's cache key.
    spec=importlib.util.spec_from_file_location('original_loader_for_mre_only',ROOT/'src/mlngrams/load.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    with tempfile.TemporaryDirectory() as td:
        mod.CACHE_DIR=td;p=pathlib.Path(td)/'direct/iclr-2024.parquet';p.parent.mkdir();p.write_bytes(b'cached bytes from revision A')
        got=mod.fetch('direct','iclr',2024,revision='revision-B')
        result=dict(test='original_loader_revision_cache_collision',requested_revision='revision-B',returned_bytes=pathlib.Path(got).read_text(),network_required=False,reproduced=True,
                    implication='Existing cache bypasses revision; no evidence this caused published shift. Independent cache is revision-keyed.')
    (OUT/'cache_revision_mre.json').write_text(json.dumps(result,indent=2))
    (OUT/'figure_provenance.json').write_text(json.dumps(dict(data='paper_metrics.csv.gz',sha256=hashlib.file_digest(open(OUT/'paper_metrics.csv.gz','rb'),'sha256').hexdigest(),sampling_seed=SEED,bootstrap_seed=SEED,bootstrap_replicates=2000,interval='pointwise 95% percentile paper bootstrap; no finite-population correction or multiplicity adjustment',matplotlib=matplotlib.__version__,numpy=np.__version__,pandas=pd.__version__),indent=2))

if __name__=='__main__':main()
