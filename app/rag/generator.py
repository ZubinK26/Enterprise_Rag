from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.config import Settings

_SYSTEM_PROMPT = """You are an enterprise policy assistant.

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
"""


def _strip_code_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _chat_completions_url(settings: Settings) -> str:
    return settings.llm_base_url.rstrip("/") + "/chat/completions"


def call_llm_json(
    settings: Settings,
    *,
    user_prompt: str,
    use_response_format: bool = True,
    timeout_s: float = 120.0,
) -> str:
    if not settings.llm_api_key.strip():
        raise RuntimeError("LLM_API_KEY is not configured")

    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    body: dict[str, Any] = {
        "model": settings.llm_model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    }
    if use_response_format:
        body["response_format"] = {"type": "json_object"}

    with httpx.Client(timeout=timeout_s) as client:
        response = client.post(_chat_completions_url(settings), headers=headers, json=body)

    if response.status_code >= 400:
        if use_response_format and response.status_code in (400, 422):
            return call_llm_json(
                settings,
                user_prompt=user_prompt,
                use_response_format=False,
                timeout_s=timeout_s,
            )
        response.raise_for_status()

    payload = response.json()
    try:
        return _assistant_text(payload)
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise RuntimeError("Unexpected LLM response shape") from exc


def _assistant_text(payload: dict[str, Any]) -> str:
    """Normalize chat-completions payloads (OpenAI + Gemini-compatible)."""

    choices = payload.get("choices")
    if not choices:
        raise ValueError("missing choices")
    message = choices[0].get("message") or choices[0].get("delta") or {}
    content = message.get("content")

    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                if part.get("type") == "text" and isinstance(part.get("text"), str):
                    parts.append(str(part["text"]))
                elif isinstance(part.get("text"), str):
                    parts.append(str(part["text"]))
                elif isinstance(part.get("content"), str):
                    parts.append(str(part["content"]))
        text = "".join(parts)
    else:
        raise ValueError("unsupported message content type")

    if not text.strip():
        raise ValueError("empty assistant content")
    return text


def build_initial_user_prompt(*, question: str, context: str) -> str:
    return (
        f"User question:\n{question}\n\n"
        f"Retrieved context:\n{context}\n\n"
        "Remember: output JSON only."
    )


def parse_llm_text_to_dict(text: str) -> dict[str, Any]:
    cleaned = _strip_code_fences(text)
    return json.loads(cleaned)
