#!/usr/bin/env python3
"""Download public PDFs for first ten randomized sample entries per year.
Check original OpenReview endpoint and content-addressed public archive; verify
bytes against dataset PDF hashes. Extract with MuPDF and plain Poppler.
"""
import argparse,concurrent.futures,hashlib,json,pathlib,subprocess,urllib.request
import fitz
import pandas as pd
from independent_function_words import metrics,boundaries

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=pathlib.Path,default=pathlib.Path('data/independent'))
    p.add_argument('--out',type=pathlib.Path,default=pathlib.Path('results/independent_function_words'))
    p.add_argument('--n',type=int,default=10);p.add_argument('--offline',action='store_true');a=p.parse_args()
    manifest=json.loads((a.out/'manifest.json').read_text())
    sample=[r for r in manifest['samples'] if r['sample_order']<a.n]
    a.root.joinpath('pdfs').mkdir(exist_ok=True)
    def get(r):
        h=r['pdf_sha256'];dest=a.root/'pdfs'/f'{h}.pdf';receipt=dict(r,attempts=[])
        if dest.exists():
            assert hashlib.sha256(dest.read_bytes()).hexdigest()==h,'Local PDF hash mismatch'
            receipt.update(matched=True,matched_url='local hash-verified PDF');return receipt
        if a.offline:
            receipt.update(matched=False,reason='Not present locally');return receipt
        urls=[f'https://openreview.net/pdf?id={r["paper_id"]}',f'https://opentextdetector.com/backend/v1/pdf-reader/{h[:24]}/file']
        for url in urls:
            try:
                raw=urllib.request.urlopen(url,timeout=90).read()
                digest=hashlib.sha256(raw).hexdigest()
                receipt['attempts'].append(dict(url=url,sha256=digest,bytes=len(raw),matches=digest==h))
                if digest==h:dest.write_bytes(raw);receipt['matched_url']=url;break
                # Preserve independently fetched mismatched source for provenance checks.
                if raw.startswith(b'%PDF'):dest.with_name(h+'-unmatched.pdf').write_bytes(raw)
            except Exception as e:receipt['attempts'].append(dict(url=url,error=str(e)))
        receipt['matched']=dest.exists()
        print(r['year'],r['paper_id'],receipt['matched'],flush=True)
        return receipt
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:receipts=list(pool.map(get,sample))
    (a.out/'pdf_manifest.json').write_text(json.dumps(dict(mupdf=fitz.VersionBind,poppler=subprocess.run(['pdftotext','-v'],capture_output=True,text=True).stderr,receipts=receipts),indent=2))
    rows=[]
    for r in receipts:
        if not r['matched']:continue
        h=r['pdf_sha256'];f=a.root/'pdfs'/f'{h}.pdf'
        doc=fitz.open(f)
        mupdf='\f'.join(page.get_text(sort=True) for page in doc)
        poppler=subprocess.run(['pdftotext','-enc','UTF-8',str(f),'-'],capture_output=True,check=True).stdout.decode()
        for method,text in [('mupdf',mupdf),('poppler_plain',poppler)]:
            (a.root/'pdfs'/f'{h}-{method}.txt').write_text(text)
            for region,(lo,hi) in boundaries(text).items():
                rows.append(dict(year=r['year'],paper_id=r['paper_id'],pdf_sha256=h,config=method,region=region,**metrics(text[lo:hi])))
        doc[0].get_pixmap(matrix=fitz.Matrix(1.2,1.2)).save(str(a.root/'pdfs'/f'{h}-page1.png'))
    frame=pd.DataFrame(rows) if rows else pd.DataFrame(columns=['year','paper_id','pdf_sha256','config','region',*metrics('').keys()])
    frame.to_csv(a.out/'pdf_metrics.csv',index=False)

if __name__=='__main__':main()
