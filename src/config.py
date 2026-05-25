"""Application configuration — loads from environment variables (§7.2)
and provides defaults for retrieval, generation, and evaluation."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

# Load .env file from the project root
load_dotenv()

# ──────────────────────────────────────────────
# §3.2 Retrieval Configuration
# ──────────────────────────────────────────────

RetrievalMethod = Literal[
    "bm25",
    "dense",
    "hybrid",
    "hybrid_reranker",
    "hybrid_reranker_filter",
]


@dataclass(frozen=True)
class RetrievalConfig:
    """Controls which retrieval strategy the engine uses (§3.2)."""

    method: RetrievalMethod = "hybrid_reranker_filter"
    k: int = 5
    rerank_k: int = 15  # candidates fetched before reranking (k * 3)


# ──────────────────────────────────────────────
# §7.2 Environment-Based Settings
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class Settings:
    # ── OpenAI ──
    openai_api_key: str = field(
        default_factory=lambda: os.environ.get("OPENAI_API_KEY", "")
    )
    llm_model: str = "gpt-4o-mini"

    # ── Voyage AI ──
    voyage_api_key: str = field(
        default_factory=lambda: os.environ.get("VOYAGE_API_KEY", "")
    )
    voyage_embedding_model: str = "voyage-2"
    voyage_rerank_model: str = "rerank-2"

    # ── Persistence paths ──
    chroma_persist_dir: Path = Path(
        os.environ.get("CHROMA_PERSIST_DIR", "./data/chroma_db")
    )
    evidence_corpus_path: Path = Path(
        os.environ.get("EVIDENCE_CORPUS_PATH", "./data/evidence_corpus/evidence.jsonl")
    )
    risk_ontology_path: Path = Path(
        os.environ.get("RISK_ONTOLOGY_PATH", "./data/ontology/risk_ontology.yaml")
    )
    benchmark_path: Path = Path(os.environ.get("BENCHMARK_PATH", "./data/benchmark/"))
    log_dir: Path = Path(os.environ.get("LOG_DIR", "./logs/"))

    # ── Study mode (§4.2) ──
    study_mode: bool = os.environ.get("STUDY_MODE", "false").lower() == "true"
    study_group: str = os.environ.get("STUDY_GROUP", "D")

    # ── LLM temperatures (§1.2 reproducibility) ──
    eval_temperature: float = float(os.environ.get("EVAL_TEMPERATURE", "0"))
    gen_temperature: float = float(os.environ.get("GEN_TEMPERATURE", "0.3"))

    # ── Retrieval defaults ──
    default_retrieval_method: RetrievalMethod = "hybrid_reranker_filter"
    default_k: int = 5

    # ── Generation defaults ──
    default_generation_variant: str = "proposed"


# ──────────────────────────────────────────────
# §5.1 Experiment Defaults
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class EvalConfig:
    """Default evaluation experiment parameters (§5.1)."""

    seed: int = 42
    retrieval_k_values: tuple[int, ...] = (1, 3, 5, 10)
    generation_variants: tuple[str, ...] = (
        "extractive",
        "vanilla_llm",
        "prompted_llm",
        "standard_rag",
        "proposed",
    )
    retrieval_configs: tuple[RetrievalMethod, ...] = (
        "bm25",
        "dense",
        "hybrid",
        "hybrid_reranker",
        "hybrid_reranker_filter",
    )
    ablation_variants: tuple[str, ...] = (
        "full_framework",
        "no_retrieval",
        "no_risk_module",
        "no_fidelity_verifier",
        "no_interactive_ui",
        "retrieval_generation_only",
        "plain_llm_baseline",
    )


# ── Global singleton ──
settings = Settings()
eval_config = EvalConfig()
