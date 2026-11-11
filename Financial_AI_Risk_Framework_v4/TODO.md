# V4 delivery status and remaining work

## Implemented and exercised in this prototype

- [x] Page-aware JSON/PDF extraction, source hash, metadata, extraction-quality flags, and table-row path when supported.
- [x] BM25 lexical baseline plus optional sentence-transformer/FAISS semantic configuration.
- [x] Four named comparison configurations, with run/config/split/model/corpus/benchmark metadata.
- [x] Metric/year/period-aware deterministic evidence answers, narrow cross-year arithmetic, quote citations, abstention, and heuristic direct/indirect prompt-injection handling.
- [x] Optional NVIDIA NIM structured-claim path with exact source-quote and numeric-token gate.
- [x] 200 synthetic benchmark cases over eight categories, split 120/40/40, with locked holdout hash and case-bootstrap intervals.
- [x] SQLite result store and Streamlit comparison/risk dashboard.
- [x] Query coverage assessment distinguishes missing company/year reports, retrieval failures, insufficient metric evidence and reporting-basis clarification; multi-company comparisons require evidence for each company and a matching stated basis.
- [x] Separate controlled coverage benchmark suite (`coverage-control`) records coverage status and coverage match in the evaluation database without changing the locked synthetic holdout.
- [x] Risk register, control catalogue, findings, system card, intended-use policy, monitoring proposal, and final V4 report.
- [x] 17 unit/integration tests passed; local Streamlit health endpoint returned `ok`.
- [x] Lexical and semantic deterministic variants executed on development, validation and holdout. Holdout was executed once after freeze.

## Open before claiming real-world validation or operational readiness

- [ ] Obtain rights-cleared real financial filings, preserve their exact version/hash, and validate PDF, OCR, tables, footnotes and restatements against original pages.
- [ ] Independently review all 200 synthetic labels first as a process check, then build a separate human-adjudicated benchmark over real filings; add second-review adjudication and reviewer agreement.
- [ ] Run both NVIDIA NIM configurations with a real, authorized key and record model/version, request/response behavior, latency, cost, retries and failures. Do not treat the mocked unit test as provider validation.
- [ ] Evaluate quote-to-claim semantic entailment, completeness, unit/sign/context correctness and source-period reconciliation; exact string/token checks are not enough.
- [ ] Investigate low P@5 and compare semantic vs lexical retrieval on a materially larger, independently authored corpus. Do not tune on the locked holdout.
- [ ] Complete privacy, access control, retention, fairness, threat-model, load/latency, availability, incident-response and production monitoring reviews.
- [ ] Define named control owners, independent effectiveness evidence, alert thresholds and release approval for any pilot.

The indexed corpus contains 15 approved public company reports. The 200-case benchmark remains synthetic, and its human-review queue is pending. The historical scores below describe only the synthetic fixtures; they are not measurements on the 15 reports. No open validation item is represented as completed by a passing synthetic test.
