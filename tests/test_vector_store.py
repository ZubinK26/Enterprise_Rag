from pathlib import Path

import faiss
import numpy as np

from app.ingestion.vector_store import ChunkRecord, read_store, write_store


def test_faiss_store_roundtrip_matches_metadata(tmp_path: Path) -> None:
    records = [
        ChunkRecord(
            doc_id="a",
            source_file="a.md",
            chunk_id="a_001",
            text="chunk one",
        ),
        ChunkRecord(
            doc_id="b",
            source_file="b.md",
            chunk_id="b_001",
            text="chunk two",
        ),
    ]

    rng = np.random.default_rng(0)
    matrix = rng.standard_normal((len(records), 8), dtype=np.float32)
    faiss.normalize_L2(matrix)

    write_store(tmp_path, matrix, records)
    store = read_store(tmp_path)

    assert store.index.ntotal == 2
    assert [r.chunk_id for r, _ in store.search(matrix[1], top_k=2)] == ["b_001", "a_001"]
