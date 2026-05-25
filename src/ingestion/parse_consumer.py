"""
Parse consumer contract PDFs into clause units.

Usage:
    python -m src.ingestion.parse_consumer --input data/raw/consumer/ --output data/processed/

Output: data/processed/consumer_clauses.jsonl
Each line: {"clause_id", "text", "clause_type", "contract_name", "source": "consumer"}
"""

import argparse
import json
from pathlib import Path


def parse_consumer_contracts(input_dir: str, output_dir: str) -> None:
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    clauses = []
    for pdf_path in input_path.glob("*.pdf"):
        clauses.extend(_parse_pdf(pdf_path))

    out_file = output_path / "consumer_clauses.jsonl"
    with out_file.open("w") as f:
        for clause in clauses:
            f.write(json.dumps(clause) + "\n")

    print(f"Extracted {len(clauses)} clauses from {input_path} → {out_file}")


def _parse_pdf(pdf_path: Path) -> list[dict]:
    """Extract and segment a single PDF into clause-level dicts using pdfplumber."""
    raise NotImplementedError


def _segment_into_clauses(raw_text: str, contract_name: str) -> list[dict]:
    """Split raw contract text into individual clause units."""
    raise NotImplementedError


def _classify_clause_type(clause_text: str) -> str:
    """Assign clause_type using keyword heuristics from the risk ontology signals."""
    raise NotImplementedError


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    parse_consumer_contracts(args.input, args.output)
