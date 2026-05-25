"""Fidelity Verifier (§3.4): checks that generated explanations are
faithful to the original clause and retrieved evidence.

Input:  clause text + generated explanation + evidence texts
Output: VerificationResult with score, entailment label, flags

Four checks:
    1. NLI entailment  — cross-encoder/nli-deberta-v3-base (local)
    2. Claim support   — are individual claims grounded in the clause/evidence?
    3. Completeness    — are key legal concepts from the clause addressed?
    4. LLM-as-judge    — structured rubric via GPT-4o-mini

Aggregated into a single fidelity score (threshold: 0.8 to pass).
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from openai import OpenAI
from sentence_transformers import CrossEncoder

from src.config import settings

logger = logging.getLogger(__name__)

# ── Legal concepts that every explanation should address ────────

_LEGAL_KEYWORDS: Set[str] = {
    "shall",
    "must",
    "will",
    "agree",
    "obligation",
    "right",
    "terminate",
    "termination",
    "liability",
    "indemnify",
    "renew",
    "cancel",
    "fee",
    "charge",
    "responsible",
    "waive",
    "binding",
    "arbitration",
    "consent",
    "approval",
    "notice",
    "deadline",
    "expire",
    "refund",
    "confidential",
    "privacy",
    "data",
    "governing",
    "jurisdiction",
    "venue",
}

# ── Error types for structured classification ──────────────────

ERROR_TYPES = ["hallucination", "distortion", "omission", "overstatement"]


# ── LLM-as-judge system prompt ─────────────────────────────────

_JUDGE_SYSTEM_PROMPT = (
    "You are a fidelity judge. Your task is to evaluate whether a "
    "plain-English explanation of a legal clause is faithful to the "
    "original clause and any supporting evidence provided.\n\n"
    "Score the explanation on three axes (each 0.0 - 1.0):\n"
    "- faithfulness: Does the explanation accurately reflect the clause?\n"
    "- completeness: Does it cover the key points without omitting material details?\n"
    "- hallucination: 1.0 = entirely grounded, 0.0 = fabricated content\n\n"
    "Also classify any fidelity errors present. Choose from:\n"
    '- "hallucination": explanation adds facts not in the clause or evidence\n'
    '- "distortion": explanation misrepresents what the clause says\n'
    '- "omission": explanation leaves out a material term or condition\n'
    '- "overstatement": explanation exaggerates the scope or severity\n'
    "If none apply, return an empty list.\n\n"
    "Return a JSON object with keys: faithfulness, completeness, "
    "hallucination, error_types, comment."
)


class FidelityVerifier:
    """Verifies that generated explanations are faithful to their source.

    Usage::

        verifier = FidelityVerifier()
        result = verifier.verify(clause_text, explanation_text, evidence_texts)
    """

    def __init__(self) -> None:
        logger.info("Loading NLI model (cross-encoder/nli-deberta-v3-base) …")
        start = time.monotonic()
        self._nli = CrossEncoder("cross-encoder/nli-deberta-v3-base")
        logger.info("NLI model loaded in %.2fs", time.monotonic() - start)
        self._llm = OpenAI(api_key=settings.openai_api_key)

    # ──────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────

    def verify(
        self,
        clause: str,
        explanation: str,
        evidence: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Run all four checks and return the aggregated verdict.

        Args:
            clause: The original clause text.
            explanation: The generated plain-English explanation.
            evidence: Retrieved evidence texts used during generation.

        Returns:
            A dict matching ``VerificationInfo`` (§2.4):
                fidelity_score, entailment_label, flags, passed, revision_count
        """
        evidence = evidence or []

        # ── 1. NLI entailment ────────────────────────────────────
        entailment_label = self._check_entailment(clause, explanation, evidence)

        # ── 2. Claim support ─────────────────────────────────────
        unsupported = self._find_unsupported_claims(explanation, clause, evidence)

        # ── 3. Completeness ──────────────────────────────────────
        missing = self._find_missing_concepts(clause, explanation)

        # ── 4. LLM-as-judge ──────────────────────────────────────
        judge_scores, error_types, judge_rationale = self._llm_judge(
            clause, explanation, evidence
        )

        # ── 5. Aggregate ─────────────────────────────────────────
        score = self._compute_fidelity(
            entailment_label, unsupported, missing, judge_scores
        )
        flags = self._generate_flags(unsupported, missing, error_types)
        passed = score >= 0.8

        return {
            "fidelity_score": round(score, 4),
            "entailment_label": entailment_label,
            "flags": flags,
            "error_types": error_types,
            "passed": passed,
            "revision_count": 0,  # Incremented by caller if revision loop runs
        }

    # ──────────────────────────────────────────────────────────────
    # 1. NLI entailment
    # ──────────────────────────────────────────────────────────────

    def _check_entailment(
        self, clause: str, explanation: str, evidence: List[str]
    ) -> str:
        """Check if the explanation is entailed by clause + evidence.

        Returns ``"entailment"``, ``"neutral"``, or ``"contradiction"``.
        """
        premise = clause + " " + " ".join(evidence)
        if not premise.strip():
            return "neutral"

        scores = self._nli.predict([(premise, explanation)])
        # DeBERTa-NLI outputs: [entailment, neutral, contradiction] logits
        labels = ["entailment", "neutral", "contradiction"]
        label = labels[scores[0].argmax()]
        return label

    # ──────────────────────────────────────────────────────────────
    # 2. Claim support
    # ──────────────────────────────────────────────────────────────

    def _find_unsupported_claims(
        self, explanation: str, clause: str, evidence: List[str]
    ) -> List[str]:
        """Extract claims from the explanation and find unsupported ones.

        A claim is "supported" if it has significant word overlap with
        the clause text or any evidence text.
        """
        claims = self._extract_claims(explanation)
        unsupported: List[str] = []

        clause_words = set(clause.lower().split())
        evidence_words: Set[str] = set()
        for e in evidence:
            evidence_words.update(e.lower().split())

        combined = clause_words | evidence_words

        for claim in claims:
            if not self._is_supported(claim, combined):
                unsupported.append(claim)

        return unsupported

    @staticmethod
    def _extract_claims(text: str) -> List[str]:
        """Split explanation into individual claim sentences."""
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z\"'(])", text)
        return [s.strip() for s in sentences if len(s.strip().split()) > 3]

    @staticmethod
    def _is_supported(claim: str, vocab: Set[str]) -> bool:
        """Check if a claim has at least 30% word overlap with the source."""
        claim_words = set(claim.lower().split())
        if not claim_words:
            return True
        overlap = len(claim_words & vocab)
        return overlap / len(claim_words) >= 0.30

    # ──────────────────────────────────────────────────────────────
    # 3. Completeness
    # ──────────────────────────────────────────────────────────────

    def _find_missing_concepts(self, clause: str, explanation: str) -> List[str]:
        """Find legal concepts present in the clause but missing
        from the explanation."""
        clause_concepts = self._extract_legal_concepts(clause)
        explained_concepts = self._extract_legal_concepts(explanation)

        return [c for c in clause_concepts if c not in explained_concepts]

    @staticmethod
    def _extract_legal_concepts(text: str) -> List[str]:
        """Extract legal keyword concepts from text."""
        words = text.lower().split()
        found: List[str] = []
        for word in words:
            clean = word.rstrip(".,;:!?()\"'")
            if clean in _LEGAL_KEYWORDS and clean not in found:
                found.append(clean)
        return found

    # ──────────────────────────────────────────────────────────────
    # 4. LLM-as-judge
    # ──────────────────────────────────────────────────────────────

    def _llm_judge(
        self, clause: str, explanation: str, evidence: List[str]
    ) -> Tuple[Dict[str, float], List[str], str]:
        """Call GPT-4o-mini with a structured rubric.

        Returns (score_dict, error_types, rationale).
        Score dict keys: faithfulness, completeness, hallucination.
        Defaults to 0.5 / empty / "" on parse failure.
        """
        evidence_block = (
            "\n".join(f"- {e[:500]}" for e in evidence[:5])
            if evidence
            else "No additional evidence."
        )

        user_prompt = (
            f"Clause: {clause}\n\n"
            f"Explanation: {explanation}\n\n"
            f"Evidence:\n{evidence_block}"
        )

        try:
            response = self._llm.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": _JUDGE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=settings.eval_temperature,
            )
            content = response.choices[0].message.content or "{}"
            data = json.loads(content)
            scores = {
                "faithfulness": float(data.get("faithfulness", 0.5)),
                "completeness": float(data.get("completeness", 0.5)),
                "hallucination": float(data.get("hallucination", 0.5)),
            }
            raw_errors = data.get("error_types", [])
            if isinstance(raw_errors, list):
                error_types = [
                    e for e in raw_errors if isinstance(e, str) and e in ERROR_TYPES
                ]
            else:
                error_types = []
            rationale = data.get("comment", "")
            return scores, error_types, rationale
        except Exception:
            logger.warning("LLM judge call failed — using defaults")
            return (
                {"faithfulness": 0.5, "completeness": 0.5, "hallucination": 0.5},
                [],
                "",
            )

    # ──────────────────────────────────────────────────────────────
    # 5. Aggregation
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def _compute_fidelity(
        entailment_label: str,
        unsupported: List[str],
        missing: List[str],
        judge_scores: Dict[str, float],
    ) -> float:
        """Aggregate the four checks into a single 0-1 score.

        Weights (§3.4):
            - NLI entailment:      30%
            - Claim support:       20%
            - Completeness:        20%
            - LLM judge average:   30%
        """
        # NLI score
        nli_map = {"entailment": 1.0, "neutral": 0.6, "contradiction": 0.0}
        nli_score = nli_map.get(entailment_label, 0.5)

        # Claim support score
        claim_score = 1.0 - (len(unsupported) * 0.15)
        claim_score = max(0.0, min(1.0, claim_score))

        # Completeness score
        completeness_score = 1.0 - (len(missing) * 0.15)
        completeness_score = max(0.0, min(1.0, completeness_score))

        # Judge average
        judge_avg = (
            judge_scores.get("faithfulness", 0.5)
            + judge_scores.get("completeness", 0.5)
            + judge_scores.get("hallucination", 0.5)
        ) / 3.0

        score = (
            nli_score * 0.30
            + claim_score * 0.20
            + completeness_score * 0.20
            + judge_avg * 0.30
        )

        return score

    @staticmethod
    def _generate_flags(
        unsupported: List[str],
        missing: List[str],
        error_types: Optional[List[str]] = None,
    ) -> List[str]:
        """Build human-readable flags for the verification output.

        Combines structured error types (from LLM judge) with
        descriptive flags (from claim/completeness checks).
        """
        flags: List[str] = list(error_types or [])
        for claim in unsupported[:5]:
            flags.append(f"unsupported_addition: {claim[:120]}")
        for concept in missing[:5]:
            flags.append(f"missing_condition: {concept}")
        return flags
