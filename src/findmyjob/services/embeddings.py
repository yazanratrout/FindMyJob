"""Local sentence embeddings for semantic deduplication.

Uses ``fastembed`` (ONNX, CPU, no PyTorch). The model is downloaded once into
``data/models/`` on first use. If it cannot be loaded, callers fall back to
skipping the semantic tier — dedup still works on the exact + canonical-key
tiers.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np

from findmyjob.config import get_settings
from findmyjob.logging import get_logger

log = get_logger("embeddings")

DEFAULT_MODEL = "intfloat/multilingual-e5-small"  # 384-dim, DE + EN


@runtime_checkable
class Embedder(Protocol):
    dim: int
    model_version: str

    def embed(self, texts: list[str]) -> np.ndarray: ...


class FastEmbedEmbedder:
    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        from fastembed import TextEmbedding

        settings = get_settings()
        settings.models_dir.mkdir(parents=True, exist_ok=True)
        self._model = TextEmbedding(model_name=model_name, cache_dir=str(settings.models_dir))
        self.model_version = model_name
        self.dim = len(next(iter(self._model.embed(["probe"]))))

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        return np.asarray(list(self._model.embed(texts)), dtype=np.float32)


_cached: Embedder | None = None
_load_failed = False


def get_embedder() -> Embedder | None:
    """Return a shared embedder, or ``None`` if it cannot be loaded."""
    global _cached, _load_failed
    if _cached is not None:
        return _cached
    if _load_failed:
        return None
    try:
        _cached = FastEmbedEmbedder()
        return _cached
    except Exception as exc:  # missing model / offline / import error
        log.warning("embeddings.unavailable", error=str(exc))
        _load_failed = True
        return None


def cosine_matrix(vectors: np.ndarray) -> np.ndarray:
    """Pairwise cosine similarity for a stack of row vectors."""
    if vectors.shape[0] == 0:
        return np.zeros((0, 0), dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    unit = vectors / norms
    return np.asarray(unit @ unit.T, dtype=np.float32)


def to_bytes(vector: np.ndarray) -> bytes:
    return np.asarray(vector, dtype=np.float32).tobytes()


def from_bytes(blob: bytes, dim: int) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32, count=dim).copy()
