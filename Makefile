.PHONY: install dev-install lint fmt typecheck test test-one \
        build-index run-api run-eval run-figures run-tables

# ── Setup ──────────────────────────────────────────────────────────────────────
install:
	pip install -e .

dev-install:
	pip install -e ".[dev]"

# ── Code quality ───────────────────────────────────────────────────────────────
lint:
	ruff check src/ tests/

fmt:
	ruff format src/ tests/

typecheck:
	mypy src/

# ── Tests ──────────────────────────────────────────────────────────────────────
test:
	pytest tests/ -v

test-one:
	pytest $(FILE) -v  # usage: make test-one FILE=tests/test_retrieval.py::test_bm25

# ── Data pipeline (Track A) ────────────────────────────────────────────────────
extract-cuad:
	python -m src.ingestion.extract_cuad --input data/raw/cuad/ --output data/processed/

parse-consumer:
	python -m src.ingestion.parse_consumer --input data/raw/consumer/ --output data/processed/

build-index:
	python -m src.retrieval.build_index --corpus data/evidence_corpus/ --output data/indexes/

# ── Backend (Track B) ──────────────────────────────────────────────────────────
run-api:
	uvicorn src.api.main:app --reload --port 8000

run-eval:
	python -c "from src.evaluation.metrics import compute_all_metrics; compute_all_metrics()"

run-figures:
	python notebooks/generate_figures.py

run-tables:
	python notebooks/generate_tables.py

# ── Frontend (Track C) ─────────────────────────────────────────────────────────
frontend-install:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build
