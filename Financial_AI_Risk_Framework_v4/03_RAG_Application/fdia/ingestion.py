from __future__ import annotations
import hashlib,json
from pathlib import Path
from typing import Any

def extract_pdf(pdf_path:str|Path,metadata:dict[str,Any],output_json:str|Path,*,extract_tables:bool=False)->dict[str,Any]:
    """Extract page text and provenance; structured table detection is opt-in because it is expensive."""
    try: import pymupdf as fitz
    except ImportError as exc: raise RuntimeError("Install PyMuPDF to ingest annual-report PDFs.") from exc
    pdf_path=Path(pdf_path); raw=pdf_path.read_bytes(); pages=[]; empty=[]; table_errors=[]
    with fitz.open(pdf_path) as doc:
        for pn,page in enumerate(doc,start=1):
            text=page.get_text("text").strip()
            if not text: empty.append(pn)
            tables=[]
            if extract_tables:
                try:
                    finder=getattr(page,"find_tables",None)
                    if finder:
                        for ti,t in enumerate(finder().tables,start=1):
                            rows=t.extract() or []
                            if rows: tables.append({"table_id":f"p{pn}-t{ti}","rows":rows})
                except Exception: table_errors.append(pn)
            pages.append({"page":pn,"section":"Extracted PDF page","text":text,"tables":tables})
        count=len(doc)
    payload={"metadata":{**metadata,"page_count":count,"file_hash":hashlib.sha256(raw).hexdigest(),"processing_status":"extracted" if not empty and not table_errors else "extracted-with-quality-flags"},"pages":pages,"quality":{"empty_pages":empty,"table_extraction_errors":table_errors,"character_count":sum(len(p["text"]) for p in pages),"tables_found":sum(len(p["tables"]) for p in pages),"table_extraction":"PyMuPDF find_tables requested; visually review material tables" if extract_tables else "not run (page text extracted; table detection is optional and may be slow)"}}
    out=Path(output_json);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8");return payload
