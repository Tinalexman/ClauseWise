import pytest

from src.retrieval.engine import RetrievalConfig, RetrievalEngine, RetrievedEvidence


def test_retrieval_config_enum() -> None:
    assert RetrievalConfig.HYBRID_RERANKER_FILTER == 5
    assert RetrievalConfig(1) == RetrievalConfig.BM25_ONLY


def test_engine_init_defaults() -> None:
    engine = RetrievalEngine()
    assert engine.config == RetrievalConfig.HYBRID_RERANKER_FILTER


def test_engine_init_custom_config() -> None:
    engine = RetrievalEngine(config=RetrievalConfig.BM25_ONLY)
    assert engine.config == RetrievalConfig.BM25_ONLY


def test_retrieve_raises_before_load() -> None:
    engine = RetrievalEngine()
    with pytest.raises((NotImplementedError, AttributeError)):
        engine.retrieve("indemnity clause", clause_type="indemnity")


@pytest.mark.skip(reason="requires built indexes")
def test_bm25_returns_results() -> None:
    engine = RetrievalEngine(config=RetrievalConfig.BM25_ONLY)
    engine.load()
    results = engine.retrieve("automatic renewal subscription", top_k=3)
    assert len(results) <= 3
    assert all(isinstance(r, RetrievedEvidence) for r in results)


@pytest.mark.skip(reason="requires built indexes")
def test_hybrid_filter_respects_clause_type() -> None:
    engine = RetrievalEngine(config=RetrievalConfig.HYBRID_RERANKER_FILTER)
    engine.load()
    results = engine.retrieve("auto-renew", clause_type="auto_renewal", top_k=5)
    for r in results:
        assert r.clause_type == "auto_renewal"
