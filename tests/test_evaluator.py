import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.rag.evaluator import analyze_case, load_eval_cases, resolve_case_file
from app.schemas import (
    EvalCase,
    QueryResponse,
    SourceReference,
    ValidationResult,
)


def test_analyze_case_all_checks_pass():
    case = EvalCase(
        id="demo",
        question="?",
        expected_source_file="policy_expenses.md",
        must_contain=["client", "reimbursed"],
        should_need_human_review=False,
    )
    response = QueryResponse(
        answer="Client dinners may be reimbursed with approvals.",
        confidence=0.88,
        needs_human_review=False,
        reasoning_summary="Grounded in expenses policy.",
        sources=[
            SourceReference(
                source_file="policy_expenses.md",
                chunk_id="policy_expenses_001",
                quote="Clients may dine when documented.",
            )
        ],
        validation=ValidationResult(passed=True, errors=[], repair_attempted=False),
    )
    scored = analyze_case(case, response)
    assert scored.passed
    assert scored.checks.expected_source_found is True


def test_analyze_case_must_contain_fail():
    case = EvalCase(
        id="missing_terms",
        question="?",
        expected_source_file="policy_expenses.md",
        must_contain=["zzz"],
        should_need_human_review=False,
    )
    response = QueryResponse(
        answer="Short answer grounded elsewhere.",
        confidence=0.9,
        needs_human_review=False,
        reasoning_summary="ok",
        sources=[
            SourceReference(
                source_file="policy_expenses.md",
                chunk_id="policy_expenses_001",
                quote="text",
            )
        ],
        validation=ValidationResult(passed=True, errors=[], repair_attempted=False),
    )
    scored = analyze_case(case, response)
    assert scored.checks.must_contain_found is False


def test_resolve_case_file_relative_to_project(tmp_path: Path):
    cases_dir = tmp_path / "_eval"
    cases_dir.mkdir()
    file_path = cases_dir / "suite.json"
    file_path.write_text("[]", encoding="utf-8")

    resolved = resolve_case_file("_eval/suite.json", root=tmp_path)

    assert resolved == file_path.resolve()


def test_resolve_case_file_blocks_directory_traversal(tmp_path: Path):
    with pytest.raises(HTTPException) as exc:
        resolve_case_file("../evil.json", root=tmp_path)
    assert exc.value.status_code == 400


def test_load_eval_cases_roundtrip(tmp_path: Path):
    payload = [
        {
            "id": "x",
            "question": "q",
            "expected_source_file": "policy.md",
            "must_contain": ["a"],
            "should_need_human_review": False,
        }
    ]
    path = tmp_path / "j.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    cases = load_eval_cases(path)
    assert len(cases) == 1
    assert cases[0].id == "x"


def test_evaluate_endpoint_errors_without_vector_index(tmp_path: Path, monkeypatch):
    import app.config as cfg
    import app.main as main
    import app.rag.evaluator as evaluator

    monkeypatch.setattr(evaluator, "PROJECT_ROOT", tmp_path.resolve())

    missing_index = tmp_path / "empty_vec"
    missing_index.mkdir()

    fake = cfg.Settings(
        docs_dir=tmp_path / "docs",
        vector_store_dir=missing_index,
        logs_db_path=tmp_path / "logs.db",
        llm_api_key="fake-key",
    )

    suite = tmp_path / "mini_cases.json"
    suite.write_text(
        json.dumps(
            [
                {
                    "id": "only",
                    "question": "test?",
                    "expected_source_file": "policy.md",
                    "must_contain": ["a"],
                    "should_need_human_review": False,
                }
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(main, "get_settings", lambda: fake)

    with TestClient(main.app) as client:
        response = client.post(
            "/evaluate",
            json={"case_file": "mini_cases.json"},
        )

    assert response.status_code == 400
    detail = response.json()["detail"].lower()
    assert "ingest" in detail or "index" in detail
