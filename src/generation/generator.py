"""Explanation Generator (§3.3): produces structured plain-English
explanations of legal clauses using one of five generation variants
for controlled experimentation.

Input:  ClauseUnit + List[EvidenceItem] + List[RiskDetail]
Output: ExplanationOutput (full §2.4 schema)

Five variants (§5.1):

    extractive    —  no LLM, picks verbatim sentences from the clause
    vanilla_llm   —  basic LLM, no evidence, no risks
    prompted_llm  —  structured output prompt, no evidence, no risks
    standard_rag  —  structured prompt + evidence, no risks
    proposed      —  structured prompt + evidence + risks (full pipeline)
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import textstat
from openai import OpenAI

from src.config import settings
from src.models import (
    ClauseUnit,
    Confidence,
    EvidenceItem,
    EvidenceUsage,
    ExplanationOutput,
    GenerationMetadata,
    GenerationVariant,
    ReadabilityMetrics,
    RiskDetail,
    SeekLegalAdvice,
)

logger = logging.getLogger(__name__)

# ── System prompts for each variant ─────────────────────────────

_PROMPTS: Dict[str, Tuple[str, str]] = {
    "basic": (
        "You are a legal explainer. Your task is to explain legal "
        "clauses in plain English so that an average consumer can "
        "understand them.",
        "Explain the following clause in plain English (2-3 sentences, "
        "simple language suitable for someone with no legal background):\n\n"
        "Clause: {clause_text}",
    ),
    "structured": (
        "You are a legal explainer. Explain the clause in plain English "
        "and return a structured JSON object with the following keys:\n"
        "- plain_english: 2-3 sentence explanation (target reading grade ≤ 8)\n"
        "- user_implications: what this means for the consumer\n"
        "- check_before_signing: list of specific action items\n"
        "- confidence: 'high', 'medium', or 'low'\n"
        "- seek_legal_advice: {{'recommended': bool, 'reason': str or null}}",
        "Clause: {clause_text}",
    ),
    "full": (
        "You are a legal explainer. Explain the clause in plain English "
        "and return a structured JSON object with the following keys:\n"
        "- plain_english: 2-3 sentence explanation (target reading grade ≤ 8)\n"
        "- user_implications: what this means for the consumer\n"
        "- check_before_signing: list of specific action items\n"
        "- confidence: 'high', 'medium', or 'low'\n"
        "- seek_legal_advice: {{'recommended': bool, 'reason': str or null}}",
        "Clause: {clause_text}\n\n"
        "Relevant legal context:\n{evidence_text}\n\n"
        "Identified risks:\n{risks_text}",
    ),
}


class ExplanationGenerator:
    """Generates plain-English clause explanations.

    Usage::

        gen = ExplanationGenerator()
        explanation = gen.generate(clause, evidence, risks, variant="proposed")
    """

    def __init__(self) -> None:
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.llm_model

    # ──────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────

    def generate(
        self,
        clause: ClauseUnit,
        evidence: Optional[List[EvidenceItem]] = None,
        risks: Optional[List[RiskDetail]] = None,
        variant: GenerationVariant = GenerationVariant.proposed,
        retrieval_config: Optional[str] = None,
    ) -> ExplanationOutput:
        """Generate an explanation using the specified *variant*.

        Args:
            clause: The clause to explain.
            evidence: Retrieved evidence items.
            risks: Risks identified by the RiskClassifier.
            variant: Which generation strategy to use.
            retrieval_config: The retrieval config used (for metadata).

        Returns:
            A fully populated ``ExplanationOutput``.
        """
        evidence = evidence or []
        risks = risks or []

        if variant == GenerationVariant.extractive:
            return self._extractive_summarize(clause, retrieval_config or "")

        return self._llm_generate(
            clause, evidence, risks, variant.value, retrieval_config or ""
        )

    # ──────────────────────────────────────────────────────────────
    # Extractive variant (no LLM)
    # ──────────────────────────────────────────────────────────────

    def _extractive_summarize(
        self, clause: ClauseUnit, retrieval_config: str
    ) -> ExplanationOutput:
        """Pick key sentences from the clause verbatim.

        Uses sentence-length heuristics to extract the most informative
        sentences — those containing legal keywords or longer than
        a simple preamble.
        """
        # Split into sentences and score each
        sentences = self._split_sentences(clause.text)
        scored = [
            (sent, self._score_sentence(sent))
            for sent in sentences
            if len(sent.split()) > 5
        ]
        scored.sort(key=lambda x: x[1], reverse=True)

        # Pick top 2-3 sentences
        top_n = min(3, len(scored))
        selected = [sent for sent, _ in scored[:top_n]]
        plain_english = " ".join(selected) if selected else clause.text[:500]

        # Compute readability locally
        readability = self._compute_readability(plain_english)

        return ExplanationOutput(
            clause_id=clause.clause_id,
            generation_variant=GenerationVariant.extractive,
            retrieval_config=retrieval_config or "none",
            plain_english=plain_english,
            user_implications="",
            risks=[],
            check_before_signing=[],
            evidence_used=[],
            confidence=Confidence.medium,
            seek_legal_advice=SeekLegalAdvice(recommended=False, reason=None),
            verification=None,
            readability=readability,
            metadata=GenerationMetadata(
                model="extractive",
                temperature=0.0,
                timestamp=datetime.now(timezone.utc),
                latency_ms=0,
                token_count_input=0,
                token_count_output=0,
            ),
        )

    # ──────────────────────────────────────────────────────────────
    # LLM generation variants
    # ──────────────────────────────────────────────────────────────

    def _llm_generate(
        self,
        clause: ClauseUnit,
        evidence: List[EvidenceItem],
        risks: List[RiskDetail],
        variant: str,
        retrieval_config: str,
    ) -> ExplanationOutput:
        """Call the LLM with the appropriate prompt template."""
        # Build prompt content based on variant
        prompt_variant = "full" if variant == "proposed" else variant
        messages = self._build_messages(clause, evidence, risks, prompt_variant)

        # Count input tokens approximately
        input_text = " ".join(m["content"] for m in messages)
        token_count_input = len(input_text.split())

        start = time.monotonic()
        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=settings.gen_temperature,
        )
        latency_ms = int((time.monotonic() - start) * 1000)

        content = response.choices[0].message.content or "{}"
        output_tokens = response.usage.total_tokens if response.usage else 0
        token_count_output = (
            output_tokens - token_count_input
            if output_tokens > token_count_input
            else len(content.split())
        )

        # Parse the LLM output
        llm_data = self._parse_llm_response(content)

        # Compute readability locally (more reliable than trusting the LLM)
        readability = self._compute_readability(llm_data.get("plain_english", ""))

        # Build evidence_used list
        evidence_used = [
            EvidenceUsage(
                evidence_id=e.evidence_id,
                relevance_score=1.0,  # Reranker score isn't available here;
                # engine.py should pass it through
            )
            for e in evidence
        ]

        return ExplanationOutput(
            clause_id=clause.clause_id,
            generation_variant=variant,  # type: ignore
            retrieval_config=retrieval_config or "none",
            plain_english=llm_data.get("plain_english", ""),
            user_implications=llm_data.get("user_implications", ""),
            risks=risks,
            check_before_signing=llm_data.get("check_before_signing", []),
            evidence_used=evidence_used,
            confidence=llm_data.get("confidence", "medium"),
            seek_legal_advice=SeekLegalAdvice(
                recommended=llm_data.get("seek_legal_advice", {}).get(
                    "recommended", False
                ),
                reason=llm_data.get("seek_legal_advice", {}).get("reason"),
            ),
            verification=None,
            readability=readability,
            metadata=GenerationMetadata(
                model=self._model,
                temperature=settings.gen_temperature,
                timestamp=datetime.now(timezone.utc),
                latency_ms=latency_ms,
                token_count_input=token_count_input,
                token_count_output=token_count_output,
            ),
        )

    # ──────────────────────────────────────────────────────────────
    # Prompt construction
    # ──────────────────────────────────────────────────────────────

    def _build_messages(
        self,
        clause: ClauseUnit,
        evidence: List[EvidenceItem],
        risks: List[RiskDetail],
        prompt_variant: str,
    ) -> List[Dict[str, str]]:
        """Build system + user messages for the given variant."""
        variant = prompt_variant if prompt_variant in _PROMPTS else "structured"
        system_prompt, user_template = _PROMPTS[variant]

        # Format evidence text
        evidence_text = (
            "\n".join(f"- [{e.evidence_id}] {e.text[:500]}" for e in evidence[:5])
            if evidence
            else "No additional context."
        )

        # Format risks text
        risks_text = (
            "\n".join(
                f"- {r.risk_category} ({r.severity.value}): {r.explanation}"
                for r in risks
            )
            if risks
            else "No risks identified."
        )

        user_prompt = user_template.format(
            clause_text=clause.text,
            evidence_text=evidence_text,
            risks_text=risks_text,
        )

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    # ──────────────────────────────────────────────────────────────
    # Response parsing
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_llm_response(content: str) -> Dict[str, Any]:
        """Parse and validate the LLM's JSON response."""
        try:
            data = json.loads(content)
            if not isinstance(data, dict):
                return {}
            return data
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM response as JSON")
            return {}

    # ──────────────────────────────────────────────────────────────
    # Readability computation
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def _compute_readability(text: str) -> ReadabilityMetrics:
        """Compute readability scores using textstat."""
        if not text or len(text.split()) < 3:
            return ReadabilityMetrics(
                flesch_reading_ease=0.0,
                flesch_kincaid_grade=0.0,
                avg_sentence_length=0.0,
                jargon_density=0.0,
            )

        return ReadabilityMetrics(
            flesch_reading_ease=textstat.flesch_reading_ease(text),
            flesch_kincaid_grade=textstat.flesch_kincaid_grade(text),
            avg_sentence_length=textstat.avg_sentence_length(text),
            jargon_density=0.0,  # Computed by evaluation pipeline (§5.2)
        )

    # ──────────────────────────────────────────────────────────────
    # Sentence helpers (for extractive variant)
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def _split_sentences(text: str) -> List[str]:
        """Rough sentence splitting for the extractive variant."""
        import re

        return [
            s.strip()
            for s in re.split(r"(?<=[.!?])\s+(?=[A-Z\"'(])", text)
            if s.strip()
        ]

    @staticmethod
    def _score_sentence(sentence: str) -> int:
        """Score a sentence by how informative it is.

        Higher scores for longer sentences and those containing
        legal keywords.
        """
        legal_keywords = {
            "shall",
            "must",
            "will",
            "agree",
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
        }
        words = sentence.lower().split()
        score = len(words) * 0.5  # length bonus
        score += sum(5 for w in words if w.rstrip(".,;:!?") in legal_keywords)
        return int(score)
