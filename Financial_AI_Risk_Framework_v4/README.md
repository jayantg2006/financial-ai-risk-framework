# FDIA V4 — NIFTY 50 annual-report assistant

This project indexes annual reports and audited consolidated financial statements for five NIFTY 50 companies over FY2023–24, FY2024–25 and FY2025-26. The latest top-five selection uses market capitalization as of 9 Nov 2026; company names, ranking basis, report URLs and file hashes are recorded in `02_Data_and_Documents/DATA_SOURCES.md` and the per-report manifests.

The Streamlit assistant is for research and manual testing. Check any answer against the cited original PDF page. This is not an investment adviser, credit decision system, or independently validated production tool. The benchmark in `04_Evaluation_Benchmark` is still a separate synthetic software-test suite; do not use its old Acme score reports to claim performance on the real filings.

## 1. Start the app

Use Python 3.10 or later. From the project directory, create and activate a virtual environment and install dependencies.

**Windows PowerShell:**

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**macOS/Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Extract and index page text from the reports. The first run may take several minutes because it processes all report pages. Page text retains the statement rows and figures as extracted by PyMuPDF; it is not a guaranteed structured table. The default fast path does not run computationally expensive table detection. It writes page-aware chunks to `02_Data_and_Documents/processed/chunks.jsonl`.

```bash
python scripts/ingest_documents.py --input 02_Data_and_Documents/raw/annual_reports --reuse-if-current
```

The packaged index has a content-hash manifest, so reuse works even if a ZIP extractor changes file timestamps. To force a complete rebuild after intentionally changing the data or parser, omit `--reuse-if-current`. If app startup indexing fails, the underlying subprocess error is shown in the Streamlit page.

Optional structured table detection is available with `--extract-tables`, but it can be very slow across thousands of pages and extracted tables still require visual checking. Use it only when needed for a smaller selected PDF.

Start the app. It reuses the existing index only when its content hash and the source PDF/metadata hashes match; otherwise it rebuilds the index.

```bash
streamlit run app/streamlit_app.py
```

The default deterministic configurations retrieve passages and return an exact source sentence; they do not call a generative LLM. Select a configuration labelled “NVIDIA NIM generation” to invoke the optional model after the evidence gate passes. Set `NVIDIA_API_KEY` in the same environment that starts Streamlit. The result reports whether generation ran, was skipped by the evidence gate, or failed claim verification. The strict quote check can make generated wording close to the source.

Open the local URL shown by Streamlit, select a company and exact fiscal year, then ask a factual question such as “What were total assets in FY2025-26?” Select the deterministic baseline first. Open each citation and verify the amount, units, consolidated/standalone basis and period against the downloaded report. An abstention means the extractor or current heuristics did not find a sufficiently clear passage; it does not mean the figure is absent from the PDF.

For multi-company comparisons, V4 reports a query coverage status before answering. It distinguishes missing company/year reports (`corpus_coverage_failure`), indexed reports with no retrieved metric passage (`retrieval_failure`), retrieved passages without a verified amount/unit (`evidence_insufficient`), and unclear or inconsistent reporting bases (`clarification_required`). Comparisons require a stated matching basis and independently retrieved evidence for every company. Inspect the Query coverage assessment panel and both report citations. The separate `coverage-control` suite uses controlled fixtures and does not alter the locked synthetic benchmark:

```bash
python scripts/run_evaluation.py --split coverage-control --config baseline
```

For semantic retrieval, install the optional packages once and choose a semantic configuration in the app:

```bash
pip install -r requirements-semantic.txt
```

The model is downloaded on first use. It can take additional time and disk space.

## 2. Check the NVIDIA NIM API separately

The API client does **not** load `.env.example` automatically. Obtain an NVIDIA NIM API key yourself and set it in the current terminal session. Do not paste a real key into source files, commit it, or share terminal logs containing it.

**Windows PowerShell:**

```powershell
$env:NVIDIA_API_KEY = "YOUR_NVIDIA_NIM_KEY"
$env:NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
$env:NVIDIA_MODEL = "meta/llama-3.2-90b-vision-instruct"
python scripts/test_nim_api.py --mode ping
```

**macOS/Linux:**

```bash
export NVIDIA_API_KEY='YOUR_NVIDIA_NIM_KEY'
export NVIDIA_BASE_URL='https://integrate.api.nvidia.com/v1'
export NVIDIA_MODEL='meta/llama-3.2-90b-vision-instruct'
python scripts/test_nim_api.py --mode ping
```

`--mode ping` checks endpoint, authentication and model response only. It asks the provider to return `NIM_OK`; it does not test retrieval, citations or the claim gate. A successful response prints `status: passed`. A missing-key message means the key is absent from that terminal. HTTP 401/403 generally indicates an invalid, expired or unauthorized key; 404 may mean the configured model/endpoint is unavailable; 429 indicates a quota/rate limit; connection and timeout errors indicate network/service issues.

Then test the complete evidence-grounded path on a report passage. Example:

```bash
python scripts/test_nim_api.py --mode rag --company "Reliance Industries Limited" --year FY2025-26 --question "What were total assets in FY2025-26?"
```

Use the exact company/year values displayed in the app. The RAG test re-indexes the reports, sends only retrieved passages to NIM, and prints the answer with source pages. If the deterministic evidence gate cannot find a passage first, it abstains and no NIM generation call is made; try a metric printed in the consolidated statements and verify the PDF manually. `--mode rag` returning a citation is not proof of semantic entailment—the implementation checks exact quoted evidence and numeric tokens only.

To try NIM inside the app, set the same variables in that same terminal before `streamlit run app/streamlit_app.py`, then select **BM25 lexical + NVIDIA NIM**. NIM use may incur provider charges/credits according to your account.

## 3. Tests and troubleshooting

Run the local code tests:

```bash
python -m unittest discover -s tests -v
```

The unit-test fixtures include synthetic cases, but the interactive app now loads the real report corpus. The existing benchmark remains fictional and is not a real-filings validation set. Do not run `scripts/run_evaluation.py` against the real report corpus using the old Acme benchmark; use it only after creating and independently checking a benchmark for these actual report pages.

If the app says it found no chunks, confirm that each report PDF and matching `<pdf-stem>.metadata.json` file are present under `02_Data_and_Documents/raw/annual_reports/`, and that the sidecar says `"status": "approved"`. If a report page is scanned or its table did not extract, check the extraction metadata and original PDF; no OCR fallback is claimed.

On Windows, a `UnicodeEncodeError` mentioning `cp1252` while writing an `.extracted.json` file means a report contains characters such as `₹` that the legacy default encoding cannot write. The current extraction and index paths explicitly use UTF-8. Use this refreshed version; to rebuild manually, run the ingestion command in the active environment. Do not change the Windows system locale.

See `02_Data_and_Documents/DATA_SOURCES.md` for the selection and report provenance. Each PDF has a metadata sidecar with its source URL, SHA-256, page count and automated candidate statement-page hints; treat those hints as navigation aids and verify the cited page and scale in the original PDF.
