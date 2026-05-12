from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import faiss
import numpy as np


@dataclass(frozen=True)
class ChunkRecord:
    doc_id: str
    source_file: str
    chunk_id: str
    text: str


@dataclass
class FaissVectorStore:
    index: faiss.Index
    records: list[ChunkRecord]

    def search(self, query_vector: np.ndarray, top_k: int) -> list[tuple[ChunkRecord, float]]:
        if self.index.ntotal == 0 or top_k <= 0:
            return []
        k = min(top_k, self.index.ntotal)
        q = np.asarray(query_vector, dtype=np.float32).reshape(1, -1)
        scores, idxs = self.index.search(q, k)
        results: list[tuple[ChunkRecord, float]] = []
        for score, idx in zip(scores[0].tolist(), idxs[0].tolist(), strict=True):
            if idx == -1:
                continue
            results.append((self.records[int(idx)], float(score)))
        return results


INDEX_FILENAME = "index.faiss"
METADATA_FILENAME = "metadata.json"


def write_store(out_dir: Path, embeddings: np.ndarray, records: list[ChunkRecord]) -> None:
    if embeddings.ndim != 2:
        raise ValueError("embeddings must be a 2D matrix")
    if embeddings.shape[0] != len(records):
        raise ValueError("embeddings row count must match records length")

    out_dir.mkdir(parents=True, exist_ok=True)
    vectors = embeddings.astype(np.float32, copy=False)
    dimension = vectors.shape[1]

    index = faiss.IndexFlatIP(dimension)
    index.add(vectors)

    index_path = out_dir / INDEX_FILENAME
    meta_path = out_dir / METADATA_FILENAME
    tmp_index = index_path.with_suffix(".faiss.tmp")
    tmp_meta = meta_path.with_suffix(".json.tmp")

    faiss.write_index(index, str(tmp_index))
    tmp_meta.write_text(
        json.dumps([asdict(r) for r in records], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp_index.replace(index_path)
    tmp_meta.replace(meta_path)


def read_store(store_dir: Path) -> FaissVectorStore:
    index_path = store_dir / INDEX_FILENAME
    meta_path = store_dir / METADATA_FILENAME
    if not index_path.is_file() or not meta_path.is_file():
        raise FileNotFoundError("vector index or metadata missing; run /ingest first")

    index = faiss.read_index(str(index_path))
    rows = json.loads(meta_path.read_text(encoding="utf-8"))
    records = [ChunkRecord(**row) for row in rows]
    if index.ntotal != len(records):
        raise ValueError("FAISS index size does not match metadata length")

    return FaissVectorStore(index=index, records=records)


def load_or_none(store_dir: Path) -> FaissVectorStore | None:
    try:
        return read_store(store_dir)
    except FileNotFoundError:
        return None
