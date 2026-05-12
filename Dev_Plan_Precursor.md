Below is a Cursor-ready dev plan. Give it this as the project spec.

---

# Dev Plan: Enterprise RAG + Agent Evaluator

## Goal

Build a small FastAPI app that demonstrates:

* document ingestion
* chunking
* retrieval
* RAG answer generation
* structured JSON output
* Pydantic validation
* repair loop for invalid outputs
* source references
* `/query` and `/evaluate` endpoints
* run logging with pass/fail outcomes

This is a portfolio/interview demo for a Junior GenAI Engineer role.

---

# Tech stack

Use:

* Python 3.11+
* FastAPI
* Uvicorn
* Pydantic
* SQLite
* sentence-transformers or OpenAI/Gemini embeddings
* FAISS or Chroma
* OpenAI/Gemini/Anthropic-compatible LLM client
* pytest

Prefer simple and explainable over complex.

---

# Project structure

```text
enterprise-rag-agent-evaluator/
  app/
    main.py
    config.py

    schemas.py
    logging_db.py

    ingestion/
      loader.py
      chunker.py
      embedder.py
      vector_store.py

    rag/
      retriever.py
      generator.py
      validator.py
      repairer.py
      evaluator.py

    data/
      docs/
        policy_security.md
        policy_expenses.md
        policy_support.md
        policy_data_privacy.md
        policy_it_access.md
      vector_store/
      logs.db

  tests/
    test_chunker.py
    test_validator.py
    test_evaluator.py

  eval_cases/
    eval_cases.json

  README.md
  requirements.txt
  .env.example
```

---

# Core behavior

## 1. Ingest documents

Endpoint:

```text
POST /ingest
```

Behavior:

* read 3–5 markdown/text documents from `app/data/docs`
* split into chunks
* assign each chunk:

  * `doc_id`
  * `source_file`
  * `chunk_id`
  * `text`
* embed chunks
* store in vector DB

Keep chunking simple:

* 500–800 characters per chunk
* 100-character overlap

---

## 2. Query documents

Endpoint:

```text
POST /query
```

Request:

```json
{
  "question": "Can employees expense client dinners?",
  "top_k": 3
}
```

Flow:

```text
question
→ retrieve top_k chunks
→ generate structured answer
→ validate with Pydantic
→ if invalid, repair once
→ return answer + citations + validation status
→ log run
```

Response schema:

```json
{
  "answer": "Yes, but only if...",
  "confidence": 0.82,
  "sources": [
    {
      "source_file": "policy_expenses.md",
      "chunk_id": "policy_expenses_003",
      "quote": "Client meals may be reimbursed..."
    }
  ],
  "needs_human_review": false,
  "reasoning_summary": "The retrieved expense policy allows client dinners under conditions.",
  "validation": {
    "passed": true,
    "errors": [],
    "repair_attempted": false
  }
}
```

---

# Pydantic schemas

Create strict schemas.

## SourceReference

Fields:

* `source_file: str`
* `chunk_id: str`
* `quote: str`

## RAGAnswer

Fields:

* `answer: str`
* `confidence: float` between 0 and 1
* `sources: list[SourceReference]`
* `needs_human_review: bool`
* `reasoning_summary: str`

Validation rules:

* `answer` cannot be empty
* `sources` must contain at least one source
* `confidence < 0.6` implies `needs_human_review = true`
* each quote must appear in retrieved context, or mark validation failed

---

# Generator

The LLM must output JSON only.

Prompt pattern:

```text
You are an enterprise policy assistant.

Answer the user question using only the retrieved context.

Return valid JSON matching this schema:
{
  "answer": string,
  "confidence": number between 0 and 1,
  "sources": [
    {
      "source_file": string,
      "chunk_id": string,
      "quote": string
    }
  ],
  "needs_human_review": boolean,
  "reasoning_summary": string
}

Rules:
- Do not use outside knowledge.
- Every factual claim must be supported by a source quote.
- If context is insufficient, say so and set needs_human_review=true.
- Output JSON only.
```

---

# Validator

Validation should check:

1. JSON parses.
2. Pydantic schema passes.
3. At least one source exists.
4. Source file and chunk ID exist in retrieved chunks.
5. Quote appears in retrieved chunk text.
6. Confidence is between 0 and 1.
7. Low confidence triggers human review.
8. If answer says insufficient context, human review should be true.

Return:

```json
{
  "passed": true,
  "errors": [],
  "repair_attempted": false
}
```

or:

```json
{
  "passed": false,
  "errors": [
    "quote_not_found_in_retrieved_context",
    "missing_sources"
  ],
  "repair_attempted": true
}
```

---

# Repair loop

If validation fails:

* send original output, validation errors, and retrieved context back to LLM
* ask for corrected JSON only
* validate again
* only one repair attempt

Repair prompt:

```text
Your previous answer failed validation.

Validation errors:
{errors}

Retrieved context:
{context}

Previous answer:
{bad_output}

Return corrected JSON only.
Do not invent sources.
Use only exact quotes from retrieved chunks.
```

If still invalid:

* return best safe fallback:

```json
{
  "answer": "I could not produce a validated answer from the available context.",
  "confidence": 0.0,
  "sources": [],
  "needs_human_review": true,
  "reasoning_summary": "Validation failed after one repair attempt."
}
```

---

# Evaluation endpoint

Endpoint:

```text
POST /evaluate
```

Request:

```json
{
  "case_file": "eval_cases/eval_cases.json"
}
```

Eval cases format:

```json
[
  {
    "id": "expense_001",
    "question": "Can employees expense client dinners?",
    "expected_source_file": "policy_expenses.md",
    "must_contain": ["client", "approval"],
    "should_need_human_review": false
  },
  {
    "id": "privacy_001",
    "question": "Can I export customer PII to a personal laptop?",
    "expected_source_file": "policy_data_privacy.md",
    "must_contain": ["PII", "not allowed"],
    "should_need_human_review": false
  }
]
```

Evaluation logic:

For each case:

* run `/query` internally
* check expected source appears
* check answer contains required terms
* check human review expectation
* check validation passed

Return:

```json
{
  "total": 5,
  "passed": 4,
  "failed": 1,
  "results": [
    {
      "id": "expense_001",
      "passed": true,
      "checks": {
        "expected_source_found": true,
        "must_contain_found": true,
        "human_review_correct": true,
        "validation_passed": true
      }
    }
  ]
}
```

---

# Logging

Use SQLite.

Create table `runs`:

Fields:

* `id`
* `timestamp`
* `question`
* `answer`
* `confidence`
* `needs_human_review`
* `sources_json`
* `validation_passed`
* `validation_errors_json`
* `repair_attempted`
* `latency_ms`

Add endpoint:

```text
GET /runs
```

Optional but useful.

---

# Sample documents

Create 5 short documents:

1. `policy_security.md`

   * password rules
   * MFA
   * device access

2. `policy_expenses.md`

   * travel
   * client meals
   * approvals
   * reimbursement limits

3. `policy_support.md`

   * support ticket priority
   * escalation
   * response times

4. `policy_data_privacy.md`

   * PII handling
   * GDPR
   * export restrictions
   * retention

5. `policy_it_access.md`

   * admin access
   * onboarding/offboarding
   * temporary permissions

Keep each around 500–1000 words.

---

# README must include

Sections:

1. What this project demonstrates
2. Architecture
3. Why validation matters
4. Endpoints
5. Example query
6. Example validated answer
7. Evaluation results
8. Failure modes handled
9. How to run
10. What was AI-assisted vs personally designed

Architecture text:

```text
Documents
→ chunking
→ embeddings
→ vector store
→ retrieval
→ structured LLM answer
→ Pydantic validation
→ quote/source grounding check
→ repair loop
→ logged answer
→ eval harness
```

---

# Acceptance criteria

Project is done when:

* `/ingest` works
* `/query` returns structured answer with sources
* invalid/malformed LLM output is repaired or safely rejected
* `/evaluate` runs at least 5 test cases
* SQLite logs runs
* README explains architecture and limitations
* at least 3 pytest tests pass
* repo can run locally with simple commands

---

# Minimal commands

README should support:

```bash
python -m venv .venv
source .venv/bin/activate  # or Windows equivalent
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Then:

```bash
curl -X POST http://localhost:8000/ingest
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question":"Can employees expense client dinners?","top_k":3}'
curl -X POST http://localhost:8000/evaluate \
  -H "Content-Type: application/json" \
  -d '{"case_file":"eval_cases/eval_cases.json"}'
```

---

# Keep it interview-useful

Do not overbuild.

The point is to show:

* RAG
* REST API
* validation
* repair loop
* eval harness
* logging
* explainability
* Cursor-assisted development

This is enough for Accenture.
