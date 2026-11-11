from __future__ import annotations
import argparse,hashlib,json,sys
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
ROOT=Path(__file__).resolve().parents[1]
DISCOVERY=ROOT/'02_Data_and_Documents/top5_source_discovery.json'
OUT=ROOT/'02_Data_and_Documents/raw/annual_reports'

def session():
    s=requests.Session();retry=Retry(total=5,connect=5,read=5,status=5,backoff_factor=1.5,status_forcelist=(408,429,500,502,503,504),allowed_methods=frozenset(['GET']))
    adapter=HTTPAdapter(max_retries=retry,pool_connections=8,pool_maxsize=8);s.mount('https://',adapter);s.mount('http://',adapter)
    s.headers.update({'User-Agent':'Financial-Document-Research-Prototype/1.0 (public annual-report download)'})
    return s

def download(item,force=False):
    ticker=item['ticker'];fy=item['financial_year'];out_dir=OUT/ticker;out_dir.mkdir(parents=True,exist_ok=True)
    stem=f'{ticker}_{fy}';dest=out_dir/f'{stem}.pdf';meta_path=out_dir/f'{stem}.metadata.json';url=item['url']
    try:
        if force or not dest.exists() or dest.stat().st_size<100_000:
            part=dest.with_suffix('.pdf.part');http=session();expected=None;first=b''
            for attempt in range(1,9):
                offset=part.stat().st_size if part.exists() else 0
                headers={'Range':f'bytes={offset}-'} if offset else {}
                try:
                    with http.get(url,headers=headers,timeout=(30,180),stream=True,allow_redirects=True) as r:
                        if offset and r.status_code==200:
                            part.unlink(missing_ok=True);offset=0
                        r.raise_for_status();ctype=r.headers.get('content-type','').lower()
                        if offset and r.status_code!=206:raise ValueError(f'Expected HTTP 206 for resume, got {r.status_code}')
                        if not offset and r.status_code not in (200,206):raise ValueError(f'Unexpected HTTP {r.status_code}')
                        cr=r.headers.get('content-range','')
                        if cr.startswith('bytes ') and '/' in cr:expected=int(cr.split('/')[-1])
                        elif not offset and r.headers.get('content-length'):expected=int(r.headers['content-length'])
                        mode='ab' if offset else 'wb'
                        with part.open(mode) as f:
                            for block in r.iter_content(1024*1024):
                                if block:
                                    if not first:first=block[:1024]
                                    f.write(block);f.flush()
                    if expected and part.stat().st_size>=expected:break
                    if not expected and not part.stat().st_size<100_000:break
                except (requests.RequestException, OSError) as exc:
                    if attempt==8:raise
                    import time;time.sleep(min(2*attempt,10))
            size=part.stat().st_size if part.exists() else 0
            with part.open('rb') as f:first=f.read(1024)
            if not first.startswith(b'%PDF-'):
                part.unlink(missing_ok=True);raise ValueError(f'URL did not return PDF bytes (first bytes={first[:32]!r})')
            if size<100_000:raise ValueError(f'PDF response implausibly small: {size} bytes')
            if expected and size!=expected:raise ValueError(f'Incomplete PDF after retries: expected {expected} bytes, received {size}')
            part.replace(dest)
        import pymupdf
        doc=pymupdf.open(dest)
        if doc.page_count<2:raise ValueError(f'PDF has implausible page count: {doc.page_count}')
        page_count=doc.page_count
        front='\n'.join(doc.load_page(i).get_text() for i in range(min(3,doc.page_count)))[:12000]
        if not front.strip():raise ValueError('No extractable text in first pages; report needs OCR/manual review')
        page_hits={}
        needles=['independent auditor','consolidated balance sheet','consolidated statement of profit','statement of profit and loss','consolidated statement of cash','cash flow statement','consolidated statement of changes in equity','statement of changes in equity']
        for i in range(doc.page_count):
            text=' '.join(doc.load_page(i).get_text().lower().split())
            found=[k for k in needles if k in text]
            if found:page_hits[str(i+1)]=found
        doc.close()
        h=hashlib.sha256(dest.read_bytes()).hexdigest()
        prior=json.loads(meta_path.read_text()) if meta_path.exists() else {}
        same_hash=prior.get('file_hash')==h
        metadata={'document_id':f'{ticker}-{fy}','company':item['company'],'ticker':ticker,'financial_year':fy,'period_end':item['period_end'],'document_type':'Issuer annual/integrated report; consolidated statements pending review','source_url':url,'investor_relations_url':item['landing'],'publication_date':prior.get('publication_date','not confirmed') if same_hash else 'not confirmed','page_count':page_count,'status':prior.get('status','pending_review') if same_hash else 'pending_review','file_hash':h,'reporting_basis':prior.get('reporting_basis','to be confirmed from statement pages') if same_hash else 'to be confirmed from statement pages','currency':prior.get('currency','to be confirmed from statement pages') if same_hash else 'to be confirmed from statement pages','market_cap_rank':item['rank'],'market_cap_inr_crore':item.get('market_cap_inr_crore'),'market_cap_as_of':item.get('market_cap_as_of'),'selection_basis':'Top five full market capitalization among NIFTY 50 constituents','text_front_matter_excerpt':front[:1200],'statement_heading_candidate_pages':page_hits}
        for key in ('statement_review','statement_pages','reviewer','review_date'):
            if same_hash and key in prior:metadata[key]=prior[key]
        meta_path.write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
        return {'ticker':ticker,'financial_year':fy,'status':'downloaded_pending_review','path':str(dest),'bytes':dest.stat().st_size,'sha256':h,'page_count':metadata['page_count'],'http_url':url,'candidate_heading_pages':page_hits}
    except Exception as exc:
        dest.with_suffix('.pdf.part').unlink(missing_ok=True)
        return {'ticker':ticker,'financial_year':fy,'status':'failed','http_url':url,'error':f'{type(exc).__name__}: {exc}'}

def main():
    global OUT
    p=argparse.ArgumentParser(description='Download and validate public annual-report PDFs from the saved source manifest. Reports stay pending review until consolidated statements are confirmed.')
    p.add_argument('--workers',type=int,default=5);p.add_argument('--force',action='store_true');p.add_argument('--manifest',default=str(DISCOVERY));p.add_argument('--output',default=str(OUT));a=p.parse_args()
    OUT=Path(a.output)
    data=json.loads(Path(a.manifest).read_text());tasks=[]
    for company in data['companies']:
        for report in company['reports']:
            tasks.append({'rank':company['rank'],'company':company['company'],'ticker':company['ticker'],'landing':company['investor_relations'],'market_cap_inr_crore':company['market_cap_inr_crore'],'market_cap_as_of':company['market_cap_as_of'],'financial_year':report['financial_year'],'period_end':report['period_end'],'url':report['url']})
    results=[]
    with ThreadPoolExecutor(max_workers=max(1,min(a.workers,8))) as pool:
        futures=[pool.submit(download,x,a.force) for x in tasks]
        for f in as_completed(futures):
            r=f.result();results.append(r);print(f"{r['status']}: {r['ticker']} {r['financial_year']}"+(f" ({r.get('bytes',0):,} bytes)" if 'bytes' in r else f" — {r.get('error')}"),flush=True)
    results.sort(key=lambda x:(x['ticker'],x['financial_year']))
    summary={'selection_source':str(Path(a.manifest).resolve()),'requested_reports':len(tasks),'downloaded_pending_review':sum(r['status']=='downloaded_pending_review' for r in results),'failed':sum(r['status']=='failed' for r in results),'reports':results}
    status_path=ROOT/'02_Data_and_Documents/processed/download_status.json';status_path.parent.mkdir(parents=True,exist_ok=True)
    status_path.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='reports'},indent=2))
    return 0 if summary['failed']==0 else 1
if __name__=='__main__':raise SystemExit(main())
