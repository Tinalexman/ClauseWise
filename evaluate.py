#!/usr/bin/env python3
"""
ClauseWise Evaluation Script

Runs benchmark clauses through selected generation variants and retrieval
configs, computes all metrics, and writes results to evaluation/results/.

Usage examples:
    python evaluate.py                                       # full benchmark, proposed variant
    python evaluate.py --variants proposed standard_rag      # multiple variants
    python evaluate.py --variants extractive --no-openai     # no API keys needed
    python evaluate.py --n 5 --dry-run                       # quick smoke test
    python evaluate.py --retrieval-config bm25 hybrid        # specific retrieval
    python evaluate.py --no-verify                           # skip fidelity check (faster)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd
import textstat
from tqdm import tqdm

# ── ensure project root is on sys.path ──────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from src.config import RetrievalConfig, settings
from src.models import (
    ClauseType,
    ClauseUnit,
    DocType,
    GenerationVariant,
)

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("evaluate")

# ── Legal jargon word list (for jargon density metric) ──────────
_JARGON = {
    "shall", "herein", "hereof", "hereby", "hereunder", "therein",
    "thereof", "whereby", "aforementioned", "notwithstanding",
    "indemnify", "indemnification", "indemnitor", "indemnitee",
    "arbitration", "arbitrate", "arbitrator", "jurisdiction",
    "venue", "governing", "liabilities", "liability", "waive",
    "waiver", "covenant", "covenants", "pursuant", "expressly",
    "mutually", "obligation", "obligations", "warranties", "warranty",
    "representations", "termination", "terminate", "terminates",
    "confidential", "confidentiality", "proprietary", "subrogation",
    "lien", "encumbrance", "indemnitor", "liquidated", "damages",
}

RESULTS_DIR = Path("evaluation/results")
BENCHMARK_PATH = Path("data/benchmark/benchmark.jsonl")


# ── Metric computation ───────────────────────────────────────────

def compute_readability(text: str) -> dict[str, float]:
    if not text or len(text.split()) < 3:
        return {"flesch_reading_ease": 0.0, "fk_grade": 0.0, "avg_sentence_length": 0.0}
    return {
        "flesch_reading_ease": textstat.flesch_reading_ease(text),
        "fk_grade": textstat.flesch_kincaid_grade(text),
        "avg_sentence_length": textstat.words_per_sentence(text),
    }


def compute_jargon_density(text: str) -> float:
    words = [w.strip(".,;:!?()\"'").lower() for w in text.split()]
    if not words:
        return 0.0
    hits = sum(1 for w in words if w in _JARGON)
    return round(hits / len(words), 4)


def compute_semantic_similarity(text_a: str, text_b: str) -> float:
    """Token-overlap Jaccard similarity — fast, no model needed."""
    if not text_a or not text_b:
        return 0.0
    set_a = set(text_a.lower().split())
    set_b = set(text_b.lower().split())
    intersection = set_a & set_b
    union = set_a | set_b
    return round(len(intersection) / len(union), 4) if union else 0.0


def compute_risk_accuracy(predicted_cats: list[str], gold_cats: list[str]) -> dict[str, float]:
    if not gold_cats:
        return {"risk_precision": 0.0, "risk_recall": 0.0, "risk_f1": 0.0}
    pred_set = set(predicted_cats)
    gold_set = set(gold_cats)
    tp = len(pred_set & gold_set)
    precision = tp / len(pred_set) if pred_set else 0.0
    recall = tp / len(gold_set) if gold_set else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    return {
        "risk_precision": round(precision, 4),
        "risk_recall": round(recall, 4),
        "risk_f1": round(f1, 4),
    }


# ── Benchmark loading ────────────────────────────────────────────

def load_benchmark(path: Path, n: int | None = None) -> list[dict]:
    if not path.exists():
        logger.warning("Benchmark not found at %s — using synthetic fallback clauses", path)
        return _synthetic_benchmark()
    items = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    if n:
        items = items[:n]
    return items


def _synthetic_benchmark() -> list[dict]:
    """5 hand-written clauses covering distinct types — used when benchmark.jsonl is absent."""
    return [
        {
            "clause_id": "synth_001",
            "text": (
                "This agreement shall automatically renew for successive one-year terms "
                "unless either party provides written notice of cancellation at least 30 days "
                "prior to the end of the then-current term."
            ),
            "clause_type": "auto_renewal",
            "source_doc": "synthetic",
            "doc_type": "subscription",
            "word_count": 44,
            "benchmark_annotations": {
                "reference_explanation": (
                    "Your subscription renews automatically every year. "
                    "To cancel, you must send written notice 30 days before your renewal date."
                ),
                "risk_categories": ["automatic_renewal"],
                "risk_severity": "medium",
            },
        },
        {
            "clause_id": "synth_002",
            "text": (
                "To the maximum extent permitted by applicable law, neither party shall be "
                "liable for any indirect, incidental, special, consequential, or punitive damages, "
                "including loss of profits, revenue, data, or goodwill, however caused."
            ),
            "clause_type": "liability_limitation",
            "source_doc": "synthetic",
            "doc_type": "service",
            "word_count": 38,
            "benchmark_annotations": {
                "reference_explanation": (
                    "The company limits the types of damages you can sue them for. "
                    "You cannot claim lost profits or indirect losses even if they cause them."
                ),
                "risk_categories": ["broad_liability"],
                "risk_severity": "high",
            },
        },
        {
            "clause_id": "synth_003",
            "text": (
                "You agree to indemnify, defend, and hold harmless the Company and its officers, "
                "directors, employees, and agents from any claims, liabilities, damages, losses, "
                "and expenses arising from your use of the service or violation of these terms."
            ),
            "clause_type": "indemnity",
            "source_doc": "synthetic",
            "doc_type": "service",
            "word_count": 45,
            "benchmark_annotations": {
                "reference_explanation": (
                    "If someone sues the company because of something you did, "
                    "you are responsible for paying the company's legal costs and any damages."
                ),
                "risk_categories": ["one_sided_indemnity"],
                "risk_severity": "high",
            },
        },
        {
            "clause_id": "synth_004",
            "text": (
                "All disputes arising from this agreement shall be resolved exclusively through "
                "binding arbitration in accordance with the rules of the American Arbitration "
                "Association, and you waive any right to a jury trial or class action."
            ),
            "clause_type": "dispute_resolution",
            "source_doc": "synthetic",
            "doc_type": "consumer_finance",
            "word_count": 43,
            "benchmark_annotations": {
                "reference_explanation": (
                    "You cannot sue the company in court or join a class action lawsuit. "
                    "Disputes must go through private arbitration, which generally favours businesses."
                ),
                "risk_categories": ["unclear_dispute_resolution"],
                "risk_severity": "high",
            },
        },
        {
            "clause_id": "synth_005",
            "text": (
                "We may share your personal data with third-party partners, affiliates, and "
                "service providers for marketing, analytics, and product improvement purposes "
                "without additional notice to you."
            ),
            "clause_type": "data_sharing",
            "source_doc": "synthetic",
            "doc_type": "privacy",
            "word_count": 35,
            "benchmark_annotations": {
                "reference_explanation": (
                    "The company can sell or share your personal data with other companies "
                    "for advertising without telling you each time."
                ),
                "risk_categories": ["excessive_data_sharing"],
                "risk_severity": "high",
            },
        },
    ]


def _clause_unit_from_row(row: dict) -> ClauseUnit:
    return ClauseUnit(
        clause_id=row["clause_id"],
        text=row["text"],
        clause_type=ClauseType(row.get("clause_type", "unknown")),
        source_doc=row.get("source_doc", "benchmark"),
        doc_type=DocType(row.get("doc_type", "service")),
        section_title=row.get("section_title"),
        word_count=row.get("word_count", len(row["text"].split())),
        is_benchmark=True,
    )


# ── Pipeline runners ─────────────────────────────────────────────

def run_retrieval(clause: ClauseUnit, method: str, dry_run: bool) -> list:
    if dry_run or not settings.voyage_api_key:
        return []
    try:
        from src.retrieval.engine import RetrievalEngine
        engine = RetrievalEngine(RetrievalConfig(method=method))  # type: ignore[arg-type]
        return engine.retrieve(clause)
    except Exception as e:
        logger.warning("Retrieval failed (%s): %s", method, e)
        return []


def run_risk_classification(clause: ClauseUnit, evidence: list, dry_run: bool) -> list:
    if dry_run or not settings.openai_api_key:
        return []
    try:
        from src.risk.classifier import RiskClassifier
        classifier = RiskClassifier()
        return classifier.classify(clause, evidence)
    except Exception as e:
        logger.warning("Risk classification failed: %s", e)
        return []


def run_generation(
    clause: ClauseUnit,
    evidence: list,
    risks: list,
    variant: str,
    retrieval_config: str,
    dry_run: bool,
) -> dict[str, Any] | None:
    if dry_run:
        return {
            "plain_english": f"[DRY RUN] Explanation for {clause.clause_id} via {variant}",
            "user_implications": "",
            "check_before_signing": [],
            "confidence": "medium",
            "readability": {"flesch_reading_ease": 0.0, "fk_grade": 0.0, "avg_sentence_length": 0.0},
            "metadata": {"latency_ms": 0, "model": "dry-run", "token_count_input": 0, "token_count_output": 0},
        }

    needs_llm = variant != "extractive"
    if needs_llm and not settings.openai_api_key:
        logger.warning("Skipping variant '%s' — OPENAI_API_KEY not set", variant)
        return None

    try:
        from src.generation.generator import ExplanationGenerator
        gen = ExplanationGenerator()
        result = gen.generate(
            clause,
            evidence=evidence,
            risks=risks,
            variant=GenerationVariant(variant),
            retrieval_config=retrieval_config,
        )
        return result.model_dump()
    except Exception as e:
        logger.warning("Generation failed (variant=%s): %s", variant, e)
        return None


def run_fidelity_verification(
    clause_text: str,
    explanation: str,
    evidence_texts: list[str],
    dry_run: bool,
    verify: bool,
) -> dict[str, Any]:
    empty = {"fidelity_score": None, "entailment_label": None, "passed": None, "flags": []}
    if dry_run or not verify:
        return empty
    if not settings.openai_api_key:
        return empty
    try:
        from src.verification.verifier import FidelityVerifier
        verifier = FidelityVerifier()
        return verifier.verify(clause_text, explanation, evidence_texts)
    except Exception as e:
        logger.warning("Fidelity verification failed: %s", e)
        return empty


# ── Result row builder ───────────────────────────────────────────

def build_result_row(
    clause: ClauseUnit,
    gold: dict,
    variant: str,
    retrieval_config: str,
    generation_output: dict[str, Any],
    evidence: list,
    risks: list,
    verification: dict[str, Any],
    latency_total_ms: int,
) -> dict[str, Any]:
    plain_english = generation_output.get("plain_english", "")
    annotations = gold.get("benchmark_annotations") or {}
    reference = annotations.get("reference_explanation", "")
    gold_risks = annotations.get("risk_categories", [])
    gold_severity = annotations.get("risk_severity")

    readability = compute_readability(plain_english)
    jargon = compute_jargon_density(plain_english)
    sim = compute_semantic_similarity(plain_english, reference) if reference else None

    predicted_risk_cats = [r["risk_category"] if isinstance(r, dict) else r.risk_category for r in risks]
    risk_acc = compute_risk_accuracy(predicted_risk_cats, gold_risks)

    gen_meta = generation_output.get("metadata") or {}

    return {
        "clause_id": clause.clause_id,
        "clause_type": clause.clause_type.value,
        "variant": variant,
        "retrieval_config": retrieval_config,
        # Readability
        "flesch_reading_ease": readability["flesch_reading_ease"],
        "fk_grade": readability["fk_grade"],
        "avg_sentence_length": readability["avg_sentence_length"],
        "jargon_density": jargon,
        # Similarity to gold reference
        "semantic_similarity_to_ref": sim,
        # Risk accuracy
        "risk_precision": risk_acc["risk_precision"],
        "risk_recall": risk_acc["risk_recall"],
        "risk_f1": risk_acc["risk_f1"],
        "gold_severity": gold_severity,
        "n_risks_predicted": len(risks),
        "n_risks_gold": len(gold_risks),
        # Fidelity verification
        "fidelity_score": verification.get("fidelity_score"),
        "entailment_label": verification.get("entailment_label"),
        "fidelity_passed": verification.get("passed"),
        # Retrieval
        "n_evidence_retrieved": len(evidence),
        # Latency / cost
        "latency_ms": latency_total_ms,
        "token_count_input": gen_meta.get("token_count_input", 0),
        "token_count_output": gen_meta.get("token_count_output", 0),
        # Text (for inspection)
        "plain_english": plain_english,
    }


# ── Summary printer ──────────────────────────────────────────────

def print_summary(df: pd.DataFrame) -> None:
    print("\n" + "=" * 72)
    print("EVALUATION SUMMARY")
    print("=" * 72)

    numeric_cols = [
        "flesch_reading_ease", "fk_grade", "jargon_density",
        "semantic_similarity_to_ref", "risk_f1", "fidelity_score",
        "latency_ms",
    ]
    available = [c for c in numeric_cols if c in df.columns]

    summary = (
        df.groupby("variant")[available]
        .mean()
        .round(3)
    )
    print(summary.to_string())

    print("\nClauses processed per variant:")
    print(df.groupby("variant")["clause_id"].count().to_string())

    if "fidelity_passed" in df.columns:
        pass_rate = df.groupby("variant")["fidelity_passed"].mean().round(3)
        print("\nFidelity pass rate per variant:")
        print(pass_rate.to_string())

    print("=" * 72)


# ── Main ─────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ClauseWise benchmark evaluation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--variants",
        nargs="+",
        default=["proposed"],
        choices=["extractive", "vanilla_llm", "prompted_llm", "standard_rag", "proposed"],
        help="Generation variants to evaluate (default: proposed)",
    )
    parser.add_argument(
        "--retrieval-config",
        nargs="+",
        dest="retrieval_configs",
        default=["hybrid_reranker_filter"],
        choices=["bm25", "dense", "hybrid", "hybrid_reranker", "hybrid_reranker_filter"],
        help="Retrieval configs to evaluate (default: hybrid_reranker_filter)",
    )
    parser.add_argument(
        "--n", type=int, default=None,
        help="Max clauses to evaluate (default: all)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Skip all API calls, generate placeholder output",
    )
    parser.add_argument(
        "--no-verify", action="store_true",
        help="Skip fidelity verification (faster, no NLI model load)",
    )
    parser.add_argument(
        "--no-openai", action="store_true",
        help="Disable OpenAI calls (extractive variant only)",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=RESULTS_DIR,
        help="Directory for output files (default: evaluation/results)",
    )
    parser.add_argument(
        "--benchmark", type=Path, default=BENCHMARK_PATH,
        help="Path to benchmark.jsonl",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Show INFO-level logs",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)

    if args.no_openai:
        os.environ["OPENAI_API_KEY"] = ""

    args.output_dir.mkdir(parents=True, exist_ok=True)

    # ── Load benchmark ───────────────────────────────────────────
    benchmark_rows = load_benchmark(args.benchmark, n=args.n)
    print(f"Loaded {len(benchmark_rows)} benchmark clauses")
    print(f"Variants:         {args.variants}")
    print(f"Retrieval:        {args.retrieval_configs}")
    print(f"Dry run:          {args.dry_run}")
    print(f"Fidelity verify:  {not args.no_verify}")

    # ── Run evaluation ───────────────────────────────────────────
    results: list[dict] = []
    total = len(benchmark_rows) * len(args.variants) * len(args.retrieval_configs)

    with tqdm(total=total, desc="Evaluating") as pbar:
        for row in benchmark_rows:
            clause = _clause_unit_from_row(row)

            for retrieval_config in args.retrieval_configs:
                # Retrieve once per (clause, config) — shared across variants
                evidence = run_retrieval(clause, retrieval_config, args.dry_run)
                evidence_texts = [e.text if hasattr(e, "text") else e.get("text", "") for e in evidence]

                for variant in args.variants:
                    t_var_start = time.monotonic()

                    risks = run_risk_classification(clause, evidence, args.dry_run)

                    gen_out = run_generation(
                        clause, evidence, risks, variant, retrieval_config, args.dry_run
                    )
                    if gen_out is None:
                        pbar.update(1)
                        continue

                    plain_english = gen_out.get("plain_english", "")
                    verification = run_fidelity_verification(
                        clause.text, plain_english, evidence_texts,
                        args.dry_run, not args.no_verify,
                    )

                    latency_ms = int((time.monotonic() - t_var_start) * 1000)

                    result_row = build_result_row(
                        clause=clause,
                        gold=row,
                        variant=variant,
                        retrieval_config=retrieval_config,
                        generation_output=gen_out,
                        evidence=evidence,
                        risks=risks,
                        verification=verification,
                        latency_total_ms=latency_ms,
                    )
                    results.append(result_row)
                    pbar.update(1)

    if not results:
        print("No results — check API keys or use --dry-run")
        return

    # ── Save results ─────────────────────────────────────────────
    df = pd.DataFrame(results)

    metrics_csv = args.output_dir / "all_metrics.csv"
    df.to_csv(metrics_csv, index=False)
    print(f"\nMetrics CSV: {metrics_csv}")

    explanations_jsonl = args.output_dir / "explanations.jsonl"
    with explanations_jsonl.open("w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")
    print(f"Explanations JSONL: {explanations_jsonl}")

    # ── Per-RQ aggregates ─────────────────────────────────────────
    _save_rq_summaries(df, args.output_dir)

    # ── Print summary ────────────────────────────────────────────
    print_summary(df)


def _save_rq_summaries(df: pd.DataFrame, out_dir: Path) -> None:
    """Save per-research-question CSV summaries."""

    # RQ2 — Readability (generation variant comparison)
    rq2_cols = ["variant", "flesch_reading_ease", "fk_grade", "avg_sentence_length", "jargon_density"]
    available = [c for c in rq2_cols if c in df.columns]
    if len(available) > 1:
        rq2 = df[available].groupby("variant").mean().round(3)
        rq2.to_csv(out_dir / "rq2_readability.csv")

    # RQ3 — Risk classification
    rq3_cols = ["variant", "risk_precision", "risk_recall", "risk_f1"]
    available = [c for c in rq3_cols if c in df.columns]
    if len(available) > 1:
        rq3 = df[available].groupby("variant").mean().round(3)
        rq3.to_csv(out_dir / "rq3_risk_accuracy.csv")

    # RQ4 — Fidelity verification
    rq4_cols = ["variant", "fidelity_score", "entailment_label", "fidelity_passed"]
    available = [c for c in rq4_cols if c in df.columns]
    if len(available) > 1:
        rq4 = df[available].groupby("variant").agg({
            "fidelity_score": "mean",
            "fidelity_passed": "mean",
        }).round(3)
        rq4.to_csv(out_dir / "rq4_fidelity.csv")

    # RQ5 — Variant comparison (semantic similarity to reference)
    if "semantic_similarity_to_ref" in df.columns:
        rq5 = df.groupby("variant")[["semantic_similarity_to_ref", "flesch_reading_ease", "fk_grade"]].mean().round(3)
        rq5.to_csv(out_dir / "rq5_variant_comparison.csv")

    # RQ1 — Retrieval config comparison
    rq1_cols = ["retrieval_config", "n_evidence_retrieved", "fidelity_score", "semantic_similarity_to_ref"]
    available = [c for c in rq1_cols if c in df.columns]
    if len(available) > 1:
        rq1 = df[available].groupby("retrieval_config").mean().round(3)
        rq1.to_csv(out_dir / "rq1_retrieval_comparison.csv")

    print(f"Per-RQ CSVs saved to {out_dir}/")


if __name__ == "__main__":
    main()
