"""Clause Chunker (§3.1)
==========================
Consumes raw text blocks from the LegalDocumentParser and reconstructs
a semantic legal hierarchy using:

1. Font-size / bold heuristics to detect headings
2. Regex patterns for numbered, alpha, and roman clause identifiers
3. Legal delimiters (PROVIDED THAT, NOTWITHSTANDING, …) as clause boundaries
4. spaCy sentence boundary detection for within-chunk segmentation

Output chunk schema:
    {
        "hierarchy":    List[str],   # e.g. ["ARTICLE 1", "1.", "(a)"]
        "text":         str,         # full clause text (≤2000 chars)
        "page_number":  int,
    }
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

import spacy

# ── Global spaCy model (loaded once) ──────────────────────────────

try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    import subprocess
    import sys

    subprocess.check_call([sys.executable, "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")


# ── Legal delimiters that carve out independent clause units ─────

LEGAL_DELIMITERS = re.compile(
    r"\b(PROVIDED THAT|PROVIDED HOWEVER|NOTWITHSTANDING|"
    r"SUBJECT TO|EXCEPT AS|IN THE EVENT THAT|"
    r"WHEREAS|NOW THEREFORE|IT IS AGREED)\b",
    re.IGNORECASE,
)


class ClauseChunker:
    """Builds a semantic legal hierarchy from raw formatted text blocks."""

    def __init__(self, body_font_size: float = 12.0) -> None:
        self.body_font_size = body_font_size

        # ── Clause-start patterns ──
        self.patterns = {
            "major_section": re.compile(
                r"^(?:ARTICLE|SECTION)\s+\d+(?:\.\d+)*\b", re.IGNORECASE
            ),
            "single_clause": re.compile(r"^(\d+)\.\s+(.*)"),
            "decimal_clause": re.compile(r"^(\d+\.\d+(?:\.\d+)*)\.?\s+(.*)"),
            "alpha_clause": re.compile(r"^\(([a-z])\)\s+(.*)"),
            "roman_clause": re.compile(r"^\(([ivx]+)\)\s+(.*)"),
        }

    # ──────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────

    def build_chunks(self, raw_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert raw text blocks into hierarchy-annotated chunks."""
        current_hierarchy: List[str] = []
        current_section_blocks: List[Tuple[str, int]] = []  # (text, page)
        chunks: List[Dict[str, Any]] = []

        def _flush() -> None:
            """Process the accumulated section blocks into one or more chunks."""
            if not current_section_blocks:
                return

            section_page = min((p for _, p in current_section_blocks if p), default=0)
            full_text = " ".join(t for t, _ in current_section_blocks)

            # 1. First, split on legal delimiters
            delimiter_parts = LEGAL_DELIMITERS.split(full_text)
            for part in delimiter_parts:
                part = part.strip()
                if not part:
                    continue

                # 2. Then split into sentences via spaCy
                self._chunk_sentences(part, current_hierarchy, section_page, chunks)

        for block in raw_blocks:
            node_id = self._detect_clause_boundary(
                block["text"], block["is_bold"], block["font_size"]
            )
            if node_id:
                _flush()
                current_section_blocks = []
                current_hierarchy = self._update_hierarchy(current_hierarchy, node_id)

            current_section_blocks.append((block["text"], block.get("page_number", 0)))

        _flush()  # final section
        return chunks

    # ──────────────────────────────────────────────────────────────
    # Clause-boundary detection
    # ──────────────────────────────────────────────────────────────

    def _detect_clause_boundary(
        self, text: str, is_bold: bool, font_size: float
    ) -> Optional[str]:
        """Detect whether *text* starts a new clause level.

        Returns the canonical identifier string (e.g. ``"ARTICLE 1"``,
        ``"1."``, ``"(a)"``) or *None* if this is continuation text.
        """
        # Bold + larger font → visual heading (even without a number)
        if is_bold and font_size > (self.body_font_size + 0.5) and len(text) < 150:
            return f"HEADER: {text[:30]}"

        if match := self.patterns["major_section"].match(text):
            return match.group(0).strip()

        if match := self.patterns["single_clause"].match(text):
            return f"{match.group(1)}."

        if match := self.patterns["decimal_clause"].match(text):
            return match.group(1)

        if match := self.patterns["alpha_clause"].match(text):
            return f"({match.group(1)})"

        if match := self.patterns["roman_clause"].match(text):
            return f"({match.group(1)})"

        return None

    # ──────────────────────────────────────────────────────────────
    # Hierarchy level assignment
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def _get_node_level(node_str: str, current_hierarchy: List[str]) -> int:
        """Determine the nesting level of a clause identifier.

        Levels (lower = more senior):
            0  – ``HEADER: …`` or ``ARTICLE / SECTION``
            1  – numeric (``1.``, ``1.1``, ``1.2.3``)
            2  – alpha ``(a)`` … ``(z)``
            3  – roman ``(i)``, ``(ii)``, … (but check for letter-trap)
            4+ – unknown
        """
        if node_str.startswith("HEADER:") or re.match(
            r"^(?:ARTICLE|SECTION)", node_str, re.IGNORECASE
        ):
            return 0

        if re.match(r"^\d+(?:\.\d+)*\.?$", node_str):
            return 1

        # Trap check: (i), (v), (x) look like roman but may be alpha continuation
        if node_str in ("(i)", "(v)", "(x)"):
            for existing in reversed(current_hierarchy):
                if re.match(r"^\([a-z]\)$", existing):
                    prev_ord = ord(existing[1])
                    cur_char = node_str[1]
                    # If it follows alphabetically, it's alpha not roman
                    if ord(cur_char) == prev_ord + 1:
                        return 2
                    break
            return 3

        if re.match(r"^\([ivx]+\)$", node_str):
            return 3

        if re.match(r"^\([a-z]\)$", node_str):
            return 2

        return 4

    @staticmethod
    def _update_hierarchy(current_hierarchy: List[str], new_node: str) -> List[str]:
        """Insert *new_node* at its level, trimming deeper siblings."""
        new_level = ClauseChunker._get_node_level(new_node, current_hierarchy)
        updated: List[str] = []
        for existing in current_hierarchy:
            if ClauseChunker._get_node_level(existing, current_hierarchy) < new_level:
                updated.append(existing)
            else:
                break
        updated.append(new_node)
        return updated

    # ──────────────────────────────────────────────────────────────
    # Sentence boundary detection (spaCy)
    # ──────────────────────────────────────────────────────────────

    def _chunk_sentences(
        self,
        text: str,
        hierarchy: List[str],
        page_number: int,
        chunks: List[Dict[str, Any]],
    ) -> None:
        """Split *text* on sentence boundaries and append chunks of ≤2000 chars."""
        doc = nlp(text)
        current_chunk: List[str] = []

        for sent in doc.sents:
            sent_text = sent.text.strip()
            if not sent_text:
                continue

            # Run-on sentence: hard-slice if >2000 chars
            if len(sent_text) > 2000:
                if current_chunk:
                    chunks.append(
                        {
                            "hierarchy": list(hierarchy),
                            "text": " ".join(current_chunk),
                            "page_number": page_number,
                        }
                    )
                    current_chunk = []
                # Hard-slice by words
                temp: List[str] = []
                for word in sent_text.split():
                    estimate = len(" ".join(temp)) + len(word) + 1
                    if estimate > 2000:
                        if temp:
                            chunks.append(
                                {
                                    "hierarchy": list(hierarchy),
                                    "text": " ".join(temp),
                                    "page_number": page_number,
                                }
                            )
                        temp = [word]
                    else:
                        temp.append(word)
                if temp:
                    current_chunk = temp
                continue

            # Normal accumulation
            estimate = (
                len(" ".join(current_chunk)) + len(sent_text) + 1
                if current_chunk
                else len(sent_text)
            )
            if estimate > 2000:
                chunks.append(
                    {
                        "hierarchy": list(hierarchy),
                        "text": " ".join(current_chunk),
                        "page_number": page_number,
                    }
                )
                current_chunk = [sent_text]
            else:
                current_chunk.append(sent_text)

        if current_chunk:
            chunks.append(
                {
                    "hierarchy": list(hierarchy),
                    "text": " ".join(current_chunk),
                    "page_number": page_number,
                }
            )
