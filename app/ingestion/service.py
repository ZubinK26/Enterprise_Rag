from __future__ import annotations

from time import perf_counter

from app.config import Settings
from app.ingestion.chunker import chunk_document
from app.ingestion.embedder import (
    embed_texts,
    get_sentence_embedder,
    resolve_embedding_model_name,
)
from app.ingestion.loader import load_markdown_docs
from app.ingestion.vector_store import ChunkRecord, write_store
from app.schemas import IngestResponse


def run_ingest(settings: Settings) -> IngestResponse:
    """
    Load corpus documents, chunk, embed, and replace the persisted FAISS index.
    """

    start = perf_counter()
    docs = load_markdown_docs(settings.docs_dir)
    if not docs:
        raise ValueError(
            f"No markdown or text documents found in {settings.docs_dir}. "
            "Add files with extension .md or .txt and try again."
        )

    records: list[ChunkRecord] = []
    for doc in docs:
        for idx, chunk_text in enumerate(chunk_document(doc.text), start=1):
            chunk_id = f"{doc.doc_id}_{idx:03d}"
            records.append(
                ChunkRecord(
                    doc_id=doc.doc_id,
                    source_file=doc.source_file,
                    chunk_id=chunk_id,
                    text=chunk_text,
                )
            )

    if not records:
        raise ValueError("Documents loaded but chunking produced zero chunks.")

    model = get_sentence_embedder(settings)
    embeddings = embed_texts(model, [r.text for r in records])
    write_store(settings.vector_store_dir, embeddings, records)

    elapsed = perf_counter() - start
    return IngestResponse(
        documents_loaded=len(docs),
        chunks_indexed=len(records),
        embedding_model=resolve_embedding_model_name(settings),
        seconds=round(elapsed, 3),
    )
