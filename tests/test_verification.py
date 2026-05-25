import pytest

from src.generation.pipeline import GeneratedExplanation, GenerationVariant
from src.verification.verifier import ERROR_TYPES, FidelityVerifier, VerificationResult


def test_error_types_complete() -> None:
    assert set(ERROR_TYPES) == {"hallucination", "distortion", "omission", "overstatement"}


def test_verifier_init_defaults() -> None:
    verifier = FidelityVerifier()
    assert verifier.threshold == 0.7
    assert abs(verifier.nli_weight + verifier.llm_weight - 1.0) < 1e-9


def test_verification_result_pass_fail() -> None:
    result = VerificationResult(
        explanation_id="test-001",
        nli_entailment_score=0.8,
        llm_judge_score=0.9,
        fidelity_score=0.86,
        passed=True,
    )
    assert result.passed is True


@pytest.mark.skip(reason="requires NLI model download + OPENAI_API_KEY")
def test_verify_returns_result(sample_clause: dict, sample_evidence: list) -> None:
    from src.generation.pipeline import GeneratedExplanation, GenerationVariant
    from src.retrieval.engine import RetrievedEvidence

    explanation = GeneratedExplanation(
        clause_id="test-001",
        variant=GenerationVariant.CLAUSEWISE,
        plain_english="This contract renews automatically unless you cancel 30 days before.",
        risk_flags=["automatic_renewal"],
        severity="high",
        recommended_action="Set a calendar reminder 30 days before renewal.",
        confidence=0.9,
    )
    evidence = [RetrievedEvidence(**e) for e in sample_evidence]
    verifier = FidelityVerifier()
    verifier.load()

    result = verifier.verify(explanation, sample_clause["text"], evidence)
    assert isinstance(result, VerificationResult)
    assert 0.0 <= result.fidelity_score <= 1.0
    assert isinstance(result.passed, bool)
