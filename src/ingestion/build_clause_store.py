"""
Build the unified clause store from CUAD + consumer contracts.

Usage:
    python -m src.ingestion.build_clause_store \\
        --cuad-dir data/raw/cuad/ \\
        --consumer-dir data/raw/consumer_contracts/ \\
        --output data/clauses.jsonl

Consolidates clauses from both sources into a single JSONL file
that the retrieval engine's EvidenceCorpus loads at startup.

References:
    - §10 Week 1-2: Data pipeline (CUAD + consumer contracts → clause units)
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import List

from src.ingestion.extract_cuad import extract_cuad as run_cuad_extraction
from src.ingestion.processor import DocumentProcessor

logger = logging.getLogger(__name__)

# ── Paths inside the output directory ──────────────────────────

CUAD_OUTPUT_SUBDIR = "cuad"
CONSUMER_OUTPUT_SUBDIR = "consumer"


def build_clause_store(
    cuad_dir: str | Path,
    consumer_dir: str | Path,
    output_path: str | Path,
    benchmark_dir: str | Path | None = None,
) -> int:
    """Run both pipelines and merge results into a single JSONL.

    Args:
        cuad_dir: Directory containing CUAD CSV files.
        consumer_dir: Directory containing consumer contract files (PDF, DOCX, MD).
        output_path: Where to write the merged clause store.
        benchmark_dir: Optional — if provided, clauses from this directory
                       get ``is_benchmark: true``.

    Returns:
        Total number of clauses written.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = output_path.parent / ".clause_store_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    all_clauses: List[dict] = []

    # ── Phase 1: CUAD ───────────────────────────────────────────
    cuad_out = tmp_dir / CUAD_OUTPUT_SUBDIR
    print(f"[1/3] Extracting CUAD clauses from {cuad_dir} …")
    run_cuad_extraction(str(cuad_dir), str(cuad_out))

    cuad_file = cuad_out / "cuad_clauses.jsonl"
    if cuad_file.exists():
        with cuad_file.open("r", encoding="utf-8") as f:
            for line in f:
                clause = json.loads(line)
                clause["source_doc"] = clause.get("contract_name", "cuad")
                clause["doc_type"] = "service"
                clause["section_title"] = None
                clause["clause_number"] = None
                clause["context_before"] = ""
                clause["context_after"] = ""
                clause["is_benchmark"] = False
                clause["benchmark_annotations"] = None
                all_clauses.append(clause)
        print(f"  → {cuad_file}: {len(all_clauses)} clauses loaded")

    # ── Phase 2: Consumer contracts ─────────────────────────────
    consumer_path = Path(consumer_dir)
    consumer_out = tmp_dir / CONSUMER_OUTPUT_SUBDIR
    consumer_out.mkdir(parents=True, exist_ok=True)
    processor = DocumentProcessor()

    supported_extensions = {".pdf", ".docx", ".md", ".txt"}
    consumer_files = [
        p
        for p in consumer_path.rglob("*")
        if p.suffix.lower() in supported_extensions and not p.name.startswith(".")
    ]

    if consumer_files:
        print(f"[2/3] Processing {len(consumer_files)} consumer contracts …")
        for file_path in consumer_files:
            try:
                clauses = processor.process(file_path)
                for clause in clauses:
                    all_clauses.append(json.loads(clause.model_dump_json()))
                print(f"  → {file_path.name}: {len(clauses)} clauses")
            except Exception as e:
                print(f"  ✗ {file_path.name}: failed — {e}")
    else:
        print("[2/3] No consumer contract files found — skipping")

    # ── Phase 3: Mark benchmark clauses ─────────────────────────
    if benchmark_dir:
        benchmark_path = Path(benchmark_dir)
        benchmark_ids: set = set()
        for bf in benchmark_path.rglob("*.jsonl"):
            with bf.open("r") as f:
                for line in f:
                    data = json.loads(line)
                    if "clause_id" in data:
                        benchmark_ids.add(data["clause_id"])

        if benchmark_ids:
            print(f"[3/3] Marking {len(benchmark_ids)} benchmark clauses …")
            for clause in all_clauses:
                if clause["clause_id"] in benchmark_ids:
                    clause["is_benchmark"] = True
        else:
            print("[3/3] No benchmark IDs found — skipping benchmark marking")
    else:
        print("[3/3] No benchmark directory provided — skipping")

    # ── Write merged output ─────────────────────────────────────
    with output_path.open("w", encoding="utf-8") as f:
        for clause in all_clauses:
            f.write(json.dumps(clause, ensure_ascii=False) + "\n")

    # Cleanup temp
    import shutil

    shutil.rmtree(tmp_dir, ignore_errors=True)

    print(f"\nDone — {len(all_clauses)} total clauses written to {output_path}")
    return len(all_clauses)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build the unified clause store from CUAD + consumer contracts."
    )
    parser.add_argument(
        "--cuad-dir",
        required=True,
        help="Directory containing CUAD CSV files",
    )
    parser.add_argument(
        "--consumer-dir",
        required=True,
        help="Directory containing consumer contract files (PDF, DOCX, MD, TXT)",
    )
    parser.add_argument(
        "--output",
        default="data/clauses.jsonl",
        help="Output path for the merged clause store (default: data/clauses.jsonl)",
    )
    parser.add_argument(
        "--benchmark-dir",
        default=None,
        help="Optional directory with benchmark clause JSONL files to mark",
    )
    args = parser.parse_args()
    build_clause_store(
        cuad_dir=args.cuad_dir,
        consumer_dir=args.consumer_dir,
        output_path=args.output,
        benchmark_dir=args.benchmark_dir,
    )
