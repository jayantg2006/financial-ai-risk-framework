from __future__ import annotations
import hashlib,json,math,re
from collections import Counter
from pathlib import Path
from typing import Iterable
from .calculations import convert_amount,parse_amounts,validate_same_unit
from .models import Answer,Chunk,Citation,ClaimCheck,Document
TOKEN_RE=re.compile(r"[A-Za-z][A-Za-z0-9%.-]*|\d+(?:\.\d+)?")
STOP={"what","was","were","is","are","the","a","an","of","in","on","at","for","to","and","from","how","much","did","does","do","it","its","acme","industries","reported","during","with","where","report","figure","stated","state","value","company","approved","corpus","according","annual","locate","find","passage","supports","support","query","exact","amount","please","did","does","the","about","financial","result","test"}
def tokenize(text:str)->list[str]: return [x.lower() for x in TOKEN_RE.findall(text)]
def load_documents(path:str|Path)->list[Document]:
    docs=[]
    for file in sorted(Path(path).glob("*.json")):
        p=json.loads(file.read_text(encoding="utf-8"));docs.append(Document(**p["metadata"]))
    return docs
def _row_text(table,row,index):
    rows=table.get("rows") or []; heads=[str(v or f"column_{i+1}").strip() for i,v in enumerate(rows[0])] if rows else []
    return f"Table row {index}: "+" | ".join(f"{heads[i] if i<len(heads) else f'column_{i+1}'}: {str(v or '').strip()}" for i,v in enumerate(row) if str(v or '').strip())
def ingest_json_documents(input_dir:str|Path,output_file:str|Path,chunk_words:int=120,overlap:int=25)->list[Chunk]:
    src=Path(input_dir); files=[src] if src.is_file() else sorted(f for f in src.rglob("*.json") if not f.name.endswith(".metadata.json")); out=Path(output_file); chunks=[]
    for f in files:
        payload=json.loads(f.read_text(encoding="utf-8"))
        if not isinstance(payload,dict) or not isinstance(payload.get("metadata"),dict):continue
        if not isinstance(payload.get("pages"),list):continue
        meta=dict(payload["metadata"]);meta.setdefault("file_hash",hashlib.sha256(f.read_bytes()).hexdigest());meta.setdefault("page_count",len(payload.get("pages",[])));meta.setdefault("document_type","Disclosure");meta.setdefault("source_url","not supplied");meta.setdefault("publication_date","not supplied");meta.setdefault("company","unknown");meta.setdefault("financial_year","unknown");meta.setdefault("document_id",f.stem)
        doc=Document(**{k:meta[k] for k in Document.__dataclass_fields__ if k in meta})
        if doc.status not in {"approved","approved-demo"}: continue
        for pg in payload.get("pages",[]):
            pn=int(pg["page"]); words=str(pg.get("text","")).split();start=0;ordinal=0
            while start<len(words):
                end=min(start+chunk_words,len(words));text=" ".join(words[start:end]);chunks.append(Chunk(f"{doc.document_id}-p{pn}-c{ordinal}",doc.document_id,doc.company,doc.financial_year,pn,str(pg.get("section","General disclosure")),text,doc.source_url,"text",None,doc.file_hash,doc.reporting_basis));ordinal+=1
                if end==len(words):break
                start=max(end-overlap,start+1)
            for ti,table in enumerate(pg.get("tables",[]),start=1):
                tid=str(table.get("table_id") or f"p{pn}-t{ti}");rows=table.get("rows") or []
                for ri,row in enumerate(rows[1:] if len(rows)>1 else rows,start=1):
                    chunks.append(Chunk(f"{doc.document_id}-p{pn}-{tid}-r{ri}",doc.document_id,doc.company,doc.financial_year,pn,str(pg.get("section","Table")),_row_text(table,row,ri),doc.source_url,"table",tid,doc.file_hash,doc.reporting_basis))
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text("\n".join(json.dumps(c.to_dict(),ensure_ascii=False) for c in chunks)+("\n" if chunks else ""),encoding="utf-8");return chunks
def load_chunks(path:str|Path)->list[Chunk]:
    return [Chunk(**json.loads(line)) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
class LexicalRetriever:
    """Transparent BM25-style sparse retrieval baseline."""
    def __init__(self,chunks:Iterable[Chunk]):
        self.chunks=list(chunks);self.tokens=[tokenize(c.text) for c in self.chunks];self.df=Counter(t for row in self.tokens for t in set(row));self.avgdl=sum(map(len,self.tokens))/max(1,len(self.tokens))
    def _score(self,query:str,i:int)->float:
        q=[t for t in tokenize(query) if t not in STOP];terms=self.tokens[i];counts=Counter(terms);score=0.;n=max(len(self.chunks),1)
        for term in q:
            tf=counts[term]
            if tf:
                idf=math.log(1+(n-self.df[term]+.5)/(self.df[term]+.5));score+=idf*(tf*2.2)/(tf+1.2*(.25+.75*len(terms)/max(self.avgdl,1)))
        return score
    def retrieve_scored(self,query:str,top_k:int=5,company:str|None=None,financial_year:str|None=None):
        rows=[]
        for i,c in enumerate(self.chunks):
            if company and c.company.casefold()!=company.casefold():continue
            if financial_year and c.financial_year.casefold()!=financial_year.casefold():continue
            rows.append((self._score(query,i),c))
        return sorted(rows,key=lambda x:x[0],reverse=True)[:max(1,top_k)]
    def retrieve(self,query:str,top_k:int=5,company:str|None=None,financial_year:str|None=None)->list[Chunk]:
        return [c for score,c in self.retrieve_scored(query,top_k,company,financial_year) if score>0]
ATTACKS=[r"(?:ignore|disregard|override|forget).{0,80}(?:previous|earlier|system|safety|instructions|rules)",r"(?:fabricate|invent|make up).{0,50}(?:figure|profit|revenue|number|data)",r"\b(?:unrestricted|jailbreak) assistant\b",r"print all confidential",r"reveal (?:hidden|secret|confidential)",r"cite.{0,60}(?:regardless|no matter what)",r"ignore.{0,80}(?:source|report|evidence)"]
def contains_instruction_attack(text:str)->bool:return any(re.search(p,text,re.I|re.S) for p in ATTACKS)
TOPICS=("cash generated from operating activities","net cash from operating activities","cash flows from operating activities","cash flow from operating activities","profit attributable to owners","profit after tax","profit before tax","profit for the year","net profit","net interest income","net interest margin","interest income","interest expense","total income","revenue from operations","revenue from sale of products","operating revenue","basic earnings per share","diluted earnings per share","earnings per share","gross non-performing assets","net non-performing assets","gross npa","net npa","capital adequacy ratio","cet1 ratio","total deposits","customer deposits","deposits","total advances","gross advances","advances","shareholders equity","shareholders equity","total liabilities","total equity","total assets","operating cash flow","cash and cash equivalents","capital expenditure","current liabilities","current assets","operating profit","net income","total borrowings","borrowings","revenue","dividend","covenant breach","risk committee","risk management","liquidity limits")
def _topic(q:str):
    q=q.casefold()
    return next((t for t in TOPICS if t in q),None)
def _overlap(q,s):
    a={x for x in tokenize(q) if x not in STOP};b={x for x in tokenize(s) if x not in STOP};return len(a&b)/max(1,len(a))
def _metric_amounts(chunks,metric):
    d={}
    pat=re.compile(re.escape(metric)+r".{0,100}?(?:INR|₹)\s*([\d,]+(?:\.\d+)?)\s*(crores|crore|lakhs|lakh|millions|million|billions|billion)?",re.I|re.S)
    for c in chunks:
        m=pat.search(c.text)
        if m:
            value=float(m.group(1).replace(",",""));scale=(m.group(2) or "").lower();unit="INR "+scale if scale else "INR"
            d[c.financial_year]=(value,unit,c)
    return d
def _calc(question,chunks):
    q=question.casefold();metric=next((m for m in ["revenue","operating profit","operating cash flow","borrowings"] if m in q),None)
    if not metric or not any(w in q for w in ["growth","increase","decrease","change","reduction","percent"]):return None
    years=list(dict.fromkeys(re.findall(r"FY20\d{2}(?:-\d{2})?",question.upper())))
    if len(years)<2:return None
    prior_year,current_year=years[0],years[1]
    v=_metric_amounts(chunks,metric);a=v.get(prior_year);b=v.get(current_year)
    if not a or not b or not validate_same_unit(a[1],b[1]):return None
    try:prior=convert_amount(a[0],a[1],b[1])
    except ValueError:return None
    if prior==0:return None
    delta=b[0]-prior;pct=delta/prior*100
    if any(w in q for w in ["percent","%","percentage","growth rate"]):
        text=f"{metric.title()} changed by {pct:.2f}% from {prior_year} to {current_year}, calculated after converting both reported values to {b[1]}."
    else:
        direction="increased" if delta>0 else "decreased" if delta<0 else "was unchanged"
        amount=abs(delta);parts=b[1].split()
        formatted=f"{parts[0]} {amount:,.2f} {' '.join(parts[1:])}" if len(parts)>1 else f"{b[1]} {amount:,.2f}"
        text=f"{metric.title()} {direction} by {formatted} from {prior_year} to {current_year}."
    return text,[a[2],b[2]]

def _balance_sheet_row(question,chunks,topic,config_name):
    """Return a concise figure only when the metric is on an explicitly consolidated balance-sheet passage."""
    if topic!="total assets":return None
    years=re.findall(r"FY20\d{2}(?:-\d{2})?",question.upper())
    if len(set(years))!=1:return None
    year=years[0]
    pattern=re.compile(r"(?i)\btotal\s+assets\b\s+((?:[\d,]+(?:\.\d+)?\s*){1,5})")
    for c in chunks:
        if c.financial_year.upper()!=year or "consolidated balance sheet" not in c.text.casefold():continue
        m=pattern.search(c.text)
        if not m:continue
        vals=re.findall(r"\d[\d,]*(?:\.\d+)?",m.group(1))
        amounts=[v for v in vals if "," in v or len(v.replace(".",""))>=3]
        if not amounts:continue
        value=amounts[0]
        row=f"Total Assets {value}"
        text=f"{c.company} reported total assets of {value} for {year} in its consolidated balance sheet. Verify the unit/scale on the cited PDF page before using the figure."
        citation=Citation(c.chunk_id,c.document_id,c.company,c.financial_year,c.page,row,"exact-source-row")
        check=ClaimCheck(text,True,"exact metric-row match on consolidated balance-sheet passage",row,(c.chunk_id,),"The amount is quoted as printed; currency scale and accounting interpretation require source-page review.")
        return Answer(question,text,[citation],"Exact source row",False,"The row was extracted from a consolidated balance-sheet page; verify its unit/scale in the original PDF.",[c],[check],config_name,"exact-source-row","answered",{"company":c.company,"financial_year":c.financial_year,"metric":topic})
    return None

_COMPANY_ALIASES={
    "ICICI Bank Limited":(r"\bicici(?:\s+bank)?\b",),
    "HDFC Bank Limited":(r"\bhdfc(?:\s+bank)?\b",),
    "State Bank of India":(r"\bsbi\b",r"\bstate\s+bank\s+of\s+india\b"),
    "Reliance Industries Limited":(r"\breliance(?:\s+industries)?\b",),
    "Bharti Airtel Limited":(r"\bbharti\s+airtel\b",r"\bairtel\b"),
}
_PAT_TERMS=("profit after tax","profit for the year","profit attributable to owners","net profit","pat")
_AMOUNT_AFTER_METRIC=re.compile(r"(?:INR|₹|Rs\.?\s*)\s*([\d,]+(?:\.\d+)?)\s*(crores?|lakhs?|millions?|billions?|thousands?)?",re.I)

def _query_year(question,selected_year):
    found=re.findall(r"FY\s*20\d{2}\s*[-–/]\s*\d{2}|FY\s*20\d{2}",question.upper())
    if found:
        year=re.sub(r"\s+","",found[0]).replace("–","-").replace("/","-")
        return year
    return (selected_year or "").upper()

def _metric_aliases(question):
    q=question.casefold()
    if re.search(r"\bpat\b|profit\s+after\s+tax|profit\s+for\s+the\s+year|net\s+profit",q):return _PAT_TERMS
    topic=_topic(question)
    return (topic,) if topic else ()

def _metric_value(chunk,aliases):
    for term in aliases:
        m=re.search(re.escape(term)+r".{0,100}?"+_AMOUNT_AFTER_METRIC.pattern,chunk.text,re.I|re.S)
        if m:
            amount_match=_AMOUNT_AFTER_METRIC.search(m.group(0))
            if amount_match:
                scale=(amount_match.group(2) or "").lower()
                currency="INR"
                unit=" ".join(x for x in (currency,scale) if x)
                return float(amount_match.group(1).replace(",","")),unit
    return None

def _basis_kind(basis):
    text=(basis or "").casefold()
    if "consolidat" in text:return "consolidated"
    if "standalone" in text:return "standalone"
    return "unspecified"

class EvidenceConstrainedAssistant:
    def __init__(self,retriever,min_evidence:int=1,min_score:float=0.,config_name:str="baseline"):
        self.retriever,self.min_evidence,self.min_score,self.config_name=retriever,min_evidence,min_score,config_name
    def _answer_comparison(self,question,companies,year,metric_aliases,top_k):
        required=[c for c in companies]
        available=self.retriever.chunks
        all_docs={name:[c for c in available if c.company.casefold()==name.casefold() and (not year or c.financial_year.upper()==year)] for name in required}
        missing=[name for name,rows in all_docs.items() if not rows]
        metric="PAT" if "pat" in metric_aliases else metric_aliases[0].title()
        details={"metric":metric,"companies":required,"financial_year":year or None,"comparison":"absolute_difference","reporting_basis":"unconfirmed","required_evidence":len(required),"evidence_by_company":{}}
        if not year:
            msg=f"Please specify the financial year for the {metric} comparison. I need the same reporting period for {', '.join(required)}. No figures have been estimated or fabricated."
            return Answer(question,msg,[],"Clarification required",True,"Financial year is ambiguous.",[],[],self.config_name,"clarification_required","clarification_required",details)
        if missing:
            items="\n".join(f"- {name} — {year} {metric}" for name in missing)
            msg=(f"Insufficient source coverage\n\nI cannot calculate the difference in {metric} between {', '.join(required)} for {year} because the required approved reports are not available in the index.\n\nMissing information:\n{items}\n\nNo financial figures have been estimated or fabricated.")
            details["missing_companies"]=missing
            return Answer(question,msg,[],"Insufficient source coverage",True,"Required company/year documents are absent from the indexed corpus.",[],[],self.config_name,"corpus_coverage_failure","corpus_coverage_failure",details)

        evidence={};basis_by_company={};retrieved_by_company={};failed_retrieval=[];insufficient=[]
        search_terms=" ".join(metric_aliases)
        for name,docs in all_docs.items():
            # Evaluate each required company independently so global top-k ranking cannot hide one side.
            relevant=[c for c in docs if any(re.search(r"(?<![A-Za-z])"+re.escape(term)+r"(?![A-Za-z])",c.text,re.I) for term in metric_aliases)]
            scored=self.retriever.retrieve_scored(search_terms+" "+year, max(20,top_k*5), company=name, financial_year=year)
            ranked=[c for score,c in scored if score>0]
            selected=[c for c in ranked if any(re.search(r"(?<![A-Za-z])"+re.escape(term)+r"(?![A-Za-z])",c.text,re.I) for term in metric_aliases)]
            if selected:retrieved_by_company[name]=selected
            if not relevant or not selected:
                failed_retrieval.append(name); details["evidence_by_company"][name]={"document_available":True,"metric_evidence_found":bool(relevant),"retrieved":bool(selected)}; continue
            candidates=[]
            for c in selected:
                val=_metric_value(c,metric_aliases)
                if val:candidates.append((c,val))
            if not candidates:
                insufficient.append(name);details["evidence_by_company"][name]={"document_available":True,"metric_evidence_found":True,"amount_verified":False};continue
            source,(value,unit)=candidates[0]
            evidence[name]=(source,value,unit)
            kinds={_basis_kind(c.reporting_basis) for c in docs}
            kinds.discard("unspecified")
            basis_by_company[name]=next(iter(kinds)) if len(kinds)==1 else "mixed_or_unspecified"
            details["evidence_by_company"][name]={"document_available":True,"metric_evidence_found":True,"amount_verified":True,"reporting_basis":basis_by_company[name],"chunk_id":source.chunk_id,"page":source.page,"unit":unit}

        if failed_retrieval:
            items="\n".join(f"- {name} — {year} {metric}" for name in failed_retrieval)
            msg=(f"Retrieval failed\n\nThe approved {year} reports are indexed, but a relevant {metric} passage was not retrieved for:\n{items}\n\nThis may be a retrieval or report-extraction problem. No financial figures have been estimated or fabricated.")
            return Answer(question,msg,[],"Retrieval failed",True,"Documents exist, but the required metric passage was not retrieved.",sum(retrieved_by_company.values(),[]),[],self.config_name,"retrieval_failure","retrieval_failure",details)
        if insufficient:
            items="\n".join(f"- {name} — {year} {metric}: amount or unit could not be verified" for name in insufficient)
            msg=(f"Evidence insufficient\n\nA {metric} passage was found in the indexed reports, but the required amount and unit could not be verified for:\n{items}\n\nNo calculation has been made and no financial figures have been estimated or fabricated.")
            return Answer(question,msg,[],"Evidence insufficient",True,"Metric passage found but a parseable amount and unit were not verified.",sum(retrieved_by_company.values(),[]),[],self.config_name,"evidence_insufficient","evidence_insufficient",details)

        requested_basis="consolidated" if re.search(r"\bconsolidated\b",question,re.I) else "standalone" if re.search(r"\bstandalone\b",question,re.I) else None
        detected=set(basis_by_company.values())
        details["reporting_basis"]={k:v for k,v in basis_by_company.items()}
        if not requested_basis or len(detected)!=1 or "mixed_or_unspecified" in detected or requested_basis not in detected:
            if not requested_basis:
                reason="Please confirm whether to use standalone or consolidated financial statements."
            else:
                reason=f"The reports do not consistently confirm {requested_basis} figures for both companies. Please clarify the reporting basis."
            msg=(f"Clarification required\n\nI found the required {metric} evidence for both companies for {year}. {reason}\n\nI will calculate the absolute difference only after confirming a matching reporting basis and verifying both figures against the cited report pages.")
            return Answer(question,msg,[],"Clarification required",True,"Reporting basis is unspecified or inconsistent.",sum(retrieved_by_company.values(),[]),[],self.config_name,"clarification_required","clarification_required",details)

        rows=[evidence[name] for name in required]
        first,second=rows[0],rows[1]
        try:converted=convert_amount(second[1],second[2],first[2])
        except ValueError:
            msg="Clarification required\n\nThe two reported figures use incompatible currencies or units, so I cannot calculate a reliable difference until the units are reconciled."
            return Answer(question,msg,[],"Clarification required",True,"Reported units are incompatible.",sum(retrieved_by_company.values(),[]),[],self.config_name,"clarification_required","clarification_required",details)
        delta=abs(first[1]-converted)
        srcs=[evidence[name][0] for name in required]
        cites=[Citation(c.chunk_id,c.document_id,c.company,c.financial_year,c.page,c.text,"source-span-exact") for c in srcs]
        unit=first[2]
        text=(f"The absolute difference in {metric} between {required[0]} and {required[1]} for {year} ({requested_basis}) is {delta:,.2f} {unit}. "
              f"{required[0]}: {first[1]:,.2f} {unit}; {required[1]}: {converted:,.2f} {unit} after unit conversion.")
        check=ClaimCheck(text,True,"deterministic arithmetic + per-company source metric and basis checks"," | ".join(c.text for c in srcs),tuple(c.chunk_id for c in srcs),"Verify both source-page units and the reported accounting line before use.")
        details["reporting_basis"]=requested_basis;details["absolute_difference"]={"value":delta,"unit":unit}
        return Answer(question,text,cites,"Calculated from cited evidence",False,"Arithmetic is deterministic; analyst must verify source values, units, and interpretation.",sum(retrieved_by_company.values(),[]),[check],self.config_name,"verified_comparison","answered",details)
    def answer(self,question:str,company:str|None=None,financial_year:str|None=None,top_k:int=5)->Answer:
        if contains_instruction_attack(question):return Answer(question,"I cannot follow instructions to bypass safeguards, disclose data, or invent financial information.",[],"Refused",True,"Direct instruction attack or fabrication request detected.",[],[],self.config_name,"refusal")
        requested_year=_query_year(question,financial_year)
        aliases=_metric_aliases(question)
        mentioned=[]
        for canonical,patterns in _COMPANY_ALIASES.items():
            if any(re.search(pattern,question,re.I) for pattern in patterns):
                actual=next((c.company for c in self.retriever.chunks if c.company.casefold()==canonical.casefold()),canonical)
                if actual not in mentioned:mentioned.append(actual)
        is_comparison=len(mentioned)>=2 and bool(re.search(r"\b(difference|compare|comparison|between|versus|vs\.?|more than|less than)\b",question,re.I))
        if is_comparison and aliases:
            return self._answer_comparison(question,mentioned,requested_year,aliases,top_k)
        requested_company=company or (mentioned[0] if len(mentioned)==1 else None)
        scored=self.retriever.retrieve_scored(question,top_k,requested_company,requested_year or financial_year);positive=[(score,c) for score,c in scored if score>0 and score>=self.min_score]
        if positive and contains_instruction_attack(positive[0][1].text):
            suspicious=[c for score,c in positive if contains_instruction_attack(c.text)]
            return Answer(question,"I cannot follow instructions embedded in source documents. Retrieved text is treated as untrusted evidence.",[],"Refused",True,"The highest-ranked evidence passage contains a prompt-injection pattern.",suspicious,[],self.config_name,"refusal")
        # Lower-ranked malicious passages are excluded from model context; their presence is not allowed to poison unrelated queries.
        retrieved=[c for score,c in positive if not contains_instruction_attack(c.text)]
        if not retrieved:
            known=[c for c in self.retriever.chunks if (not requested_company or c.company.casefold()==requested_company.casefold()) and (not requested_year or c.financial_year.upper()==requested_year)]
            status="retrieval_failure" if known else "corpus_coverage_failure"
            if status=="corpus_coverage_failure":
                missing=f" for {requested_company}" if requested_company else ""
                missing+=f" {requested_year}" if requested_year else ""
                message=f"Insufficient source coverage: no approved indexed report was found{missing}."
            else:message="The approved report is indexed, but the retrieval system did not find a relevant passage for this question."
            return Answer(question,message,[],"Insufficient source coverage" if status=="corpus_coverage_failure" else "Retrieval failed",True,message,retrieved,[],self.config_name,status,status,{"company":requested_company,"financial_year":requested_year})
        calc=_calc(question,retrieved)
        if calc:
            text,sources=calc;checks=[ClaimCheck(text,True,"deterministic arithmetic + source-value match"," | ".join(c.text for c in sources),tuple(c.chunk_id for c in sources),"Not independently reviewed by a human.")];cites=[Citation(c.chunk_id,c.document_id,c.company,c.financial_year,c.page,c.text,"source-span-exact") for c in sources]
            return Answer(question,text,cites,"Calculated from cited evidence",False,"Arithmetic is deterministic; analyst must verify source values, units, and interpretation.",retrieved,checks,self.config_name,"deterministic-source-and-arithmetic-check","answered",{"financial_years":[c.financial_year for c in sources],"metric":_topic(question)})
        table_answer=_balance_sheet_row(question,retrieved,_topic(question),self.config_name)
        if table_answer:return table_answer
        sentences=[(c,s.strip()) for c in retrieved for s in re.split(r"(?<=[.!?])\s+",c.text) if s.strip()]
        topic=_topic(question)
        if topic:
            sentences=[(c,s) for c,s in sentences if topic in s.casefold()]
        requested_years=re.findall(r"FY20\d{2}(?:-\d{2})?",question.upper())
        if len(set(requested_years))==1:
            yr=requested_years[0]
            sentences=[(c,s) for c,s in sentences if c.financial_year.upper()==yr or yr in s.upper()]
        if re.search(r"\b(?:quarter|quarterly|Q[1-4])\b",question,re.I):
            sentences=[(c,s) for c,s in sentences if re.search(r"\b(?:quarter|quarterly|Q[1-4])\b",s,re.I)]
        dimensions=[("geographic",("geographic","geographical","country","region")),("by country",("country",)),("by region",("region",)),("segment",("segment",)),("per share",("per share",)),("per unit",("per unit",))]
        for marker,needles in dimensions:
            if marker in question.casefold():sentences=[(c,s) for c,s in sentences if any(n in s.casefold() for n in needles)]
        if not sentences:return Answer(question,"Evidence insufficient: the report is indexed, but the retrieved passages do not contain a verifiable answer for the requested metric and period.",[],"Evidence insufficient",True,"No answer-bearing sentence matched the requested metric and reporting period.",retrieved,[],self.config_name,"evidence_insufficient","evidence_insufficient",{"company":requested_company,"financial_year":requested_year,"metric":topic})
        c,s=max(sentences,key=lambda x:_overlap(question,x[1]))
        if not topic and _overlap(question,s)<.60:return Answer(question,"Evidence insufficient: the retrieved passage did not closely match the question.",[],"Evidence insufficient",True,"Retrieved passage did not meet the relevance threshold.",retrieved,[],self.config_name,"evidence_insufficient","evidence_insufficient",{"company":requested_company,"financial_year":requested_year})
        citation=Citation(c.chunk_id,c.document_id,c.company,c.financial_year,c.page,s,"exact-source-span");check=ClaimCheck(s,True,"exact source sentence returned; not semantic entailment",s,(c.chunk_id,),"Interpretation still requires analyst review.")
        return Answer(question,s,[citation],"Exact source sentence",False,"Verbatim evidence text; exact quotation does not validate broader interpretation.",retrieved,[check],self.config_name,"exact-source-span","answered",{"company":c.company,"financial_year":c.financial_year})
