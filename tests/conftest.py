import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def sample_clause() -> dict:
    return {
        "clause_id": "test-001",
        "text": (
            "This agreement will automatically renew for successive one-year terms "
            "unless either party provides written notice of cancellation at least "
            "30 days prior to the end of the then-current term."
        ),
        "clause_type": "auto_renewal",
        "contract_name": "test_contract.pdf",
        "source": "test",
    }


@pytest.fixture
def sample_evidence() -> list[dict]:
    return [
        {
            "evidence_id": "ev-001",
            "text": "Auto-renewal clauses automatically extend a contract for another term.",
            "source_type": "definition",
            "legal_concept": "auto_renewal",
            "clause_type": "auto_renewal",
            "citation": "Black's Law Dictionary (simplified)",
            "score": 0.92,
        }
    ]
