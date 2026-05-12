from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException

from app.config import get_settings
from app.ingestion import run_ingest
from app.logging_db import fetch_recent_runs, init_logging_db
from app.rag import run_query
from app.rag.evaluator import run_evaluation
from app.schemas import (
    EvaluateRequest,
    EvaluateResponse,
    IngestResponse,
    QueryRequest,
    QueryResponse,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_logging_db(get_settings())
    yield


app = FastAPI(
    title=get_settings().app_name,
    lifespan=lifespan,
)


@app.post("/evaluate", response_model=EvaluateResponse)
def evaluate(payload: EvaluateRequest) -> EvaluateResponse:
    """Run scripted regression checks by executing the ``POST /query`` pipeline."""

    return run_evaluation(get_settings(), payload)


@app.post("/query", response_model=QueryResponse)
def query(payload: QueryRequest) -> QueryResponse:
    """Retrieve relevant chunks and return a grounded, validated structured answer."""

    return run_query(get_settings(), payload)


@app.post("/ingest", response_model=IngestResponse)
def ingest() -> IngestResponse:
    """Load ``app/data/docs``, chunk, embed locally, and rebuild the FAISS index."""

    try:
        return run_ingest(get_settings())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/runs")
def list_runs() -> dict[str, object]:
    """Return recent query/eval runs persisted in SQLite (see ``logging_db.insert_run``)."""

    return {"runs": fetch_recent_runs(get_settings())}
