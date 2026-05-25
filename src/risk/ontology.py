"""Risk Ontology Loader (§2.3 / §3.5).
==============================
Loads the risk ontology from a YAML file and provides
formatted output for LLM prompts.

The ontology defines 8 consumer risk categories with
definitions, severity defaults, detection signals, and
recommended actions.

Supports two YAML formats:
  - Standard: version + risk_categories (from SRS §2.3)
  - Compact:  categories (without version/ids)

Usage::

    from src.risk.ontology import load_ontology

    ontology = load_ontology()
    prompt_text = format_ontology(ontology)
    category = ontology.risk_categories.get("automatic_renewal")
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

from src.config import settings
from src.models import DetectionSignals, RiskCategory, RiskOntology

# ── Auto-generated ID prefix for compact format ────────────────

_KEY_TO_ID = {
    "automatic_renewal": "RISK_AUTO_RENEW",
    "broad_liability": "RISK_BROAD_LIABILITY",
    "vague_cancellation": "RISK_VAGUE_CANCEL",
    "one_sided_indemnity": "RISK_ONE_SIDED_INDEMNITY",
    "hidden_penalties": "RISK_HIDDEN_PENALTY",
    "excessive_data_sharing": "RISK_DATA_SHARING",
    "unclear_dispute_resolution": "RISK_DISPUTE",
    "missing_refund_terms": "RISK_NO_REFUND",
}


def load_ontology(path: Optional[Path] = None) -> RiskOntology:
    """Load and validate the risk ontology YAML file.

    Args:
        path: Path to the YAML file. Defaults to
              ``settings.risk_ontology_path``.

    Returns:
        A validated ``RiskOntology`` instance.
    """
    path = path or settings.risk_ontology_path

    with path.open("r", encoding="utf-8") as f:
        raw: dict = yaml.safe_load(f)

    # Support both formats: risk_categories (SRS) or categories (compact)
    raw_categories = raw.get("risk_categories") or raw.get("categories") or {}

    categories: dict[str, RiskCategory] = {}
    for key, cat in raw_categories.items():
        signals = None
        if "detection_signals" in cat and cat["detection_signals"]:
            ds = cat["detection_signals"]
            signals = DetectionSignals(
                keywords=ds.get("keywords", []),
                patterns=ds.get("patterns", []),
            )

        # Auto-generate ID if missing
        cat_id = cat.get("id") or _KEY_TO_ID.get(key, f"RISK_{key.upper()}")

        categories[key] = RiskCategory(
            id=cat_id,
            definition=cat.get("definition"),
            severity_default=cat.get("severity_default", "medium"),
            consumer_impact=cat.get("consumer_impact"),
            recommended_actions=cat.get("recommended_actions", []),
            detection_signals=signals,
            example_clauses=cat.get("example_clauses", []),
        )

    ontology = RiskOntology(
        version=raw.get("version", "1.0"),
        risk_categories=categories,
    )

    return ontology


def format_ontology(ontology: RiskOntology) -> str:
    """Render the ontology as a prompt-friendly string.

    Each category is formatted as::

        - {name} ({id} | {severity}): {definition[:1 sentence]}
          Signals: {keywords}
    """
    lines: list[str] = []
    for key, cat in ontology.risk_categories.items():
        # First sentence of definition
        definition = cat.definition or ""
        first_sentence = definition.split(".")[0].strip() + "." if definition else ""

        line = f"  - {key} ({cat.id} | {cat.severity_default}): {first_sentence}"

        if cat.detection_signals and cat.detection_signals.keywords:
            kws = ", ".join(cat.detection_signals.keywords)
            line += f"\n    Signals: {kws}"

        lines.append(line)

    return "\n".join(lines)


# ── Cached singleton (loaded once at import time) ──────────────
_ontology: Optional[RiskOntology] = None


def get_ontology() -> RiskOntology:
    """Return the cached ontology singleton.

    Loads on first call, cached thereafter so the RiskClassifier
    doesn't re-read the YAML file on every request.
    """
    global _ontology
    if _ontology is None:
        _ontology = load_ontology()
    return _ontology


def get_risk_category(key: str) -> Optional[RiskCategory]:
    """Look up a risk category by its dict key (e.g. ``"automatic_renewal"``)."""
    return get_ontology().risk_categories.get(key)


def get_risk_by_id(risk_id: str) -> Optional[RiskCategory]:
    """Look up a risk category by its ID (e.g. ``"RISK_AUTO_RENEW"``)."""
    for cat in get_ontology().risk_categories.values():
        if cat.id == risk_id:
            return cat
    return None
