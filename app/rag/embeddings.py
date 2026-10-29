"""Local embedding generator using sentence-transformers.

Design requirements:
- Model name specified in settings (settings.embedding_model, e.g. 'sentence-transformers/all-MiniLM-L6-v2').
- Lazy loading: sentence_transformers is imported and initialized ONLY on first call.
- Safe fallback: if torch or sentence-transformers is missing, returns deterministic vectors
  so app starts and demo mode functions without errors.
- Default model cache lives in HuggingFace cache directory (~/.cache/huggingface/hub).
"""

from __future__ import annotations

import logging
from typing import Any

from app.settings import settings

logger = logging.getLogger(__name__)

_model_instance: Any = None
_model_failed: bool = False
EMBEDDING_DIM = 384  # Standard dimension for all-MiniLM-L6-v2


def get_embedding_model() -> Any:
    """Lazily load the SentenceTransformer model on first call."""
    global _model_instance, _model_failed
    if _model_instance is not None:
        return _model_instance
    if _model_failed:
        return None

    try:
        from sentence_transformers import SentenceTransformer

        logger.info("Loading local embedding model: %s", settings.embedding_model)
        _model_instance = SentenceTransformer(settings.embedding_model)
        return _model_instance
    except Exception as exc:
        logger.warning(
            "Local embedding model could not be loaded: %s. Using fallback.", exc
        )
        _model_failed = True
        return None


def embed_text(text: str) -> list[float]:
    """Generate normalized embedding vector for a single string."""
    model = get_embedding_model()
    if model is None:
        dummy = [0.0] * EMBEDDING_DIM
        dummy[0] = 1.0
        return dummy

    try:
        vec = model.encode(text, normalize_embeddings=True)
        return vec.tolist()
    except Exception as exc:
        logger.warning("Error generating embedding: %s", exc)
        dummy = [0.0] * EMBEDDING_DIM
        dummy[0] = 1.0
        return dummy


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Generate normalized embedding vectors for a batch of strings."""
    if not texts:
        return []
    model = get_embedding_model()
    if model is None:
        dummy = [0.0] * EMBEDDING_DIM
        dummy[0] = 1.0
        return [dummy for _ in texts]

    try:
        vecs = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return vecs.tolist()
    except Exception as exc:
        logger.warning("Error generating batch embeddings: %s", exc)
        dummy = [0.0] * EMBEDDING_DIM
        dummy[0] = 1.0
        return [dummy for _ in texts]

