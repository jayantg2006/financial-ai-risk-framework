# FDIA V4 architecture

1. **Ingestion and provenance.** JSON fixtures and PDFs are extracted page by page. The system records document metadata, a SHA-256 file hash, page count and extraction quality flags. PDF table rows are preserved when `page.find_tables()` is available; visual verification remains mandatory for material table use.
2. **Chunking.** Text is split within each page with overlap; table rows become separate chunks retaining page and table IDs. `fdia.models` defines the document, chunk, citation and claim-check records.
3. **Retrieval.** `LexicalRetriever` implements a BM25-style sparse baseline. `FaissSemanticRetriever` optionally encodes text using a SentenceTransformer and cosine-like inner-product FAISS index. Company and financial-year filters are applied before returning evidence.
4. **Evidence and security gates.** High-ranked injection-pattern passages are refused; lower-ranked untrusted passages are removed from context. Target metric and year constraints gate deterministic sentence selection. These rules are heuristics, not robust prompt-injection proof or entailment.
5. **Generation and verification.** The baseline returns source sentences or deterministic cross-year arithmetic. NIM is opt-in and must produce structured claims, exact quotes and numeric tokens matching a returned source span. This verifies quotation/number presence only; it does not establish that the claim follows logically from the quote.
6. **Evaluation.** Eight categories, separate development/validation/holdout files, case-level bootstrap intervals and run-stamped SQLite records. The holdout manifest hash is checked and the CLI requires `--allow-holdout`.
7. **Interface and governance.** Streamlit displays answer status, limitations, claims, citations, retrieved source passages, run comparisons and registers.

## Four configurations

| Name | Retrieval | Answer generation |
|---|---|---|
| baseline | BM25 lexical | deterministic source extraction/calculation |
| nim | BM25 lexical | NVIDIA NIM; quote/numeric gate |
| semantic_baseline | sentence-transformer + FAISS | deterministic source extraction/calculation |
| semantic_nim | sentence-transformer + FAISS | NVIDIA NIM; quote/numeric gate |

The test data in the repository is synthetic. No configuration should be inferred superior without comparable executions on reviewed cases and a frozen corpus/version.
