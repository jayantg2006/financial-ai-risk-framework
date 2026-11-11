from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any

@dataclass(frozen=True)
class Document:
    document_id: str
    company: str
    financial_year: str
    document_type: str
    source_url: str
    publication_date: str
    page_count: int
    status: str = "approved"
    file_hash: str | None = None
    processing_status: str | None = None
    reporting_basis: str = "not specified"
    currency: str = "not specified"
    ticker: str | None = None
    period_end: str | None = None

@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    document_id: str
    company: str
    financial_year: str
    page: int
    section: str
    text: str
    source_url: str
    evidence_type: str = "text"
    table_id: str | None = None
    source_hash: str | None = None
    reporting_basis: str = "not specified"
    def to_dict(self) -> dict[str, Any]: return asdict(self)

@dataclass(frozen=True)
class Citation:
    chunk_id: str
    document_id: str
    company: str
    financial_year: str
    page: int
    excerpt: str
    support_status: str = "pending_review"
    def to_dict(self) -> dict[str, Any]: return asdict(self)

@dataclass(frozen=True)
class ClaimCheck:
    claim: str
    supported: bool
    verification_method: str
    support_quote: str | None = None
    citation_ids: tuple[str, ...] = ()
    limitation: str | None = None

@dataclass
class Answer:
    question: str
    text: str
    citations: list[Citation]
    confidence: str
    abstained: bool
    limitation: str | None = None
    retrieved_chunks: list[Chunk] | None = None
    claim_checks: list[ClaimCheck] = field(default_factory=list)
    config_name: str = "baseline"
    verification_status: str = "heuristic"
    coverage_status: str = "not_assessed"
    coverage_details: dict[str, Any] = field(default_factory=dict)
    generation_status: str = "not_used"

def risk_band(score: int) -> str:
    if score <= 4: return "Low"
    if score <= 9: return "Moderate"
    if score <= 16: return "High"
    return "Critical"
