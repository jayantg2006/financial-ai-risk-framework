from __future__ import annotations
import argparse,json,os,sys,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'03_RAG_Application')]

def main():
    parser=argparse.ArgumentParser(description='Check NVIDIA NIM connectivity separately from FDIA evidence-grounded RAG.')
    parser.add_argument('--mode',choices=['ping','rag'],default='ping',help='ping tests only endpoint/auth/model; rag tests a cited answer against the indexed reports')
    parser.add_argument('--question',help='Required for --mode rag. Ask a factual question answerable from a cited report page.')
    parser.add_argument('--company',help='Optional exact company name for --mode rag, e.g. Reliance Industries Limited.')
    parser.add_argument('--year',help='Optional exact fiscal-year label from the indexed report, e.g. FY2025-26.')
    parser.add_argument('--top-k',type=int,default=5)
    args=parser.parse_args()
    key=os.getenv('NVIDIA_API_KEY')
    if not key:
        print('ERROR: NVIDIA_API_KEY is not set. Set it in the current shell/session; this script never reads a committed key or prints the key value.',file=sys.stderr)
        return 2
    base_url=os.getenv('NVIDIA_BASE_URL','https://integrate.api.nvidia.com/v1')
    model=os.getenv('NVIDIA_MODEL','meta/llama-3.2-90b-vision-instruct')
    try:
        from openai import OpenAI
    except ImportError:
        print('ERROR: install requirements.txt in the active virtual environment first.',file=sys.stderr)
        return 2
    client=OpenAI(api_key=key,base_url=base_url,timeout=60,max_retries=1)
    if args.mode=='ping':
        try:
            response=client.chat.completions.create(model=model,messages=[{'role':'user','content':'Reply with exactly NIM_OK and no other text.'}],temperature=0,max_tokens=16)
            content=(response.choices[0].message.content or '').strip()
        except Exception as exc:
            print(json.dumps({'status':'failed','base_url':base_url,'model':model,'error_type':type(exc).__name__,'error':str(exc)},indent=2))
            return 1
        passed='NIM_OK' in content
        print(json.dumps({'status':'passed' if passed else 'unexpected-response','base_url':base_url,'model':model,'response':content,'meaning':'endpoint/auth/model connectivity only; this does not test RAG retrieval or the evidence gate'},indent=2))
        return 0 if passed else 1
    if not args.question:
        parser.error('--question is required for --mode rag')
    chunks_path=ROOT/'02_Data_and_Documents/processed/chunks.jsonl'
    reports=ROOT/'02_Data_and_Documents/raw/annual_reports'
    try:
        result=subprocess.run([sys.executable,str(ROOT/'scripts/ingest_documents.py'),'--input',str(reports),'--output',str(chunks_path),'--reuse-if-current'],capture_output=True,text=True,check=True)
    except subprocess.CalledProcessError as exc:
        print('ERROR: report ingestion failed before the RAG test.\n'+exc.stderr,file=sys.stderr);return 2
    from fdia.rag import LexicalRetriever,load_chunks
    from fdia.llm import LLMGenerationUnavailable,NVIDIAEvidenceAssistant
    chunks=load_chunks(chunks_path)
    if not chunks:
        print('ERROR: no approved report chunks were indexed.',file=sys.stderr);return 2
    assistant=NVIDIAEvidenceAssistant(LexicalRetriever(chunks),model=model,config_name='nim-api-smoke')
    try:
        answer=assistant.answer(args.question,args.company,args.year,args.top_k)
    except LLMGenerationUnavailable as exc:
        print(json.dumps({'status':'api-or-generation-failed','model':model,'error':str(exc),'ingestion':result.stdout.strip()},indent=2));return 1
    payload={'status':'abstained' if answer.abstained else 'answered','config':answer.config_name,'model':model,'question':answer.question,'answer':answer.text,'verification_status':answer.verification_status,'abstained':answer.abstained,'citations':[{'company':c.company,'financial_year':c.financial_year,'document_id':c.document_id,'page':c.page,'chunk_id':c.chunk_id,'source_url':next((x.source_url for x in chunks if x.chunk_id==c.chunk_id),None)} for c in answer.citations],'limitation':answer.limitation,'ingestion':result.stdout.strip()}
    print(json.dumps(payload,ensure_ascii=False,indent=2))
    return 0 if not answer.abstained and answer.citations else 1

if __name__=='__main__':raise SystemExit(main())
