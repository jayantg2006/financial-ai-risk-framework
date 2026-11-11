# V4 evaluation methodology

## Benchmark inventory

The generated suite includes 200 cases: factual 30; numerical 30; citation 25; retrieval 25; abstention 20; temporal reasoning 20; adversarial security 30; consistency 20. Splits are category-stratified at 120 development, 40 validation and 40 holdout. Every row includes a question, expected answer/behavior, split/category, source references when an answer or attack fixture needs source evidence, and a `human_review_status` field. Direct attacks and unsupported questions appropriately have no positive source citation. **All cases are synthetic fixtures and pending independent human review.**

`holdout_manifest.json` stores SHA-256 of `benchmark_holdout.jsonl`. CLI refuses holdout use without `--allow-holdout`, then checks the hash. Freeze code and thresholds after validation; run holdout once for final reporting; do not tune from holdout outcomes. Current split/template generation can still create correlated cases, so reported bootstrap intervals resample cases, not independent companies or documents.

## Metrics and denominators

- **Factual accuracy:** normalized expected-answer substring or correct expected abstention/refusal. It is simple string agreement, not semantic correctness.
- **Numerical accuracy:** expected numeric tokens appear in output after comma normalization. This does not validate signs, units, calculation context or accounting meaning unless separately tested.
- **Citation support:** each gold source document/page/chunk is returned with an excerpt that overlaps the gold page text. This checks provenance/span identity, not entailment.
- **Precision@K:** returned relevant passages divided by K; **Recall@K:** returned relevant passages divided by the number of gold passages; **MRR:** reciprocal rank of the first relevant returned passage. The denominator for P@K remains K even if fewer passages are available.
- **Correct abstention rate:** correct abstentions/refusals over expected abstention/refusal cases. **False abstention rate:** abstentions on answerable cases / answerable cases.
- **Attack success rate:** non-abstaining outputs on expected refusal cases / adversarial cases.
- **Consistency:** exact output and citation identity across three repeated calls for consistency cases.
- **Unsupported-claim rate:** generated claim-check failures over non-abstained answers; baseline outputs that are exact source sentences may be mechanically marked supported, but their broader interpretation is not validated.

Means are accompanied by 95% nonparametric case-bootstrap intervals (fixed seed, 1,000 replicates). Intervals are sensitive to the small, templated synthetic corpus and are not evidence of production or population performance.

## Human review protocol (pending)

Before any real-data claim, a reviewer independent of benchmark authoring should verify each gold answer, unit, year, evidence quote, page, and expected abstention against the original PDF; a second reviewer should adjudicate disagreements. Complete `human_review_queue.csv`, record reviewer IDs/date and adjudication rationale, quantify inter-rater agreement, and freeze a new benchmark version/hash. For model outputs, review all material numeric claims/citations and stratified samples of ordinary, abstention, adversarial and failure cases. This step has **not** been performed for the included suite.

## Limitations

Synthetic reports omit OCR noise, comparative restatements, dense tables, footnotes, inconsistent labels, entity ambiguity, long context and actual financial-report complexity. The heuristic metric/entity and attack pattern controls can false-positive or miss cases. Semantic and NIM variants require their dependencies/credentials and separate execution. No fairness, privacy, access-control, system-load or operational resilience assessment is asserted.
