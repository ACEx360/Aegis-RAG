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
                if "priority_score" not in existing_cols:
                    conn.exec_driver_sql("ALTER TABLE emails ADD COLUMN priority_score FLOAT")
                if "priority_label" not in existing_cols:
                    conn.exec_driver_sql("ALTER TABLE emails ADD COLUMN priority_label VARCHAR")
                if "fraud_score" not in existing_cols:
                    conn.exec_driver_sql("ALTER TABLE emails ADD COLUMN fraud_score FLOAT")
                conn.commit()
        except Exception:
            pass
