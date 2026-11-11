from __future__ import annotations
import argparse,hashlib,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"03_RAG_Application"),str(ROOT/"05_Evaluation_Engine")]
from fdia.rag import EvidenceConstrainedAssistant,LexicalRetriever,ingest_json_documents,load_chunks
from fdia.models import Chunk
from fdia.llm import LLMGenerationUnavailable,NVIDIAEvidenceAssistant
from fdia_eval.engine import evaluate_case,save_run,summarise
from fdia.semantic import FaissSemanticRetriever,SemanticDependenciesUnavailable
p=argparse.ArgumentParser(description="Compare the four FDIA V4 retrieval/generation configurations")
p.add_argument('--split',choices=['development','validation','holdout','coverage-control'],default='validation')
p.add_argument('--allow-holdout',action='store_true',help='Required to evaluate the locked holdout; do not tune based on holdout results')
p.add_argument('--config',choices=['baseline','nim','semantic_baseline','semantic_nim','all'],default='all')
p.add_argument('--k',type=int,default=5);p.add_argument('--db',default=str(ROOT/'06_Validation_Results/evaluation.sqlite'));p.add_argument('--output',default=str(ROOT/'06_Validation_Results/latest_comparison.json'))
a=p.parse_args()
if a.split=='holdout' and not a.allow_holdout:raise SystemExit('Holdout is locked. Pass --allow-holdout only for the final assessment; never tune on its results.')
bpath=(ROOT/'04_Evaluation_Benchmark/query_coverage_cases.jsonl') if a.split=='coverage-control' else ROOT/f'04_Evaluation_Benchmark/benchmark_{a.split}.jsonl';raw=bpath.read_bytes();digest=hashlib.sha256(raw).hexdigest()
if a.split=='holdout':
 m=json.loads((ROOT/'04_Evaluation_Benchmark/holdout_manifest.json').read_text())
 if digest!=m['sha256']:raise SystemExit('Locked holdout hash mismatch; restore the original holdout before use.')
cases=[json.loads(x) for x in raw.decode().splitlines() if x.strip()]
if a.split!='coverage-control' and any(c.get('data_status')=='synthetic_demo_only' for c in cases):
 raise SystemExit('This benchmark contains fictional Acme demo cases and is not valid for the real NIFTY 50 filings. Use the Streamlit app for manual report testing, or provide a separately human-verified benchmark before running this evaluator.')
chunk_path=ROOT/'02_Data_and_Documents/processed/chunks.jsonl'
if a.split=='coverage-control':chunks=[]
else:
 # Rebuild each run so changed source files cannot silently use a stale chunk index.
 ingest_json_documents(ROOT/'02_Data_and_Documents/raw',chunk_path)
 chunks=load_chunks(chunk_path)
lex=LexicalRetriever(chunks);requested=['baseline','nim','semantic_baseline','semantic_nim'] if a.config=='all' else [a.config]
run_summaries={};skipped={}
for name in requested:
 try:
  if name.startswith('semantic_') and chunks:retriever=FaissSemanticRetriever(chunks);method='sentence-transformers+FAISS'
  else:retriever=lex;method='BM25 lexical'
  if name.endswith('_nim') or name=='nim':assistant=NVIDIAEvidenceAssistant(retriever,config_name=name);model=assistant.model
  else:assistant=EvidenceConstrainedAssistant(retriever,config_name=name);model='deterministic-extractive'
  # Evaluate all cases; repeat consistency cases three times inside evaluate_case.
  results=[]
  for case in cases:
   case_assistant=assistant
   if a.split=='coverage-control':
    fixture=[];available=case.get('available_documents',[]);bases=case.get('reporting_basis',{})
    for i,company in enumerate(available):
     basis=bases.get(company,'not specified')
     if case.get('fixture_type')=='no_metric_passages':text=f'Audited {basis} financial statements for FY2025-26.'
     elif case.get('fixture_type')=='metric_without_amount':text='Profit after tax is disclosed, but the amount and reporting unit are not available in this extracted passage.'
     else:text=f'Audited {basis} financial statements for FY2025-26. Profit after tax INR {100-i*20} crore for FY2025-26.'
     fixture.append(Chunk(f'COV-{case["test_id"]}-{i}',f'{company}-FY2025-26',company,'FY2025-26',42,'Consolidated statement',text,'https://example.invalid/report','text',None,None,basis))
    case_assistant=EvidenceConstrainedAssistant(LexicalRetriever(fixture),config_name=name)
   results.append(evaluate_case(case,case_assistant,k=a.k,repeats=3))
  run_id=save_run(results,a.db,{'config_name':name,'split':a.split,'code_version':'4.0.0','corpus_version':'coverage-control-fixtures' if a.split=='coverage-control' else 'synthetic-demo-v4','benchmark_hash':digest,'model_name':model,'retrieval_method':method,'top_k':a.k})
  run_summaries[name]={'run_id':run_id,'summary':summarise(results),'failures':[{'test_id':r.test_id,'category':r.category,'question':next(c['question'] for c in cases if c['test_id']==r.test_id),'answer':r.answer_text,'expected_behavior':r.expected_behavior,'coverage_status':r.coverage_status,'notes':r.notes} for r in results if r.factual_match==0 or r.citation_supported==0 or r.attack_success==1 or r.coverage_match==0]}
 except (LLMGenerationUnavailable,SemanticDependenciesUnavailable) as exc:skipped[name]=str(exc)
 except Exception as exc:skipped[name]=f'{type(exc).__name__}: {exc}'
report={'suite':'FDIA-V4','split':a.split,'benchmark_hash':digest,'case_count':len(cases),'top_k':a.k,'tuning_policy':'holdout excluded unless explicitly unlocked; results never auto-tune configuration','configurations':run_summaries,'skipped':skipped}
out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n');print(json.dumps(report,indent=2))
