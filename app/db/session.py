"""Database engine, session factory, and FastAPI dependency.

Separated from models.py so tests can override get_db with an in-memory
SQLite engine using StaticPool without circular imports.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base
from app.settings import settings

engine = create_engine(
    settings.db_url,
    connect_args={"check_same_thread": False, "timeout": 30.0},
    echo=False,
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable WAL mode, 30s busy timeout, and NORMAL synchronous on SQLite connections."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA synchronous=NORMAL")
    except Exception:
        pass
    finally:
        cursor.close()


SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Generator[Session]:
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
                if "priority_reason" not in existing_cols:
                    conn.exec_driver_sql("ALTER TABLE emails ADD COLUMN priority_reason TEXT")
                if "priority_evidence" not in existing_cols:
                    conn.exec_driver_sql("ALTER TABLE emails ADD COLUMN priority_evidence TEXT DEFAULT '[]'")
                if "embedding" not in existing_cols:
                    conn.exec_driver_sql("ALTER TABLE emails ADD COLUMN embedding TEXT")
                if "is_rag_indexed" not in existing_cols:
                    conn.exec_driver_sql("ALTER TABLE emails ADD COLUMN is_rag_indexed BOOLEAN DEFAULT 0")
                if "fraud_score" not in existing_cols:
                    conn.exec_driver_sql("ALTER TABLE emails ADD COLUMN fraud_score FLOAT")
                if "fraud_label" not in existing_cols:
                    conn.exec_driver_sql("ALTER TABLE emails ADD COLUMN fraud_label VARCHAR")
                if "fraud_reason" not in existing_cols:
                    conn.exec_driver_sql("ALTER TABLE emails ADD COLUMN fraud_reason TEXT")
                if "fraud_layers" not in existing_cols:
                    conn.exec_driver_sql("ALTER TABLE emails ADD COLUMN fraud_layers TEXT DEFAULT '[]'")
                if "fraud_evidence" not in existing_cols:
                    conn.exec_driver_sql("ALTER TABLE emails ADD COLUMN fraud_evidence TEXT DEFAULT '[]'")
                if "fraud_version" not in existing_cols:
                    conn.exec_driver_sql("ALTER TABLE emails ADD COLUMN fraud_version VARCHAR")
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
        if not email.body_text or not email.body_text.strip():
            derived_text = ""
            if email.body_html:
                derived_text = derive_body_text_from_html(email.body_html)
            if not derived_text or not derived_text.strip():
                # Fallback to snippet (§BUG 2)
                derived_text = email.snippet or ""
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
