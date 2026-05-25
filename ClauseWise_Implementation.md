# ClauseWise

### *Understand Every Clause Before You Sign*

---

**Project Implementation Document**
Technical Architecture · Task Breakdown · 7-Day Sprint Plan

Version 1.0 — May 2026

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Engineering Domain Split](#2-engineering-domain-split)
3. [Track A — ML Engineering](#3-track-a--ml-engineering)
4. [Track B — Backend + Evaluation](#4-track-b--backend--evaluation)
5. [Track C — Frontend + User Study](#5-track-c--frontend--user-study)
6. [7-Day Sprint Schedule](#6-7-day-sprint-schedule)
7. [Cost Estimate + Risk Mitigation](#7-cost-estimate--risk-mitigation)
8. [Final Repository Structure](#8-final-repository-structure)

---

## 1. Project Overview

### 1.1 Product Name & Identity

**ClauseWise** — *"Understand Every Clause Before You Sign"*

ClauseWise is a retrieval-grounded legal information access system that helps everyday people understand complex contract clauses. It transforms dense legal language into plain English, flags consumer risks, grounds every explanation in retrieved legal evidence, and verifies that no meaning is lost or fabricated in the process.

The name communicates the core value proposition: clause-level intelligence that makes users wiser about what they are signing. It is consumer-facing, memorable, and distinct from existing tools like "Legalese Translator" or "Terms Simplifier" because it emphasises risk-awareness and evidence-grounded trust, not just readability.

### 1.2 User-Facing Value

**Upload a contract. Click any clause. Get a plain-English explanation backed by legal evidence, with risks flagged and actions recommended.**

ClauseWise serves renters reviewing leases, employees reading employment contracts, consumers evaluating subscription terms, freelancers parsing client agreements, and anyone who encounters legal documents without a law degree.

### 1.3 Research Framing

The system supports 7 research questions for an MSc thesis targeting Information Processing & Management. The implementation produces 14 publication-ready figures and 14 tables from real experimental data across retrieval quality, legal fidelity, readability, risk detection, hallucination control, user comprehension, and trust.

---

## 2. Engineering Domain Split

The project is split into three distinct engineering tracks. Each track has its own tasks, dependencies, and deliverables. A single developer executes all three sequentially; in a team setting, Track A and Track B can run in parallel after Day 1.

| Track | Scope | Days | Deliverables |
|-------|-------|------|-------------|
| **Track A** | ML Engineering | Day 1–3 | Pipeline, models, metrics |
| **Track B** | Backend + Evaluation | Day 3–5 | API, figures, tables, docs |
| **Track C** | Frontend + User Study | Day 6–7 | UI, study protocol, demo |

---

## 3. Track A — ML Engineering

This track covers everything that touches models, embeddings, retrieval, generation, classification, and verification. It is the scientific core of the thesis.

### A1. Data Pipeline

**▪ Task A1.1 — CUAD Clause Extraction**

Download CUAD from the Atticus Project GitHub repository. Parse the master annotations CSV. Extract clause text and clause type for all contracts. Filter to 10 consumer-relevant clause types (indemnity, termination, confidentiality, auto_renewal, liability_limitation, payment_terms, dispute_resolution, data_sharing, non_compete, refund_policy). Output ~500 clauses to `data/processed/cuad_clauses.jsonl`.

```bash
python -m src.ingestion.extract_cuad --input data/raw/CUAD/ --output data/processed/
```

**▪ Task A1.2 — Consumer Contract Collection**

Collect 10–15 publicly available consumer-facing contracts: Spotify ToS, Netflix ToS, Airbnb rental terms, WeWork lease, a sample residential lease, a sample employment contract, a gym membership agreement, a SaaS subscription agreement, a freelance client contract, and 2–3 privacy policies. Parse using pdfplumber/unstructured. Segment into clause units. Output ~100 clauses to `data/processed/consumer_clauses.jsonl`.

**▪ Task A1.3 — Benchmark Curation**

Select 50 clauses (5 per clause type) from both CUAD and consumer contracts. For each clause, write: reference plain-English explanation, risk categories, risk severity, required consumer action, supporting evidence span, and expert notes. This is the gold standard for all evaluation. Output to `data/benchmark/benchmark.jsonl`. Budget: 2 hours. Use Claude to draft explanations, then verify and correct each one.

**▪ Task A1.4 — Evidence Corpus Construction**

Build `data/evidence_corpus/evidence.jsonl` with ~70 items: 10 clause-type definitions (Black's Law Dictionary simplified), 30 plain-language explanations (3 per clause type from consumer.gov, FTC guides, Nolo.com), 20 annotated clause examples (2 per type with reference explanations), and 10 consumer-protection summaries. Each item has: evidence_id, text, source_type, legal_concept, clause_type, citation.

**▪ Task A1.5 — Risk Ontology**

Create `data/ontology/risk_ontology.yaml` with 8 risk categories: automatic_renewal, broad_liability, vague_cancellation, one_sided_indemnity, hidden_penalties, excessive_data_sharing, unclear_dispute_resolution, missing_refund_terms. Each category has: definition, severity_default, consumer_impact, recommended_actions, detection_signals (keywords + regex patterns), and example_clauses.

**⏱ Estimated time: 8 hours (Day 1)**

---

### A2. Retrieval Engine

**▪ Task A2.1 — Build Vector Index**

Embed all evidence corpus items using `sentence-transformers/all-MiniLM-L6-v2`. Store in ChromaDB (persistent). Build BM25 index using `rank_bm25` library. Store serialised index to `data/indexes/`.

```bash
python -m src.retrieval.build_index --corpus data/evidence_corpus/ --output data/indexes/
```

**▪ Task A2.2 — Implement 5 Retrieval Configurations**

Build a single `RetrievalEngine` class with a config parameter that switches behaviour:

- **Config 1 — BM25 only:** lexical keyword matching.
- **Config 2 — Dense only:** cosine similarity on MiniLM embeddings via FAISS.
- **Config 3 — Hybrid:** reciprocal rank fusion of BM25 + dense scores.
- **Config 4 — Hybrid + Reranker:** above + `cross-encoder/ms-marco-MiniLM-L-6-v2` reranking.
- **Config 5 — Hybrid + Reranker + Clause-type filter:** above + metadata filter restricting candidates to matching clause type before reranking.

**▪ Task A2.3 — Retrieval Evaluation**

Run all 5 configs on the 50 benchmark clauses at k = {1, 3, 5, 10}. Compute Recall@k, Precision@k, nDCG@k, MRR, and evidence relevance score. Save to `evaluation/results/retrieval_metrics.csv`. This directly produces **Table RQ2-T1**.

**⏱ Estimated time: 4 hours (Day 2 AM)**

---

### A3. Generation Pipeline

**▪ Task A3.1 — Implement 5 Generation Variants**

- **Variant 1 — Extractive:** TextRank summary using `sumy` library. No LLM.
- **Variant 2 — Vanilla LLM:** GPT-4o-mini with clause text only and a basic prompt.
- **Variant 3 — Prompted LLM:** GPT-4o-mini with structured prompt (JSON output, 8th-grade target) but no retrieved evidence.
- **Variant 4 — Standard RAG:** GPT-4o-mini with structured prompt + top-5 evidence from hybrid retriever.
- **Variant 5 — Proposed (ClauseWise):** GPT-4o-mini with structured prompt + top-5 evidence from best retriever (Config 5) + risk context from ontology + fidelity instructions.

**▪ Task A3.2 — Generate All Explanations**

Run all 5 variants on all 50 benchmark clauses = 250 explanations. Store in `evaluation/results/explanations.jsonl`. API cost: ~200 LLM calls × ~$0.0025 = **$0.50**. Runtime: ~7 minutes.

**⏱ Estimated time: 4 hours (Day 2 PM)**

---

### A4. Risk Classification

**▪ Task A4.1 — LLM-as-Classifier**

For each of the 50 benchmark clauses, call GPT-4o-mini with the risk ontology in-context plus 3 few-shot examples. Parse multi-label risk predictions with severity levels. Compare against benchmark gold labels. Compute per-class P/R/F1, macro-F1, severity agreement. Save to `evaluation/results/risk_metrics.csv`. This produces **Table RQ4-T1** data.

50 calls × ~$0.003 = **$0.15**. Runtime: ~2 minutes.

**⏱ Estimated time: 2 hours (Day 3 AM)**

---

### A5. Fidelity Verification

**▪ Task A5.1 — NLI Entailment Checker**

Load `cross-encoder/nli-deberta-v3-base` locally. For each of the 250 explanations, compute entailment score: is the explanation entailed by (original clause + retrieved evidence)? Runs locally on CPU, no API cost. Runtime: ~5 minutes.

**▪ Task A5.2 — LLM-as-Judge**

For each of the 250 explanations, call GPT-4o-mini with a structured rubric scoring fidelity, completeness, no-hallucination, no-distortion, and appropriate-caution. Flag error types. 250 calls × ~$0.0025 = **$0.60**. Runtime: ~8 minutes.

**▪ Task A5.3 — Aggregate Fidelity Score**

Combine NLI + LLM-judge into fidelity_score (0–1). Apply pass/fail threshold. Count error types before and after verification. Save to `evaluation/results/verification_metrics.csv`. This produces **Table RQ5-T1** data.

**⏱ Estimated time: 3 hours (Day 3 AM continued)**

---

## 4. Track B — Backend + Evaluation

This track covers metric computation, statistical analysis, figure generation, table formatting, the FastAPI backend, and the thesis document assembly. It consumes Track A's raw outputs.

### B1. Full Metric Computation

**▪ Task B1.1 — Generation Quality Metrics**

For each of the 250 explanations, compute: faithfulness (RAGAS), answer_relevance (RAGAS), completeness, evidence_support_rate, hallucination_rate, semantic_similarity, legal_fidelity_score, and readability metrics (Flesch RE, FK Grade, avg sentence length, jargon density).

**▪ Task B1.2 — Correlation and Regression Analysis (RQ2)**

Compute Pearson and Spearman correlations between retrieval metrics and downstream metrics. Run OLS regression. Save to `evaluation/results/regression_metrics.csv`. This produces **Table RQ2-T2** data.

**▪ Task B1.3 — Composite Quality Index (RQ7)**

Normalise each metric to 0–1 scale. Compute weighted average per system variant. Run ablation analysis: re-compute with each module disabled. Save to `evaluation/results/composite_index.csv`. This produces **Tables RQ7-T1 and RQ7-T2**.

**⏱ Estimated time: 3 hours (Day 3 PM)**

---

### B2. Publication-Ready Figures

**▪ Task B2.1 — Generate All 14 Figures**

Build `notebooks/generate_figures.py`. Time budget: ~30 minutes per figure = 7 hours total.

| # | Figure ID | Type | Data Source | Library |
|---|-----------|------|-------------|---------|
| 1 | RQ1-F1 | Radar chart | 5 models × 6 metrics | matplotlib polar |
| 2 | RQ1-F2 | Heatmap | 10 clause types × 4 models | seaborn.heatmap |
| 3 | RQ2-F1 | Scatter + regression | nDCG@5 vs fidelity | matplotlib scatter |
| 4 | RQ2-F2 | Bubble plot | 5 retrievers × 3 dims | matplotlib scatter |
| 5 | RQ3-F1 | Pareto frontier | readability vs fidelity | matplotlib scatter |
| 6 | RQ3-F2 | Dumbbell plot | grade level before/after | matplotlib hlines |
| 7 | RQ4-F1 | Confusion matrix | 8×8 risk categories | seaborn.heatmap |
| 8 | RQ4-F2 | Alluvial / Sankey | clause → risk → action | plotly Sankey |
| 9 | RQ5-F1 | Stacked bar | errors before/after | matplotlib bar |
| 10 | RQ5-F2 | Agreement heatmap | verifier vs expert | seaborn.heatmap |
| 11 | RQ6-F1 | Grouped bar | 4 groups × 5 outcomes | matplotlib bar |
| 12 | RQ6-F2 | Interaction heatmap | 7 components × 5 dims | seaborn.heatmap |
| 13 | RQ7-F1 | Radar chart | 5 systems × 7 dims | matplotlib polar |
| 14 | RQ7-F2 | Quadrant bubble | usefulness vs trust | matplotlib scatter |

**⏱ Estimated time: 7 hours (Day 4)**

---

### B3. Publication-Ready Tables

**▪ Task B3.1 — Generate All 14 Tables**

Format each table as LaTeX (journal), Markdown (review), and CSV (archive). Cross-check that real numbers tell a coherent story.

**⏱ Estimated time: 3 hours (Day 5 AM)**

---

### B4. FastAPI Backend

**▪ Task B4.1 — API Endpoints**

- `POST /api/v1/simplify` — full pipeline: clause → retrieval → generation → verification → response
- `POST /api/v1/upload` — document upload → clause extraction → return clause list
- `POST /api/v1/followup` — answer follow-up question about a clause
- `GET /api/v1/clause/{id}` — retrieve clause details and all generated explanations
- `POST /api/v1/study/log` — log user interaction events during study

**▪ Task B4.2 — Thesis Document Rebuild**

Re-run the thesis docx generator with real experimental values. Swap placeholder images with new figures. Update narrative text. Output: `Thesis_Proposal_REAL.docx`.

**⏱ Estimated time: 5 hours (Day 5 PM)**

---

## 5. Track C — Frontend + User Study

This track covers the interactive React UI and the human-centred evaluation protocol.

### C1. Interactive UI

**▪ Task C1.1 — Project Setup**

```bash
npx create-next-app@latest frontend --typescript --tailwind --app
cd frontend && npx shadcn@latest init && npx shadcn@latest add card badge tabs textarea button
```

**▪ Task C1.2 — Core Panels (30 min each)**

1. **ClausePanel** — displays original clause with highlighted legal terms
2. **ExplanationPanel** — shows plain-English explanation, confidence badge, "seek legal advice" flag
3. **RiskPanel** — colored severity badges (red=critical, orange=high, yellow=medium, green=low)
4. **EvidencePanel** — collapsible accordion of evidence items with sources
5. **ComparisonView** — side-by-side toggle showing original vs simplified
6. **FollowUpPanel** — text input → API call → answer display
7. **StudyControls** — group selector (A/B/C/D) controlling panel visibility

**▪ Task C1.3 — Study Condition Visibility**

| Component | Group A | Group B | Group C | Group D |
|-----------|---------|---------|---------|---------|
| Clause text | ✓ | ✓ | ✓ | ✓ |
| Explanation | ✗ | ✓ | ✓ | ✓ |
| Risk flags | ✗ | ✗ | ✓ | ✓ |
| Evidence panel | ✗ | ✗ | ✗ | ✓ |
| Clause comparison | ✗ | ✗ | ✓ | ✓ |
| Follow-up Q&A | ✗ | ✗ | ✓ | ✓ |

**⏱ Estimated time: 4 hours (Day 6 AM)**

---

### C2. User Study Protocol

**▪ Task C2.1 — Study Design Document**

Write `user_study/protocol.md` covering: between-subjects design (4 groups × 40 participants), participant criteria, recruitment plan, 5 clauses per participant, 12-minute time limit, comprehension questions, post-task questionnaire, SUS, interaction logging, data analysis plan, and sample size justification.

**▪ Task C2.2 — Study Materials**

Create consent form, comprehension questions for 5 representative clauses, Likert scale questionnaires, and SUS form.

**▪ Task C2.3 — Interaction Logger**

Build a silent React component that records clicks, scroll positions, panel open/close, dwell time, follow-up questions, and timestamps. Sends batched events to `/api/v1/study/log`.

**⏱ Estimated time: 4 hours (Day 6 PM)**

---

### C3. Integration + Demo

**▪ Task C3.1 — End-to-End Test**

Upload a real consumer contract (e.g., Spotify ToS). Verify full flow across all 4 study conditions. Fix broken pipes.

**▪ Task C3.2 — Demo Recording**

Record a 3-minute screencast demonstrating the complete user journey.

**▪ Task C3.3 — Documentation**

Update README.md, CLAUDE.md, write RESULTS_SUMMARY.md, final thesis document rebuild.

**⏱ Estimated time: 8 hours (Day 7)**

---

## 6. 7-Day Sprint Schedule

| Day | Track | Tasks | What You Build | Exit Deliverable |
|-----|-------|-------|---------------|-----------------|
| **Mon** | A | A1.1–A1.5 | CUAD extraction, consumer contracts, benchmark, evidence corpus, risk ontology | 600 clauses, 70 evidence, 50 benchmark |
| **Tue AM** | A | A2.1–A2.3 | Vector index, 5 retrieval configs, retrieval evaluation | retrieval_metrics.csv |
| **Tue PM** | A | A3.1–A3.2 | 5 generation variants, 250 explanations, readability metrics | explanations.jsonl |
| **Wed AM** | A | A4.1, A5.1–5.3 | Risk classifier, NLI verifier, LLM-judge, fidelity scores | risk_metrics.csv, verification_metrics.csv |
| **Wed PM** | B | B1.1–B1.3 | All generation metrics, correlation analysis, composite index, ablation | all_metrics.json |
| **Thu** | B | B2.1 | All 14 publication-ready figures (PNG + PDF) | 14 figures in evaluation/figures/ |
| **Fri AM** | B | B3.1 | All 14 tables (LaTeX + Markdown + CSV) | 14 tables in evaluation/tables/ |
| **Fri PM** | B | B4.1–B4.2 | FastAPI endpoints, thesis document with real data | API running, Thesis_REAL.docx |
| **Sat AM** | C | C1.1–C1.3 | React UI with all 7 panels, 4 study conditions | Working frontend |
| **Sat PM** | C | C2.1–C2.3 | Study protocol, consent form, comprehension Qs, logger | user_study/ complete |
| **Sun** | C | C3.1–C3.3 | E2E test, demo video, docs, final packaging | Demo-ready system |

---

## 7. Cost Estimate + Risk Mitigation

### 7.1 API Cost

| Operation | Calls | Model | Est. Cost | Runtime |
|-----------|-------|-------|-----------|---------|
| Generation (5 × 50) | 200 | gpt-4o-mini | $0.50 | ~7 min |
| Risk classification | 50 | gpt-4o-mini | $0.15 | ~2 min |
| LLM-judge verification | 250 | gpt-4o-mini | $0.60 | ~8 min |
| Ablation re-runs | 200 | gpt-4o-mini | $0.50 | ~7 min |
| Testing + follow-up | 20 | gpt-4o-mini | $0.05 | ~1 min |
| **TOTAL** | **~720** | | **~$1.80** | **~25 min** |

### 7.2 Emergency Shortcuts

- **Day 1 long?** Cut consumer contracts to 5 documents. 50 CUAD + 30 consumer = enough.
- **Day 2 retrieval slow?** Drop BM25-only and dense-only. Keep hybrid, hybrid+reranker, hybrid+reranker+filter.
- **Day 3 verifier complex?** Skip NLI model. Use LLM-judge only.
- **Day 4 figures slow?** Generate 10 core figures, defer 4 "deeper insight" figures.
- **Day 6 UI too ambitious?** Build Streamlit app instead of React. 2 hours vs 4.

---

## 8. Final Repository Structure

```
clausewise/
├── CLAUDE.md
├── README.md
├── pyproject.toml
├── .env
├── data/
│   ├── raw/cuad/                    # CUAD download
│   ├── raw/consumer/                # Consumer contract PDFs
│   ├── processed/
│   │   ├── cuad_clauses.jsonl       # ~500 clauses
│   │   └── consumer_clauses.jsonl   # ~100 clauses
│   ├── evidence_corpus/
│   │   └── evidence.jsonl           # ~70 items
│   ├── benchmark/
│   │   └── benchmark.jsonl          # 50 annotated clauses
│   ├── ontology/
│   │   └── risk_ontology.yaml       # 8 risk categories
│   └── indexes/
│       ├── chroma_db/               # Dense vector index
│       └── bm25_index.pkl           # BM25 index
├── src/
│   ├── ingestion/                   # Track A — A1
│   ├── retrieval/                   # Track A — A2
│   ├── generation/                  # Track A — A3
│   ├── risk/                        # Track A — A4
│   ├── verification/                # Track A — A5
│   ├── evaluation/                  # Track B — B1
│   └── api/                         # Track B — B4
├── frontend/                        # Track C — C1
├── notebooks/
│   ├── generate_figures.py          # Track B — B2
│   └── generate_tables.py           # Track B — B3
├── evaluation/
│   ├── configs/full_eval.yaml
│   ├── results/                     # All metric CSVs + JSONs
│   ├── figures/                     # 14 PNG + PDF files
│   └── tables/                      # 14 LaTeX + MD + CSV files
├── user_study/                      # Track C — C2
├── thesis/
│   └── Thesis_Proposal_REAL.docx
└── tests/
```
