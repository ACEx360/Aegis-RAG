"""Tests for SQLite database models and constraints."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Base, Email, LLMCache


def test_email_creation_and_defaults(db_session: Session):
    """Test Email model creation with default values."""
    email = Email(
        gmail_id="test_msg_101",
        subject="Welcome to Aegis",
        sender="noreply@example.com",
    )
    db_session.add(email)
    db_session.commit()
    db_session.refresh(email)

    assert email.id is not None
    assert email.gmail_id == "test_msg_101"
    assert email.opened_at is None  # Defaults to None
    assert email.is_read is False
    assert email.is_demo is False
    assert email.ingested_at is not None
    assert email.ingested_at.tzinfo is not None  # Timezone-aware


def test_email_opened_at_tracking(db_session: Session):
    """Setting opened_at persists correctly."""
    email = Email(gmail_id="test_msg_102", subject="Important notification")
    db_session.add(email)
    db_session.commit()

    now = dt.datetime.now(dt.timezone.utc)
    email.opened_at = now
    db_session.commit()
    db_session.refresh(email)

    assert email.opened_at == now


def test_llm_cache_unique_constraint(db_session: Session):
    """LLMCache must enforce unique constraint on (gmail_id, task_type, prompt_version)."""
    entry1 = LLMCache(
        gmail_id="msg_cache_1",
        task_type="priority",
        prompt_version="v1",
        response_json='{"score": 85}',
    )
    db_session.add(entry1)
    db_session.commit()

    # Same key should fail with IntegrityError
    entry2 = LLMCache(
        gmail_id="msg_cache_1",
        task_type="priority",
        prompt_version="v1",
        response_json='{"score": 90}',
    )
    db_session.add(entry2)
    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()

    # Different prompt_version should succeed (§14)
    entry3 = LLMCache(
        gmail_id="msg_cache_1",
        task_type="priority",
        prompt_version="v2",
        response_json='{"score": 92}',
    )
    db_session.add(entry3)
    db_session.commit()
    assert entry3.id is not None


def test_concurrent_writes_do_not_lock(tmp_path):
    """Two concurrent sessions writing to SQLite with WAL and busy_timeout do not fail (§BUG 1)."""
    import threading
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker

    db_file = tmp_path / "test_concurrency.db"
    file_engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False, "timeout": 30.0},
    )

    @event.listens_for(file_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    Base.metadata.create_all(bind=file_engine)
    FileSession = sessionmaker(bind=file_engine, expire_on_commit=False)

    errors = []

    def writer(thread_id: int):
        session = FileSession()
        try:
            for i in range(10):
                email = Email(
                    gmail_id=f"thread_{thread_id}_msg_{i}",
                    subject=f"Subject from thread {thread_id} item {i}",
                )
                session.add(email)
                session.commit()
        except Exception as exc:
            errors.append(exc)
        finally:
            session.close()

    t1 = threading.Thread(target=writer, args=(1,))
    t2 = threading.Thread(target=writer, args=(2,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert not errors, f"Concurrent writes failed with errors: {errors}"

    check_session = FileSession()
    count = check_session.query(Email).count()
    check_session.close()
    assert count == 20

