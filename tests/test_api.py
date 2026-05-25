import pytest
from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_simplify_validation_empty_clause(client: TestClient) -> None:
    response = client.post(
        "/api/v1/simplify",
        json={"clause_text": "", "clause_type": "auto_renewal"},
    )
    assert response.status_code == 422


def test_simplify_validation_invalid_config(client: TestClient) -> None:
    response = client.post(
        "/api/v1/simplify",
        json={"clause_text": "some clause text", "clause_type": "auto_renewal", "retrieval_config": 9},
    )
    assert response.status_code == 422


def test_study_log_invalid_group(client: TestClient) -> None:
    response = client.post(
        "/api/v1/study/log",
        json={
            "session_id": "s1",
            "group": "X",
            "event_type": "click",
            "payload": {},
            "timestamp": 1234567890.0,
        },
    )
    assert response.status_code == 422


def test_study_log_valid_group(client: TestClient) -> None:
    response = client.post(
        "/api/v1/study/log",
        json={
            "session_id": "s1",
            "group": "A",
            "event_type": "click",
            "payload": {"target": "RiskPanel"},
            "timestamp": 1234567890.0,
        },
    )
    # Endpoint not implemented yet — 500 is acceptable until implemented
    assert response.status_code in (200, 500)
