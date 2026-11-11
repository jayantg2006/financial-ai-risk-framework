from __future__ import annotations

import os
from typing import Iterable

from .models import Chunk
from .rag import LexicalRetriever


class SemanticDependenciesUnavailable(RuntimeError):
    pass


class FaissSemanticRetriever:
    """Sentence-transformer dense retrieval with a FAISS inner-product index."""

    def __init__(self, chunks: Iterable[Chunk], model_name: str | None = None):
        try:
            import faiss
            import numpy as np
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise SemanticDependenciesUnavailable("Install optional dependencies with `pip install -r requirements-semantic.txt` to use sentence-transformer + FAISS retrieval.") from exc
        self.faiss, self.np = faiss, np
        self.chunks = list(chunks)
        if not self.chunks:
            raise ValueError("Cannot build a semantic index with no chunks.")
        self.model_name = model_name or os.getenv("FDIA_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        self.model = SentenceTransformer(self.model_name)
        vectors = self.model.encode([c.text for c in self.chunks], normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
        vectors = np.asarray(vectors, dtype="float32")
        self.index = faiss.IndexFlatIP(vectors.shape[1])
        self.index.add(vectors)

    def retrieve_scored(self, query: str, top_k: int = 5, company: str | None = None, financial_year: str | None = None):
        # Filter after ranking; scan the full index so metadata filters cannot hide a match.
        q = self.model.encode([query], normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False).astype("float32")
        scores, ids = self.index.search(q, len(self.chunks))
        out = []
        for score, idx in zip(scores[0], ids[0]):
            if idx < 0:
                continue
            chunk = self.chunks[int(idx)]
            if company and chunk.company.casefold() != company.casefold():
                continue
            if financial_year and chunk.financial_year.casefold() != financial_year.casefold():
                continue
            out.append((float(score), chunk))
            if len(out) >= top_k:
                break
        return out

    def retrieve(self, query: str, top_k: int = 5, company: str | None = None, financial_year: str | None = None) -> list[Chunk]:
        return [c for score, c in self.retrieve_scored(query, top_k, company, financial_year) if score > 0]
