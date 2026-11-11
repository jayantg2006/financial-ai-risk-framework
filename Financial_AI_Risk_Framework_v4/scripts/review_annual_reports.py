from __future__ import annotations
import json,re,sys
from pathlib import Path
import pymupdf
ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'02_Data_and_Documents/top5_source_discovery.json'
PDF_ROOT=ROOT/'02_Data_and_Documents/raw/annual_reports'
OUT=ROOT/'02_Data_and_Documents/processed/report_review_candidates.json'
TERMS={
 'auditor_report':['independent auditor','independent auditors','auditor’s report','auditor\'s report'],
 'consolidated_balance_sheet':['consolidated balance sheet','balance sheet as at'],
 'consolidated_profit_loss':['consolidated statement of profit and loss','statement of profit and loss','consolidated income statement'],
 'consolidated_cash_flows':['consolidated statement of cash flows','statement of cash flows','cash flow statement'],
 'consolidated_changes_in_equity':['consolidated statement of changes in equity','statement of changes in equity','changes in equity'],
 'consolidated_notes':['notes to the consolidated financial statements','notes to consolidated financial statements']}
def main():
 data=json.loads(MANIFEST.read_text());results=[]
 for company in data['companies']:
  for report in company['reports']:
   ticker=company['ticker'];fy=report['financial_year'];pdf=PDF_ROOT/ticker/f'{ticker}_{fy}.pdf'
   item={'company':company['company'],'ticker':ticker,'financial_year':fy,'period_end':report['period_end'],'source_url':report['url'],'pdf_path':str(pdf),'status':'not_reviewed','physical_page_count':None,'first_pages_excerpt':'','identity_hits':[],'financial_year_hits':[],'consolidated_word_occurrences':0,'candidate_statement_pages':{k:[] for k in TERMS},'text_extraction_pages':0,'empty_text_pages':[],'review_notes':'Candidate headings are automated text matches only; inspect the source PDF before setting metadata status to approved.'}
   if not pdf.exists() or pdf.stat().st_size<100_000:
    item['status']='missing_or_invalid_pdf';results.append(item);continue
   try:
    doc=pymupdf.open(pdf);item['physical_page_count']=doc.page_count;page_text=[]
    for i in range(doc.page_count):
     text=doc.load_page(i).get_text('text') or '';norm=' '.join(text.casefold().split())
     if text.strip():item['text_extraction_pages']+=1
     else:item['empty_text_pages'].append(i+1)
     if i<3:page_text.append(text)
     if any(x.casefold() in norm for x in [company['company'].casefold(),company['ticker'].casefold()]):item['identity_hits'].append(i+1)
     if fy.casefold() in norm or report['period_end'] in norm:item['financial_year_hits'].append(i+1)
     item['consolidated_word_occurrences']+=norm.count('consolidated')
     for key,phrases in TERMS.items():
      if any(p.casefold() in norm for p in phrases):item['candidate_statement_pages'][key].append(i+1)
    doc.close();item['first_pages_excerpt']=' '.join(' '.join(' '.join(page_text).split()).split())[:1800]
    flags=[]
    if not item['identity_hits']:flags.append('issuer name/ticker not found in extractable text')
    if not item['financial_year_hits']:flags.append('FY/period-end not found in extractable text')
    if item['consolidated_word_occurrences']==0:flags.append('no extracted occurrence of “consolidated”')
    if item['empty_text_pages']:flags.append(f"{len(item['empty_text_pages'])} page(s) have no selectable text; inspect/OCR")
    item['status']='candidate_for_manual_review' if not flags else 'manual_review_required'
    item['review_notes']+=' Flags: '+('; '.join(flags) if flags else 'identity/year and consolidated language matched; statement headings still need manual confirmation.')
   except Exception as exc:item['status']='pdf_read_error';item['review_notes']=f'{type(exc).__name__}: {exc}'
   results.append(item)
 OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps({'review_type':'read-only automated candidate extraction; not approval','count':len(results),'reports':results},ensure_ascii=False,indent=2)+'\n')
 print(f'Wrote {OUT}')
 for r in results:
  print(f"{r['status']}: {r['ticker']} {r['financial_year']} · pages {r['physical_page_count']} · auditor {r['candidate_statement_pages'].get('auditor_report',[])} · BS {r['candidate_statement_pages'].get('consolidated_balance_sheet',[])} · P&L {r['candidate_statement_pages'].get('consolidated_profit_loss',[])} · CF {r['candidate_statement_pages'].get('consolidated_cash_flows',[])}")
if __name__=='__main__':main()
