import json

from app.ingestion.vector_store import ChunkRecord
from app.rag.validator import (
    mentions_insufficient_context,
    parse_answer_payload,
    semantic_validate,
    validate_pipeline,
)
from app.schemas import SAFE_FALLBACK_ANSWER, RAGAnswer


def sample_record() -> ChunkRecord:
    return ChunkRecord(
        doc_id="policy_expenses",
        source_file="policy_expenses.md",
        chunk_id="policy_expenses_001",
        text=(
            "Client dinners may be reimbursed when there is documented business rationale. "
            "Approvals escalate through Concur tiers."
        ),
    )


def test_semantic_validate_accepts_matching_quote():
    retrieved = [sample_record()]
    answer = RAGAnswer(
        answer="Yes, client dinners are reimbursable with documentation.",
        confidence=0.8,
        needs_human_review=False,
        reasoning_summary="The expense policy cites client reimbursement rules.",
        sources=[
            {
                "source_file": "policy_expenses.md",
                "chunk_id": "policy_expenses_001",
                "quote": "Client dinners may be reimbursed when there is documented business rationale.",
            }
        ],
    )
    assert semantic_validate(answer, retrieved) == []


def test_semantic_validate_flags_unknown_chunk():
    answer = RAGAnswer(
        answer="Anything.",
        confidence=0.85,
        needs_human_review=False,
        reasoning_summary="Reason.",
        sources=[
            {
                "source_file": "missing.md",
                "chunk_id": "missing_001",
                "quote": "oops",
            }
        ],
    )
    errs = semantic_validate(answer, [sample_record()])
    assert "unknown_source_chunk" in errs


def test_semantic_validate_flags_bad_quote():
    answer = RAGAnswer(
        answer="Anything.",
        confidence=0.85,
        needs_human_review=False,
        reasoning_summary="Reason.",
        sources=[
            {
                "source_file": "policy_expenses.md",
                "chunk_id": "policy_expenses_001",
                "quote": "this substring is not inside the retrieved chunk text",
            }
        ],
    )
    errs = semantic_validate(answer, [sample_record()])
    assert "quote_not_found_in_retrieved_context" in errs


def test_semantic_validate_allows_safe_fallback():
    fb = RAGAnswer(
        answer=SAFE_FALLBACK_ANSWER,
        confidence=0.0,
        sources=[],
        needs_human_review=True,
        reasoning_summary="Validation failed after one repair attempt.",
    )
    assert semantic_validate(fb, [sample_record()]) == []


def test_insufficient_context_must_flag_review():
    answer = RAGAnswer(
        answer="There is insufficient context to answer confidently.",
        confidence=0.9,
        needs_human_review=False,
        reasoning_summary="Test.",
        sources=[
            {
                "source_file": "policy_expenses.md",
                "chunk_id": "policy_expenses_001",
                "quote": "Client dinners may be reimbursed when there is documented business rationale.",
            }
        ],
    )
    errs = semantic_validate(answer, [sample_record()])
    assert "insufficient_context_requires_human_review" in errs


def test_parse_answer_payload_detects_bad_json():
    answer, errs = parse_answer_payload("NOT JSON {{{")
    assert answer is None
    assert errs == ["json_parse_error"]


def test_parse_answer_payload_rejects_bad_schema():
    answer, errs = parse_answer_payload(
        json.dumps(
            {
                "answer": "ok",
                "confidence": 0.8,
                "sources": [],  # missing required source for pydantic constraints
                "needs_human_review": False,
                "reasoning_summary": "x",
            }
        )
    )
    assert answer is None
    assert errs == ["pydantic_validation_error"]


def test_validate_pipeline_prioritizes_pydantic_errors():
    retrieved = [sample_record()]
    pydantic_errors = ["pydantic_validation_error"]
    assert validate_pipeline(None, pydantic_errors, retrieved) == pydantic_errors


def test_mentions_insufficient_context_heuristic():
    assert mentions_insufficient_context("Not enough information in the retrieved context.") is True
    assert mentions_insufficient_context("Yes, approvals are documented.") is False
