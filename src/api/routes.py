"""FastAPI route definitions (§4.1 / §4.2).

Six endpoints wiring together all core modules:

    POST /api/v1/simplify      — full pipeline: retrieve → classify → generate → verify
    POST /api/v1/upload        — ingest a document → extract clauses
    POST /api/v1/followup      — answer a follow-up question about a clause
    GET  /api/v1/clause/{id}   — retrieve a stored clause + explanations
    POST /api/v1/evaluate      — run evaluation metrics on a set of clauses
    POST /api/v1/study/log     — log user interaction events
"""

from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile

from src.config import RetrievalConfig, settings
from src.generation.generator import ExplanationGenerator
from src.ingestion.processor import DocumentProcessor
from src.models import (
    ClauseUnit,
    EvaluateRequest,
    EvaluateResponse,
    ExplanationOutput,
    FollowUpRequest,
    FollowUpResponse,
    GenerationVariant,
    RetrievalMethod,
    RiskDetail,
    SimplifyRequest,
    SimplifyResponse,
    StudyLogRequest,
    StudyLogResponse,
    UploadResponse,
)
from src.retrieval.engine import RetrievalEngine
from src.risk.classifier import RiskClassifier
from src.verification.verifier import FidelityVerifier

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")

# ── Shared instances (lazy-loaded on first use) ────────────────

_processor: Optional[DocumentProcessor] = None
_engine: Optional[RetrievalEngine] = None
_classifier: Optional[RiskClassifier] = None
_generator: Optional[ExplanationGenerator] = None
_verifier: Optional[FidelityVerifier] = None

# In-memory store for clauses and explanations (§4.1 GET /clause/{id})
_clause_store: Dict[str, ClauseUnit] = {}
_explanation_store: Dict[str, List[ExplanationOutput]] = {}


def _get_processor() -> DocumentProcessor:
    global _processor
    if _processor is None:
        _processor = DocumentProcessor()
    return _processor


def _get_engine(
    method: RetrievalMethod = RetrievalMethod.hybrid_reranker_filter,
) -> RetrievalEngine:
    global _engine
    if _engine is None:
        _engine = RetrievalEngine(RetrievalConfig(method=method.value))
    return _engine


def _get_classifier() -> RiskClassifier:
    global _classifier
    if _classifier is None:
        _classifier = RiskClassifier()
    return _classifier


def _get_generator() -> ExplanationGenerator:
    global _generator
    if _generator is None:
        _generator = ExplanationGenerator()
    return _generator


def _get_verifier() -> FidelityVerifier:
    global _verifier
    if _verifier is None:
        _verifier = FidelityVerifier()
    return _verifier


# ──────────────────────────────────────────────────────────────
# POST /api/v1/simplify  (§4.1)
# ──────────────────────────────────────────────────────────────


@router.post("/simplify", response_model=SimplifyResponse)
async def simplify(req: SimplifyRequest) -> SimplifyResponse:
    """Process a clause through the full pipeline.

    Steps:
        1. Build a ClauseUnit from the request
        2. Retrieve relevant evidence
        3. Classify consumer risks
        4. Generate plain-English explanation
        5. Verify fidelity (optional)
    """
    start = time.monotonic()

    # ── 1. Build clause unit ────────────────────────────────────
    clause = ClauseUnit(
        clause_id=f"req_{uuid.uuid4().hex[:8]}_{req.generation_variant.value}",
        text=req.clause_text,
        clause_type=req.clause_type or "unknown",  # type: ignore[arg-type]
        source_doc="api",
        doc_type="service",
        word_count=len(req.clause_text.split()),
    )
    _clause_store[clause.clause_id] = clause

    # ── 2. Retrieve evidence ────────────────────────────────────
    engine = _get_engine(req.retrieval_config)
    evidence = engine.retrieve(clause)
    retrieval_latency = int((time.monotonic() - start) * 1000)

    # ── 3. Classify risks ───────────────────────────────────────
    classifier = _get_classifier()
    risks = classifier.classify(clause, evidence)

    # ── 4. Generate explanation ─────────────────────────────────
    generator = _get_generator()
    explanation = generator.generate(
        clause=clause,
        evidence=evidence,
        risks=risks,
        variant=req.generation_variant,
        retrieval_config=req.retrieval_config.value,
    )

    # ── 5. Verify fidelity (optional) ───────────────────────────
    verification_metadata = None
    if req.include_verification:
        verifier = _get_verifier()
        result = verifier.verify(
            clause=clause.text,
            explanation=explanation.plain_english,
            evidence=[e.text for e in evidence],
        )
        verification_metadata = {
            "score": result["fidelity_score"],
            "flags": result["flags"],
            "passed": result["passed"],
        }
        # Attach verification to the explanation output
        explanation.verification = {
            "fidelity_score": result["fidelity_score"],
            "entailment_label": result["entailment_label"],
            "flags": result["flags"],
            "error_types": result.get("error_types", []),
            "passed": result["passed"],
            "revision_count": result.get("revision_count", 0),
        }

    # Store for later retrieval
    _explanation_store.setdefault(clause.clause_id, []).append(explanation)

    return SimplifyResponse(
        explanation=explanation,
        retrieval_metadata={
            "config": req.retrieval_config.value,
            "k": settings.default_k,
            "latency_ms": retrieval_latency,
        },
        verification_metadata=verification_metadata,
    )


# ──────────────────────────────────────────────────────────────
# POST /api/v1/upload  (§4.1)
# ──────────────────────────────────────────────────────────────


@router.post("/upload", response_model=UploadResponse)
async def upload(file: UploadFile = File(...)) -> UploadResponse:
    """Upload a contract document for clause extraction."""
    if file.filename is None:
        raise HTTPException(status_code=400, detail="No filename provided")

    # Save the uploaded file temporarily
    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".pdf", ".docx", ".md", ".txt"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {suffix} (supported: PDF, DOCX, MD, TXT)",
        )

    tmp_path = settings.log_dir / "uploads" / file.filename
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    tmp_path.write_bytes(content)

    # Process
    processor = _get_processor()
    try:
        clauses = processor.process(tmp_path)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    finally:
        tmp_path.unlink(missing_ok=True)

    # Store clauses
    document_id = f"doc_{uuid.uuid4().hex[:12]}"
    for clause in clauses:
        _clause_store[clause.clause_id] = clause

    return UploadResponse(
        document_id=document_id,
        clauses=clauses,
        clause_count=len(clauses),
    )


# ──────────────────────────────────────────────────────────────
# POST /api/v1/followup  (§4.1)
# ──────────────────────────────────────────────────────────────


@router.post("/followup", response_model=FollowUpResponse)
async def followup(req: FollowUpRequest) -> FollowUpResponse:
    """Answer a follow-up question about a previously processed clause."""
    clause = _clause_store.get(req.clause_id)
    if clause is None:
        raise HTTPException(
            status_code=404,
            detail=f"Clause {req.clause_id} not found. Process it via /simplify first.",
        )

    # Retrieve evidence for context
    engine = _get_engine()
    evidence = engine.retrieve(clause, k=3)

    # Simple Q&A via the LLM
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)

    nl = chr(10)
    history_block = ""
    if req.conversation_history:
        history_block = nl.join(
            f"{'User' if m.get('role') == 'user' else 'Assistant'}: {m.get('content', '')}"
            for m in req.conversation_history[-5:]
        )

    evidence_block = nl.join(
        f"- [{e.evidence_id}] {e.text[:500]}" for e in evidence[:3]
    )

    if history_block:
        prompt = (
            f"Clause: {clause.text}{nl}{nl}"
            f"Relevant legal context:{nl}{evidence_block}{nl}{nl}"
            f"Previous conversation:{nl}{history_block}{nl}{nl}"
            f"Question: {req.question}{nl}{nl}"
            "Answer concisely and accurately. Base your answer on the clause "
            "and legal context above. If the answer isn't in the clause or "
            "evidence, say so."
        )
    else:
        prompt = (
            f"Clause: {clause.text}{nl}{nl}"
            f"Relevant legal context:{nl}{evidence_block}{nl}{nl}"
            f"Question: {req.question}{nl}{nl}"
            "Answer concisely and accurately. Base your answer on the clause "
            "and legal context above. If the answer isn't in the clause or "
            "evidence, say so."
        )

    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )

    answer = response.choices[0].message.content or ""

    return FollowUpResponse(
        answer=answer,
        evidence_used=evidence,
    )


# ──────────────────────────────────────────────────────────────
# GET /api/v1/clause/{clause_id}  (§4.1)
# ──────────────────────────────────────────────────────────────


@router.get("/clause/{clause_id}")
async def get_clause(clause_id: str) -> dict:
    """Get clause details and all generated explanations."""
    clause = _clause_store.get(clause_id)
    if clause is None:
        raise HTTPException(
            status_code=404,
            detail=f"Clause {clause_id} not found.",
        )

    explanations = _explanation_store.get(clause_id, [])

    return {
        "clause": clause.model_dump(),
        "explanations": [e.model_dump() for e in explanations],
        "explanation_count": len(explanations),
    }


# ──────────────────────────────────────────────────────────────
# POST /api/v1/evaluate  (§4.1)
# ──────────────────────────────────────────────────────────────


@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate(req: EvaluateRequest) -> EvaluateResponse:
    """Run evaluation metrics on a set of explanations."""
    results: Dict[str, float] = {}

    explanations: List[ExplanationOutput] = []
    for cid in req.clause_ids:
        explanations.extend(_explanation_store.get(cid, []))

    if not explanations:
        raise HTTPException(
            status_code=404,
            detail="No explanations found for the given clause IDs.",
        )

    for metric in req.metrics:
        if metric == "avg_readability":
            scores = [
                e.readability.flesch_kincaid_grade
                for e in explanations
                if e.readability
            ]
            results["avg_fk_grade"] = sum(scores) / len(scores) if scores else 0.0
        elif metric == "avg_confidence":
            conf_map = {"high": 1.0, "medium": 0.5, "low": 0.0}
            scores = [conf_map.get(e.confidence.value, 0.5) for e in explanations]
            results["avg_confidence"] = sum(scores) / len(scores) if scores else 0.0
        elif metric == "avg_latency":
            latencies = [e.metadata.latency_ms for e in explanations if e.metadata]
            results["avg_latency_ms"] = (
                sum(latencies) / len(latencies) if latencies else 0.0
            )
        elif metric == "fidelity_pass_rate":
            passed = sum(
                1 for e in explanations if e.verification and e.verification.passed
            )
            results["fidelity_pass_rate"] = (
                passed / len(explanations) if explanations else 0.0
            )
        else:
            results[metric] = 0.0

    return EvaluateResponse(results=results)


# ──────────────────────────────────────────────────────────────
# POST /api/v1/study/log  (§4.2)
# ──────────────────────────────────────────────────────────────


@router.post("/study/log", response_model=StudyLogResponse)
async def study_log(req: StudyLogRequest) -> StudyLogResponse:
    """Log user interaction events during the study."""
    log_path = settings.log_dir / "study_logs.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    import json as json_module

    with log_path.open("a", encoding="utf-8") as f:
        for event in req.events:
            record = {
                "participant_id": req.participant_id,
                "session_id": req.session_id,
                "group": req.group.value,
                "type": event.type.value,
                "target": event.target,
                "timestamp": event.timestamp.isoformat(),
                "duration_ms": event.duration_ms,
                "metadata": event.metadata,
            }
            f.write(json_module.dumps(record, ensure_ascii=False) + "\n")

    return StudyLogResponse(
        status="logged",
        event_count=len(req.events),
    )
