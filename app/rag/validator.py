from __future__ import annotations

import json
import re
from collections.abc import Sequence

from pydantic import ValidationError

from app.ingestion.vector_store import ChunkRecord
from app.rag.generator import parse_llm_text_to_dict
from app.schemas import RAGAnswer, SAFE_FALLBACK_ANSWER


def _normalize_for_match(text: str) -> str:
    return " ".join(text.split())


_INSUFFICIENT_CONTEXT_PATTERNS = (
    r"\binsufficient context\b",
    r"\bnot enough information\b",
    r"\bcannot answer from the (?:provided |available )?context\b",
    r"\bcontext does not (?:contain|include)\b",
    r"\bno relevant information\b",
)


def mentions_insufficient_context(answer: str) -> bool:
    lowered = answer.lower()
    return any(re.search(pat, lowered) for pat in _INSUFFICIENT_CONTEXT_PATTERNS)


def semantic_validate(answer: RAGAnswer, retrieved: Sequence[ChunkRecord]) -> list[str]:
    errors: list[str] = []

    if RAGAnswer.is_safe_fallback(
        answer.answer, answer.confidence, answer.needs_human_review
    ):
        return errors

    if not answer.sources:
        errors.append("missing_sources")

    lookup: dict[tuple[str, str], str] = {}
    for record in retrieved:
        lookup[(record.source_file, record.chunk_id)] = record.text

    for src in answer.sources:
        key = (src.source_file, src.chunk_id)
        if key not in lookup:
            errors.append("unknown_source_chunk")
            continue
        chunk_text = lookup[key]
        if _normalize_for_match(src.quote) not in _normalize_for_match(chunk_text):
            errors.append("quote_not_found_in_retrieved_context")

    if mentions_insufficient_context(answer.answer) and not answer.needs_human_review:
        errors.append("insufficient_context_requires_human_review")

    return sorted(set(errors))


def parse_answer_payload(raw_llm_output: str) -> tuple[RAGAnswer | None, list[str]]:
    errors: list[str] = []

    try:
        data = parse_llm_text_to_dict(raw_llm_output)
    except json.JSONDecodeError:
        return None, ["json_parse_error"]

    try:
        return RAGAnswer.model_validate(data), []
    except ValidationError:
        return None, ["pydantic_validation_error"]


def validate_pipeline(
    answer: RAGAnswer | None, pydantic_errors: list[str], retrieved: Sequence[ChunkRecord]
) -> list[str]:
    if pydantic_errors:
        return pydantic_errors[:]
    assert answer is not None
    return semantic_validate(answer, retrieved)


def safe_fallback_answer() -> RAGAnswer:
    return RAGAnswer(
        answer=SAFE_FALLBACK_ANSWER,
        confidence=0.0,
        sources=[],
        needs_human_review=True,
        reasoning_summary="Validation failed after one repair attempt.",
    )
