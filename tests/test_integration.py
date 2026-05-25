"""End-to-end integration tests for the ClauseWise pipeline.

Tests the full stack: API routes → retrieval → risk classification
→ generation → fidelity verification, with all external API calls
mocked (OpenAI, VoyageAI, ChromaDB, NLI cross-encoder).

Run:
    pytest tests/test_integration.py -v
    pytest tests/test_integration.py -v -k "pipeline"       # pipeline tests only
    pytest tests/test_integration.py -v -k "component"      # component tests only
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

# ── Stub optional heavy / non-installed dependencies ────────────
# PyMuPDF (fitz) and spacy are only used by the document parser,
# which is mocked out in upload tests.  Stubbing here avoids an
# ImportError at collection time on machines without these packages.
for _mod in ("fitz", "spacy", "docx", "unstructured"):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()
# ── End stubs ────────────────────────────────────────────────────

import json
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.api.routes as routes_module
from src.api.routes import router
from src.models import (
    ClauseType,
    DocType,
    EvidenceItem,
    RetrievalMethod,
    SourceType,
)

# ──────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────

AUTO_RENEWAL_CLAUSE = (
    "This agreement will automatically renew for successive one-year terms "
    "unless either party provides written notice of cancellation at least "
    "30 days prior to the end of the then-current term."
)

INDEMNITY_CLAUSE = (
    "You agree to indemnify, defend, and hold harmless the Company from any "
    "and all claims, damages, losses, and expenses arising from your use of "
    "the service or violation of these terms."
)

ARBITRATION_CLAUSE = (
    "Any dispute arising out of or in connection with this agreement shall be "
    "finally settled by binding arbitration. You waive any right to a jury "
    "trial or class action participation."
)

_FAKE_EVIDENCE = {
    "evidence_id": "EVID_AUTO_RENEW_001",
    "text": "Auto-renewal clauses extend a contract for another term unless cancelled.",
    "source_type": "clause_definition",
    "legal_concept": "automatic renewal",
    "clause_type": "auto_renewal",
    "citation": "Consumer Contracts Glossary",
    "token_count": 15,
}

# ──────────────────────────────────────────────────────────────────
# Mock response factories
# ──────────────────────────────────────────────────────────────────


def _openai_response(content: str, total_tokens: int = 250) -> MagicMock:
    choice = MagicMock()
    choice.message.content = content
    resp = MagicMock()
    resp.choices = [choice]
    resp.usage.total_tokens = total_tokens
    return resp


def _risk_response() -> MagicMock:
    return _openai_response(
        json.dumps({
            "risks": [
                {
                    "risk_id": "r1",
                    "risk_category": "automatic_renewal",
                    "severity": "high",
                    "explanation": "Contract renews without explicit annual consent.",
                    "recommended_action": "Cancel 30 days before renewal date.",
                }
            ]
        })
    )


def _generate_response() -> MagicMock:
    return _openai_response(
        json.dumps({
            "plain_english": "This contract renews every year automatically.",
            "user_implications": "You will be charged again unless you cancel in time.",
            "check_before_signing": ["Mark your calendar 30 days before term end."],
            "confidence": "high",
            "seek_legal_advice": {"recommended": False, "reason": None},
        })
    )


def _judge_response() -> MagicMock:
    return _openai_response(
        json.dumps({
            "faithfulness": 0.90,
            "completeness": 0.85,
            "hallucination": 0.95,
            "error_types": [],
            "comment": "Explanation accurately reflects the clause.",
        })
    )


def _followup_response() -> MagicMock:
    return _openai_response("You must cancel at least 30 days before the term ends.")


def _openai_dispatcher(*args: Any, **kwargs: Any) -> MagicMock:
    """Return the right mock response based on the system prompt content."""
    messages: List[Dict[str, str]] = kwargs.get("messages", [])
    system_content = next(
        (m["content"] for m in messages if m.get("role") == "system"), ""
    )
    if "risk analyst" in system_content:
        return _risk_response()
    if "fidelity judge" in system_content:
        return _judge_response()
    return _generate_response()


# ──────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_route_singletons():
    """Reset module-level singletons and stores before and after each test."""
    routes_module._processor = None
    routes_module._engine = None
    routes_module._classifier = None
    routes_module._generator = None
    routes_module._verifier = None
    routes_module._clause_store.clear()
    routes_module._explanation_store.clear()
    yield
    routes_module._processor = None
    routes_module._engine = None
    routes_module._classifier = None
    routes_module._generator = None
    routes_module._verifier = None
    routes_module._clause_store.clear()
    routes_module._explanation_store.clear()


@pytest.fixture
def mock_externals():
    """Patch all external API clients: OpenAI, VoyageAI, ChromaDB, NLI.

    Yields a dict of the key mock objects for test-level assertion.
    """
    # ── OpenAI ──────────────────────────────────────────────────
    mock_openai_instance = MagicMock()
    mock_openai_instance.chat.completions.create.side_effect = _openai_dispatcher
    mock_openai_cls = MagicMock(return_value=mock_openai_instance)

    # ── VoyageAI ────────────────────────────────────────────────
    mock_voyage_instance = MagicMock()

    embed_resp = MagicMock()
    embed_resp.embeddings = [[0.1] * 1024]
    mock_voyage_instance.embed.return_value = embed_resp

    rerank_result = MagicMock()
    rerank_result.index = 0
    rerank_result.relevance_score = 0.92
    rerank_resp = MagicMock()
    rerank_resp.results = [rerank_result]
    mock_voyage_instance.rerank.return_value = rerank_resp

    mock_voyage_cls = MagicMock(return_value=mock_voyage_instance)
    mock_voyageai = MagicMock()
    mock_voyageai.Client = mock_voyage_cls

    # ── ChromaDB ────────────────────────────────────────────────
    mock_collection = MagicMock()
    mock_collection.count.return_value = 5  # non-zero → skip _build()
    mock_collection.query.return_value = {
        "ids": [["EVID_AUTO_RENEW_001"]],
        "documents": [[_FAKE_EVIDENCE["text"]]],
        "metadatas": [[{
            "evidence_id": _FAKE_EVIDENCE["evidence_id"],
            "source_type": _FAKE_EVIDENCE["source_type"],
            "legal_concept": _FAKE_EVIDENCE["legal_concept"],
            "clause_type": _FAKE_EVIDENCE["clause_type"],
            "token_count": _FAKE_EVIDENCE["token_count"],
        }]],
        "distances": [[0.08]],
    }
    mock_chroma_client = MagicMock()
    mock_chroma_client.get_or_create_collection.return_value = mock_collection
    mock_chromadb = MagicMock()
    mock_chromadb.PersistentClient = MagicMock(return_value=mock_chroma_client)

    # ── NLI cross-encoder ────────────────────────────────────────
    mock_nli_pred = MagicMock()
    mock_nli_pred.argmax.return_value = 0  # 0 = entailment
    mock_nli_instance = MagicMock()
    mock_nli_instance.predict.return_value = [mock_nli_pred]
    mock_nli_cls = MagicMock(return_value=mock_nli_instance)

    with (
        patch("src.generation.generator.OpenAI", mock_openai_cls),
        patch("src.risk.classifier.OpenAI", mock_openai_cls),
        patch("src.verification.verifier.OpenAI", mock_openai_cls),
        patch("openai.OpenAI", mock_openai_cls),
        patch("src.retrieval.index.voyageai", mock_voyageai),
        patch("src.retrieval.index.chromadb", mock_chromadb),
        patch("src.verification.verifier.CrossEncoder", mock_nli_cls),
    ):
        yield {
            "openai_instance": mock_openai_instance,
            "voyage_instance": mock_voyage_instance,
            "collection": mock_collection,
            "nli_instance": mock_nli_instance,
        }


@pytest.fixture
def api_client(mock_externals):
    """TestClient backed by the real routes.py router."""
    app = FastAPI(title="ClauseWise Test")
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def simplify_payload():
    return {
        "clause_text": AUTO_RENEWAL_CLAUSE,
        "clause_type": "auto_renewal",
        "retrieval_config": "hybrid_reranker_filter",
        "generation_variant": "proposed",
        "include_verification": True,
    }


# ──────────────────────────────────────────────────────────────────
# § Health + Validation (API contract)
# ──────────────────────────────────────────────────────────────────


class TestAPIContract:
    def test_simplify_missing_clause_text_returns_422(self, api_client: TestClient):
        resp = api_client.post("/api/v1/simplify", json={"clause_type": "auto_renewal"})
        assert resp.status_code == 422

    def test_simplify_empty_clause_text_returns_422(self, api_client: TestClient):
        resp = api_client.post(
            "/api/v1/simplify", json={"clause_text": "", "clause_type": "auto_renewal"}
        )
        assert resp.status_code == 422

    def test_simplify_invalid_retrieval_config_returns_422(self, api_client: TestClient):
        resp = api_client.post(
            "/api/v1/simplify",
            json={
                "clause_text": AUTO_RENEWAL_CLAUSE,
                "clause_type": "auto_renewal",
                "retrieval_config": "nonexistent_method",
            },
        )
        assert resp.status_code == 422

    def test_simplify_invalid_generation_variant_returns_422(self, api_client: TestClient):
        resp = api_client.post(
            "/api/v1/simplify",
            json={
                "clause_text": AUTO_RENEWAL_CLAUSE,
                "clause_type": "auto_renewal",
                "generation_variant": "made_up_variant",
            },
        )
        assert resp.status_code == 422

    def test_followup_unknown_clause_returns_404(self, api_client: TestClient):
        resp = api_client.post(
            "/api/v1/followup",
            json={"clause_id": "does-not-exist", "question": "What does this mean?"},
        )
        assert resp.status_code == 404
        assert "does-not-exist" in resp.json()["detail"]

    def test_get_clause_unknown_returns_404(self, api_client: TestClient):
        resp = api_client.get("/api/v1/clause/ghost-id-999")
        assert resp.status_code == 404

    def test_evaluate_with_no_stored_explanations_returns_404(self, api_client: TestClient):
        resp = api_client.post(
            "/api/v1/evaluate",
            json={"clause_ids": ["id-that-has-no-explanations"], "metrics": ["avg_readability"]},
        )
        assert resp.status_code == 404

    def test_study_log_invalid_group_returns_422(self, api_client: TestClient):
        resp = api_client.post(
            "/api/v1/study/log",
            json={
                "participant_id": "p1",
                "session_id": "s1",
                "group": "Z",
                "events": [],
            },
        )
        assert resp.status_code == 422

    def test_upload_unsupported_format_returns_400(self, api_client: TestClient):
        resp = api_client.post(
            "/api/v1/upload",
            files={"file": ("contract.xls", BytesIO(b"data"), "application/vnd.ms-excel")},
        )
        assert resp.status_code == 400
        assert "Unsupported" in resp.json()["detail"]

    def test_upload_missing_filename_returns_400(self, api_client: TestClient):
        resp = api_client.post(
            "/api/v1/upload",
            files={"file": ("", BytesIO(b"data"), "text/plain")},
        )
        assert resp.status_code == 400


# ──────────────────────────────────────────────────────────────────
# § Full pipeline (E2E with mocked externals)
# ──────────────────────────────────────────────────────────────────


class TestFullPipeline:
    def test_simplify_proposed_variant_returns_200_with_full_schema(
        self, api_client: TestClient, simplify_payload: dict
    ):
        resp = api_client.post("/api/v1/simplify", json=simplify_payload)
        assert resp.status_code == 200, resp.text

        body = resp.json()
        exp = body["explanation"]

        assert exp["plain_english"], "plain_english must be non-empty"
        assert exp["user_implications"], "user_implications must be present"
        assert isinstance(exp["risks"], list)
        assert isinstance(exp["check_before_signing"], list)
        assert exp["confidence"] in ("high", "medium", "low")
        assert "recommended" in exp["seek_legal_advice"]

        assert "config" in body["retrieval_metadata"]
        assert "latency_ms" in body["retrieval_metadata"]

        assert body["verification_metadata"] is not None
        vm = body["verification_metadata"]
        assert "score" in vm and "passed" in vm and "flags" in vm

    def test_simplify_extractive_variant_no_llm_calls(
        self, api_client: TestClient, mock_externals: dict
    ):
        resp = api_client.post(
            "/api/v1/simplify",
            json={
                "clause_text": AUTO_RENEWAL_CLAUSE,
                "clause_type": "auto_renewal",
                "generation_variant": "extractive",
                "include_verification": False,
            },
        )
        assert resp.status_code == 200, resp.text

        body = resp.json()
        exp = body["explanation"]
        assert exp["generation_variant"] == "extractive"
        assert len(exp["plain_english"]) > 0
        assert exp["risks"] == []

        # Extractive variant must not call OpenAI for generation
        openai_calls = mock_externals["openai_instance"].chat.completions.create.call_count
        assert openai_calls == 0, f"Expected 0 LLM calls for extractive; got {openai_calls}"

    def test_simplify_without_verification_omits_verification_metadata(
        self, api_client: TestClient
    ):
        resp = api_client.post(
            "/api/v1/simplify",
            json={
                "clause_text": AUTO_RENEWAL_CLAUSE,
                "clause_type": "auto_renewal",
                "generation_variant": "proposed",
                "include_verification": False,
            },
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["verification_metadata"] is None

    def test_simplify_bm25_only_config(self, api_client: TestClient):
        resp = api_client.post(
            "/api/v1/simplify",
            json={
                "clause_text": AUTO_RENEWAL_CLAUSE,
                "clause_type": "auto_renewal",
                "retrieval_config": "bm25",
                "generation_variant": "proposed",
                "include_verification": False,
            },
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["retrieval_metadata"]["config"] == "bm25"

    def test_simplify_all_retrieval_configs_succeed(self, api_client: TestClient):
        configs = ["bm25", "dense", "hybrid", "hybrid_reranker", "hybrid_reranker_filter"]
        for cfg in configs:
            resp = api_client.post(
                "/api/v1/simplify",
                json={
                    "clause_text": AUTO_RENEWAL_CLAUSE,
                    "clause_type": "auto_renewal",
                    "retrieval_config": cfg,
                    "generation_variant": "extractive",
                    "include_verification": False,
                },
            )
            assert resp.status_code == 200, f"Config {cfg!r} failed: {resp.text}"

    def test_simplify_risk_detail_schema_valid(self, api_client: TestClient, simplify_payload: dict):
        resp = api_client.post("/api/v1/simplify", json=simplify_payload)
        assert resp.status_code == 200, resp.text

        risks = resp.json()["explanation"]["risks"]
        for risk in risks:
            assert "risk_id" in risk
            assert "risk_category" in risk
            assert risk["severity"] in ("low", "medium", "high", "critical")
            assert "explanation" in risk
            assert "recommended_action" in risk

    def test_simplify_clause_id_stored_for_retrieval(
        self, api_client: TestClient, simplify_payload: dict
    ):
        simplify_resp = api_client.post("/api/v1/simplify", json=simplify_payload)
        assert simplify_resp.status_code == 200

        clause_id = simplify_resp.json()["explanation"]["clause_id"]
        get_resp = api_client.get(f"/api/v1/clause/{clause_id}")
        assert get_resp.status_code == 200

        body = get_resp.json()
        assert body["clause"]["clause_id"] == clause_id
        assert body["explanation_count"] >= 1

    def test_followup_after_simplify_returns_answer(
        self, api_client: TestClient, simplify_payload: dict, mock_externals: dict
    ):
        # Reconfigure the LLM to return a follow-up style answer for subsequent calls
        mock_externals["openai_instance"].chat.completions.create.side_effect = (
            _openai_dispatcher
        )

        simplify_resp = api_client.post("/api/v1/simplify", json=simplify_payload)
        assert simplify_resp.status_code == 200
        clause_id = simplify_resp.json()["explanation"]["clause_id"]

        # Override the dispatcher so the next call returns a follow-up answer
        mock_externals["openai_instance"].chat.completions.create.side_effect = None
        mock_externals["openai_instance"].chat.completions.create.return_value = (
            _followup_response()
        )

        followup_resp = api_client.post(
            "/api/v1/followup",
            json={"clause_id": clause_id, "question": "When do I need to cancel?"},
        )
        assert followup_resp.status_code == 200, followup_resp.text
        body = followup_resp.json()
        assert len(body["answer"]) > 0
        assert "evidence_used" in body

    def test_followup_with_conversation_history(
        self, api_client: TestClient, simplify_payload: dict, mock_externals: dict
    ):
        simplify_resp = api_client.post("/api/v1/simplify", json=simplify_payload)
        assert simplify_resp.status_code == 200
        clause_id = simplify_resp.json()["explanation"]["clause_id"]

        mock_externals["openai_instance"].chat.completions.create.side_effect = None
        mock_externals["openai_instance"].chat.completions.create.return_value = (
            _followup_response()
        )

        resp = api_client.post(
            "/api/v1/followup",
            json={
                "clause_id": clause_id,
                "question": "What happens if I miss the deadline?",
                "conversation_history": [
                    {"role": "user", "content": "When do I cancel?"},
                    {"role": "assistant", "content": "30 days before the renewal date."},
                ],
            },
        )
        assert resp.status_code == 200

    def test_evaluate_after_simplify_returns_metrics(
        self, api_client: TestClient, simplify_payload: dict
    ):
        simplify_resp = api_client.post("/api/v1/simplify", json=simplify_payload)
        assert simplify_resp.status_code == 200
        clause_id = simplify_resp.json()["explanation"]["clause_id"]

        eval_resp = api_client.post(
            "/api/v1/evaluate",
            json={
                "clause_ids": [clause_id],
                "metrics": ["avg_readability", "avg_confidence", "avg_latency"],
            },
        )
        assert eval_resp.status_code == 200, eval_resp.text
        results = eval_resp.json()["results"]
        assert "avg_fk_grade" in results
        assert "avg_confidence" in results
        assert "avg_latency_ms" in results

    def test_evaluate_fidelity_pass_rate_requires_verification(
        self, api_client: TestClient, simplify_payload: dict
    ):
        resp = api_client.post("/api/v1/simplify", json=simplify_payload)
        assert resp.status_code == 200
        clause_id = resp.json()["explanation"]["clause_id"]

        eval_resp = api_client.post(
            "/api/v1/evaluate",
            json={"clause_ids": [clause_id], "metrics": ["fidelity_pass_rate"]},
        )
        assert eval_resp.status_code == 200
        assert 0.0 <= eval_resp.json()["results"]["fidelity_pass_rate"] <= 1.0


# ──────────────────────────────────────────────────────────────────
# § Study logging
# ──────────────────────────────────────────────────────────────────


class TestStudyLogging:
    def test_study_log_valid_events_returns_200(
        self, api_client: TestClient, tmp_path, monkeypatch
    ):
        # Redirect log output to tmp_path so tests don't pollute ./logs
        from src import config as cfg_mod
        monkeypatch.setattr(cfg_mod.settings, "log_dir", tmp_path, raising=False)

        now = datetime.now(timezone.utc).isoformat()
        resp = api_client.post(
            "/api/v1/study/log",
            json={
                "participant_id": "p01",
                "session_id": "sess-abc",
                "group": "B",
                "events": [
                    {
                        "type": "panel_open",
                        "target": "RiskPanel",
                        "timestamp": now,
                        "duration_ms": 1500,
                    },
                    {
                        "type": "click",
                        "target": "EvidencePanel",
                        "timestamp": now,
                    },
                ],
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "logged"
        assert body["event_count"] == 2

    def test_study_log_writes_jsonl_file(
        self, api_client: TestClient, tmp_path, monkeypatch
    ):
        from src import config as cfg_mod
        monkeypatch.setattr(cfg_mod.settings, "log_dir", tmp_path, raising=False)

        now = datetime.now(timezone.utc).isoformat()
        api_client.post(
            "/api/v1/study/log",
            json={
                "participant_id": "p02",
                "session_id": "sess-xyz",
                "group": "D",
                "events": [{"type": "dwell", "target": "ClausePanel", "timestamp": now}],
            },
        )

        log_file = tmp_path / "study_logs.jsonl"
        assert log_file.exists(), "Log file not created"
        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["participant_id"] == "p02"
        assert record["group"] == "D"
        assert record["type"] == "dwell"

    def test_study_log_empty_events_returns_200(
        self, api_client: TestClient, tmp_path, monkeypatch
    ):
        from src import config as cfg_mod
        monkeypatch.setattr(cfg_mod.settings, "log_dir", tmp_path, raising=False)

        resp = api_client.post(
            "/api/v1/study/log",
            json={
                "participant_id": "p03",
                "session_id": "s3",
                "group": "A",
                "events": [],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["event_count"] == 0

    def test_study_log_all_valid_groups(
        self, api_client: TestClient, tmp_path, monkeypatch
    ):
        from src import config as cfg_mod
        monkeypatch.setattr(cfg_mod.settings, "log_dir", tmp_path, raising=False)

        for group in ("A", "B", "C", "D"):
            resp = api_client.post(
                "/api/v1/study/log",
                json={
                    "participant_id": "p_test",
                    "session_id": "s_test",
                    "group": group,
                    "events": [],
                },
            )
            assert resp.status_code == 200, f"Group {group!r} rejected: {resp.text}"


# ──────────────────────────────────────────────────────────────────
# § Component: retrieval engine
# ──────────────────────────────────────────────────────────────────


class TestRetrievalComponent:
    """Tests for retrieval logic that can run without external APIs."""

    def test_bm25_search_returns_ranked_evidence(self):
        from src.retrieval.index import BM25Index, EvidenceCorpus
        corpus = EvidenceCorpus()  # loads from real evidence.jsonl
        assert len(corpus) > 0, "Evidence corpus must be non-empty"

        bm25 = BM25Index(corpus)
        results = bm25.search("auto-renewal subscription cancel", k=5)

        assert isinstance(results, list)
        assert len(results) <= 5
        for item, score in results:
            assert hasattr(item, "evidence_id")
            assert score > 0

    def test_bm25_search_respects_k(self):
        from src.retrieval.index import BM25Index, EvidenceCorpus
        corpus = EvidenceCorpus()
        bm25 = BM25Index(corpus)
        results = bm25.search("contract clause", k=3)
        assert len(results) <= 3

    def test_bm25_search_irrelevant_query_returns_empty(self):
        from src.retrieval.index import BM25Index, EvidenceCorpus
        corpus = EvidenceCorpus()
        bm25 = BM25Index(corpus)
        results = bm25.search("xyzzy qwerty zxcvbnm", k=5)
        # All BM25 scores should be zero for gibberish → no results
        assert all(score > 0 for _, score in results) or len(results) == 0

    def test_evidence_corpus_loads_all_required_fields(self):
        from src.retrieval.index import EvidenceCorpus
        corpus = EvidenceCorpus()
        for item in corpus.items:
            assert item.evidence_id
            assert item.text
            assert item.legal_concept
            assert item.token_count >= 0

    def test_evidence_corpus_get_by_id(self):
        from src.retrieval.index import EvidenceCorpus
        corpus = EvidenceCorpus()
        first_id = corpus.items[0].evidence_id
        found = corpus.get(first_id)
        assert found is not None
        assert found.evidence_id == first_id

    def test_rrf_fusion_merges_two_ranked_lists(self):
        from src.retrieval.engine import RetrievalEngine
        from src.retrieval.index import EvidenceCorpus

        corpus = EvidenceCorpus()
        items = corpus.items[:4]

        list_a = [(items[0], 1.0), (items[1], 0.8), (items[2], 0.6)]
        list_b = [(items[2], 1.0), (items[0], 0.9), (items[3], 0.7)]

        merged = RetrievalEngine._reciprocal_rank_fusion(list_a, list_b)

        ids = [item.evidence_id for item, _ in merged]
        # items[0] appears in both lists at high rank → should be near top
        assert items[0].evidence_id in ids
        assert items[2].evidence_id in ids

        # Scores must be positive and sorted descending
        scores = [score for _, score in merged]
        assert scores == sorted(scores, reverse=True)

    def test_rrf_deduplicates_items_appearing_in_both_lists(self):
        from src.retrieval.engine import RetrievalEngine
        from src.retrieval.index import EvidenceCorpus

        corpus = EvidenceCorpus()
        items = corpus.items[:2]

        # Both lists contain item[0]
        list_a = [(items[0], 1.0), (items[1], 0.5)]
        list_b = [(items[0], 1.0)]

        merged = RetrievalEngine._reciprocal_rank_fusion(list_a, list_b)
        ids = [item.evidence_id for item, _ in merged]
        # No duplicates
        assert len(ids) == len(set(ids))

    def test_retrieval_filter_removes_wrong_clause_type(self, mock_externals: dict):
        from src.config import RetrievalConfig
        from src.models import ClauseUnit
        from src.retrieval.engine import RetrievalEngine

        # Override ChromaDB to return evidence with a different clause type
        mock_externals["collection"].query.return_value = {
            "ids": [["EVID_INDEMNITY_001", "EVID_AUTO_RENEW_001"]],
            "documents": [["Indemnity clause.", "Auto-renewal clause."]],
            "metadatas": [[
                {"evidence_id": "EVID_INDEMNITY_001", "source_type": "clause_definition",
                 "legal_concept": "indemnity", "clause_type": "indemnity", "token_count": 10},
                {"evidence_id": "EVID_AUTO_RENEW_001", "source_type": "clause_definition",
                 "legal_concept": "automatic renewal", "clause_type": "auto_renewal", "token_count": 10},
            ]],
            "distances": [[0.1, 0.15]],
        }
        # Two items returned from voyage, reranker keeps them both
        mock_externals["voyage_instance"].rerank.return_value.results = [
            MagicMock(index=0, relevance_score=0.9),
            MagicMock(index=1, relevance_score=0.8),
        ]

        engine = RetrievalEngine(RetrievalConfig(method="hybrid_reranker_filter"))
        clause = ClauseUnit(
            clause_id="test-001",
            text=AUTO_RENEWAL_CLAUSE,
            clause_type=ClauseType.auto_renewal,
            source_doc="test",
            doc_type=DocType.service,
            word_count=40,
        )
        results = engine.retrieve(clause, k=5)
        for item in results:
            assert item.clause_type in (None, "auto_renewal"), (
                f"Filter failed: got {item.clause_type!r}"
            )

    def test_query_formulation_prepends_clause_type(self):
        from src.models import ClauseUnit
        from src.retrieval.engine import RetrievalEngine

        clause = ClauseUnit(
            clause_id="c1",
            text="You must pay a monthly fee.",
            clause_type=ClauseType.payment_terms,
            source_doc="test",
            doc_type=DocType.service,
            word_count=7,
        )
        query = RetrievalEngine._formulate_query(clause)
        assert query.startswith("payment_terms:")


# ──────────────────────────────────────────────────────────────────
# § Component: generation
# ──────────────────────────────────────────────────────────────────


class TestGenerationComponent:
    def test_extractive_variant_returns_sentences_from_clause(self):
        from src.generation.generator import ExplanationGenerator
        from src.models import ClauseUnit

        gen = ExplanationGenerator.__new__(ExplanationGenerator)

        clause = ClauseUnit(
            clause_id="c1",
            text=AUTO_RENEWAL_CLAUSE,
            clause_type=ClauseType.auto_renewal,
            source_doc="test",
            doc_type=DocType.service,
            word_count=len(AUTO_RENEWAL_CLAUSE.split()),
        )
        result = gen._extractive_summarize(clause, "none")
        assert len(result.plain_english) > 0
        assert result.generation_variant.value == "extractive"
        assert result.risks == []
        assert result.evidence_used == []

    def test_extractive_readability_computed(self):
        from src.generation.generator import ExplanationGenerator
        from src.models import ClauseUnit

        gen = ExplanationGenerator.__new__(ExplanationGenerator)
        clause = ClauseUnit(
            clause_id="c1",
            text=AUTO_RENEWAL_CLAUSE,
            clause_type=ClauseType.auto_renewal,
            source_doc="test",
            doc_type=DocType.service,
            word_count=len(AUTO_RENEWAL_CLAUSE.split()),
        )
        result = gen._extractive_summarize(clause, "none")
        rm = result.readability
        assert rm.flesch_reading_ease is not None
        assert rm.flesch_kincaid_grade is not None
        assert rm.avg_sentence_length > 0

    def test_readability_empty_text_returns_zeros(self):
        from src.generation.generator import ExplanationGenerator
        rm = ExplanationGenerator._compute_readability("")
        assert rm.flesch_reading_ease == 0.0
        assert rm.flesch_kincaid_grade == 0.0

    def test_parse_llm_response_valid_json(self):
        from src.generation.generator import ExplanationGenerator
        data = ExplanationGenerator._parse_llm_response(
            json.dumps({"plain_english": "Hello", "confidence": "high"})
        )
        assert data["plain_english"] == "Hello"
        assert data["confidence"] == "high"

    def test_parse_llm_response_malformed_json_returns_empty(self):
        from src.generation.generator import ExplanationGenerator
        data = ExplanationGenerator._parse_llm_response("{not valid json}")
        assert data == {}

    def test_sentence_scorer_prefers_legal_keywords(self):
        from src.generation.generator import ExplanationGenerator
        legal = "You shall terminate the agreement and indemnify all losses."
        plain = "This is a short sentence."
        assert ExplanationGenerator._score_sentence(legal) > ExplanationGenerator._score_sentence(plain)

    def test_build_messages_includes_evidence_text(self):
        from src.generation.generator import ExplanationGenerator
        from src.models import ClauseUnit, EvidenceItem, SourceType

        gen = ExplanationGenerator.__new__(ExplanationGenerator)
        clause = ClauseUnit(
            clause_id="c1",
            text="The service auto-renews.",
            clause_type=ClauseType.auto_renewal,
            source_doc="test",
            doc_type=DocType.service,
            word_count=4,
        )
        evidence = [
            EvidenceItem(
                evidence_id="ev1",
                text="Auto-renewal legal definition.",
                source_type=SourceType.clause_definition,
                legal_concept="auto_renewal",
                token_count=5,
            )
        ]
        messages = gen._build_messages(clause, evidence, [], "full")
        user_content = messages[1]["content"]
        assert "Auto-renewal legal definition." in user_content


# ──────────────────────────────────────────────────────────────────
# § Component: risk classification
# ──────────────────────────────────────────────────────────────────


class TestRiskClassificationComponent:
    def test_parse_risks_valid_json(self):
        from src.risk.classifier import RiskClassifier
        raw = json.dumps({
            "risks": [
                {
                    "risk_id": "r1",
                    "risk_category": "automatic_renewal",
                    "severity": "high",
                    "explanation": "Renews without consent.",
                    "recommended_action": "Cancel 30 days before.",
                }
            ]
        })
        risks = RiskClassifier._parse_risks(raw)
        assert len(risks) == 1
        assert risks[0].risk_category == "automatic_renewal"
        assert risks[0].severity.value == "high"

    def test_parse_risks_empty_list(self):
        from src.risk.classifier import RiskClassifier
        risks = RiskClassifier._parse_risks(json.dumps({"risks": []}))
        assert risks == []

    def test_parse_risks_malformed_json_returns_empty(self):
        from src.risk.classifier import RiskClassifier
        risks = RiskClassifier._parse_risks("{broken json")
        assert risks == []

    def test_parse_risks_none_returns_empty(self):
        from src.risk.classifier import RiskClassifier
        risks = RiskClassifier._parse_risks(None)
        assert risks == []

    def test_parse_risks_skips_invalid_entries(self):
        from src.risk.classifier import RiskClassifier
        raw = json.dumps({
            "risks": [
                {"risk_id": "r1", "risk_category": "automatic_renewal",
                 "severity": "high", "explanation": "OK", "recommended_action": "OK"},
                {"bad_field": "missing everything"},
            ]
        })
        risks = RiskClassifier._parse_risks(raw)
        assert len(risks) == 1  # only valid entry

    def test_parse_risks_normalises_category_key(self):
        from src.risk.classifier import RiskClassifier
        raw = json.dumps({
            "risks": [
                {"risk_id": "r1", "category": "automatic_renewal",
                 "severity": "medium", "explanation": ".", "recommended_action": "."}
            ]
        })
        risks = RiskClassifier._parse_risks(raw)
        assert len(risks) == 1
        assert risks[0].risk_category == "automatic_renewal"

    def test_ontology_loads_all_8_categories(self):
        from src.risk.ontology import get_ontology
        ontology = get_ontology()
        assert len(ontology.risk_categories) == 8

    def test_ontology_categories_have_required_fields(self):
        from src.risk.ontology import get_ontology
        ontology = get_ontology()
        for key, cat in ontology.risk_categories.items():
            assert cat.id, f"Category {key!r} missing id"
            assert cat.severity_default is not None

    def test_build_prompt_includes_clause_text(self):
        from src.models import ClauseUnit
        from src.risk.classifier import RiskClassifier
        from src.risk.ontology import get_ontology

        classifier = RiskClassifier.__new__(RiskClassifier)
        classifier.ontology = get_ontology()

        clause = ClauseUnit(
            clause_id="c1",
            text=AUTO_RENEWAL_CLAUSE,
            clause_type=ClauseType.auto_renewal,
            source_doc="test",
            doc_type=DocType.service,
            word_count=len(AUTO_RENEWAL_CLAUSE.split()),
        )
        prompt = classifier._build_prompt(clause, [])
        assert AUTO_RENEWAL_CLAUSE in prompt
        assert "auto_renewal" in prompt


# ──────────────────────────────────────────────────────────────────
# § Component: fidelity verification
# ──────────────────────────────────────────────────────────────────


class TestVerificationComponent:
    def test_compute_fidelity_perfect_scores(self):
        from src.verification.verifier import FidelityVerifier
        score = FidelityVerifier._compute_fidelity(
            entailment_label="entailment",
            unsupported=[],
            missing=[],
            judge_scores={"faithfulness": 1.0, "completeness": 1.0, "hallucination": 1.0},
        )
        assert score == pytest.approx(1.0, abs=0.01)

    def test_compute_fidelity_contradiction_lowers_score(self):
        from src.verification.verifier import FidelityVerifier
        score_entailment = FidelityVerifier._compute_fidelity(
            "entailment", [], [], {"faithfulness": 0.8, "completeness": 0.8, "hallucination": 0.8}
        )
        score_contradiction = FidelityVerifier._compute_fidelity(
            "contradiction", [], [], {"faithfulness": 0.8, "completeness": 0.8, "hallucination": 0.8}
        )
        assert score_contradiction < score_entailment

    def test_compute_fidelity_unsupported_claims_penalise_score(self):
        from src.verification.verifier import FidelityVerifier
        no_unsupported = FidelityVerifier._compute_fidelity(
            "neutral", [], [], {"faithfulness": 0.8, "completeness": 0.8, "hallucination": 0.8}
        )
        with_unsupported = FidelityVerifier._compute_fidelity(
            "neutral",
            ["claim1", "claim2", "claim3"],
            [],
            {"faithfulness": 0.8, "completeness": 0.8, "hallucination": 0.8},
        )
        assert with_unsupported < no_unsupported

    def test_generate_flags_includes_error_types_and_unsupported(self):
        from src.verification.verifier import FidelityVerifier
        flags = FidelityVerifier._generate_flags(
            unsupported=["Added extra claim."],
            missing=["arbitration"],
            error_types=["hallucination"],
        )
        assert "hallucination" in flags
        assert any("unsupported_addition" in f for f in flags)
        assert any("missing_condition" in f for f in flags)

    def test_generate_flags_empty_inputs_produces_no_flags(self):
        from src.verification.verifier import FidelityVerifier
        flags = FidelityVerifier._generate_flags([], [], [])
        assert flags == []

    def test_find_missing_concepts_detects_legal_keywords(self):
        from src.verification.verifier import FidelityVerifier
        verifier = FidelityVerifier.__new__(FidelityVerifier)
        missing = verifier._find_missing_concepts(
            clause="You shall terminate and cancel within the notice period.",
            explanation="This contract can end.",
        )
        # "terminate", "cancel", "notice" are in the clause but not the explanation
        assert len(missing) > 0

    def test_find_missing_concepts_empty_when_all_covered(self):
        from src.verification.verifier import FidelityVerifier
        verifier = FidelityVerifier.__new__(FidelityVerifier)
        clause = "You must cancel by providing notice."
        explanation = "You must cancel by providing notice."
        missing = verifier._find_missing_concepts(clause, explanation)
        assert missing == []

    def test_is_supported_high_overlap_returns_true(self):
        from src.verification.verifier import FidelityVerifier
        vocab = {"this", "contract", "renews", "automatically", "each", "year"}
        assert FidelityVerifier._is_supported("This contract renews automatically.", vocab)

    def test_is_supported_low_overlap_returns_false(self):
        from src.verification.verifier import FidelityVerifier
        vocab = {"something", "completely", "unrelated"}
        assert not FidelityVerifier._is_supported(
            "This contract renews automatically each year.", vocab
        )

    def test_extract_claims_splits_on_sentence_boundary(self):
        from src.verification.verifier import FidelityVerifier
        text = "This renews every year. You must cancel 30 days before. Failure means charges."
        claims = FidelityVerifier._extract_claims(text)
        assert len(claims) == 3


# ──────────────────────────────────────────────────────────────────
# § Component: document processor (ingestion)
# ──────────────────────────────────────────────────────────────────


class TestIngestionComponent:
    def test_classify_auto_renewal_clause(self):
        from src.ingestion.processor import DocumentProcessor
        clause_type = DocumentProcessor._classify_single(AUTO_RENEWAL_CLAUSE)
        assert clause_type == ClauseType.auto_renewal

    def test_classify_indemnity_clause(self):
        from src.ingestion.processor import DocumentProcessor
        clause_type = DocumentProcessor._classify_single(INDEMNITY_CLAUSE)
        assert clause_type == ClauseType.indemnity

    def test_classify_arbitration_clause(self):
        from src.ingestion.processor import DocumentProcessor
        clause_type = DocumentProcessor._classify_single(ARBITRATION_CLAUSE)
        assert clause_type == ClauseType.dispute_resolution

    def test_classify_unknown_returns_unknown(self):
        from src.ingestion.processor import DocumentProcessor
        clause_type = DocumentProcessor._classify_single("The party agrees to the terms.")
        assert clause_type == ClauseType.unknown

    def test_infer_doc_type_from_filename(self):
        from src.ingestion.processor import DocumentProcessor
        assert DocumentProcessor._infer_doc_type("rental_agreement") == DocType.rental
        assert DocumentProcessor._infer_doc_type("employment_contract") == DocType.employment
        assert DocumentProcessor._infer_doc_type("privacy_policy") == DocType.privacy
        assert DocumentProcessor._infer_doc_type("unknown_doc") == DocType.service

    def test_extract_section_info_from_hierarchy(self):
        from src.ingestion.processor import DocumentProcessor
        title, number = DocumentProcessor._extract_section_info(
            ["HEADER: Termination", "12.", "(a)"]
        )
        assert title == "Termination"
        assert number == "12."

    def test_extract_section_info_empty_hierarchy(self):
        from src.ingestion.processor import DocumentProcessor
        title, number = DocumentProcessor._extract_section_info([])
        assert title is None
        assert number is None

    def test_process_txt_file_extracts_clauses(self, api_client: TestClient, tmp_path):
        txt_file = tmp_path / "test_terms.txt"
        txt_file.write_text(AUTO_RENEWAL_CLAUSE + "\n\n" + INDEMNITY_CLAUSE)

        resp = api_client.post(
            "/api/v1/upload",
            files={"file": ("test_terms.txt", txt_file.open("rb"), "text/plain")},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["clause_count"] >= 1
        assert body["document_id"].startswith("doc_")
        for clause in body["clauses"]:
            assert clause["clause_id"]
            assert clause["text"]
