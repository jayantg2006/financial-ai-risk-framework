# NVIDIA NIM API test steps

This guide separates a provider connectivity check from an evidence-grounded application test. No key is bundled. The repository’s `.env.example` is a placeholder and is not loaded automatically.

## A. Endpoint, key and model connectivity

1. Obtain an NVIDIA NIM API key through your NVIDIA account. Do not put the real key in a source file or commit it.
2. Activate the project virtual environment and install dependencies (`pip install -r requirements.txt`).
3. Set the environment variables in the same terminal that will run the test.

PowerShell:

```powershell
$env:NVIDIA_API_KEY = "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"
$env:NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
$env:NVIDIA_MODEL = "nvidia/nemotron-3.5-bolt-e4b"
python scripts/test_nim_api.py --mode ping
```

macOS/Linux:

```bash
export NVIDIA_API_KEY='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'
export NVIDIA_BASE_URL='https://integrate.api.nvidia.com/v1'
export NVIDIA_MODEL='meta/llama-3.2-90b-vision-instruct'
python scripts/test_nim_api.py --mode ping
```

A successful ping returns a JSON status of `passed` and a response containing `NIM_OK`. This only tests network access, credentials, endpoint and selected model. It does not query a report, test retrieval, or validate citations. The script redacts the key and does not write it to disk.

If it fails, verify that the key is set in the current terminal, the endpoint URL ends in `/v1`, the model is enabled for your account, and the account has quota. HTTP 401/403 normally indicates an invalid or unauthorized key; 404 suggests the model/path is unavailable; 429 indicates quota or rate limiting. The displayed error text is from the provider and may require checking NVIDIA’s current account console.

## B. RAG/API integration on the real filings

After ping succeeds, use a question whose answer is visible on an indexed consolidated statement page:

```bash
python scripts/test_nim_api.py --mode rag \
  --company "Reliance Industries Limited" \
  --year FY2025-26 \
  --question "What were total assets in FY2025-26?"
```

This mode reuses the current report index only when the content hashes of the PDFs and metadata sidecars match its manifest; otherwise it rebuilds the index. It then retrieves passages, calls NIM only if the deterministic evidence gate finds source material, and checks exact quote and numeric-token support. The output includes the source document, PDF page, report URL and gate status. If it abstains before making a model call, choose a statement item that appears verbatim in the selected company/year PDF; do not remove the guard merely to force a call.

## C. Test NIM inside Streamlit

Set the same three environment variables in the terminal and launch the app from the project root:

```bash
streamlit run app/streamlit_app.py
```

Choose `BM25 lexical + NVIDIA NIM`, then choose the exact company and fiscal year and ask a supported factual question. The app should show the NIM output, claim checks and PDF-page citations. A successful `ping` alone does not prove this end-to-end path works.

The response gate is intentionally limited: a verbatim quote plus matching number tokens does not prove semantic entailment, correct accounting interpretation, or completeness. Verify the original PDF before relying on an answer. Provider usage may consume credits or incur charges.
