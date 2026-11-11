from __future__ import annotations
import json,sqlite3,sys,subprocess
from dataclasses import replace
from pathlib import Path
import pandas as pd
import streamlit as st
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'03_RAG_Application'),str(ROOT/'05_Evaluation_Engine')]
from fdia.rag import EvidenceConstrainedAssistant,LexicalRetriever,ingest_json_documents,load_chunks
from fdia.llm import NVIDIAEvidenceAssistant,LLMGenerationUnavailable
from fdia.semantic import FaissSemanticRetriever,SemanticDependenciesUnavailable
from fdia_eval.engine import save_run,summarise

st.set_page_config(page_title='FDIA | V4 Risk Assessment',page_icon='◆',layout='wide')
st.markdown('''<style>.block-container{max-width:1440px;padding-top:1.4rem}.hero{padding:1.5rem 2rem;border-radius:18px;background:linear-gradient(120deg,#14213d,#20536d,#0f766e);color:#fff;margin-bottom:1rem}.hero h1{margin:0;font-size:2.1rem}.hero p{color:#e3edf1;max-width:880px}.warn{padding:.9rem 1rem;background:#fff7ed;border-left:4px solid #d97706;border-radius:8px}</style>''',unsafe_allow_html=True)
@st.cache_resource
def load_base():
    chunks_path=ROOT/'02_Data_and_Documents/processed/chunks.jsonl'
    try:
        proc=subprocess.run([sys.executable,str(ROOT/'scripts/ingest_documents.py'),'--input',str(ROOT/'02_Data_and_Documents/raw/annual_reports'),'--output',str(chunks_path),'--reuse-if-current'],check=True,capture_output=True,text=True)
    except subprocess.CalledProcessError as exc:
        st.error('Report indexing failed. The underlying error is shown below; confirm the project dependencies are installed in the same Python environment used to run Streamlit.')
        detail=(exc.stderr or '').strip() or (exc.stdout or '').strip() or str(exc)
        st.code(detail)
        st.info('From the project folder, run `python -m pip install -r requirements.txt`, then test with `python scripts/ingest_documents.py --input 02_Data_and_Documents/raw/annual_reports --reuse-if-current`.')
        st.stop()
    chunks=load_chunks(chunks_path)
    # Older packaged indexes do not carry reporting basis; enrich them from the approved source sidecars without re-extracting large PDFs.
    basis_by_doc={}
    for sidecar in (ROOT/'02_Data_and_Documents/raw/annual_reports').rglob('*.metadata.json'):
        try:
            meta=json.loads(sidecar.read_text(encoding='utf-8'));basis_by_doc[meta['document_id']]=meta.get('reporting_basis','not specified')
        except (OSError,ValueError,KeyError,TypeError):continue
    chunks=[replace(c,reporting_basis=basis_by_doc.get(c.document_id,c.reporting_basis)) for c in chunks]
    return chunks,LexicalRetriever(chunks)
chunks,lexical=load_base()

def make_assistant(config):
    semantic=config.startswith('semantic_');nim=config in {'nim','semantic_nim'}
    retriever=FaissSemanticRetriever(chunks) if semantic else lexical
    return NVIDIAEvidenceAssistant(retriever,config_name=config) if nim else EvidenceConstrainedAssistant(retriever,config_name=config)

st.markdown('''<div class="hero"><div style="letter-spacing:.14em;text-transform:uppercase;font-size:.75rem;color:#7dd3c7;font-weight:700">Financial Document Intelligence Assistant · V4</div><h1>Financial report research assistant</h1><p>Ask questions against source-linked NIFTY 50 annual reports. Review every cited PDF page. The system is a research prototype, not a production validation or decision system.</p></div>''',unsafe_allow_html=True)
mode=st.sidebar.selectbox('Configuration',[
    'baseline','nim','semantic_baseline','semantic_nim'],format_func=lambda x:{'baseline':'BM25 retrieval + deterministic answer (no LLM)','nim':'BM25 retrieval + NVIDIA NIM generation','semantic_baseline':'Semantic retrieval + deterministic answer (no LLM)','semantic_nim':'Semantic retrieval + NVIDIA NIM generation'}[x])
if mode.endswith('_baseline') or mode=='baseline':
    st.sidebar.caption('Deterministic mode retrieves evidence and returns a source sentence. It does not call a generative LLM.')
else:
    st.sidebar.caption('NVIDIA NIM generates claims from retrieved evidence. NVIDIA_API_KEY must be set in the environment that starts Streamlit. Exact-quote checks can make its wording close to the source.')
view=st.sidebar.radio('Workspace',['Ask FDIA','Evaluation comparison','Risk & governance'])
st.sidebar.caption(f'Corpus: {len(chunks)} page/table chunks · {len({c.document_id for c in chunks})} annual reports')
st.sidebar.caption('Material outputs require analyst source review. No investment or credit decisions.')
if view=='Ask FDIA':
    st.subheader('Ask against the indexed annual reports')
    col1,col2,col3=st.columns([1.2,1,1]);companies=sorted({c.company for c in chunks});years=sorted({c.financial_year for c in chunks},reverse=True);company=col1.selectbox('Company',['All companies']+companies);year=col2.selectbox('Financial year',['All years']+years);top_k=col3.slider('Top passages',1,10,5)
    question=st.text_input('Question',placeholder='e.g. What were total assets in FY2025-26?')
    st.caption('Ask for a figure or disclosure and specify the fiscal year. Open the citation to check it against the original report page.')
    if st.button('Run selected configuration',type='primary',disabled=not question):
        try:
            assistant=make_assistant(mode)
            answer=assistant.answer(question,None if company=='All companies' else company,None if year=='All years' else year,top_k)
            (st.warning if answer.abstained else st.success)(answer.text)
            generation_label={'not_used':'Not used (deterministic answer)','skipped_by_evidence_gate':'Skipped (evidence gate abstained)','nvidia_nim_generated':'NVIDIA NIM generated claims','nvidia_nim_returned_no_claims':'NVIDIA NIM returned no claims','nvidia_nim_claim_rejected':'NVIDIA NIM claims failed verification'}.get(answer.generation_status,answer.generation_status)
            st.write(f'**Status:** {answer.confidence} · **Coverage:** {answer.coverage_status.replace("_", " ")} · **Generation:** {generation_label} · **Verification:** {answer.verification_status} · **Abstained:** {answer.abstained}')
            if answer.coverage_details:
                with st.expander('Query coverage assessment'):
                    st.json(answer.coverage_details)
            if answer.limitation:st.markdown(f'<div class="warn"><b>Limitation / control note:</b> {answer.limitation}</div>',unsafe_allow_html=True)
            st.markdown('### Claim checks')
            if answer.claim_checks:st.dataframe([{'Claim':c.claim,'Supported by implemented gate':c.supported,'Method':c.verification_method,'Evidence quote':c.support_quote,'Limitation':c.limitation} for c in answer.claim_checks],width='stretch',hide_index=True)
            st.markdown('### Citations and source evidence')
            if answer.citations:
                for c in answer.citations:
                    with st.expander(f'{c.company} · {c.financial_year} · PDF page {c.page} · {c.support_status}'):
                        st.write(c.excerpt);st.caption(f'{c.document_id} · chunk {c.chunk_id}')
                        source=next((x for x in (answer.retrieved_chunks or []) if x.chunk_id==c.chunk_id),None)
                        if source and source.source_url:st.link_button('Open original report PDF',source.source_url,key=f'pdf-{c.chunk_id}')
            else:st.info('No citation returned. The answer abstained or was refused.')
            with st.expander('Retrieved passages used for evidence inspection'):
                for c in answer.retrieved_chunks or []:st.markdown(f'**{c.document_id} · page {c.page} · {c.evidence_type}**\n\n{c.text}')
        except (LLMGenerationUnavailable,SemanticDependenciesUnavailable) as e:st.error(str(e))
        except Exception as e:st.error(f'Configuration failed: {type(e).__name__}: {e}')
elif view=='Evaluation comparison':
    st.subheader('Benchmark run comparison')
    st.warning('Stored evaluation runs and the 200-case benchmark are from the earlier fictional Acme demo. They do not measure retrieval or answer quality on the real NIFTY 50 reports.')
    st.write('Runs are configuration- and split-stamped. NIM is skipped when credentials are absent. The locked holdout in the historical synthetic suite requires explicit CLI opt-in and a matching manifest hash.')
    db=ROOT/'06_Validation_Results/evaluation.sqlite'
    if not db.exists():st.info('No stored evaluation yet. Run `python scripts/run_evaluation.py --split validation --config all`.')
    else:
        con=sqlite3.connect(db)
        result_columns={row[1] for row in con.execute('PRAGMA table_info(evaluation_results)')}
        if 'coverage_status' not in result_columns:con.execute("ALTER TABLE evaluation_results ADD COLUMN coverage_status TEXT NOT NULL DEFAULT 'not_assessed'")
        if 'coverage_details_json' not in result_columns:con.execute("ALTER TABLE evaluation_results ADD COLUMN coverage_details_json TEXT NOT NULL DEFAULT '{}'")
        if 'coverage_match' not in result_columns:con.execute('ALTER TABLE evaluation_results ADD COLUMN coverage_match REAL')
        con.commit();runs=pd.read_sql_query('SELECT * FROM evaluation_runs ORDER BY created_at DESC',con);rows=[]
        for _,r in runs.iterrows():
            s=json.loads(r.summary_json)
            rows.append({'run_id':r.run_id,'config':r.config_name,'split':r.split,'model':r.model_name,'retrieval':r.retrieval_method,'n':r.case_count,**{m:s.get(m,{}).get('mean') for m in ['factual_accuracy','numerical_accuracy','citation_support','precision_at_k','recall_at_k','mrr','correct_abstention_rate','false_abstention_rate','attack_success_rate','consistency_rate']},'coverage_status_accuracy':s.get('coverage_status_accuracy',{}).get('mean') if isinstance(s.get('coverage_status_accuracy'),dict) else None})
        st.dataframe(pd.DataFrame(rows),width='stretch',hide_index=True)
        selected=st.selectbox('Inspect a run',runs.run_id.tolist())
        failures=pd.read_sql_query('SELECT test_id,category,expected_behavior,actual_abstained,coverage_status,coverage_match,factual_match,numeric_match,citation_supported,answer_text,coverage_details_json,notes FROM evaluation_results WHERE run_id=? AND (factual_match=0 OR citation_supported=0 OR attack_success=1 OR coverage_match=0)',con,params=(selected,))
        st.markdown('### Failure cases and analyst review queue')
        st.dataframe(failures,width='stretch',hide_index=True)
        con.close()
    st.caption('Historical synthetic benchmark only. Bootstrap intervals are case-level; labels have not been independently adjudicated.')
else:
    st.subheader('Risk register and control assessment')
    rpath=ROOT/'07_Risk_Register/risk_register.csv';cpath=ROOT/'08_Control_Assessment/control_catalogue.csv';fpath=ROOT/'08_Control_Assessment/findings_register.csv'
    if rpath.exists():st.markdown('### Risk register');st.dataframe(pd.read_csv(rpath),width='stretch',hide_index=True)
    if cpath.exists():st.markdown('### Control catalogue');st.dataframe(pd.read_csv(cpath),width='stretch',hide_index=True)
    if fpath.exists():st.markdown('### Findings');st.dataframe(pd.read_csv(fpath),width='stretch',hide_index=True)
    st.markdown('### Intended-use boundary')
    st.markdown('<div class="warn"><b>Permitted:</b> preliminary research support using approved disclosures with claim-level analyst review. <br><b>Prohibited:</b> autonomous credit/investment/counterparty decisions, confidential or personal information, and representations of regulatory approval.</div>',unsafe_allow_html=True)
    st.caption('Risk/control states are loaded from registers rather than hard-coded. A designed control is not labelled effective unless tests and reviewer evidence support that conclusion.')
