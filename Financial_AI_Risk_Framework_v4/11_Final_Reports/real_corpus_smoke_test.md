# Real-corpus integration smoke test

**Run date:** 10 November 2026  
**Purpose:** Confirm the V4 research prototype can ingest the 15 downloaded issuer reports and answer a simple real-report query with a page citation. This is a smoke test, not a comprehensive accuracy validation.

## Corpus

- 15 official annual/integrated reports or financial-statement PDFs: five companies over FY2023-24, FY2024-25 and FY2025-26.
- Issuers: Bharti Airtel, HDFC Bank, ICICI Bank, Reliance Industries and State Bank of India.
- PDF integrity/signature, page counts, SHA-256 values, issuer and fiscal-year identity were checked. ICICI Bank’s FY2023-24 and FY2024-25 files are the separate Financial Statements PDFs linked from the issuer’s official annual-report archive.
- Page-aware extraction generated 31,747 text chunks from all 15 reports. Default processing preserves extracted PDF page text and citations. Structured table detection is optional and deliberately not part of the default path because the PyMuPDF page-table pass was prohibitively slow across thousands of pages.

## Checks completed

- `python -m unittest discover -s tests -v`: **21 tests passed**.
- `python -m compileall -q 03_RAG_Application scripts app`: completed successfully.
- Streamlit `AppTest`: **0 app exceptions**; it displayed the five companies, three fiscal years, and all 15 reports.
- End-to-end deterministic UI smoke query: “What were total assets in FY2025-26?” for Reliance Industries Limited. The app returned a concise answer with **PDF page 100** citation and source link. It selected the `Total Assets 21,78,140` row from the consolidated balance sheet, rather than a different subsidiary/notes value elsewhere in the report.
- Freshness-aware indexing command reused the existing 31,747-chunk index instead of reprocessing unchanged PDFs.
- NIM CLI help and missing-credential handling were checked. No NVIDIA API key was present, so no external NIM request was attempted; connectivity and live generation remain for the user to test with their own account/key.

## Important limitations

The real-corpus test is only one query and does not establish answer accuracy, coverage, or safety across all companies/metrics. Page text extraction is not guaranteed to preserve financial table row/column alignment; OCR is not provided for image-only pages. Currency is INR, but units and scales vary (for example crore, million or omitted thousands) by company/report/statement. The assistant intentionally asks the analyst to confirm the printed scale and reporting basis on the cited source page. Exact-source quotation and token checks do not prove semantic entailment or accounting interpretation.

The historical 200-case benchmark remains synthetic Acme data and must not be cited as performance evidence for these real filings. Use the app for local research and manual verification only, not for investment, credit or other autonomous decisions.
