"""
GenerationPipeline — 5 variants from extractive to full ClauseWise RAG.

Variant 1: Extractive (TextRank via sumy, no LLM)
Variant 2: Vanilla LLM (GPT-4o-mini, clause text only)
Variant 3: Prompted LLM (structured prompt + JSON output, no evidence)
Variant 4: Standard RAG (Variant 3 + hybrid retrieval evidence)
Variant 5: ClauseWise full (Variant 3 + Config-5 evidence + risk ontology context)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional

from openai import OpenAI

from src.config import settings
from src.models import EvidenceItem
from src.generation.prompts import (
    build_rag_prompt,
    build_structured_prompt,
    build_vanilla_prompt,
)

logger = logging.getLogger(__name__)


class GenerationVariant(IntEnum):
    EXTRACTIVE = 1
    VANILLA_LLM = 2
    PROMPTED_LLM = 3
    STANDARD_RAG = 4
    CLAUSEWISE = 5


@dataclass
class GeneratedExplanation:
    clause_id: str
    variant: GenerationVariant
    plain_english: str
    risk_flags: list[str]
    severity: str  # critical | high | medium | low
    recommended_action: str
    confidence: float
    evidence_used: list[EvidenceItem] = field(default_factory=list)
    seek_legal_advice: bool = False
    raw_response: str = ""


class GenerationPipeline:
    def __init__(
        self,
        variant: GenerationVariant = GenerationVariant.CLAUSEWISE,
        openai_api_key: str = "",
        model: str = "gpt-4o-mini",
    ) -> None:
        self.variant = variant
        self.model = model
        self._client: Optional[OpenAI] = None
        self._openai_api_key = openai_api_key or settings.openai_api_key
        self._sumy_summarizer = None
        self._sumy_parser = None

    def load(self) -> None:
        """Initialise OpenAI client (and sumy resources for Variant 1)."""
        if self.variant != GenerationVariant.EXTRACTIVE:
            self._client = OpenAI(api_key=self._openai_api_key)
            logger.info("OpenAI client ready — model=%s", self.model)

        if self.variant == GenerationVariant.EXTRACTIVE:
            from sumy.parsers.plaintext import PlaintextParser
            from sumy.nlp.tokenizers import Tokenizer
            from sumy.summarizers.text_rank import TextRankSummarizer

            self._sumy_parser_cls = PlaintextParser
            self._sumy_tokenizer_cls = Tokenizer
            self._sumy_summarizer = TextRankSummarizer()
            logger.info("Sumy TextRank summarizer ready")

    def generate(
        self,
        clause_id: str,
        clause_text: str,
        clause_type: str,
        evidence: list[EvidenceItem] | None = None,
        risk_context: dict | None = None,
    ) -> GeneratedExplanation:
        match self.variant:
            case GenerationVariant.EXTRACTIVE:
                return self._extractive(clause_id, clause_text)
            case GenerationVariant.VANILLA_LLM:
                return self._vanilla_llm(clause_id, clause_text)
            case GenerationVariant.PROMPTED_LLM:
                return self._prompted_llm(clause_id, clause_text, clause_type)
            case GenerationVariant.STANDARD_RAG:
                return self._rag(clause_id, clause_text, clause_type, evidence or [])
            case GenerationVariant.CLAUSEWISE:
                return self._clausewise(
                    clause_id, clause_text, clause_type, evidence or [], risk_context or {}
                )
            case _:
                raise ValueError(f"Unknown variant: {self.variant}")

    # ------------------------------------------------------------------
    # Variant implementations
    # ------------------------------------------------------------------

    def _extractive(self, clause_id: str, clause_text: str) -> GeneratedExplanation:
        """TextRank summary via sumy. No LLM call."""
        from sumy.parsers.plaintext import PlaintextParser
        from sumy.nlp.tokenizers import Tokenizer
        from sumy.summarizers.text_rank import TextRankSummarizer

        parser = PlaintextParser.from_string(clause_text, Tokenizer("english"))
        summarizer = self._sumy_summarizer or TextRankSummarizer()
        sentences = summarizer(parser.document, sentences_count=3)
        summary = " ".join(str(s) for s in sentences) or clause_text[:300]

        return GeneratedExplanation(
            clause_id=clause_id,
            variant=self.variant,
            plain_english=summary,
            risk_flags=[],
            severity="medium",
            recommended_action="Review this clause carefully before signing.",
            confidence=0.5,
            seek_legal_advice=False,
            raw_response=summary,
        )

    def _vanilla_llm(self, clause_id: str, clause_text: str) -> GeneratedExplanation:
        messages = build_vanilla_prompt(clause_text)
        raw = self._call_llm(messages)
        return self._parse_llm_response(clause_id, raw, self.variant, [])

    def _prompted_llm(
        self, clause_id: str, clause_text: str, clause_type: str
    ) -> GeneratedExplanation:
        messages = build_structured_prompt(clause_text, clause_type)
        raw = self._call_llm(messages)
        return self._parse_llm_response(clause_id, raw, self.variant, [])

    def _rag(
        self,
        clause_id: str,
        clause_text: str,
        clause_type: str,
        evidence: list[EvidenceItem],
    ) -> GeneratedExplanation:
        messages = build_rag_prompt(clause_text, clause_type, evidence)
        raw = self._call_llm(messages)
        return self._parse_llm_response(clause_id, raw, self.variant, evidence)

    def _clausewise(
        self,
        clause_id: str,
        clause_text: str,
        clause_type: str,
        evidence: list[EvidenceItem],
        risk_context: dict,
    ) -> GeneratedExplanation:
        messages = build_rag_prompt(clause_text, clause_type, evidence, risk_context)
        raw = self._call_llm(messages)
        return self._parse_llm_response(clause_id, raw, self.variant, evidence)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _call_llm(self, messages: list[dict]) -> str:
        """Call GPT-4o-mini with JSON mode and return the raw content string."""
        if self._client is None:
            self._client = OpenAI(api_key=self._openai_api_key)

        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=settings.gen_temperature,
        )
        return response.choices[0].message.content or ""

    def _parse_llm_response(
        self,
        clause_id: str,
        raw: str,
        variant: GenerationVariant,
        evidence: list[EvidenceItem],
    ) -> GeneratedExplanation:
        """Parse JSON response into GeneratedExplanation. Degrades gracefully."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("JSON parse failed for clause %s — using raw text", clause_id)
            data = {}

        return GeneratedExplanation(
            clause_id=clause_id,
            variant=variant,
            plain_english=data.get("plain_english", raw[:300]),
            risk_flags=data.get("risk_flags", []),
            severity=data.get("severity", "medium"),
            recommended_action=data.get("recommended_action", ""),
            confidence=float(data.get("confidence", 0.5)),
            evidence_used=evidence,
            seek_legal_advice=bool(data.get("seek_legal_advice", False)),
            raw_response=raw,
        )
