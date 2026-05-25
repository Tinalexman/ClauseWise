# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

ClauseWise is an MSc thesis system (Information Processing & Management) that transforms legal contract clauses into plain-English explanations grounded in retrieved legal evidence, with risk classification and fidelity verification. It supports 7 research questions evaluated across 50 benchmark clauses.

## Environment Setup

```bash
source venv/bin/activate          # Python 3.12 venv
pip install -r requirements.txt   # once created

# Frontend
cd frontend && npm install
```

Environment variables go in `.env` (not committed). Required: `OPENAI_API_KEY`.

## Commands

### Data Pipeline (Track A)

```bash
# Extract clauses from CUAD dataset
python -m src.ingestion.extract_cuad --input data/raw/cuad/ --output data/processed/

# Build vector + BM25 indexes from evidence corpus
python -m src.retrieval.build_index --corpus data/evidence_corpus/ --output data/indexes/
```

### Backend

```bash
uvicorn src.api.main:app --reload   # FastAPI dev server (default: localhost:8000)
```

### Evaluation

```bash
# Generate all 14 figures
python notebooks/generate_figures.py

# Generate all 14 tables (LaTeX + Markdown + CSV)
python notebooks/generate_tables.py
```

### Frontend

```bash
cd frontend && npm run dev    # Next.js dev server
cd frontend && npm run build
cd frontend && npm run lint
```

### Tests

```bash
pytest tests/                        # all tests
pytest tests/test_retrieval.py -v    # single file
pytest -k "test_hybrid_retrieval"    # single test by name
```

## Architecture

The system has three tracks that execute sequentially (A → B → C):

### Track A — ML Pipeline (`src/`)

**Data flow:** raw PDFs/CSVs → ingestion → processed JSONL → indexes → retrieval → generation → verification

- `src/ingestion/` — CUAD clause extraction (pdfplumber/unstructured), consumer contract parsing, outputs `data/processed/*.jsonl`
- `src/retrieval/` — `RetrievalEngine` class with 5 configs switchable via a `config` parameter:
  1. BM25 only (`rank_bm25`)
  2. Dense only (MiniLM-L6-v2 embeddings via FAISS)
  3. Hybrid (reciprocal rank fusion of BM25 + dense)
  4. Hybrid + cross-encoder reranker (`ms-marco-MiniLM-L-6-v2`)
  5. Hybrid + reranker + clause-type metadata filter ← **best config, used in production**
- `src/generation/` — 5 generation variants (extractive → vanilla LLM → prompted LLM → RAG → ClauseWise full). The production variant (Variant 5) uses GPT-4o-mini + retrieval Config 5 + risk ontology context.
- `src/risk/` — LLM-as-classifier using GPT-4o-mini with the risk ontology in-context + 3 few-shot examples. 8 risk categories defined in `data/ontology/risk_ontology.yaml`.
- `src/verification/` — dual fidelity check: NLI entailment (`nli-deberta-v3-base`, runs locally) + LLM-as-judge (GPT-4o-mini rubric). Combined into a `fidelity_score` 0–1 with a pass/fail threshold.
- `src/evaluation/` — metric computation (RAGAS faithfulness/relevance, readability via Flesch/FK Grade, hallucination rate)

### Track B — Backend + Evaluation (`src/api/`, `notebooks/`, `evaluation/`)

- FastAPI app at `src/api/main.py` with 5 endpoints: `POST /api/v1/simplify`, `POST /api/v1/upload`, `POST /api/v1/followup`, `GET /api/v1/clause/{id}`, `POST /api/v1/study/log`
- `POST /api/v1/simplify` runs the full pipeline: clause → Config 5 retrieval → Variant 5 generation → dual verification → JSON response
- Figures/tables scripts read from `evaluation/results/*.csv` and write to `evaluation/figures/` and `evaluation/tables/`

### Track C — Frontend (`frontend/`)

Next.js (TypeScript, Tailwind, App Router) + shadcn/ui. 7 panels:
- `ClausePanel`, `ExplanationPanel`, `RiskPanel`, `EvidencePanel`, `ComparisonView`, `FollowUpPanel`, `StudyControls`

`StudyControls` switches between 4 study conditions (A/B/C/D) that toggle panel visibility — Group A sees only raw clause text; Group D sees all panels. A silent interaction logger component batches events to `/api/v1/study/log`.

### Key Data Files

| File | Contents |
|------|----------|
| `data/benchmark/benchmark.jsonl` | 50 gold-standard annotated clauses (5 per clause type) — source of truth for all evaluation |
| `data/evidence_corpus/evidence.jsonl` | ~70 evidence items with `evidence_id`, `text`, `source_type`, `legal_concept`, `clause_type`, `citation` |
| `data/ontology/risk_ontology.yaml` | 8 risk categories with severity, detection signals (keywords + regex), and recommended actions |
| `evaluation/results/explanations.jsonl` | 250 generated explanations (50 clauses × 5 variants) |

### Clause Types

10 consumer-relevant types: `indemnity`, `termination`, `confidentiality`, `auto_renewal`, `liability_limitation`, `payment_terms`, `dispute_resolution`, `data_sharing`, `non_compete`, `refund_policy`

### Risk Categories

8 categories: `automatic_renewal`, `broad_liability`, `vague_cancellation`, `one_sided_indemnity`, `hidden_penalties`, `excessive_data_sharing`, `unclear_dispute_resolution`, `missing_refund_terms`
