import pytest

from src.generation.pipeline import GeneratedExplanation, GenerationPipeline, GenerationVariant
from src.retrieval.engine import RetrievedEvidence


def test_variant_enum() -> None:
    assert GenerationVariant.CLAUSEWISE == 5
    assert GenerationVariant(1) == GenerationVariant.EXTRACTIVE


def test_pipeline_init_defaults() -> None:
    pipeline = GenerationPipeline()
    assert pipeline.variant == GenerationVariant.CLAUSEWISE


def test_generate_raises_before_load(sample_clause: dict) -> None:
    pipeline = GenerationPipeline()
    with pytest.raises((NotImplementedError, AttributeError)):
        pipeline.generate(
            clause_id=sample_clause["clause_id"],
            clause_text=sample_clause["text"],
            clause_type=sample_clause["clause_type"],
        )


@pytest.mark.skip(reason="requires OPENAI_API_KEY")
def test_extractive_variant_no_llm(sample_clause: dict) -> None:
    pipeline = GenerationPipeline(variant=GenerationVariant.EXTRACTIVE)
    pipeline.load()
    result = pipeline.generate(
        clause_id=sample_clause["clause_id"],
        clause_text=sample_clause["text"],
        clause_type=sample_clause["clause_type"],
    )
    assert isinstance(result, GeneratedExplanation)
    assert result.variant == GenerationVariant.EXTRACTIVE
    assert len(result.plain_english) > 0
    assert result.evidence_used == []


@pytest.mark.skip(reason="requires OPENAI_API_KEY")
def test_clausewise_variant_uses_evidence(sample_clause: dict, sample_evidence: list) -> None:
    from src.retrieval.engine import RetrievedEvidence
    evidence = [RetrievedEvidence(**e) for e in sample_evidence]
    pipeline = GenerationPipeline(variant=GenerationVariant.CLAUSEWISE)
    pipeline.load()
    result = pipeline.generate(
        clause_id=sample_clause["clause_id"],
        clause_text=sample_clause["text"],
        clause_type=sample_clause["clause_type"],
        evidence=evidence,
    )
    assert result.variant == GenerationVariant.CLAUSEWISE
    assert len(result.evidence_used) > 0
