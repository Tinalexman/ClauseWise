"""Pydantic schemas matching the data architecture in Technical Architecture §2."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────


class ClauseType(str, Enum):
    unknown = "unknown"
    indemnity = "indemnity"
    termination = "termination"
    confidentiality = "confidentiality"
    auto_renewal = "auto_renewal"
    liability_limitation = "liability_limitation"
    payment_terms = "payment_terms"
    dispute_resolution = "dispute_resolution"
    data_sharing = "data_sharing"
    refund_policy = "refund_policy"
    non_compete = "non_compete"


class DocType(str, Enum):
    rental = "rental"
    employment = "employment"
    subscription = "subscription"
    privacy = "privacy"
    insurance = "insurance"
    service = "service"
    consumer_finance = "consumer_finance"


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class GenerationVariant(str, Enum):
    extractive = "extractive"
    vanilla_llm = "vanilla_llm"
    prompted_llm = "prompted_llm"
    standard_rag = "standard_rag"
    proposed = "proposed"


class RetrievalMethod(str, Enum):
    none = "none"
    bm25 = "bm25"
    dense = "dense"
    hybrid = "hybrid"
    hybrid_reranker = "hybrid_reranker"
    hybrid_reranker_filter = "hybrid_reranker_filter"


class Confidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class EntailmentLabel(str, Enum):
    entailment = "entailment"
    neutral = "neutral"
    contradiction = "contradiction"


class StudyGroup(str, Enum):
    a = "A"
    b = "B"
    c = "C"
    d = "D"


class SourceType(str, Enum):
    legal_dictionary = "legal_dictionary"
    clause_definition = "clause_definition"
    annotated_example = "annotated_example"
    plain_language_guide = "plain_language_guide"
    consumer_protection = "consumer_protection"
    clause_template = "clause_template"


class EventType(str, Enum):
    click = "click"
    scroll = "scroll"
    dwell = "dwell"
    panel_open = "panel_open"
    panel_close = "panel_close"
    question_asked = "question_asked"
    answer_viewed = "answer_viewed"


# ──────────────────────────────────────────────
# §2.1 Clause Schema
# ──────────────────────────────────────────────


class BenchmarkAnnotations(BaseModel):
    reference_explanation: Optional[str] = None
    risk_categories: List[str] = Field(default_factory=list)
    risk_severity: Optional[Severity] = None
    required_consumer_action: Optional[str] = None
    legal_fidelity_score: Optional[float] = Field(None, ge=0, le=1)
    readability_target: Optional[float] = None
    expert_notes: Optional[str] = None


class ClauseUnit(BaseModel):
    clause_id: str = Field(..., description="Unique, format: {source}_{index}_{type}")
    text: str
    clause_type: ClauseType
    source_doc: str
    doc_type: DocType
    section_title: Optional[str] = None
    clause_number: Optional[str] = Field(None, description="e.g. '12.3'")
    context_before: Optional[str] = Field(
        None, description="Preceding clause, max 200 tokens"
    )
    context_after: Optional[str] = Field(
        None, description="Following clause, max 200 tokens"
    )
    word_count: int
    is_benchmark: bool = False
    benchmark_annotations: Optional[BenchmarkAnnotations] = None


# ──────────────────────────────────────────────
# §2.2 Evidence Corpus Schema
# ──────────────────────────────────────────────


class EvidenceItem(BaseModel):
    evidence_id: str
    text: str
    source_type: SourceType
    legal_concept: str
    clause_type: Optional[str] = None
    jurisdiction_note: Optional[str] = None
    risk_category: Optional[str] = None
    citation: Optional[str] = None
    token_count: int


# ──────────────────────────────────────────────
# §2.3 Risk Ontology Schema
# ──────────────────────────────────────────────


class DetectionSignals(BaseModel):
    keywords: List[str] = Field(default_factory=list)
    patterns: List[str] = Field(default_factory=list)


class RiskCategory(BaseModel):
    id: str
    definition: Optional[str] = None
    severity_default: Severity = Severity.medium
    consumer_impact: Optional[str] = None
    recommended_actions: List[str] = Field(default_factory=list)
    detection_signals: Optional[DetectionSignals] = None
    example_clauses: List[str] = Field(default_factory=list)


class RiskOntology(BaseModel):
    version: str = "1.0"
    risk_categories: Dict[str, RiskCategory]


# ──────────────────────────────────────────────
# §2.4 Explanation Output Schema
# ──────────────────────────────────────────────


class RiskDetail(BaseModel):
    risk_id: str
    risk_category: str
    severity: Severity
    explanation: str
    recommended_action: str


class EvidenceUsage(BaseModel):
    evidence_id: str
    relevance_score: float


class SeekLegalAdvice(BaseModel):
    recommended: bool
    reason: Optional[str] = None


class VerificationInfo(BaseModel):
    fidelity_score: float = Field(..., ge=0, le=1)
    entailment_label: EntailmentLabel
    flags: List[str] = Field(default_factory=list)
    passed: bool
    revision_count: int = 0


class ReadabilityMetrics(BaseModel):
    flesch_reading_ease: float
    flesch_kincaid_grade: float
    avg_sentence_length: float
    jargon_density: float = Field(..., description="Percentage of legal terms retained")


class GenerationMetadata(BaseModel):
    model: str
    temperature: float
    timestamp: datetime
    latency_ms: int
    token_count_input: int
    token_count_output: int


class ExplanationOutput(BaseModel):
    clause_id: str
    generation_variant: GenerationVariant
    retrieval_config: RetrievalMethod
    plain_english: str = Field(..., description="2-3 sentences, target FK grade ≤ 8")
    user_implications: str
    risks: List[RiskDetail] = Field(default_factory=list)
    check_before_signing: List[str] = Field(default_factory=list)
    evidence_used: List[EvidenceUsage] = Field(default_factory=list)
    confidence: Confidence
    seek_legal_advice: SeekLegalAdvice
    verification: Optional[VerificationInfo] = None
    readability: ReadabilityMetrics
    metadata: GenerationMetadata


# ──────────────────────────────────────────────
# §3.4 Verification Result
# ──────────────────────────────────────────────


class VerificationResult(BaseModel):
    fidelity_score: float = Field(..., ge=0, le=1)
    entailment_label: EntailmentLabel
    flags: List[str] = Field(default_factory=list)
    passed: bool
    revision_count: int = 0


# ──────────────────────────────────────────────
# §4.1 API Request / Response Schemas
# ──────────────────────────────────────────────


class SimplifyRequest(BaseModel):
    clause_text: str
    clause_type: Optional[ClauseType] = None
    retrieval_config: RetrievalMethod = RetrievalMethod.hybrid_reranker_filter
    generation_variant: GenerationVariant = GenerationVariant.proposed
    include_verification: bool = True


class SimplifyResponse(BaseModel):
    explanation: ExplanationOutput
    retrieval_metadata: Dict[str, Any] = Field(default_factory=dict)
    verification_metadata: Optional[Dict[str, Any]] = None


class UploadResponse(BaseModel):
    document_id: str
    clauses: List[ClauseUnit]
    clause_count: int


class FollowUpRequest(BaseModel):
    clause_id: str
    question: str
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)


class FollowUpResponse(BaseModel):
    answer: str
    evidence_used: List[EvidenceItem] = Field(default_factory=list)


class EvaluateRequest(BaseModel):
    clause_ids: List[str]
    metrics: List[str]


class EvaluateResponse(BaseModel):
    results: Dict[str, float]


# ──────────────────────────────────────────────
# §4.2 Study Logging Schemas
# ──────────────────────────────────────────────


class StudyLogEvent(BaseModel):
    type: EventType
    target: str
    timestamp: datetime
    duration_ms: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class StudyLogRequest(BaseModel):
    participant_id: str
    session_id: str
    group: StudyGroup
    events: List[StudyLogEvent]


class StudyLogResponse(BaseModel):
    status: str = "logged"
    event_count: int
