from __future__ import annotations

from typing import Any, Self

from pydantic import BaseModel, Field, field_validator, model_validator

SAFE_FALLBACK_ANSWER = "I could not produce a validated answer from the available context."


class SourceReference(BaseModel):
    """A single grounding citation from retrieved policy text."""

    model_config = {"extra": "forbid"}

    source_file: str
    chunk_id: str
    quote: str


class RAGAnswer(BaseModel):
    """Structured LLM output for policy Q&A."""

    model_config = {"extra": "forbid"}

    answer: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    sources: list[SourceReference] = Field(default_factory=list)
    needs_human_review: bool
    reasoning_summary: str = Field(min_length=1)

    @staticmethod
    def is_safe_fallback(answer: str, confidence: float, needs_review: bool) -> bool:
        return needs_review and confidence == 0.0 and answer.strip() == SAFE_FALLBACK_ANSWER

    @model_validator(mode="after")
    def low_confidence_requires_review(self) -> Self:
        if self.confidence < 0.6 and not self.needs_human_review:
            raise ValueError("needs_human_review must be True when confidence < 0.6")
        return self

    @model_validator(mode="after")
    def sources_required_unless_fallback(self) -> Self:
        if self.sources:
            return self
        if self.is_safe_fallback(self.answer, self.confidence, self.needs_human_review):
            return self
        raise ValueError("sources must contain at least one entry (unless using safe fallback)")


class ValidationResult(BaseModel):
    """Outcome of validating a candidate RAG JSON answer."""

    model_config = {"extra": "forbid"}

    passed: bool
    errors: list[str] = Field(default_factory=list)
    repair_attempted: bool = False


class QueryRequest(BaseModel):
    model_config = {"extra": "forbid"}

    question: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=50)


class QueryResponse(RAGAnswer):
    """Full API response returned by ``POST /query``."""

    model_config = {"extra": "forbid"}

    validation: ValidationResult


class EvaluateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    case_file: str = Field(min_length=1)


class EvalCase(BaseModel):
    model_config = {"extra": "forbid"}

    id: str
    question: str
    expected_source_file: str
    must_contain: list[str]
    should_need_human_review: bool


class EvalCaseChecks(BaseModel):
    model_config = {"extra": "forbid"}

    expected_source_found: bool
    must_contain_found: bool
    human_review_correct: bool
    validation_passed: bool


class EvalCaseResult(BaseModel):
    model_config = {"extra": "forbid"}

    id: str
    passed: bool
    checks: EvalCaseChecks


class EvaluateResponse(BaseModel):
    model_config = {"extra": "forbid"}

    total: int
    passed: int
    failed: int
    results: list[EvalCaseResult]


class IngestResponse(BaseModel):
    model_config = {"extra": "forbid"}

    documents_loaded: int
    chunks_indexed: int
    embedding_model: str
    seconds: float


class RunLogRecord(BaseModel):
    """Shape of a row returned from `GET /runs` (subset of stored columns)."""

    model_config = {"extra": "forbid"}

    id: int
    timestamp: str
    question: str
    answer: str
    confidence: float
    needs_human_review: bool
    sources_json: str
    validation_passed: bool
    validation_errors_json: str
    repair_attempted: bool
    latency_ms: int

    @field_validator("sources_json", "validation_errors_json", mode="before")
    @classmethod
    def _coerce_json_field(cls, v: Any) -> str:
        if isinstance(v, dict | list):
            import json

            return json.dumps(v)
        if v is None:
            return "[]"
        return str(v)
