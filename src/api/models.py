from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# /api/v1/simplify
# ------------------------------------------------------------------

class SimplifyRequest(BaseModel):
    clause_text: str = Field(..., min_length=10)
    clause_type: str
    retrieval_config: int = Field(default=5, ge=1, le=5)
    generation_variant: int = Field(default=5, ge=1, le=5)


class EvidenceItem(BaseModel):
    evidence_id: str
    text: str
    source_type: str
    citation: str
    score: float


class RiskFlag(BaseModel):
    category: str
    severity: str
    rationale: str
    recommended_action: str


class SimplifyResponse(BaseModel):
    clause_id: str
    plain_english: str
    risk_flags: list[RiskFlag]
    severity: str
    recommended_action: str
    confidence: float
    evidence: list[EvidenceItem]
    fidelity_score: float
    passed_verification: bool
    seek_legal_advice: bool


# ------------------------------------------------------------------
# /api/v1/upload
# ------------------------------------------------------------------

class ClauseItem(BaseModel):
    clause_id: str
    text: str
    clause_type: str
    contract_name: str


class UploadResponse(BaseModel):
    contract_name: str
    total_clauses: int
    clauses: list[ClauseItem]


# ------------------------------------------------------------------
# /api/v1/followup
# ------------------------------------------------------------------

class FollowUpRequest(BaseModel):
    clause_id: str
    question: str = Field(..., min_length=5)


class FollowUpResponse(BaseModel):
    answer: str
    confidence: float


# ------------------------------------------------------------------
# /api/v1/study/log
# ------------------------------------------------------------------

class StudyLogEvent(BaseModel):
    session_id: str
    group: str = Field(..., pattern="^[ABCD]$")
    event_type: str  # click | scroll | panel_open | panel_close | followup | dwell
    payload: dict
    timestamp: float
