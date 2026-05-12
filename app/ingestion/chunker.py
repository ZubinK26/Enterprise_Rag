from __future__ import annotations

import re


def _collapse_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def chunk_document(
    text: str,
    *,
    min_chars: int = 500,
    max_chars: int = 800,
    overlap: int = 100,
) -> list[str]:
    """
    Split policy text into overlapping chunks.

    Target window is ``min_chars``–``max_chars`` where possible, with
    ``overlap`` characters carried into the next chunk.
    """

    text = _collapse_whitespace(text)
    if not text:
        return []

    out: list[str] = []
    start = 0
    n = len(text)

    while start < n:
        if n - start <= max_chars:
            piece = text[start:n].strip()
            if piece:
                out.append(piece)
            break

        end_limit = min(start + max_chars, n)
        search_lo = start + min_chars
        window = text[search_lo:end_limit]
        split_at = end_limit

        for sep in ("\n\n", "\n", " "):
            pos = window.rfind(sep)
            if pos == -1:
                continue
            candidate = search_lo + pos + len(sep)
            if candidate <= end_limit and candidate - start >= min_chars:
                split_at = candidate
                break

        piece = text[start:split_at].strip()
        if piece:
            out.append(piece)

        if split_at >= n:
            break

        next_start = split_at - overlap
        if next_start <= start:
            next_start = split_at
        start = next_start

    return out
