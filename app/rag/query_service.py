from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter

import httpx
from fastapi import HTTPException

from app.config import Settings
from app.ingestion.vector_store import read_store
from app.logging_db import insert_run
from app.rag.generator import build_initial_user_prompt, call_llm_json
from app.rag.repairer import build_repair_user_prompt
from app.rag.retriever import format_retrieved_context, retrieve_chunks
from app.rag.validator import (
    parse_answer_payload,
    safe_fallback_answer,
    validate_pipeline,
)
from app.schemas import QueryRequest, QueryResponse, ValidationResult

_NO_INDEX_DETAIL = (
    "Vector index not found. Run `POST /ingest` locally before querying."
)


def run_query(settings: Settings, body: QueryRequest) -> QueryResponse:
    started = perf_counter()
    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        store = read_store(settings.vector_store_dir)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=_NO_INDEX_DETAIL) from exc

    top_k = body.top_k or settings.default_top_k
    scored = retrieve_chunks(store, settings, body.question, top_k=top_k)
    retrieved = [record for record, _score in scored]

    if not retrieved:
        fallback = safe_fallback_answer()
        fallback = fallback.model_copy(
            update={
                "reasoning_summary": (
                    "No indexed chunks retrieved for this query. "
                    "Try re-running ingest or rephrasing the question."
                )
            }
        )
        latency_ms = max(1, int((perf_counter() - started) * 1000))
        insert_run(
            settings,
            timestamp=timestamp,
            question=body.question,
            answer=fallback.answer,
            confidence=float(fallback.confidence),
            needs_human_review=fallback.needs_human_review,
            sources=[],
            validation_passed=False,
            validation_errors=["no_retrieved_chunks"],
            repair_attempted=False,
            latency_ms=latency_ms,
        )
        return QueryResponse(
            **fallback.model_dump(),
            validation=ValidationResult(
                passed=False,
                errors=["no_retrieved_chunks"],
                repair_attempted=False,
            ),
        )

    if not settings.llm_api_key.strip():
        raise HTTPException(
            status_code=503,
            detail="LLM_API_KEY is not configured but is required for /query.",
        )

    context = format_retrieved_context(scored)

    try:
        initial_raw = call_llm_json(
            settings,
            user_prompt=build_initial_user_prompt(question=body.question, context=context),
        )
        parsed, pydantic_errors = parse_answer_payload(initial_raw)
        errors = validate_pipeline(parsed, pydantic_errors, retrieved)

        if not errors:
            final = parsed
            assert final is not None
            latency_ms = max(1, int((perf_counter() - started) * 1000))
            insert_run(
                settings,
                timestamp=timestamp,
                question=body.question,
                answer=final.answer,
                confidence=float(final.confidence),
                needs_human_review=final.needs_human_review,
                sources=[s.model_dump() for s in final.sources],
                validation_passed=True,
                validation_errors=[],
                repair_attempted=False,
                latency_ms=latency_ms,
            )
            return QueryResponse(
                **final.model_dump(),
                validation=ValidationResult(
                    passed=True,
                    errors=[],
                    repair_attempted=False,
                ),
            )

        repair_prompt = build_repair_user_prompt(
            errors=errors,
            context=context,
            bad_output=initial_raw.strip(),
        )
        repair_raw = call_llm_json(settings, user_prompt=repair_prompt)

        parsed2, perr2 = parse_answer_payload(repair_raw)
        errors_after = validate_pipeline(parsed2, perr2, retrieved)

        if not errors_after:
            final = parsed2
            assert final is not None
            latency_ms = max(1, int((perf_counter() - started) * 1000))
            insert_run(
                settings,
                timestamp=timestamp,
                question=body.question,
                answer=final.answer,
                confidence=float(final.confidence),
                needs_human_review=final.needs_human_review,
                sources=[s.model_dump() for s in final.sources],
                validation_passed=True,
                validation_errors=[],
                repair_attempted=True,
                latency_ms=latency_ms,
            )
            return QueryResponse(
                **final.model_dump(),
                validation=ValidationResult(
                    passed=True,
                    errors=[],
                    repair_attempted=True,
                ),
            )

        fallback = safe_fallback_answer()
        latency_ms = max(1, int((perf_counter() - started) * 1000))
        insert_run(
            settings,
            timestamp=timestamp,
            question=body.question,
            answer=fallback.answer,
            confidence=float(fallback.confidence),
            needs_human_review=fallback.needs_human_review,
            sources=[],
            validation_passed=False,
            validation_errors=errors_after,
            repair_attempted=True,
            latency_ms=latency_ms,
        )
        return QueryResponse(
            **fallback.model_dump(),
            validation=ValidationResult(
                passed=False,
                errors=errors_after,
                repair_attempted=True,
            ),
        )

    except httpx.HTTPStatusError as exc:
        latency_ms = max(1, int((perf_counter() - started) * 1000))
        insert_run(
            settings,
            timestamp=timestamp,
            question=body.question,
            answer="LLM upstream error",
            confidence=0.0,
            needs_human_review=True,
            sources=[],
            validation_passed=False,
            validation_errors=["llm_upstream_error"],
            repair_attempted=False,
            latency_ms=latency_ms,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Upstream LLM request failed ({exc.response.status_code}).",
        ) from exc
    except RuntimeError as exc:
        latency_ms = max(1, int((perf_counter() - started) * 1000))
        insert_run(
            settings,
            timestamp=timestamp,
            question=body.question,
            answer="LLM configuration error",
            confidence=0.0,
            needs_human_review=True,
            sources=[],
            validation_passed=False,
            validation_errors=["llm_configuration_error"],
            repair_attempted=False,
            latency_ms=latency_ms,
        )
        raise HTTPException(status_code=503, detail=str(exc)) from exc
