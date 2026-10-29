"""Local vector search using NumPy cosine similarity over stored embeddings.

Design:
- Uses SQLite to store embeddings and metadata.
- Similarity computed directly with NumPy dot products over normalized vectors.
- No FAISS dependency needed.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from app.db.models import Email
from app.rag.embeddings import embed_text
from app.settings import settings

logger = logging.getLogger(__name__)


def build_email_rag_text(email: Email) -> str:
    """Format an email into standard text representation for embedding."""
    body_snippet = (email.body_text or "")[: settings.max_body_chars_for_rag].strip()
    return f"Subject: {email.subject} | From: {email.sender} | {body_snippet}"


def index_email(email: Email, db: Session) -> None:
    """Compute and store embedding for a single email if not already indexed."""
    if email.embedding and email.is_rag_indexed:
        return
    text = build_email_rag_text(email)
    vec = embed_text(text)
    email.embedding = json.dumps(vec)
    email.is_rag_indexed = True


def search_similar_emails(
    query_text: str,
    db: Session,
    is_demo: bool,
    top_k: int = 3,
    exclude_gmail_id: str | None = None,
) -> list[tuple[Email, float]]:
    """Find top-k most similar past emails using NumPy cosine similarity.

    Returns list of (Email, similarity_score) tuples, highest similarity first.
    """
    try:
        import numpy as np
    except ImportError:
        logger.warning("NumPy not available for vector search.")
        return []

    # Fetch candidate emails with embeddings
    query = (
        db.query(Email)
        .filter(
            Email.is_demo == is_demo,
            Email.embedding.isnot(None),
        )
    )
    if exclude_gmail_id:
        query = query.filter(Email.gmail_id != exclude_gmail_id)

    candidates = query.all()
    if not candidates:
        return []

    vectors: list[list[float]] = []
    valid_candidates: list[Email] = []

    for em in candidates:
        try:
            vec = json.loads(em.embedding)  # type: ignore[arg-type]
            if isinstance(vec, list) and len(vec) > 0:
                vectors.append(vec)
                valid_candidates.append(em)
        except Exception:
            continue

    if not valid_candidates:
        return []

    query_vec = embed_text(query_text)
    q_arr = np.array(query_vec, dtype=np.float32)
    matrix = np.array(vectors, dtype=np.float32)

    # Cosine similarity for unit vectors is the dot product
    q_norm = np.linalg.norm(q_arr)
    if q_norm > 0:
        q_arr = q_arr / q_norm

    m_norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    m_norms[m_norms == 0] = 1e-8
    matrix = matrix / m_norms

    scores = np.dot(matrix, q_arr)

    # Top-k indices
    top_indices = np.argsort(scores)[::-1][:top_k]

    results: list[tuple[Email, float]] = []
    for idx in top_indices:
        results.append((valid_candidates[idx], float(scores[idx])))

    return results

