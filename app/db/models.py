"""SQLite models — emails and LLM cache.

Uses SQLAlchemy 2.0 declarative style (Mapped[] + mapped_column) with
timezone-aware UTC datetimes throughout.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import DateTime, Float, String, Text, TypeDecorator, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> dt.datetime:
    """Timezone-aware UTC timestamp for default column values."""
    return dt.datetime.now(dt.UTC)


class UTCDateTime(TypeDecorator):
    """DateTime type that guarantees timezone-aware UTC datetimes on SQLite."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is not None:
            if isinstance(value, dt.datetime):
                if value.tzinfo is None:
                    value = value.replace(tzinfo=dt.UTC)
                else:
                    value = value.astimezone(dt.UTC)
        return value

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is not None and isinstance(value, dt.datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=dt.UTC)
        return value


class Base(DeclarativeBase):
    """Shared base for all ORM models."""


class Email(Base):
    """An ingested email — from Gmail or the built-in demo set."""

    __tablename__ = "emails"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    gmail_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    thread_id: Mapped[str | None] = mapped_column(String, default=None)
    subject: Mapped[str] = mapped_column(String, default="")
    sender: Mapped[str] = mapped_column(String, default="")
    # JSON-encoded list[str]
    recipients: Mapped[str] = mapped_column(Text, default="[]")
    date: Mapped[dt.datetime | None] = mapped_column(UTCDateTime, default=None)
    body_text: Mapped[str] = mapped_column(Text, default="")
    body_html: Mapped[str] = mapped_column(Text, default="")
    snippet: Mapped[str] = mapped_column(String, default="")
    # JSON-encoded list[dict[str, str]] — [{text, href}] (§Part A)
    links: Mapped[str] = mapped_column(Text, default="[]")
    # JSON-encoded list[str]
    labels: Mapped[str] = mapped_column(Text, default="[]")
    # JSON-encoded list[{name, value}] — preserves duplicate headers (§14)
    raw_headers: Mapped[str] = mapped_column(Text, default="[]")
    has_attachments: Mapped[bool] = mapped_column(default=False)
    # JSON-encoded list[dict]
    attachment_meta: Mapped[str] = mapped_column(Text, default="[]")
    # Gmail UNREAD label absent → is_read = True
    is_read: Mapped[bool] = mapped_column(default=False)
    is_demo: Mapped[bool] = mapped_column(default=False)
    # Set by POST /api/emails/{id}/open — NULL until user opens (§14)
    opened_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime, default=None)
    ingested_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=_utcnow)

    # Stage 3 Priority & RAG fields (§6, §Stage 3)
    priority_score: Mapped[float | None] = mapped_column(Float, default=None)
    priority_label: Mapped[str | None] = mapped_column(String, default=None)
    priority_reason: Mapped[str | None] = mapped_column(Text, default=None)
    priority_evidence: Mapped[str] = mapped_column(Text, default="[]")  # JSON list[str] of numbered facts
    embedding: Mapped[str | None] = mapped_column(Text, default=None)  # JSON-encoded float vector
    is_rag_indexed: Mapped[bool] = mapped_column(default=False)

    # Stage 4 Fraud fields (§7, §16)
    fraud_score: Mapped[float | None] = mapped_column(Float, default=None)
    fraud_label: Mapped[str | None] = mapped_column(String, default=None)
    fraud_reason: Mapped[str | None] = mapped_column(Text, default=None)
    fraud_layers: Mapped[str] = mapped_column(Text, default="[]")  # JSON list[dict] of layer results
    fraud_evidence: Mapped[str] = mapped_column(Text, default="[]")  # JSON list[str] of numbered facts
    fraud_version: Mapped[str | None] = mapped_column(String, default=None)


class LLMCache(Base):
    """Cache for Gemini outputs, keyed by email + task + prompt version.

    Why prompt_version: lets us invalidate caches when we change prompts
    without manually purging the table (§14).
    """

    __tablename__ = "llm_cache"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    gmail_id: Mapped[str] = mapped_column(String, index=True)
    task_type: Mapped[str] = mapped_column(String)
    prompt_version: Mapped[str] = mapped_column(String)
    response_json: Mapped[str] = mapped_column(Text)
    model_name: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=_utcnow)

    __table_args__ = (
        UniqueConstraint(
            "gmail_id", "task_type", "prompt_version", name="uq_cache_key"
        ),
    )
