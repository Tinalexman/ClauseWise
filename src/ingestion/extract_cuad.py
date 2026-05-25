"""
Extract clause text and type from the CUAD dataset.

Usage:
    python -m src.ingestion.extract_cuad --input data/raw/cuad/ --output data/processed/

Output: data/processed/cuad_clauses.jsonl
Each line: {"clause_id", "text", "clause_type", "contract_name", "source": "cuad"}

References:
    - §8 Risk Mitigation: CUAD supplemented with consumer contracts
    - §10 Week 1-2: Data pipeline (CUAD + consumer contracts → clause units)
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List, Optional, Set

# ── Map CUAD question types to internal clause_type slugs ──────
# CUAD defines ~41 question types; only those in our ClauseType
# enum are extracted. Unmapped types are skipped.

CUAD_TO_CLAUSE_TYPE: Dict[str, str] = {
    # Indemnity
    "indemnification - cap": "indemnity",
    "indemnification - no cap": "indemnity",
    "indemnification - reciprocal": "indemnity",
    "indemnification - non-reciprocal": "indemnity",
    # Termination
    "termination for convenience": "termination",
    "termination for cause": "termination",
    "effect of termination": "termination",
    "post-termination services": "termination",
    # Confidentiality
    "confidentiality of agreement": "confidentiality",
    "non-disclosure obligations": "confidentiality",
    "exceptions to confidentiality": "confidentiality",
    # Auto-renewal
    "auto-renewal": "auto_renewal",
    "renewal term": "auto_renewal",
    # Liability limitation
    "limitation of liability": "liability_limitation",
    "limitation of liability - cap on damages": "liability_limitation",
    "limitation of liability - exclusion of consequential damages": "liability_limitation",
    "limitation of liability - mutual": "liability_limitation",
    # Payment terms
    "payment terms": "payment_terms",
    "revenue / profit sharing": "payment_terms",
    "pricing": "payment_terms",
    "fee structure": "payment_terms",
    # Dispute resolution
    "governing law": "dispute_resolution",
    "jurisdiction / venue": "dispute_resolution",
    "arbitration": "dispute_resolution",
    "dispute resolution": "dispute_resolution",
    "class action waiver": "dispute_resolution",
    "jury trial waiver": "dispute_resolution",
    # Data sharing
    "data protection / privacy": "data_sharing",
    "data retention": "data_sharing",
    "data ownership": "data_sharing",
    # Non-compete
    "non-compete": "non_compete",
    "non-solicitation": "non_compete",
    "exclusivity": "non_compete",
    "non-competition": "non_compete",
    # Refund policy
    "cancellation policy": "refund_policy",
    "money back guarantee": "refund_policy",
    # Unmapped CUAD question types are silently skipped
}

# Clause types in our schema (for validation)
VALID_TYPES: Set[str] = {
    "indemnity",
    "termination",
    "confidentiality",
    "auto_renewal",
    "liability_limitation",
    "payment_terms",
    "dispute_resolution",
    "data_sharing",
    "non_compete",
    "refund_policy",
}


def extract_cuad(input_dir: str, output_dir: str) -> None:
    """Run CUAD extraction pipeline."""
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    clauses = _parse_annotations(input_path)
    out_file = output_path / "cuad_clauses.jsonl"
    with out_file.open("w", encoding="utf-8") as f:
        for clause in clauses:
            f.write(json.dumps(clause, ensure_ascii=False) + "\n")

    print(f"Extracted {len(clauses)} clauses → {out_file}")


def _parse_annotations(input_path: Path) -> List[dict]:
    """Parse CUAD CSV files and return filtered clause dicts.

    CUAD provides one CSV per contract. Each row contains:
        - file_name:    contract document name
        - question:     question type (maps to clause_type)
        - answer:       "Yes" / "No" (only "Yes" rows are extracted)
        - context:      text snippet supporting the answer
    """
    clauses: List[dict] = []
    seen: Set[str] = set()  # deduplicate (contract, context) pairs

    csv_files = list(input_path.rglob("*.csv"))
    if not csv_files:
        print(f"Warning: No CSV files found in {input_path}")
        return clauses

    for csv_file in csv_files:
        contract_name = csv_file.stem

        with csv_file.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                answer = (row.get("answer") or "").strip().lower()
                if answer != "yes":
                    continue

                question = (row.get("question") or "").strip().lower()
                context = (row.get("context") or "").strip()

                clause_type = _normalize_clause_type(question)
                if clause_type is None or not context:
                    continue

                # Deduplicate: same contract + same text
                dedup_key = f"{contract_name}::{context[:200]}"
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)

                clause_id = f"cuad_{contract_name}_{len(clauses):04d}_{clause_type}"

                clauses.append(
                    {
                        "clause_id": clause_id,
                        "text": context,
                        "clause_type": clause_type,
                        "contract_name": contract_name,
                        "source": "cuad",
                        "word_count": len(context.split()),
                    }
                )

    return clauses


def _normalize_clause_type(raw_type: str) -> Optional[str]:
    """Map CUAD question type to internal clause_type slug.

    Returns None if the type is not in our ClauseType enum scope,
    which causes the row to be skipped.
    """
    cleaned = raw_type.strip().lower()
    # Direct lookup
    mapped = CUAD_TO_CLAUSE_TYPE.get(cleaned)
    if mapped and mapped in VALID_TYPES:
        return mapped

    # Fuzzy fallback: check if any key is a substring of the question
    for key, slug in CUAD_TO_CLAUSE_TYPE.items():
        if key in cleaned:
            if slug in VALID_TYPES:
                return slug

    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract clause text and type from the CUAD dataset."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to CUAD raw directory (searched recursively for CSVs)",
    )
    parser.add_argument(
        "--output", required=True, help="Path to processed output directory"
    )
    args = parser.parse_args()
    extract_cuad(args.input, args.output)
