"""Quick end-to-end test of the full ClauseWise pipeline."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import RetrievalConfig, settings
from src.models import ClauseType, ClauseUnit, DocType

# ── 1. Ontology ────────────────────────────────────────────────
print("\n=== 1. ONTOLOGY ===")
from src.risk.ontology import load_ontology

onto = load_ontology()
print(f"Loaded {len(onto.risk_categories)} categories")

# ── 2. PDF Processing ─────────────────────────────────────────
print("\n=== 2. PDF PROCESSING ===")
pdf = "data/raw/consumer_contract/sec.gov_Archives_edgar_data_819793_000089109218004221_e78842ex10u.htm.pdf"
if os.path.exists(pdf):
    from src.ingestion.processor import DocumentProcessor

    proc = DocumentProcessor()
    pdf_clauses = proc.process(pdf)
    print(f"Extracted {len(pdf_clauses)} clauses")
    if pdf_clauses:
        print(f"  First: [{pdf_clauses[0].clause_type}] {pdf_clauses[0].text[:80]}...")
else:
    print(f"  PDF not found — skipped")
    pdf_clauses = []

# ── 3. Retrieval ──────────────────────────────────────────────
print("\n=== 3. RETRIEVAL ===")
evidence: list = []
test_clause = ClauseUnit(
    clause_id="test_0001",
    text="This agreement shall automatically renew for successive terms unless cancelled in writing 30 days prior.",
    clause_type=ClauseType.auto_renewal,
    source_doc="test",
    doc_type=DocType.subscription,
    word_count=16,
)

if settings.voyage_api_key and settings.voyage_api_key != "pa-...":
    from src.retrieval.engine import RetrievalEngine

    engine = RetrievalEngine(RetrievalConfig(method="hybrid_reranker_filter"))
    evidence = engine.retrieve(test_clause)
    print(f"Retrieved {len(evidence)} items")
    for e in evidence[:2]:
        print(f"  [{e.evidence_id}] {e.text[:60]}...")
else:
    print("  VOYAGE_API_KEY not set — skipped")

# ── 4. Classifier ─────────────────────────────────────────────
print("\n=== 4. RISK CLASSIFIER ===")
risks: list = []
if settings.openai_api_key and settings.openai_api_key != "sk-...":
    from src.risk.classifier import RiskClassifier

    classifier = RiskClassifier()
    risks = classifier.classify(test_clause, evidence)
    print(f"Found {len(risks)} risks")
    for r in risks:
        print(f"  [{r.severity}] {r.risk_category}: {r.explanation[:60]}...")
else:
    print("  OPENAI_API_KEY not set — skipped")

# ── 5. Generator ──────────────────────────────────────────────
print("\n=== 5. GENERATOR ===")
from src.generation.generator import ExplanationGenerator
from src.models import GenerationVariant

gen = ExplanationGenerator()

extractive = gen.generate(test_clause, variant=GenerationVariant.extractive)
print(f"Extractive: {extractive.plain_english[:100]}...")

if settings.openai_api_key and settings.openai_api_key != "sk-...":
    proposed = gen.generate(
        test_clause,
        evidence,
        risks,
        variant=GenerationVariant.proposed,
        retrieval_config="hybrid_reranker_filter",
    )
    print(f"Proposed:   {proposed.plain_english[:100]}...")
    print(f"FK Grade:   {proposed.readability.flesch_kincaid_grade}")

# ── 6. Verifier (skipped — needs sentence-transformers) ───────
print("\n=== 6. VERIFIER (skip - install sentence-transformers manually) ===")

print("\n=== DONE ===")
