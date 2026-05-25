"""FastAPI application entry point (§7.1).

Runs the ClauseWise backend:

    uvicorn src.main:app --reload

Endpoints (all under ``/api/v1/``):

    POST /simplify      — full pipeline (retrieve → classify → generate → verify)
    POST /upload        — ingest a document → extract clauses
    POST /followup      — answer a follow-up question
    GET  /clause/{id}   — retrieve stored clause + explanations
    POST /evaluate      — run evaluation metrics
    POST /study/log     — log user study events
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.config import settings

# ── Logging ────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


# ── Lifespan (startup / shutdown) ──────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: ensure required directories exist."""
    logger.info("Starting ClauseWise API …")
    logger.info("  Evidence corpus : %s", settings.evidence_corpus_path)
    logger.info("  Risk ontology   : %s", settings.risk_ontology_path)
    logger.info("  ChromaDB        : %s", settings.chroma_persist_dir)
    logger.info("  Study mode      : %s", settings.study_mode)
    logger.info("  LLM model       : %s", settings.llm_model)

    # Ensure directories exist
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    settings.chroma_persist_dir.mkdir(parents=True, exist_ok=True)

    yield

    logger.info("Shutting down ClauseWise API …")


# ── App ────────────────────────────────────────────────────────

app = FastAPI(
    title="ClauseWise API",
    description="Retrieval-grounded legal information access system",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow the React frontend during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routes
app.include_router(router)


# ── Health check ───────────────────────────────────────────────


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "study_mode": settings.study_mode}
