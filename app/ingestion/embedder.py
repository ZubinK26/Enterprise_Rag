from __future__ import annotations

import numpy as np

from app.config import Settings

_DEFAULT_MODEL = "all-MiniLM-L6-v2"

_model = None
_model_name: str | None = None


def resolve_embedding_model_name(settings: Settings) -> str:
    name = (settings.embedding_model or "").strip()
    return name or _DEFAULT_MODEL


def get_sentence_embedder(settings: Settings):
    """Lazily load a ``sentence-transformers`` model (cached per model name)."""

    global _model, _model_name
    target = resolve_embedding_model_name(settings)
    if _model is None or _model_name != target:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(target)
        _model_name = target
    return _model


def embed_texts(model, texts: list[str], *, batch_size: int = 32) -> np.ndarray:
    """Return L2-normalized float32 embeddings shaped ``(len(texts), dim)``."""

    if not texts:
        return np.zeros((0, 0), dtype=np.float32)
    vectors = model.encode(
        texts,
        batch_size=batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return np.asarray(vectors, dtype=np.float32)
