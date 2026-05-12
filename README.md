# Enterprise RAG + Agent Evaluator

Small **FastAPI** service that demonstrates **document ingestion**, **chunking**, **local embeddings**, **FAISS retrieval**, **Gemini (OpenAI-compatible) generation**, **strict Pydantic validation**, **a one-shot repair loop**, **SQLite query logging**, and a **simple JSON regression harness** (`POST /evaluate`).

Designed as a Junior GenAI / applied-ML portfolio piece: understandable code paths over framework noise.

[![CI](https://github.com/ZubinK26/Ent_Rag/actions/workflows/ci.yml/badge.svg)](https://github.com/ZubinK26/Ent_Rag/actions/workflows/ci.yml)

> If you name the repo something other than **`Ent_Rag`**, edit the badge URLs accordingly.

Pinned **offline snapshots** from a clean local ingest + Gemini eval run live under [`results/ingest_snapshot.json`](./results/ingest_snapshot.json) and [`results/evaluate_snapshot.json`](./results/evaluate_snapshot.json) (`6/6` passed when captured).

---

## 1. What this project demonstrates

- **Retrieval-Augmented Generation (RAG)** over a fixed corpus of Markdown policy snippets  
- **Structured JSON outputs** from the LLM, parsed and validated before returning to callers  
- **Grounding checks**: citations must reference real retrieved chunks with **verbatim quotes**  
- **Resilience**: one automatic **repair** pass when validation fails, then a deterministic **safe fallback**  
- **Observability**: every `/query` (and failures during evaluation) persisted in **SQLite** with latency and validation flags  
- **Quality gate**: scripted **evaluation cases** that replay the production query pipeline  

---

## 2. Architecture

```text
Documents
→ chunking
→ embeddings
→ vector store
→ retrieval
→ structured LLM answer
→ Pydantic validation
→ quote/source grounding check
→ repair loop (max once)
→ logged answer
→ eval harness (/evaluate)
```

| Layer | Notes |
|--------|------|
| Ingest | Reads `app/data/docs/*.md`, chunks (≈500–800 chars, 100 overlap), embeds with **sentence-transformers**, persists **FAISS** + chunk metadata JSON |
| Query | Embedding similarity → top‑k chunks → Gemini chat-completions (**OpenAI-compatible endpoint**) → parse JSON → semantic validation → optional repair LLM call |
| Logs | SQLite `runs` table; `GET /runs` surfaces recent rows |
| Eval | JSON cases under `eval_cases/`; each invokes the same logic as `/query`, then checks sources, wording, flags, validation |

---

## 3. Why validation matters

Unstructured LLMs **hallucinate plausible policy language**. Strict checks ensure:

1. Returned JSON conforms to **`RAGAnswer`** (confidence bounds, mandatory review when `< 0.6`, citations unless using the sanctioned fallback payload).  
2. Every citation’s **`chunk_id` / `source_file`** existed in retrieval.  
3. Each **`quote` appears verbatim** (whitespace-normalized) in that chunk — reducing fake citations in demos and interviews.

When checks fail once, we ask the model to **repair** using validation errors plus the retrieved context. If validation still fails, we return an explicit fallback answer requiring human review rather than pretending success.

---

## 4. Endpoints

| Method | Path | Description |
|--------|------|----------------|
| `POST` | `/ingest` | Rebuild embeddings + FAISS index from `app/data/docs` |
| `POST` | `/query` | RAG answer with citations + `validation` block |
| `POST` | `/evaluate` | Runs eval JSON file (replay `/query` per case) |
| `GET` | `/runs` | Recent persisted query rows |
| `GET` | `/health` | Liveness probe |
| `GET` | `/docs` | Swagger UI (FastAPI) |

Interactive docs: **`http://127.0.0.1:8000/docs`** when the server is running.

---

## 5. Example query

PowerShell (`Invoke-RestMethod`):

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/query `
  -ContentType "application/json" `
  -Body '{"question":"Can employees expense client dinners?","top_k":4}'
```

Bash / curl:

```bash
curl -s http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question":"Can employees expense client dinners?","top_k":4}'
```

---

## 6. Example validated answer shape

`/query` returns a flat **`RAGAnswer`** payload plus **`validation`**:

```json
{
  "answer": "Employees may reimburse qualifying client dinners when business purpose and approvals are documented per the expense policy.",
  "confidence": 0.82,
  "sources": [
    {
      "source_file": "policy_expenses.md",
      "chunk_id": "policy_expenses_002",
      "quote": "Client dinners demand written summaries highlighting discussion topics…"
    }
  ],
  "needs_human_review": false,
  "reasoning_summary": "The expense policy emphasizes approval routing and contemporaneous receipts.",
  "validation": {
    "passed": true,
    "errors": [],
    "repair_attempted": false
  }
}
```

Quotes and scores **will vary** with model temperature and Gemini updates; grounding checks anchor answers to retrieval.

---

## 7. Evaluation results

Run ingestion once, configure `.env`, then:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/evaluate `
  -ContentType "application/json" `
  -Body '{"case_file":"eval_cases/eval_cases.json"}'
```

The response summarizes **total / passed / failed** plus per‑case booleans (`expected_source_found`, `must_contain_found`, `human_review_correct`, `validation_passed`).

**Expectation-setting:** live LLMs are non-deterministic. For portfolio review, paste a recent **`/evaluate` JSON snapshot** into a discussion doc or screenshot `total/passed`.

---

## 8. Failure modes handled

| Scenario | Behaviour |
|-----------|-----------|
| No FAISS index | `POST /query`/`/evaluate` → **400**, instruct run `/ingest` |
| No `LLM_API_KEY` while chunks exist | **503** on `/query` and `/evaluate` |
| Gemini / network errors mid-query | logged `llm_upstream_error`; response **502** |
| Invalid LLM JSON or failed schema | `validation.errors` populated; triggers **repair** once |
| Still invalid post-repair | Deterministic **`SAFE_FALLBACK_ANSWER`** with `repair_attempted: true` |
| Retrieved zero chunks | Safe fallback reasoning + logged `no_retrieved_chunks` |

---

## 9. How to run

### Prerequisites

- **Python ≥ 3.11** recommended  
- [**Google AI Studio API key**](https://aistudio.google.com/apikey) (Gemini via OpenAI-compatible REST)  

### Setup

```bash
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Unix:
# source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

cp .env.example .env   # or copy manually on Windows
# Fill LLM_API_KEY in .env
```

### Bootstrap local data & serve

```bash
uvicorn app.main:app --reload
```

Separate terminal (once server is warm):

```bash
curl -X POST http://127.0.0.1:8000/ingest
curl -X POST http://127.0.0.1:8000/query -H "Content-Type: application/json" \
     -d '{"question":"Summarize MFA rules.","top_k":3}'
```

First ingest downloads the **sentence-transformer** embedding model (~tens–hundreds MB depending on caching).

### Quality checks

```bash
pytest tests -q
```

### Repository layout

```text
app/
  main.py               # Routes
  config.py             # pydantic-settings
  schemas.py            # Request/response models
  logging_db.py         # SQLite persistence
  data/docs/            # Markdown corpus
  data/vector_store/    # FAISS artifact + chunk metadata JSON
  ingestion/
  rag/
eval_cases/eval_cases.json
tests/
```

---

## 10. AI-assisted vs personal design choices

**Assisted / accelerated with coding agents (Cursor + ChatGPT-class models):**

- Boilerplate scaffolding, FastAPI routing, pydantic validators, SQLite helpers  
- Glue code for Gemini OpenAI-compat edge cases (fence stripping, heterogeneous `content`)  
- Test harness scaffolding and evaluator structure  

**Personally owned product decisions:**

- Chunking heuristic (overlap + soft boundaries vs aggressive hard splits)  
- Validation/error tokens and deterministic fallback behaviour tuned for interviewer narrative  
- Sample policy corpus wording + eval assertions aligned to those documents  
- Trade-offs: sentence-transformers + FAISS for offline demo vs cloud-only embeddings  

Treat LLM-produced prose in policy docs **as synthetic** — replace with sanitized internal samples before any real regulated use.

---

## Security & OSS hygiene

- **Never commit `.env`** (listed in `.gitignore`). Rotate keys leaked in chat or screen shares.  
- Default **MIT License** (`LICENSE`) for portfolio cloning; swap if employer policy conflicts.  

---

## License

See [`LICENSE`](./LICENSE).
