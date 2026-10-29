"""RAG history indexing and user contact discovery.

Requirements:
- On sync, index up to ~200 recent emails as history (separate from sync window).
- Embed subject + sender + first ~500 chars of body_text.
- Derive 'people the user writes to' from SENT label / sent contacts without consuming SYNC_MAX.
- Demo mode provides built-in past history and known contacts so RAG works without Gmail.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.db.models import Email
from app.ingest.gmail_client import gmail_client
from app.rag.vector_store import index_email
from app.settings import settings

logger = logging.getLogger(__name__)

# Built-in sent contacts for Demo mode (§Stage 3)
DEMO_SENT_CONTACTS: set[str] = {
    "priya@workspace.example.com",
    "alex.r@workspace.example.com",
    "lead@workspace.example.com",
    "s.chen@university.example.edu",
    "mom@family.example.com",
    "ravi.k@personal.example.com",
    "anita@personal.example.com",
}

_cached_real_contacts: set[str] | None = None


def get_known_contacts(is_demo: bool) -> set[str]:
    """Return the set of lowercased email addresses the user has written to."""
    global _cached_real_contacts
    if is_demo:
        return DEMO_SENT_CONTACTS

    if _cached_real_contacts is not None:
        return _cached_real_contacts

    try:
        contacts = gmail_client.fetch_sent_contacts(days=settings.sent_days)
        _cached_real_contacts = contacts
        return contacts
    except Exception as exc:
        logger.warning("Could not fetch sent contacts from Gmail: %s", exc)
        return set()


def refresh_known_contacts() -> set[str]:
    """Force re-fetch of sent contacts from Gmail."""
    global _cached_real_contacts
    _cached_real_contacts = None
    return get_known_contacts(is_demo=False)


def index_history_emails(db: Session, is_demo: bool) -> int:
    """Index unindexed past emails into the vector store.

    Returns the count of newly indexed emails.
    """
    unindexed = (
        db.query(Email)
        .filter(
            Email.is_demo == is_demo,
            Email.is_rag_indexed == False,
        )
        .limit(settings.rag_history_max)
        .all()
    )

    count = 0
    for email in unindexed:
        index_email(email, db)
        count += 1

    if count > 0:
        db.commit()

    return count

