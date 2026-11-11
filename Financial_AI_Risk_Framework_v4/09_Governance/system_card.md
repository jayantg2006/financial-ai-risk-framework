# FDIA V4 system card

**System:** Financial Document Intelligence Assistant (prototype)  
**Version:** 4.0.0  
**Status:** Research-support demonstration; not production approved.  
**Data included:** The interactive application indexes 15 approved public reports for Reliance Industries, Bharti Airtel, HDFC Bank, ICICI Bank and State Bank of India across FY2023-24, FY2024-25 and FY2025-26. The separate 200-case evaluation benchmark and unit-test fixtures use synthetic Acme Industries reports and synthetic attacks. Their scores do not measure performance on the 15 public reports.  
**Models:** BM25-style lexical baseline and optional sentence-transformer/FAISS; optional NVIDIA NIM model configured at runtime. Provider/model are stored per benchmark run.

## Intended use and audience

Find and quote information in authorized reports; compute narrow reported-value changes; support preliminary analyst research. Human source verification is required.

## Prohibited use

Autonomous credit, lending, underwriting, counterparty, investment or regulatory decisions; private/confidential or personal data; use as legal/accounting assurance; public claims of validation or safety.

## Safeguards and scope

Company/year metadata filters, document approval status, page-aware provenance, source-sentence response, narrow deterministic arithmetic, abstention, query-coverage statuses for company comparisons, attack-pattern checks, NIM quote/numeric gate, locked benchmark protocol and SQL run metadata. Controls are heuristic and have not been independently validated. Exact quotation does not prove entailment or completeness.

## Known limitations

Human benchmark review pending; all benchmark labels are self-generated and synthetic. PDF/table extraction requires visual checks. The current system does not robustly reconcile restatements, units across source tables, accounting policies, entity mergers, OCR errors or legal footnotes. No user access control, privacy/retention, fairness, scale, latency, disaster recovery or production monitoring assessment is completed. NIM was not run without credentials. Semantic results depend on the actual model version and index execution.

## Change and incident expectations

Any source-corpus, parser, chunking, embedding, prompt, model, threshold or calculation change requires versioning, development/validation regression and security tests. Only after freeze should the locked holdout be run. Material wrong-year, unsupported numeric, citation, prompt-injection, sensitive-data or unavailability events should be escalated and documented.
