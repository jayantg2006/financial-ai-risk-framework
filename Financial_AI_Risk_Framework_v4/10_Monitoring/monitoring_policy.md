# Monitoring and change policy (proposed; not a live service)

The repository is an offline prototype. Its current SQLite ledger records benchmark configuration, split, code/corpus version, benchmark hash, model/retrieval method, top-K, case metrics and summary. It does **not** provide production request telemetry, access control, data-retention enforcement, uptime or live alerting. Avoid storing sensitive user questions in a production system without a privacy/legal review.

## Validation monitoring indicators

Track by configuration, company/report/year and category: factual/numerical match, citation support, P@K/Recall@K/MRR, correct and false abstention, attack success, unsupported claims, consistency, parser empty-page/table warnings, and human-review disagreement. Always show counts/denominators, benchmark/corpus/model versions, and uncertainty intervals. Any material citation mismatch, unsupported number, leak, successful injection or wrong-year response is an incident regardless of aggregate score.

## Proposed cadence (not operational)

- Every source/model/prompt/parser/index change: run unit, PDF/table, adversarial, validation and regression tests.
- Before release: independent review of intended use, data rights/privacy, access controls and all material numbers/citations.
- In a future controlled pilot: weekly failure sample and monthly versioned benchmark, with quarterly independent review. Define a named owner, incident route, retention and alert thresholds before deployment.

No thresholds in this prototype should be treated as production SLAs. The locked holdout is reserved for a final frozen assessment, not recurring tuning.
