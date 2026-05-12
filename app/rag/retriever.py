from __future__ import annotations

from collections.abc import Sequence

from app.config import Settings
from app.ingestion.embedder import embed_texts, get_sentence_embedder
from app.ingestion.vector_store import ChunkRecord, FaissVectorStore


def retrieve_chunks(
    store: FaissVectorStore,
    settings: Settings,
    question: str,
    *,
    top_k: int,
) -> list[tuple[ChunkRecord, float]]:
    model = get_sentence_embedder(settings)
    vector = embed_texts(model, [question])
    if vector.size == 0:
        return []
    return store.search(vector[0], top_k=top_k)


def format_retrieved_context(chunks: Sequence[tuple[ChunkRecord, float]]) -> str:
    blocks: list[str] = []
    for record, _score in chunks:
        blocks.append(
            f"[source_file={record.source_file} chunk_id={record.chunk_id}]\n"
            f"{record.text}"
        )
    return "\n\n---\n\n".join(blocks)
