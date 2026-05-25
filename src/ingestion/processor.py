"""Document Processor (§3.1)
=============================
Orchestrates the ingestion pipeline:

    LegalDocumentParser  →  ClauseChunker  →  type classification  →  ClauseUnit

This is the public API for the ingestion layer. Downstream modules
(RetrievalEngine, RiskClassifier, etc.) consume ``ClauseUnit`` objects
produced here.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from src.ingestion.chunker import ClauseChunker
from src.ingestion.parser import LegalDocumentParser
from src.models import ClauseType, ClauseUnit, DocType

# ── Clause-type keyword signals (bootstrap / weak supervision) ──

CLAUSE_TYPE_SIGNALS: Dict[ClauseType, List[str]] = {
    ClauseType.indemnity: [
        "indemnify",
        "indemnification",
        "hold harmless",
        "defend",
        "against all losses",
    ],
    ClauseType.termination: [
        "terminate",
        "termination",
        "expire",
        "expiration",
        "cancel",
        "cancellation",
        "end of term",
    ],
    ClauseType.confidentiality: [
        "confidential",
        "confidentiality",
        "non-disclosure",
        "proprietary",
        "trade secret",
    ],
    ClauseType.auto_renewal: [
        "renew",
        "automatically renew",
        "auto-renew",
        "successive term",
        "shall continue",
    ],
    ClauseType.liability_limitation: [
        "limitation of liability",
        "limit our liability",
        "not be liable",
        "maximum liability",
        "exclusive remedy",
        "cap on liability",
    ],
    ClauseType.payment_terms: [
        "payment",
        "fee",
        "charge",
        "invoice",
        "payable",
        "subscription fee",
        "billing",
        "late payment",
    ],
    ClauseType.dispute_resolution: [
        "arbitration",
        "arbitrate",
        "binding arbitration",
        "dispute",
        "governing law",
        "venue",
        "class action",
        "waiver",
        "mandatory arbitration",
    ],
    ClauseType.data_sharing: [
        "data",
        "privacy",
        "personal information",
        "collect",
        "share",
        "disclose",
        "processing",
    ],
    ClauseType.refund_policy: [
        "refund",
        "no refund",
        "non-refundable",
        "cancellation fee",
        "money back",
    ],
    ClauseType.non_compete: [
        "non-compete",
        "non compete",
        "non-competition",
        "competitive",
        "solicit",
        "restrictive covenant",
    ],
}


class DocumentProcessor:
    """Full ingestion pipeline: parse → chunk → classify → ClauseUnit.

    Usage::

        proc = DocumentProcessor()
        clauses = proc.process("contract.pdf")
        for clause in clauses:
            print(clause.clause_id, clause.clause_type)
    """

    def __init__(self) -> None:
        self.parser = LegalDocumentParser()
        self.chunker: Optional[ClauseChunker] = None

    # ──────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────

    def process(self, file_path: str | Path) -> List[ClauseUnit]:
        """Full pipeline: parse → chunk → classify → ClauseUnit list."""
        file_path = Path(file_path)
        # 1. Parse
        raw_blocks = self.parser.parse(file_path)
        # 2. Chunk with calibrated body font size
        self.chunker = ClauseChunker(body_font_size=self.parser.body_font_size)
        chunks = self.chunker.build_chunks(raw_blocks)
        # 3. Convert chunks → ClauseUnit
        return self._chunks_to_clause_units(chunks, file_path.stem)

    # ──────────────────────────────────────────────────────────────
    # Chunk → ClauseUnit conversion
    # ──────────────────────────────────────────────────────────────

    def _chunks_to_clause_units(
        self, chunks: List[Dict[str, Any]], source_name: str
    ) -> List[ClauseUnit]:
        """Map each chunk into a ClauseUnit, adding type + metadata."""
        units: List[ClauseUnit] = []

        for idx, chunk in enumerate(chunks):
            text = chunk["text"]
            hierarchy = chunk.get("hierarchy", [])
            page_number = chunk.get("page_number", 0)
            word_count = len(text.split())

            # Derive section info from hierarchy
            section_title, clause_number = self._extract_section_info(hierarchy)

            # Classify clause type
            clause_type = self._classify_single(text)

            # Build clause_id: {source}_{index:04d}_{type}
            clause_id = f"{source_name}_{idx + 1:04d}_{clause_type.value}"

            # Context (sibling chunks)
            context_before = chunks[idx - 1]["text"][:1000] if idx > 0 else ""
            context_after = (
                chunks[idx + 1]["text"][:1000] if idx + 1 < len(chunks) else ""
            )

            doc_type = self._infer_doc_type(source_name)

            units.append(
                ClauseUnit(
                    clause_id=clause_id,
                    text=text,
                    clause_type=clause_type,
                    source_doc=source_name,
                    doc_type=doc_type,
                    section_title=section_title,
                    clause_number=clause_number,
                    context_before=context_before,
                    context_after=context_after,
                    word_count=word_count,
                    is_benchmark=False,
                    benchmark_annotations=None,
                )
            )

        return units

    # ──────────────────────────────────────────────────────────────
    # Hierarchy → section_title / clause_number
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_section_info(
        hierarchy: List[str],
    ) -> tuple[Optional[str], Optional[str]]:
        """Derive ``section_title`` and ``clause_number`` from hierarchy.

        Examples::

            ["ARTICLE 1", "1.", "(a)"]
                → section_title="ARTICLE 1", clause_number="1."

            ["HEADER: Term and Termination", "5."]
                → section_title="Term and Termination", clause_number="5."

            []
                → section_title=None, clause_number=None
        """
        section_title: Optional[str] = None
        clause_number: Optional[str] = None

        for node in hierarchy:
            if node.startswith("HEADER:"):
                section_title = node.replace("HEADER:", "").strip()
            elif re.match(r"^(?:ARTICLE|SECTION)\s+\d+", node, re.IGNORECASE):
                section_title = section_title or node
            elif re.match(r"^\d+(?:\.\d+)*\.?$", node):
                clause_number = node
            elif clause_number is None and re.match(r"^\([a-z]\)$", node):
                # If we see alpha before any number, use it as the clause ref
                clause_number = node

        return section_title, clause_number

    # ──────────────────────────────────────────────────────────────
    # Clause-type classification (keyword bootstrapping)
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def _classify_single(text: str) -> ClauseType:
        """Match text against keyword signals; fall back to *indemnity*."""
        text_lower = text.lower()
        best_type = ClauseType.unknown
        best_score = 0

        for clause_type, keywords in CLAUSE_TYPE_SIGNALS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > best_score:
                best_score = score
                best_type = clause_type

        return best_type

    # ──────────────────────────────────────────────────────────────
    # Document type inference
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def _infer_doc_type(filename: str) -> DocType:
        """Guess document type from filename keywords."""
        name = filename.lower()
        if any(w in name for w in ("rent", "lease", "tenancy")):
            return DocType.rental
        if any(w in name for w in ("employ", "offer letter", "employment")):
            return DocType.employment
        if any(
            w in name
            for w in (
                "subscrib",
                "saas",
                "tos",
                "terms of service",
                "service agreement",
                "terms",
            )
        ):
            return DocType.subscription
        if "privacy" in name:
            return DocType.privacy
        if any(w in name for w in ("insurance", "policy")):
            return DocType.insurance
        if any(w in name for w in ("loan", "credit", "finance")):
            return DocType.consumer_finance
        return DocType.service

    # ──────────────────────────────────────────────────────────────
    # Serialisation helpers
    # ──────────────────────────────────────────────────────────────

    def process_to_jsonl(self, file_path: str | Path, output_path: str | Path) -> int:
        """Process document and write clauses to a JSONL file.

        Returns the number of clauses written.
        """
        clauses = self.process(file_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            for clause in clauses:
                f.write(clause.model_dump_json() + "\n")
        return len(clauses)

    def process_batch(
        self, file_paths: List[str | Path], output_dir: str | Path
    ) -> Generator[int, None, None]:
        """Process multiple documents, writing one JSONL per file.

        Yields clause counts as each file finishes.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        for fp in file_paths:
            fp = Path(fp)
            out = output_dir / f"{fp.stem}_clauses.jsonl"
            count = self.process_to_jsonl(fp, out)
            yield count
