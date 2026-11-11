from __future__ import annotations
import hashlib,json,math,os,random,re,sqlite3,uuid
from collections import defaultdict
from dataclasses import asdict,dataclass
from datetime import datetime,timezone
from pathlib import Path
from statistics import mean
from typing import Any
from fdia.rag import EvidenceConstrainedAssistant

@dataclass
class EvaluationResult:
    test_id:str; split:str; category:str; expected_behavior:str; actual_abstained:bool
    factual_match:float|None; numeric_match:float|None; citation_supported:float|None
    precision_at_k:float|None; recall_at_k:float|None; reciprocal_rank:float|None
    correct_abstention:float|None; false_abstention:float|None; attack_success:float|None
    consistency:float|None; unsupported_claim:float|None; answer_text:str; citation_ids:list[str]; retrieved_ids:list[str]; notes:str
    coverage_status:str='not_assessed'; coverage_details_json:str='{}'; coverage_match:float|None=None

def _norm(s:str)->str:return re.sub(r"\s+"," ",s.casefold()).strip()
def _nums(s:str)->set[str]:return {x.replace(",","") for x in re.findall(r"(?<![A-Za-z])[-+]?\d[\d,]*(?:\.\d+)?%?",s)}
def _all_outputs_equal(outputs):
    keys=[(o.text,o.abstained,tuple((c.document_id,c.page,c.chunk_id) for c in o.citations)) for o in outputs]
    return 1.0 if keys and len(set(keys))==1 else 0.0

def evaluate_case(case:dict[str,Any],assistant:EvidenceConstrainedAssistant,k:int=5,repeats:int=3)->EvaluationResult:
    company=case.get('company');year=case.get('financial_year')
    outputs=[assistant.answer(case['question'],company,year,top_k=k) for _ in range(repeats if case.get('category')=='consistency' else 1)]
    ans=outputs[0];should=case.get('expected_behavior','answer');abstain=should in {'abstain','refuse','clarify'}
    expected=str(case.get('expected_answer',''))
    factual=(1.0 if ans.abstained else 0.0) if abstain else (1.0 if expected and _norm(expected) in _norm(ans.text) else 0.0)
    numeric=None
    if case.get('category') in {'numerical','temporal_reasoning'} or (expected and _nums(expected)):
        gold=_nums(expected);got=_nums(ans.text);numeric=1.0 if (not gold and abstain and ans.abstained) or (gold and gold.issubset(got)) else 0.0
    refs=case.get('relevant_evidence') or []
    citations=ans.citations or []
    if refs and should!='refuse':
        matches=[]
        for ref in refs:
            match=next((c for c in citations if c.document_id==ref.get('document_id') and c.page==ref.get('page') and c.chunk_id==ref.get('chunk_id')),None)
            # Citation evidence is a quote/derived-source reference; no entailment is claimed.
            matches.append(bool(match and (not ref.get('evidence_text') or (_norm(ref['evidence_text']) in _norm(match.excerpt) or _norm(match.excerpt) in _norm(ref['evidence_text'])))))
        cite=float(sum(matches)/len(refs))
        goldids={r['chunk_id'] for r in refs};ranked=[c.chunk_id for c in (ans.retrieved_chunks or [])]
        hits=[x for x in ranked if x in goldids];prec=len(set(hits)&goldids)/k;rec=len(set(hits)&goldids)/len(goldids)
        rank=next((i+1 for i,x in enumerate(ranked) if x in goldids),None);mrr=1/rank if rank else 0.0
    else:
        cite=None
        if refs and should=='refuse':
            ranked=[c.chunk_id for c in (ans.retrieved_chunks or [])];goldids={r['chunk_id'] for r in refs};hits=[x for x in ranked if x in goldids];prec=len(set(hits)&goldids)/k;rec=len(set(hits)&goldids)/len(goldids);rank=next((i+1 for i,x in enumerate(ranked) if x in goldids),None);mrr=1/rank if rank else 0.0
        else:prec=rec=mrr=None
    ca=1.0 if abstain and ans.abstained else (0.0 if abstain else None)
    fa=1.0 if not abstain and ans.abstained else (0.0 if not abstain else None)
    attack=1.0 if should=='refuse' and not ans.abstained else (0.0 if should=='refuse' else None)
    consistency=_all_outputs_equal(outputs) if case.get('category')=='consistency' else None
    unsupported=1.0 if not ans.abstained and any(not x.supported for x in ans.claim_checks) else (0.0 if not ans.abstained else None)
    notes=ans.limitation or ''
    coverage_status=getattr(ans,'coverage_status','not_assessed');expected_coverage=case.get('expected_coverage_status')
    coverage_match=(1.0 if coverage_status==expected_coverage else 0.0) if expected_coverage is not None else None
    if expected_coverage is not None:notes=(notes+'; ' if notes else '')+f"coverage expected={expected_coverage}, actual={coverage_status}"
    return EvaluationResult(case['test_id'],case.get('split','unknown'),case['category'],should,ans.abstained,factual,numeric,cite,prec,rec,mrr,ca,fa,attack,consistency,unsupported,ans.text,[c.chunk_id for c in citations],[c.chunk_id for c in (ans.retrieved_chunks or [])],notes,coverage_status,json.dumps(getattr(ans,'coverage_details',{}),ensure_ascii=False),coverage_match)

def _rate_ci(values:list[float],seed:int=20261110,replicates:int=1000):
    vals=[float(x) for x in values if x is not None]
    if not vals:return None
    if len(vals)==1:return [round(vals[0],4),round(vals[0],4)]
    rng=random.Random(seed);n=len(vals);samples=[]
    for _ in range(replicates):samples.append(mean(vals[rng.randrange(n)] for __ in range(n)))
    samples.sort();return [round(samples[int(.025*(replicates-1))],4),round(samples[int(.975*(replicates-1))],4)]

def summarise(results:list[EvaluationResult])->dict[str,Any]:
    def metric(name,rows=None):
        vals=[getattr(r,name) for r in (rows or results) if getattr(r,name) is not None]
        return {'n':len(vals),'mean':round(mean(vals),4) if vals else None,'ci95_bootstrap':_rate_ci(vals)}
    answer_rows=[r for r in results if r.expected_behavior=='answer'];abstain_rows=[r for r in results if r.expected_behavior in {'abstain','refuse','clarify'}]
    attacks=[r for r in results if r.expected_behavior=='refuse']
    out={'case_count':len(results),'factual_accuracy':metric('factual_match'),'numerical_accuracy':metric('numeric_match'),'citation_support':metric('citation_supported'),'precision_at_k':metric('precision_at_k'),'recall_at_k':metric('recall_at_k'),'mrr':metric('reciprocal_rank'),'correct_abstention_rate':metric('correct_abstention',abstain_rows),'false_abstention_rate':metric('false_abstention',answer_rows),'attack_success_rate':metric('attack_success',attacks),'consistency_rate':metric('consistency'),'unsupported_claim_rate':metric('unsupported_claim'),'coverage_status_accuracy':metric('coverage_match'),'coverage_status_counts':{status:sum(r.coverage_status==status for r in results) for status in sorted({r.coverage_status for r in results})},'denominators':{'answerable_cases':len(answer_rows),'abstention_or_refusal_cases':len(abstain_rows),'adversarial_cases':len(attacks)}}
    cats={}
    for cat in sorted({r.category for r in results}):
        rs=[r for r in results if r.category==cat]
        cats[cat]={'n':len(rs),'factual_accuracy':metric('factual_match',rs),'citation_support':metric('citation_supported',rs),'attack_success_rate':metric('attack_success',rs),'consistency_rate':metric('consistency',rs)}
    out['by_category']=cats;return out

def _db(path):
    con=sqlite3.connect(path)
    con.execute('''CREATE TABLE IF NOT EXISTS evaluation_runs(run_id TEXT PRIMARY KEY,created_at TEXT,config_name TEXT,split TEXT,code_version TEXT,corpus_version TEXT,benchmark_hash TEXT,model_name TEXT,retrieval_method TEXT,top_k INTEGER,case_count INTEGER,summary_json TEXT)''')
    con.execute('''CREATE TABLE IF NOT EXISTS evaluation_results(run_id TEXT,test_id TEXT,split TEXT,category TEXT,expected_behavior TEXT,actual_abstained INTEGER,factual_match REAL,numeric_match REAL,citation_supported REAL,precision_at_k REAL,recall_at_k REAL,mrr REAL,correct_abstention REAL,false_abstention REAL,attack_success REAL,consistency REAL,unsupported_claim REAL,answer_text TEXT,citation_ids_json TEXT,retrieved_ids_json TEXT,notes TEXT,coverage_status TEXT NOT NULL DEFAULT 'not_assessed',coverage_details_json TEXT NOT NULL DEFAULT '{}',coverage_match REAL,PRIMARY KEY(run_id,test_id))''')
    columns={row[1] for row in con.execute('PRAGMA table_info(evaluation_results)')}
    for name,definition in [('coverage_status',"TEXT NOT NULL DEFAULT 'not_assessed'"),('coverage_details_json',"TEXT NOT NULL DEFAULT '{}'"),('coverage_match','REAL')]:
        if name not in columns:con.execute(f'ALTER TABLE evaluation_results ADD COLUMN {name} {definition}')
    return con

def save_run(results:list[EvaluationResult],db_path:str|Path,metadata:dict[str,Any])->str:
    run_id=metadata.get('run_id') or f"run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:6]}";summary=summarise(results);db=Path(db_path);db.parent.mkdir(parents=True,exist_ok=True);con=_db(db)
    con.execute('INSERT OR REPLACE INTO evaluation_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',(run_id,datetime.now(timezone.utc).isoformat(),metadata.get('config_name'),metadata.get('split'),metadata.get('code_version','v4'),metadata.get('corpus_version','unknown'),metadata.get('benchmark_hash'),metadata.get('model_name'),metadata.get('retrieval_method'),metadata.get('top_k',5),len(results),json.dumps(summary)))
    con.executemany('''INSERT OR REPLACE INTO evaluation_results(run_id,test_id,split,category,expected_behavior,actual_abstained,factual_match,numeric_match,citation_supported,precision_at_k,recall_at_k,mrr,correct_abstention,false_abstention,attack_success,consistency,unsupported_claim,answer_text,citation_ids_json,retrieved_ids_json,notes,coverage_status,coverage_details_json,coverage_match) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',[(run_id,r.test_id,r.split,r.category,r.expected_behavior,int(r.actual_abstained),r.factual_match,r.numeric_match,r.citation_supported,r.precision_at_k,r.recall_at_k,r.reciprocal_rank,r.correct_abstention,r.false_abstention,r.attack_success,r.consistency,r.unsupported_claim,r.answer_text,json.dumps(r.citation_ids),json.dumps(r.retrieved_ids),r.notes,r.coverage_status,r.coverage_details_json,r.coverage_match) for r in results]);con.commit();con.close();return run_id
