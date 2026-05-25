"""
Generate all 14 publication-ready figures from evaluation results.

Run: python notebooks/generate_figures.py
Output: evaluation/figures/ (PNG + PDF, 300 dpi)

Figure index:
  RQ1-F1  Radar chart       — 5 models × 6 metrics
  RQ1-F2  Heatmap           — 10 clause types × 4 models
  RQ2-F1  Scatter+regression— nDCG@5 vs fidelity
  RQ2-F2  Bubble plot       — 5 retrievers × 3 dims
  RQ3-F1  Pareto frontier   — readability vs fidelity
  RQ3-F2  Dumbbell plot     — FK grade before/after simplification
  RQ4-F1  Confusion matrix  — 8×8 risk categories
  RQ4-F2  Sankey diagram    — clause → risk → action
  RQ5-F1  Stacked bar       — error types before/after verification
  RQ5-F2  Agreement heatmap — verifier vs expert
  RQ6-F1  Grouped bar       — 4 study groups × 5 comprehension outcomes
  RQ6-F2  Interaction heatmap — 7 UI components × 5 dimensions
  RQ7-F1  Radar chart       — 5 systems × 7 composite dims
  RQ7-F2  Quadrant bubble   — usefulness vs trust
"""

from pathlib import Path

import matplotlib.pyplot as plt
import seaborn as sns  # noqa: F401 — used in heatmap/confusion functions

RESULTS_DIR = Path("evaluation/results")
FIGURES_DIR = Path("evaluation/figures")
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

DPI = 300
FORMATS = ["png", "pdf"]


def save(fig: plt.Figure, name: str) -> None:
    for fmt in FORMATS:
        fig.savefig(FIGURES_DIR / f"{name}.{fmt}", dpi=DPI, bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------------------------------
# RQ1 — Generation quality across 5 variants
# ------------------------------------------------------------------

def rq1_f1_radar() -> None:
    raise NotImplementedError


def rq1_f2_heatmap() -> None:
    raise NotImplementedError


# ------------------------------------------------------------------
# RQ2 — Retrieval quality vs downstream quality
# ------------------------------------------------------------------

def rq2_f1_scatter() -> None:
    raise NotImplementedError


def rq2_f2_bubble() -> None:
    raise NotImplementedError


# ------------------------------------------------------------------
# RQ3 — Readability
# ------------------------------------------------------------------

def rq3_f1_pareto() -> None:
    raise NotImplementedError


def rq3_f2_dumbbell() -> None:
    raise NotImplementedError


# ------------------------------------------------------------------
# RQ4 — Risk classification
# ------------------------------------------------------------------

def rq4_f1_confusion() -> None:
    raise NotImplementedError


def rq4_f2_sankey() -> None:
    raise NotImplementedError


# ------------------------------------------------------------------
# RQ5 — Fidelity verification
# ------------------------------------------------------------------

def rq5_f1_stacked_bar() -> None:
    raise NotImplementedError


def rq5_f2_agreement_heatmap() -> None:
    raise NotImplementedError


# ------------------------------------------------------------------
# RQ6 — User study
# ------------------------------------------------------------------

def rq6_f1_grouped_bar() -> None:
    raise NotImplementedError


def rq6_f2_interaction_heatmap() -> None:
    raise NotImplementedError


# ------------------------------------------------------------------
# RQ7 — Composite quality index
# ------------------------------------------------------------------

def rq7_f1_radar() -> None:
    raise NotImplementedError


def rq7_f2_quadrant_bubble() -> None:
    raise NotImplementedError


# ------------------------------------------------------------------

ALL_FIGURES = [
    rq1_f1_radar, rq1_f2_heatmap,
    rq2_f1_scatter, rq2_f2_bubble,
    rq3_f1_pareto, rq3_f2_dumbbell,
    rq4_f1_confusion, rq4_f2_sankey,
    rq5_f1_stacked_bar, rq5_f2_agreement_heatmap,
    rq6_f1_grouped_bar, rq6_f2_interaction_heatmap,
    rq7_f1_radar, rq7_f2_quadrant_bubble,
]

if __name__ == "__main__":
    for fn in ALL_FIGURES:
        print(f"Generating {fn.__name__}...")
        fn()
    print(f"Done. {len(ALL_FIGURES)} figures saved to {FIGURES_DIR}/")
