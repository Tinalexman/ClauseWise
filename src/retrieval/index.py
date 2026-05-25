"""Index management for the Retrieval Engine (§3.2).

Provides three index types used by ``RetrievalEngine``:

- ``BM25Index``        — sparse keyword index (local, no API cost)
- ``VoyageIndex``      — dense vector index via Voyage 2 embeddings + ChromaDB
- ``VoyageReranker``   — cross-encoder reranker via Voyage Reranker API

All indexes are built from the evidence corpus at startup and
persisted so subsequent loads are fast.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import time

import chromadb
import voyageai
from rank_bm25 import BM25Okapi

from src.config import settings
from src.models import EvidenceItem

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Evidence corpus loader
# ──────────────────────────────────────────────────────────────


class EvidenceCorpus:
    """Loads the evidence corpus from JSONL and provides fast lookups by ID.

    All indexes share this single corpus instance so they agree on
    the document set (§2.2).
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        path = path or settings.evidence_corpus_path
        self.items: List[EvidenceItem] = []
        self._by_id: Dict[str, EvidenceItem] = {}

        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    item = EvidenceItem(**json.loads(line))
                    self.items.append(item)
                    self._by_id[item.evidence_id] = item
            logger.info("Loaded %d evidence items from %s", len(self.items), path)
        else:
            logger.warning("Evidence corpus not found at %s — empty corpus", path)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, idx: int) -> EvidenceItem:
        return self.items[idx]

    def get(self, evidence_id: str) -> Optional[EvidenceItem]:
        return self._by_id.get(evidence_id)

    @property
    def texts(self) -> List[str]:
        return [item.text for item in self.items]

    @property
    def ids(self) -> List[str]:
        return [item.evidence_id for item in self.items]


# ──────────────────────────────────────────────────────────────
# BM25 sparse index (§3.2)
# ──────────────────────────────────────────────────────────────


class BM25Index:
    """Sparse keyword index built from the evidence corpus.

    Uses `rank_bm25.BM25Okapi` under the hood. Purely local — no API cost.
    """

    def __init__(self, corpus: EvidenceCorpus) -> None:
        self._corpus = corpus
        tokenized = [self._tokenize(t) for t in corpus.texts]
        self._bm25 = BM25Okapi(tokenized)
        logger.info("BM25 index built on %d documents", len(corpus))

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Simple whitespace + lowercase tokenizer."""
        return text.lower().split()

    def search(self, query: str, k: int = 15) -> List[Tuple[EvidenceItem, float]]:
        """Retrieve top-k evidence items with BM25 scores."""
        tokenized_query = self._tokenize(query)
        scores = self._bm25.get_scores(tokenized_query)
        # Get top-k indices sorted by score descending
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[
            :k
        ]

        results: List[Tuple[EvidenceItem, float]] = []
        for idx in top_indices:
            if scores[idx] > 0:
                results.append((self._corpus[idx], scores[idx]))
        return results


# ──────────────────────────────────────────────────────────────
# Voyage 2 dense index (§3.2, replacing FAISS + all-MiniLM-L6-v2)
# ──────────────────────────────────────────────────────────────


class VoyageIndex:
    """Dense vector index using Voyage 2 embeddings stored in ChromaDB.

    On first build:
        1. Embed the entire evidence corpus via the Voyage 2 API
        2. Store vectors + metadata in a local ChromaDB collection

    On subsequent loads (if ChromaDB collection exists):
        1. Load the collection directly — no re-embedding needed

    On search:
        1. Embed the query via Voyage 2
        2. Query ChromaDB for the nearest neighbours
    """

    def __init__(self, corpus: EvidenceCorpus) -> None:
        self._client = chromadb.PersistentClient(path=str(settings.chroma_persist_dir))
        self._collection_name = "evidence_vectors_voyage2"
        self._voyage = voyageai.Client(api_key=settings.voyage_api_key)
        self._model = settings.voyage_embedding_model

        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        # Build index if this is a fresh collection
        if self._collection.count() == 0 and len(corpus) > 0:
            self._build(corpus)

        logger.info(
            "Voyage index ready — %d vectors in collection '%s'",
            self._collection.count(),
            self._collection_name,
        )

    # ──────────────────────────────────────────────
    # Build
    # ──────────────────────────────────────────────

    def _build(self, corpus: EvidenceCorpus) -> None:
        """Embed the entire corpus and store in ChromaDB."""
        logger.info("Embedding %d documents with Voyage %s …", len(corpus), self._model)

        batch_size = 128
        for start in range(0, len(corpus), batch_size):
            batch = corpus.items[start : start + batch_size]
            texts = [item.text for item in batch]
            ids = [item.evidence_id for item in batch]

            # Embed via Voyage 2 API
            response = self._voyage.embed(
                texts=texts, model=self._model, input_type="document"
            )
            embeddings = response.embeddings

            # Build metadata dicts
            metadatas: List[Dict[str, Any]] = []
            for item in batch:
                meta: Dict[str, Any] = {
                    "evidence_id": item.evidence_id,
                    "source_type": item.source_type.value,
                    "legal_concept": item.legal_concept,
                    "token_count": item.token_count,
                }
                if item.clause_type:
                    meta["clause_type"] = item.clause_type
                if item.risk_category:
                    meta["risk_category"] = item.risk_category
                if item.citation:
                    meta["citation"] = item.citation
                metadatas.append(meta)

            self._collection.add(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=texts,
            )

        logger.info(
            "Index build complete — %d vectors stored", self._collection.count()
        )

    # ──────────────────────────────────────────────
    # Search
    # ──────────────────────────────────────────────

    def search(self, query: str, k: int = 15) -> List[Tuple[EvidenceItem, float]]:
        """Embed the query and return top-k nearest neighbours from ChromaDB."""
        for attempt in range(3):
            try:
                response = self._voyage.embed(
                    texts=[query], model=self._model, input_type="query"
                )
                break
            except Exception as e:
                if "RateLimit" in type(e).__name__ and attempt < 2:
                    wait = 20 * (attempt + 1)
                    logger.warning("Voyage rate limit — waiting %ds", wait)
                    time.sleep(wait)
                else:
                    logger.warning("Dense embed failed (%s) — returning empty", e)
                    return []
        else:
            return []
        query_vector = response.embeddings[0]

        # Query ChromaDB
        results = self._collection.query(
            query_embeddings=[query_vector],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )

        hits: List[Tuple[EvidenceItem, float]] = []
        if results["ids"] and results["ids"][0]:
            for idx, doc_id in enumerate(results["ids"][0]):
                meta = results["metadatas"][0][idx] if results["metadatas"] else {}
                text = results["documents"][0][idx] if results["documents"] else ""
                distance = results["distances"][0][idx] if results["distances"] else 0.0
                # ChromaDB returns cosine distance; convert to similarity score
                score = 1.0 - distance

                item = EvidenceItem(
                    evidence_id=doc_id,
                    text=text,
                    source_type=meta.get("source_type", "legal_dictionary"),
                    legal_concept=meta.get("legal_concept", ""),
                    clause_type=meta.get("clause_type"),
                    risk_category=meta.get("risk_category"),
                    citation=meta.get("citation"),
                    token_count=meta.get("token_count", 0),
                )
                hits.append((item, score))

        return hits


# ──────────────────────────────────────────────────────────────
# Voyage Reranker (§3.2, replacing ms-marco-MiniLM-L-6-v2)
# ──────────────────────────────────────────────────────────────


class VoyageReranker:
    """Cross-encoder reranker via the Voyage Reranker API.

    Takes a query and candidate list, returns a re-ranked top-k.
    """

    def __init__(self) -> None:
        self._voyage = voyageai.Client(api_key=settings.voyage_api_key)
        self._model = settings.voyage_rerank_model

    def rerank(
        self,
        query: str,
        candidates: List[Tuple[EvidenceItem, float]],
        top_k: int = 5,
    ) -> List[Tuple[EvidenceItem, float]]:
        """Rerank candidates using Voyage Reranker and return top-k."""
        if not candidates:
            return []

        documents = [item.text for item, _ in candidates]
        # Map back to original EvidenceItem objects by index
        original_items = [item for item, _ in candidates]

        for attempt in range(3):
            try:
                response = self._voyage.rerank(
                    query=query,
                    documents=documents,
                    model=self._model,
                    top_k=top_k,
                )
                break
            except Exception as e:
                if "RateLimit" in type(e).__name__ and attempt < 2:
                    wait = 20 * (attempt + 1)
                    logger.warning("Voyage rate limit hit — waiting %ds (attempt %d/3)", wait, attempt + 1)
                    time.sleep(wait)
                else:
                    logger.warning("Reranker failed (%s) — returning unranked candidates", e)
                    return candidates[:top_k]
        else:
            return candidates[:top_k]

        results: List[Tuple[EvidenceItem, float]] = []
        for result in response.results:
            idx = result.index
            item = original_items[idx]
            score = result.relevance_score
            results.append((item, score))

        return results
