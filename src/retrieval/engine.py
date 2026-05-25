"""Retrieval Engine (§3.2): routes queries to the appropriate index
strategy and applies fusion, filtering, and reranking.

Input:  ClauseUnit (from DocumentProcessor)
Output: List[EvidenceItem] with relevance scores

Five retrieval strategies, determined by ``RetrievalConfig.method``:

    bm25                    — sparse keyword search only
    dense                   — Voyage 2 dense vector search only
    hybrid                  — reciprocal-rank fusion of BM25 + dense
    hybrid_reranker         — fusion → Voyage Reranker
    hybrid_reranker_filter  — fusion → clause-type filter → reranker
"""

from __future__ import annotations

import logging
from typing import List, Tuple

from src.config import RetrievalConfig
from src.models import ClauseUnit, EvidenceItem
from src.retrieval.index import BM25Index, EvidenceCorpus, VoyageIndex, VoyageReranker

logger = logging.getLogger(__name__)

# RRF constant (k = 60 is standard in information retrieval)
_RRF_K = 60


class RetrievalEngine:
    """Orchestrates evidence retrieval against the corpus.

    Usage::

        engine = RetrievalEngine(RetrievalConfig(method="hybrid_reranker_filter"))
        evidence = engine.retrieve(clause)
    """

    def __init__(self, config: RetrievalConfig) -> None:
        self.config = config
        # Shared corpus instance — all indexes agree on the document set
        self.corpus = EvidenceCorpus()
        self.bm25 = BM25Index(self.corpus)
        self.dense = VoyageIndex(self.corpus)
        self.reranker = VoyageReranker()
        logger.info(
            "RetrievalEngine ready — method=%s, k=%d",
            config.method,
            config.k,
        )

    # ──────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────

    def retrieve(self, clause: ClauseUnit, k: int | None = None) -> List[EvidenceItem]:
        """Run the full retrieval pipeline for *clause*.

        Steps (§3.2):
            1. Formulate query
            2. Retrieve candidates (BM25 / dense / hybrid)
            3. Filter by clause type  (``hybrid_reranker_filter`` only)
            4. Rerank               (methods containing ``reranker``)
        """
        k = k or self.config.k
        query = self._formulate_query(clause)

        # ── Step 2: Retrieve candidates ──────────────────────────
        candidates = self._retrieve_candidates(query, clause, k)

        # ── Step 4: Rerank ───────────────────────────────────────
        if "reranker" in self.config.method:
            candidates = self.reranker.rerank(query, candidates, top_k=k)

        # Strip scores — the SRS output is List[EvidenceItem]
        return [item for item, _ in candidates[:k]]

    # ──────────────────────────────────────────────────────────────
    # Query formulation (§3.2, Step 1)
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def _formulate_query(clause: ClauseUnit) -> str:
        """Build a search query from the clause.

        Prepending the clause type provides a strong lexical signal
        for both BM25 and dense retrieval.
        """
        return f"{clause.clause_type.value}: {clause.text}"

    # ──────────────────────────────────────────────────────────────
    # Candidate retrieval (§3.2, Step 2 + Step 3)
    # ──────────────────────────────────────────────────────────────

    def _retrieve_candidates(
        self, query: str, clause: ClauseUnit, k: int
    ) -> List[Tuple[EvidenceItem, float]]:
        """Fetch top candidates according to ``self.config.method``."""
        method = self.config.method
        candidate_count = k * 3  # fetch 3× for reranking headroom

        if method == "bm25":
            return self.bm25.search(query, k=candidate_count)

        if method == "dense":
            return self.dense.search(query, k=candidate_count)

        if method in ("hybrid", "hybrid_reranker", "hybrid_reranker_filter"):
            bm25_results = self.bm25.search(query, k=candidate_count)
            dense_results = self.dense.search(query, k=candidate_count)
            candidates = self._reciprocal_rank_fusion(bm25_results, dense_results)

            # Step 3: Filter by clause type
            if method == "hybrid_reranker_filter":
                candidates = [
                    (item, score)
                    for item, score in candidates
                    if item.clause_type is None
                    or item.clause_type == clause.clause_type.value
                ]

            return candidates

        raise ValueError(f"Unknown retrieval method: {method}")

    # ──────────────────────────────────────────────────────────────
    # Reciprocal rank fusion
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def _reciprocal_rank_fusion(
        list_a: List[Tuple[EvidenceItem, float]],
        list_b: List[Tuple[EvidenceItem, float]],
    ) -> List[Tuple[EvidenceItem, float]]:
        """Merge two ranked lists using RRF.

        The original score from each index is discarded — only rank
        position matters for fusion. The merged list is sorted by
        the RRF score descending.
        """
        rrf_scores: dict[str, float] = {}
        item_map: dict[str, EvidenceItem] = {}

        for rank, (item, _) in enumerate(list_a):
            rrf_scores[item.evidence_id] = 1.0 / (_RRF_K + rank)
            item_map[item.evidence_id] = item

        for rank, (item, _) in enumerate(list_b):
            rrf_scores[item.evidence_id] = rrf_scores.get(
                item.evidence_id, 0.0
            ) + 1.0 / (_RRF_K + rank)
            item_map[item.evidence_id] = item

        # Sort by RRF score descending
        sorted_ids = sorted(rrf_scores, key=lambda eid: rrf_scores[eid], reverse=True)

        return [(item_map[eid], rrf_scores[eid]) for eid in sorted_ids]
