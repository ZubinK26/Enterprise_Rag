from __future__ import annotations

import json
from pathlib import Path

from fastapi import HTTPException

from app.config import PROJECT_ROOT, Settings
from app.ingestion.vector_store import read_store
from app.rag.query_service import run_query
from app.schemas import (
    EvalCase,
    EvalCaseChecks,
    EvalCaseResult,
    EvaluateRequest,
    EvaluateResponse,
    QueryRequest,
    QueryResponse,
    ValidationResult,
)


def resolve_case_file(case_file: str, *, root: Path | None = None) -> Path:
    """Resolve a project-relative evaluation JSON path safely (blocks ``..`` breakout)."""

    base = root if root is not None else PROJECT_ROOT.resolve()
    raw = Path(case_file.strip())
    if raw.is_absolute():
        raise HTTPException(status_code=400, detail="case_file must be a relative repo path.")

    resolved = (base / raw).resolve()
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid case_file: path escapes project root.",
        ) from exc

    if not resolved.is_file():
        raise HTTPException(
            status_code=400,
            detail=f"Evaluation file not found: {resolved.as_posix()}",
        )

    return resolved


def load_eval_cases(path: Path) -> list[EvalCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise HTTPException(status_code=400, detail="eval_cases JSON must be a list.")
    return [EvalCase.model_validate(entry) for entry in payload]


def analyze_case(case: EvalCase, response: QueryResponse) -> EvalCaseResult:
    answer_lower = response.answer.lower()
    expected_source_found = any(
        source.source_file == case.expected_source_file for source in response.sources
    )
    must_contain_found = all(fragment.lower() in answer_lower for fragment in case.must_contain)
    human_review_correct = response.needs_human_review == case.should_need_human_review
    validation_passed = response.validation.passed

    checks = EvalCaseChecks(
        expected_source_found=expected_source_found,
        must_contain_found=must_contain_found,
        human_review_correct=human_review_correct,
        validation_passed=validation_passed,
    )

    summary_passed = (
        checks.expected_source_found
        and checks.must_contain_found
        and checks.human_review_correct
        and checks.validation_passed
    )

    return EvalCaseResult(id=case.id, passed=summary_passed, checks=checks)


def _fallback_response(*, reasoning: str) -> QueryResponse:
    """Neutral failure surface for scorer when a query cannot complete normally."""

    from app.schemas import SAFE_FALLBACK_ANSWER

    return QueryResponse(
        answer=SAFE_FALLBACK_ANSWER,
        confidence=0.0,
        sources=[],
        needs_human_review=True,
        reasoning_summary=reasoning,
        validation=ValidationResult(
            passed=False,
            errors=["evaluation_query_failed"],
            repair_attempted=False,
        ),
    )


def run_evaluation(settings: Settings, body: EvaluateRequest) -> EvaluateResponse:
    """
    Execute every eval case by calling the same ``run_query`` pipeline used by ``POST /query``.
    """

    if not settings.llm_api_key.strip():
        raise HTTPException(
            status_code=503,
            detail="LLM_API_KEY is not configured but is required for /evaluate.",
        )

    try:
        read_store(settings.vector_store_dir)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=400,
            detail="Vector index not found. Run `POST /ingest` before evaluating.",
        ) from exc

    case_path = resolve_case_file(body.case_file)
    cases = load_eval_cases(case_path)

    results: list[EvalCaseResult] = []
    passed = 0

    for case in cases:
        try:
            response = run_query(
                settings,
                QueryRequest(question=case.question, top_k=settings.default_top_k),
            )
        except HTTPException as exc:
            detail = exc.detail
            reason = detail if isinstance(detail, str) else "Query failed during evaluation."
            response = _fallback_response(reasoning=reason)

        scored = analyze_case(case, response)
        results.append(scored)
        if scored.passed:
            passed += 1

    total = len(results)
    failed = total - passed

    return EvaluateResponse(
        total=total,
        passed=passed,
        failed=failed,
        results=results,
    )
