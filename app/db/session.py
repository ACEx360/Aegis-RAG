"""Database engine, session factory, and FastAPI dependency.

Separated from models.py so tests can override get_db with an in-memory
SQLite engine using StaticPool without circular imports.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base
from app.settings import settings

engine = create_engine(
    settings.db_url,
    connect_args={"check_same_thread": False},
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — yields a DB session, closes it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables if they don't already exist and ensure columns exist."""
    Base.metadata.create_all(bind=engine)

    # Lightweight SQLite column migration for dev environments
    with engine.connect() as conn:
        try:
            result = conn.exec_driver_sql("PRAGMA table_info(emails)").fetchall()
            existing_cols = {row[1] for row in result}
            if existing_cols:
                if "links" not in existing_cols:
                    conn.exec_driver_sql("ALTER TABLE emails ADD COLUMN links TEXT DEFAULT '[]'")
                if "priority_score" not in existing_cols:
                    conn.exec_driver_sql("ALTER TABLE emails ADD COLUMN priority_score FLOAT")
                if "priority_label" not in existing_cols:
                    conn.exec_driver_sql("ALTER TABLE emails ADD COLUMN priority_label VARCHAR")
                if "fraud_score" not in existing_cols:
                    conn.exec_driver_sql("ALTER TABLE emails ADD COLUMN fraud_score FLOAT")
                conn.commit()
        except Exception:
            pass


def reprocess_stored_emails(db: Session) -> int:
    """Reprocess stored emails so old rows get derived body_text and links.

    Idempotent: only modifies and commits rows whose values actually change.
    """
    import html
    import json
    from app.db.models import Email
    from app.ingest.normalizer import derive_body_text_from_html, extract_all_links

    emails = db.query(Email).all()
    updated_count = 0

    for email in emails:
        changed = False

        # 1. html.unescape subject and snippet
        if email.subject:
            unescaped_sub = html.unescape(email.subject)
            if unescaped_sub != email.subject:
                email.subject = unescaped_sub
                changed = True

        if email.snippet:
            unescaped_snip = html.unescape(email.snippet)
            if unescaped_snip != email.snippet:
                email.snippet = unescaped_snip
                changed = True

        # 2. Derive body_text if empty and body_html exists
        if (not email.body_text or not email.body_text.strip()) and email.body_html:
            derived_text = derive_body_text_from_html(email.body_html)
            if derived_text and derived_text != email.body_text:
                email.body_text = derived_text
                changed = True

        # 3. Extract links from HTML and plain text
        extracted_links = extract_all_links(
            body_html=email.body_html or "",
            body_text=email.body_text or "",
        )
        current_links_json = email.links or "[]"
        try:
            current_links = json.loads(current_links_json)
        except Exception:
            current_links = []

        if extracted_links != current_links:
            email.links = json.dumps(extracted_links)
            changed = True

        if changed:
            updated_count += 1

    if updated_count > 0:
        db.commit()

    return updated_count
