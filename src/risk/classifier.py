"""Risk Classifier (§3.5): identifies consumer risks in legal clauses
using the LLM guided by the risk ontology.

Input:  ClauseUnit + optional EvidenceItem context
Output: List[RiskDetail] — each risk found in the clause

The ontology (§2.3) provides the LLM with definitions, severity
defaults, and detection signals for 8 risk categories. The LLM
identifies which risks are *clearly present* in the clause text,
and returns a structured JSON array at temperature=0 for
reproducibility (§1.2).
"""

from __future__ import annotations

import json
import logging
from typing import List, Optional

from openai import OpenAI

from src.config import settings
from src.models import ClauseUnit, EvidenceItem, RiskDetail
from src.risk.ontology import format_ontology, get_ontology

logger = logging.getLogger(__name__)

# ── System prompt (constant across all classifications) ─────────

_SYSTEM_PROMPT = (
    "You are a legal risk analyst. Your task is to identify consumer "
    "risks in contract clauses. Only flag risks that are clearly "
    "present in the clause text. Do not invent risks. "
    "Respond with a JSON object containing a single key 'risks' "
    "mapped to an array of risk objects."
)


class RiskClassifier:
    """Identifies consumer risks in a legal clause via LLM + ontology.

    Usage::

        classifier = RiskClassifier()
        risks = classifier.classify(clause, evidence)
    """

    def __init__(self) -> None:
        self.ontology = get_ontology()
        self._client = OpenAI(api_key=settings.openai_api_key)
        logger.info(
            "RiskClassifier ready — %d risk categories loaded",
            len(self.ontology.risk_categories),
        )

    # ──────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────

    def classify(
        self,
        clause: ClauseUnit,
        evidence: Optional[List[EvidenceItem]] = None,
    ) -> List[RiskDetail]:
        """Analyse *clause* for consumer risks.

        Args:
            clause: The clause to analyse.
            evidence: Optional supporting evidence to include for
                      additional LLM context (reserved for future use).

        Returns:
            A list of ``RiskDetail`` objects, one per risk found.
            Empty list if no risks are detected.
        """
        prompt = self._build_prompt(clause, evidence or [])

        response = self._client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=settings.eval_temperature,  # 0 for reproducibility
        )

        content = response.choices[0].message.content
        return self._parse_risks(content)

    # ──────────────────────────────────────────────────────────────
    # Prompt construction (§3.5)
    # ──────────────────────────────────────────────────────────────

    def _build_prompt(self, clause: ClauseUnit, evidence: List[EvidenceItem]) -> str:
        """Build the user message for the LLM."""
        sections: list[str] = [
            "Analyze this legal clause for consumer risks.",
            "",
            f"Clause: {clause.text}",
            f"Clause type: {clause.clause_type.value}",
            "",
            "Risk categories to check:",
            format_ontology(self.ontology),
            "",
            "For each risk found, return:",
            "- risk_id, category, severity (low/medium/high/critical),",
            "  explanation, recommended_action",
            "",
            "Return a JSON object with a single key 'risks' mapped to",
            "an array of risk objects. If no risks are found,",
            "return { 'risks': [] }.",
            "Only identify risks that are clearly present in the clause text.",
        ]

        # Evidence is included in the signature per §3.5 but not
        # explicitly used in the prompt pseudocode.  If provided,
        # add it as optional context.
        if evidence:
            sections.extend(
                [
                    "",
                    "Relevant legal context:",
                    *[f"- [{e.evidence_id}] {e.text[:500]}" for e in evidence[:3]],
                ]
            )

        return "\n".join(sections)

    # ──────────────────────────────────────────────────────────────
    # Response parsing
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_risks(content: Optional[str]) -> List[RiskDetail]:
        """Parse the LLM JSON response into validated RiskDetail objects.

        Returns an empty list on any parse failure rather than crashing,
        so the caller can gracefully degrade.
        """
        if not content:
            logger.warning("Empty LLM response — no risks returned")
            return []

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM response as JSON — %s", content[:200])
            return []

        raw_risks = data.get("risks", [])
        if not isinstance(raw_risks, list):
            logger.warning("'risks' key is not a list — %s", type(raw_risks).__name__)
            return []

        risks: List[RiskDetail] = []
        for raw in raw_risks:
            try:
                # Normalise "category" (common LLM output) to "risk_category"
                if "category" in raw and "risk_category" not in raw:
                    raw["risk_category"] = raw.pop("category")
                risks.append(RiskDetail(**raw))
            except Exception:
                logger.warning("Skipping invalid risk entry — %s", raw)

        return risks
