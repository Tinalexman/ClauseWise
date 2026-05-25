"""
Generate all 14 publication-ready tables from evaluation results.

Run: python notebooks/generate_tables.py
Output: evaluation/tables/ — each table as .tex, .md, and .csv

Table index:
  RQ1-T1  Generation metrics summary (5 variants × 8 metrics)
  RQ1-T2  Per-clause-type breakdown (10 types × 4 models)
  RQ2-T1  Retrieval metrics (5 configs × k={1,3,5,10})
  RQ2-T2  Correlation / OLS regression (retrieval → generation)
  RQ3-T1  Readability metrics (5 variants)
  RQ3-T2  Jargon density + sentence length
  RQ4-T1  Risk classification P/R/F1 per category
  RQ4-T2  Severity agreement matrix
  RQ5-T1  Fidelity scores before/after verification
  RQ5-T2  Error type counts (5 variants)
  RQ6-T1  User study comprehension outcomes (4 groups)
  RQ6-T2  SUS scores + trust ratings
  RQ7-T1  Composite quality index (5 systems)
  RQ7-T2  Ablation analysis (module contribution)
"""

from pathlib import Path

import pandas as pd  # noqa: F401 — used in all table generator functions

RESULTS_DIR = Path("evaluation/results")
TABLES_DIR = Path("evaluation/tables")
TABLES_DIR.mkdir(parents=True, exist_ok=True)


def save(df: pd.DataFrame, name: str, caption: str = "", label: str = "") -> None:
    df.to_csv(TABLES_DIR / f"{name}.csv", index=False)
    df.to_markdown(TABLES_DIR / f"{name}.md", index=False)
    latex = df.to_latex(
        index=False,
        caption=caption or name,
        label=label or f"tab:{name.lower()}",
        escape=False,
    )
    (TABLES_DIR / f"{name}.tex").write_text(latex)


# ------------------------------------------------------------------
# Table generators — one function per table
# ------------------------------------------------------------------

def rq1_t1_generation_metrics() -> None:
    raise NotImplementedError


def rq1_t2_clause_type_breakdown() -> None:
    raise NotImplementedError


def rq2_t1_retrieval_metrics() -> None:
    raise NotImplementedError


def rq2_t2_correlation_regression() -> None:
    raise NotImplementedError


def rq3_t1_readability() -> None:
    raise NotImplementedError


def rq3_t2_jargon_sentence() -> None:
    raise NotImplementedError


def rq4_t1_risk_prf() -> None:
    raise NotImplementedError


def rq4_t2_severity_agreement() -> None:
    raise NotImplementedError


def rq5_t1_fidelity_scores() -> None:
    raise NotImplementedError


def rq5_t2_error_types() -> None:
    raise NotImplementedError


def rq6_t1_comprehension_outcomes() -> None:
    raise NotImplementedError


def rq6_t2_sus_trust() -> None:
    raise NotImplementedError


def rq7_t1_composite_index() -> None:
    raise NotImplementedError


def rq7_t2_ablation() -> None:
    raise NotImplementedError


# ------------------------------------------------------------------

ALL_TABLES = [
    rq1_t1_generation_metrics, rq1_t2_clause_type_breakdown,
    rq2_t1_retrieval_metrics, rq2_t2_correlation_regression,
    rq3_t1_readability, rq3_t2_jargon_sentence,
    rq4_t1_risk_prf, rq4_t2_severity_agreement,
    rq5_t1_fidelity_scores, rq5_t2_error_types,
    rq6_t1_comprehension_outcomes, rq6_t2_sus_trust,
    rq7_t1_composite_index, rq7_t2_ablation,
]

if __name__ == "__main__":
    for fn in ALL_TABLES:
        print(f"Generating {fn.__name__}...")
        fn()
    print(f"Done. {len(ALL_TABLES)} tables saved to {TABLES_DIR}/")
