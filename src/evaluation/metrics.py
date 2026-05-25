"""
Metric computation for all 5 generation variants across 50 benchmark clauses.

Computes per-explanation:
  - RAGAS: faithfulness, answer_relevance
  - Readability: Flesch Reading Ease, Flesch-Kincaid Grade, avg sentence length, jargon density
  - Hallucination rate, evidence support rate, semantic similarity, legal fidelity score

Saves to evaluation/results/all_metrics.json and per-RQ CSVs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def compute_all_metrics(
    explanations_path: str = "evaluation/results/explanations.jsonl",
    benchmark_path: str = "data/benchmark/benchmark.jsonl",
    output_dir: str = "evaluation/results",
) -> dict[str, Any]:
    expl_path = Path(explanations_path)
    bench_path = Path(benchmark_path)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    explanations = _load_jsonl(expl_path)
    benchmark = {item["clause_id"]: item for item in _load_jsonl(bench_path)}

    results = []
    for expl in explanations:
        gold = benchmark.get(expl["clause_id"], {})
        row = _compute_row(expl, gold)
        results.append(row)

    df = pd.DataFrame(results)
    df.to_csv(out_path / "all_metrics.csv", index=False)

    summary = _aggregate(df)
    (out_path / "all_metrics.json").write_text(json.dumps(summary, indent=2))
    return summary


def compute_retrieval_metrics(
    results_path: str = "evaluation/results/retrieval_raw.jsonl",
    output_path: str = "evaluation/results/retrieval_metrics.csv",
    k_values: list[int] | None = None,
) -> pd.DataFrame:
    """Recall@k, Precision@k, nDCG@k, MRR, evidence relevance — for all 5 retrieval configs."""
    raise NotImplementedError


# ------------------------------------------------------------------
# Per-explanation metric functions
# ------------------------------------------------------------------

def _compute_row(explanation: dict, gold: dict) -> dict:
    raise NotImplementedError


def flesch_reading_ease(text: str) -> float:
    raise NotImplementedError


def flesch_kincaid_grade(text: str) -> float:
    raise NotImplementedError


def jargon_density(text: str, jargon_list: list[str] | None = None) -> float:
    """Fraction of tokens that are legal jargon terms."""
    raise NotImplementedError


def hallucination_rate(explanation_text: str, source_texts: list[str]) -> float:
    """Fraction of factual claims in explanation not supported by source_texts."""
    raise NotImplementedError


def evidence_support_rate(explanation_text: str, evidence_texts: list[str]) -> float:
    raise NotImplementedError


def semantic_similarity(text_a: str, text_b: str) -> float:
    raise NotImplementedError


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _load_jsonl(path: Path) -> list[dict]:
    with path.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def _aggregate(df: pd.DataFrame) -> dict:
    raise NotImplementedError
