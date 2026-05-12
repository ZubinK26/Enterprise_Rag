from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LoadedDocument:
    doc_id: str
    source_file: str
    text: str


def _normalize_text(raw: str) -> str:
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def load_markdown_docs(docs_dir: Path) -> list[LoadedDocument]:
    """Load all ``*.md`` and ``*.txt`` files under ``docs_dir`` (non-recursive)."""

    docs_dir = docs_dir.expanduser().resolve()
    if not docs_dir.is_dir():
        return []

    documents: list[LoadedDocument] = []
    paths = sorted(
        list(docs_dir.glob("*.md")) + list(docs_dir.glob("*.txt")), key=lambda p: p.name
    )
    for path in paths:
        if path.name.startswith("."):
            continue
        raw = path.read_text(encoding="utf-8")
        normalized = _normalize_text(raw)
        if not normalized:
            continue
        documents.append(
            LoadedDocument(
                doc_id=path.stem.lower(),
                source_file=path.name,
                text=normalized,
            )
        )

    return documents
