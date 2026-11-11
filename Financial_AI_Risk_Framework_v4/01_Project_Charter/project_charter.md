# Project Charter — FDIA Independent Validation

## Purpose

Develop and independently assess a financial-document RAG application for preliminary analyst research. The application is designed to retrieve evidence from approved corporate disclosures, produce a bounded answer, cite the source, and abstain when evidence is insufficient.

## Intended use

Permitted for preliminary research assistance by financial, credit, risk, and research analysts. Every material output requires human review against the cited source.

## Prohibited use

No autonomous credit approval, investment recommendation, final counterparty decision, confidential banking data, personal financial information, or claim of regulatory certification.

## Assessment questions

1. Is the answer factually supported by the approved corpus?
2. Is the correct company and reporting year retrieved?
3. Are numerical claims and calculations reliable?
4. Are citations precise and complete?
5. Does the system abstain when evidence is unavailable?
6. Does it safely handle direct and indirect prompt injection?
7. Can results be reproduced and monitored after change?

## Success criteria

The project is complete when the system, benchmark, metrics, risk register, controls, monitoring artefacts, and limitations are reproducible from the repository. Results must include negative findings and must not be represented as universal safety evidence.
