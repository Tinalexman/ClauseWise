# ClauseWise — *Understand Every Clause Before You Sign*

Retrieval-grounded legal information access system that transforms dense contract clauses into plain-English explanations, flags consumer risks, and verifies every explanation against retrieved legal evidence.

Built as a thesis project supporting 7 research questions evaluated across 50 benchmark clauses.

---

## Architecture Overview

```
Upload contract → Extract clauses → [Retrieval → Generation → Risk Classification → Fidelity Verification] → Response
```

Three engineering tracks, each owned by a separate collaborator:

| Track | Scope | Folders |
|-------|-------|---------|
| **A — ML Engineering** | Pipeline, models, retrieval, generation, evaluation | `src/ingestion/`, `src/retrieval/`, `src/generation/`, `src/risk/`, `src/verification/`, `src/evaluation/` |
| **B — Backend + Evaluation** | FastAPI, figures, tables | `src/api/`, `notebooks/` |
| **C — Frontend + User Study** | React UI, study protocol | `frontend/`, `user_study/` |

---

## First-Time Setup (All Collaborators)

```bash
git clone <repo-url>
cd ClauseWise

# Create and activate virtual environment
python3.12 -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate

# Install all dependencies
pip install -e ".[dev]"

# Set up environment variables
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### Branch Convention

Each collaborator works on a dedicated branch:

```bash
git checkout -b track-a/<your-name>   # ML engineering
git checkout -b track-b/<your-name>   # Backend + evaluation
git checkout -b track-c/<your-name>   # Frontend + user study
```

---

## Track A — ML Engineering

**Owner:** builds the data pipeline, retrieval engine, generation variants, risk classifier, and fidelity verifier.

### Dependencies on other tracks
- None. Track A is the foundation — Tracks B and C consume its outputs.

### Day-by-day tasks

| Day | Task | Entry point |
|-----|------|-------------|
| 1 | CUAD extraction + consumer contract parsing | `src/ingestion/extract_cuad.py`, `src/ingestion/parse_consumer.py` |
| 1 | Evidence corpus + risk ontology | `data/evidence_corpus/evidence.jsonl`, `data/ontology/risk_ontology.yaml` |
| 2 AM | Build BM25 + ChromaDB indexes | `src/retrieval/build_index.py` |
| 2 AM | Implement all 5 retrieval configs | `src/retrieval/engine.py` |
| 2 PM | Implement all 5 generation variants | `src/generation/pipeline.py`, `src/generation/prompts.py` |
| 3 AM | Risk classifier + fidelity verifier | `src/risk/classifier.py`, `src/verification/verifier.py` |
| 3 PM | Full metric computation | `src/evaluation/metrics.py` |

### Key commands

```bash
# Step 1 — extract clauses
python -m src.ingestion.extract_cuad --input data/raw/cuad/ --output data/processed/
python -m src.ingestion.parse_consumer --input data/raw/consumer/ --output data/processed/

# Step 2 — build indexes
python -m src.retrieval.build_index --corpus data/evidence_corpus/ --output data/indexes/

# Step 3 — run evaluation
python -c "from src.evaluation.metrics import compute_all_metrics; compute_all_metrics()"
```

### Key design decisions to respect

- `RetrievalEngine` must accept a `config: RetrievalConfig` parameter (IntEnum 1–5). Do not split into separate classes.
- Config 5 (`HYBRID_RERANKER_FILTER`) is the production config used by the API.
- `GenerationPipeline` must accept a `variant: GenerationVariant` parameter (IntEnum 1–5). Variant 5 (`CLAUSEWISE`) is production.
- `fidelity_score` = `nli_weight * nli_score + llm_weight * llm_score` (weights in `src/config.py`).
- All output JSONL files must match the schemas documented in `CLAUDE.md` — Track B reads them directly.

---

## Track B — Backend + Evaluation

**Owner:** builds the FastAPI backend and generates all 14 publication-ready figures and tables from Track A's outputs.

### Dependencies on other tracks
- Requires Track A's output files in `evaluation/results/` before generating figures/tables.
- API connects to Track A's `RetrievalEngine`, `GenerationPipeline`, `RiskClassifier`, and `FidelityVerifier`.

### Day-by-day tasks

| Day | Task | Entry point |
|-----|------|-------------|
| 3 PM | Metric computation (consumes Track A outputs) | `src/evaluation/metrics.py` |
| 4 | All 14 figures | `notebooks/generate_figures.py` |
| 5 AM | All 14 tables | `notebooks/generate_tables.py` |
| 5 PM | FastAPI endpoints | `src/api/main.py` |

### Key commands

```bash
# Run API dev server
uvicorn src.api.main:app --reload --port 8000

# Generate figures (requires evaluation/results/ populated by Track A)
python notebooks/generate_figures.py

# Generate tables
python notebooks/generate_tables.py
```

### API contract

All request/response schemas are defined in `src/api/models.py`. Do not change field names — Track C's frontend depends on them.

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/simplify` | Full pipeline: clause → explanation + risks + verification |
| `POST /api/v1/upload` | PDF/DOCX → extracted clause list |
| `POST /api/v1/followup` | Follow-up question about a clause |
| `GET /api/v1/clause/{id}` | Fetch clause + all variant explanations |
| `POST /api/v1/study/log` | Log user study interaction events |

---

## Track C — Frontend + User Study

**Owner:** builds the React UI with 4 study conditions and designs the human evaluation protocol.

### Dependencies on other tracks
- Requires Track B's API running on `http://localhost:8000`.

### Setup

```bash
# First time only
npx create-next-app@latest frontend --typescript --tailwind --app --eslint --no-git
cd frontend
npx shadcn@latest init
npx shadcn@latest add card badge tabs textarea button

npm run dev   # starts on http://localhost:3000
```

### Day-by-day tasks

| Day | Task | Location |
|-----|------|----------|
| 6 AM | 7 panels + study condition visibility | `frontend/` |
| 6 PM | Study protocol, consent form, interaction logger | `user_study/` |
| 7 | E2E test + demo recording | — |

### 7 panels to implement

| Panel | Purpose |
|-------|---------|
| `ClausePanel` | Display original clause with highlighted legal terms |
| `ExplanationPanel` | Plain-English explanation + confidence badge + "seek legal advice" flag |
| `RiskPanel` | Severity badges (red=critical, orange=high, yellow=medium, green=low) |
| `EvidencePanel` | Collapsible accordion of evidence items with citations |
| `ComparisonView` | Side-by-side original vs simplified toggle |
| `FollowUpPanel` | Text input → `POST /api/v1/followup` → answer |
| `StudyControls` | Group selector (A/B/C/D) that controls panel visibility |

### Study condition visibility matrix

| Panel | Group A | Group B | Group C | Group D |
|-------|:-------:|:-------:|:-------:|:-------:|
| Clause text | ✓ | ✓ | ✓ | ✓ |
| Explanation | ✗ | ✓ | ✓ | ✓ |
| Risk flags | ✗ | ✗ | ✓ | ✓ |
| Evidence | ✗ | ✗ | ✗ | ✓ |
| Comparison | ✗ | ✗ | ✓ | ✓ |
| Follow-up Q&A | ✗ | ✗ | ✓ | ✓ |

The silent interaction logger must batch events to `POST /api/v1/study/log`. Logged fields: `session_id`, `group`, `event_type` (click/scroll/panel_open/panel_close/followup/dwell), `payload`, `timestamp`.

---

## Common Commands (All Tracks)

```bash
make lint          # ruff check
make fmt           # ruff format
make typecheck     # mypy
make test          # all tests
make test-one FILE=tests/test_retrieval.py::test_bm25_returns_results
```

---

## Data Layout

```
data/
├── raw/cuad/            ← CUAD download (not committed)
├── raw/consumer/        ← consumer contract PDFs (not committed)
├── processed/           ← generated JSONL (not committed)
├── evidence_corpus/     ← ~70 evidence items (not committed)
├── benchmark/           ← 50 gold-standard annotated clauses (not committed)
├── ontology/
│   └── risk_ontology.yaml   ← committed — 8 risk categories with detection signals
└── indexes/             ← built BM25 + ChromaDB indexes (not committed)
```

Data files in `data/` (except `ontology/`) are gitignored — each collaborator builds them locally by running the pipeline.
