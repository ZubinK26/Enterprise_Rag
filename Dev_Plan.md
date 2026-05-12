# Development Plan: Enterprise RAG + Agent Evaluator

This document turns `Dev_Plan_Precursor.md` into an implementation roadmap. Completing **all phases** below satisfies **every deliverable and acceptance criterion** in the precursor.

---

## 1. Success definition (traceability)

| Precursor requirement | Done when | Verify |
|----------------------|-----------|--------|
| Document ingestion | `POST /ingest` reads docs, chunks, embeds, persists | Call `/ingest`; vector store has entries; logs if applicable |
| Chunking | 500–800 chars, 100 overlap, metadata per chunk | Unit test + spot-check chunk sizes |
| Retrieval + RAG | `POST /query` retrieves `top_k`, generates answer | Integration call with known question |
| Structured JSON + Pydantic | Response matches `RAGAnswer` + nested validation | Schema tests + live response |
| Repair loop | One repair on failure; then safe fallback | Force bad LLM output in test or mock |
| Source references | `sources` with file, chunk_id, quote | Validator + response shape |
| `/evaluate` | Runs cases from JSON, scores checks | `POST /evaluate` returns totals + per-case |
| Run logging (SQLite) | `runs` table + fields as spec | `GET /runs` shows rows after queries |
| Sample docs (5) | Policy MD files ~500–1000 words each | Files exist; ingest succeeds |
| Eval cases (≥5) | `eval_cases/eval_cases.json` | Evaluate `total` ≥ 5 |
| pytest (≥3 passing) | `tests/` as spec | `pytest` green |
| README (10 sections) | All listed sections present | Manual review |
| Local run (simple commands) | venv, pip, .env, uvicorn | Fresh clone walkthrough |

---

## 2. Tech stack (fixed)

- Python 3.11+
- FastAPI, Uvicorn, Pydantic v2
- SQLite (runs DB)
- Embeddings: **one** of sentence-transformers (local) or OpenAI/Gemini API
- Vector store: **one** of FAISS or Chroma
- LLM: OpenAI / Gemini / Anthropic **compatible** client (config-driven base URL + model)
- pytest

**Decision (record in README):** Pick embedding + vector backend once; avoid supporting every combination in code paths.

---

## 3. Target repository layout

Match the precursor tree under `app/`, `tests/`, `eval_cases/`, plus:

- `requirements.txt` — pinned or ranges suitable for reproducible local run
- `.env.example` — `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, embedding flags if API-based, optional `EMBEDDING_MODEL`
- `README.md` — all required sections (see §10)

**Note:** Precursor shows `logs.db` under `app/data/`; implement creation on startup or first write with clear path in `config.py`.

---

## 4. Phase A — Project skeleton

1. Create package `app/` with `main.py`, `config.py`, `schemas.py`, `logging_db.py`.
2. Wire FastAPI app: CORS only if needed (default off for demo).
3. Health check (optional): `GET /health` for quick smoke — not in spec; skip or keep minimal.
4. `config.py`: load `.env`; paths to `data/docs`, `data/vector_store`, DB path; `top_k` defaults; LLM/embedding settings.
5. `requirements.txt` + `.env.example`.

**Exit:** `uvicorn app.main:app` starts; no business logic yet.

---

## 5. Phase B — Pydantic schemas (`schemas.py`)

Implement strict models:

- `SourceReference`: `source_file`, `chunk_id`, `quote`
- `RAGAnswer`: `answer`, `confidence` (0–1), `sources` (min 1 **after** successful validation path — see note), `needs_human_review`, `reasoning_summary`
- `ValidationResult` (or equivalent): `passed`, `errors: list[str]`, `repair_attempted`
- Query request: `question`, `top_k`
- Evaluate request: `case_file`
- Evaluate response types: per-case checks + aggregate counts

**Model validators / field validators:**

- `confidence` in [0, 1]
- If `confidence < 0.6` → enforce `needs_human_review is True` (precursor rule)
- `answer` non-empty when claiming success (fallback response may use empty `sources` only in the **explicit** safe-fallback shape — align validator with that exception)

**Exit:** Import tests or schema-only tests pass; JSON OpenAPI reflects models.

---

## 6. Phase C — Sample data

1. Add five markdown files under `app/data/docs/` with content per precursor themes (~500–1000 words each).
2. Ensure filenames match eval cases: `policy_expenses.md`, `policy_data_privacy.md`, etc.

**Exit:** Files present; ingest can list them reliably.

---

## 7. Phase D — Ingestion pipeline (`app/ingestion/`)

| Module | Responsibility |
|--------|----------------|
| `loader.py` | Discover and read `.md`/`.txt` from `app/data/docs` |
| `chunker.py` | Split text: target 500–800 chars, overlap 100; stable `chunk_id` naming (e.g. `{doc_stem}_{index:03d}`) |
| `embedder.py` | Embed chunk text via chosen backend |
| `vector_store.py` | Persist/query vectors + metadata (`doc_id`, `source_file`, `chunk_id`, `text`) |

**Ingest orchestration:**

- `POST /ingest`: clear or upsert vectors (document choice: **replace collection** per ingest is simplest for demo)
- Return summary: docs processed, chunk count, timing (optional)

**Exit:** After ingest, retrieval returns chunks from known phrases in sample docs.

---

## 8. Phase E — RAG core (`app/rag/`)

| Module | Responsibility |
|--------|----------------|
| `retriever.py` | Embed question; `top_k` similarity search; return chunk records + concatenated context string |
| `generator.py` | Build prompts; call LLM; parse **JSON-only** response |
| `validator.py` | Steps 1–8 from precursor: parse JSON → Pydantic → source/chunk existence in retrieved set → substring check for quotes in chunk text → confidence range → low-confidence ⇒ human review → “insufficient context” semantics ⇒ human review |
| `repairer.py` | Single repair prompt with errors + context + bad output; re-validate |
| `evaluator.py` | Load eval file; for each case run internal query pipeline; compute checks |

**Validator error codes:** Use stable string tokens (as in precursor examples) for `errors[]` — aids debugging and eval.

**Fallback path:** If still invalid after repair, return fixed safe `RAGAnswer` with empty `sources`, `confidence: 0`, `needs_human_review: true`, reasoning as specified — and `ValidationResult` should reflect failure + `repair_attempted: true`.

**Exit:** End-to-end path callable without HTTP for unit tests (inject retriever/mock LLM).

---

## 9. Phase F — HTTP API (`app/main.py`)

| Method | Path | Behavior |
|--------|------|----------|
| POST | `/ingest` | Run full ingest |
| POST | `/query` | Full flow: retrieve → generate → validate → optional repair → log → response |
| POST | `/evaluate` | Resolve `case_file` relative to repo root (or configurable base); run ≥5 cases |
| GET | `/runs` | Return recent rows (define limit, e.g. 100, in README) |

**Logging (per query):** Insert into `runs` with all precursor fields + `latency_ms` (wall time for query handler).

**Exit:** `curl` examples from precursor work on Windows (document `Invoke-RestMethod` or Git Bash alongside bash `curl`).

---

## 10. Phase G — SQLite logging (`logging_db.py`)

- Create `runs` table on startup if missing.
- Columns: `id`, `timestamp`, `question`, `answer`, `confidence`, `needs_human_review`, `sources_json`, `validation_passed`, `validation_errors_json`, `repair_attempted`, `latency_ms`.
- Serialize `sources` and `errors` as JSON strings.

**Exit:** `GET /runs` returns data after `/query`.

---

## 11. Phase H — Evaluation harness

1. Add `eval_cases/eval_cases.json` with **at least 5** cases covering multiple policies.
2. Per case, internally invoke the same code path as `/query` (no HTTP loopback required, but behavior must match).

**Checks per precursor:**

- `expected_source_file` appears in returned `sources`
- Answer text contains each `must_contain` substring (case policy: recommend case-insensitive)
- `needs_human_review` matches `should_need_human_review`
- `validation.passed` is true

**Response shape:** `total`, `passed`, `failed`, `results[]` with nested `checks` booleans.

**Exit:** Evaluate returns coherent pass/fail; failing case is explainable via `checks`.

---

## 12. Phase I — Tests (`tests/`)

| File | Minimum coverage |
|------|------------------|
| `test_chunker.py` | Length bounds, overlap, deterministic IDs |
| `test_validator.py` | Valid answer; fabricated quote fails; missing source fails; confidence rule |
| `test_evaluator.py` | Mock RAG outputs to assert scoring logic |

**Target:** ≥3 tests **passing** in CI/local; aim for broader coverage without overbuilding.

**Exit:** `pytest` passes from repo root.

---

## 13. Phase J — README (mandatory sections)

Include **exactly** these section themes (titles can vary slightly but content must appear):

1. What this project demonstrates  
2. Architecture (include the precursor pipeline diagram as inline text)  
3. Why validation matters  
4. Endpoints  
5. Example query  
6. Example validated answer  
7. Evaluation results  
8. Failure modes handled  
9. How to run (Windows + Unix: venv, `pip install -r requirements.txt`, copy `.env`, `uvicorn`)  
10. What was AI-assisted vs personally designed  

**Also document:** Limitations (no auth, toy corpus, model variance), and which env vars are required.

---

## 14. Implementation order (recommended)

1. Schemas + config + empty routes  
2. Logging DB + `GET /runs`  
3. Chunker + tests  
4. Embedder + vector store + ingest  
5. Retriever + generator (with mock)  
6. Validator + repairer + fallback  
7. Wire `POST /query` + logging  
8. Eval cases + evaluator + `POST /evaluate`  
9. README + sample curl/Windows examples  
10. Final pass against acceptance checklist (§15)

---

## 15. Final acceptance checklist (project “done”)

- [ ] `POST /ingest` completes on sample docs  
- [ ] `POST /query` returns structured answer with grounded `sources`  
- [ ] Malformed / invalid LLM output: one repair attempt, then safe fallback  
- [ ] `POST /evaluate` runs ≥ 5 cases from JSON  
- [ ] SQLite persists runs; `GET /runs` works  
- [ ] README covers architecture + limitations + all 10 sections  
- [ ] At least 3 pytest tests pass  
- [ ] Fresh machine can run with precursor “minimal commands” (Windows equivalents documented)  

---

## 16. Out of scope (keep interview-useful)

- User authentication / multi-tenancy  
- Production deployment, Kubernetes, monitoring  
- Advanced chunking (semantic, hierarchical)  
- Dual embedding backends or dual vector stores in one build  

---

**Status:** This `Dev_Plan.md` is the single implementation guide; execute phases A–J in order unless parallelizing tests/docs with backend work.
