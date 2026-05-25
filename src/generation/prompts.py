"""
Prompt templates for the generation pipeline.

All prompts target GPT-4o-mini and expect JSON-structured output.
Reading grade target: 8th grade (Flesch-Kincaid).
"""

from src.models import EvidenceItem

SYSTEM_PROMPT = """\
You are a legal plain-language expert. Your job is to explain contract clauses \
to everyday people (8th-grade reading level). Always be accurate, never fabricate \
legal facts, and flag risks clearly. Respond only in the JSON format specified.\
"""

JSON_OUTPUT_SCHEMA = """\
{
  "plain_english": "<explanation in plain English, ≤120 words>",
  "risk_flags": ["<risk category slug>", ...],
  "severity": "critical | high | medium | low",
  "recommended_action": "<one concrete action the reader should take>",
  "confidence": <float 0-1>,
  "seek_legal_advice": <true | false>
}\
"""


def build_vanilla_prompt(clause_text: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Explain this contract clause in plain English.\n\n"
                f"CLAUSE:\n{clause_text}\n\n"
                f"Respond in this JSON format:\n{JSON_OUTPUT_SCHEMA}"
            ),
        },
    ]


def build_structured_prompt(clause_text: str, clause_type: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Clause type: {clause_type}\n\n"
                f"CLAUSE:\n{clause_text}\n\n"
                f"Explain this clause for a non-lawyer. Identify risks and recommend action.\n\n"
                f"Respond in this JSON format:\n{JSON_OUTPUT_SCHEMA}"
            ),
        },
    ]


def build_rag_prompt(
    clause_text: str,
    clause_type: str,
    evidence: list[EvidenceItem],
    risk_context: dict | None = None,
) -> list[dict]:
    evidence_block = "\n\n".join(
        f"[{i+1}] ({e.source_type.value}) {e.text}\nSource: {e.citation or 'N/A'}"
        for i, e in enumerate(evidence)
    )

    risk_block = ""
    if risk_context:
        risk_block = (
            f"\n\nRISK ONTOLOGY CONTEXT:\n"
            + "\n".join(
                f"- {cat}: {info.get('consumer_impact', '')}"
                for cat, info in risk_context.items()
            )
        )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Clause type: {clause_type}\n\n"
                f"CLAUSE:\n{clause_text}\n\n"
                f"LEGAL EVIDENCE (use to ground your explanation):\n{evidence_block}"
                f"{risk_block}\n\n"
                f"Using the evidence above, explain this clause for a non-lawyer. "
                f"Do not add facts not in the clause or evidence.\n\n"
                f"Respond in this JSON format:\n{JSON_OUTPUT_SCHEMA}"
            ),
        },
    ]
