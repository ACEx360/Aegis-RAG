"""Pydantic schemas for public API requests and responses.

Design notes:
- EmailListResponse: Lightweight representation for list views.
- EmailDetailResponse: Includes body_text and raw_headers, but excludes body_html
  by default to prevent accidental unsafe rendering (§14).
- is_unread: Computed property (True if unread in Gmail/demo AND opened_at is None).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.ingest.schemas import HeaderPair


class EmailListResponse(BaseModel):
    """Compact summary of an email for list views."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    gmail_id: str
    thread_id: str | None = None
    subject: str = ""
    sender: str = ""
    recipients: list[str] = Field(default_factory=list)
    date: dt.datetime | None = None
    snippet: str = ""
    labels: list[str] = Field(default_factory=list)
    has_attachments: bool = False
    is_read: bool = False
    is_demo: bool = False
    opened_at: dt.datetime | None = None
    ingested_at: dt.datetime
    priority_score: float | None = None
    priority_label: str | None = None
    fraud_score: float | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_unread(self) -> bool:
        """Unread = (not is_read or 'UNREAD' in labels) AND opened_at is None."""
        has_unread_label = "UNREAD" in self.labels if self.labels else (not self.is_read)
        return bool(has_unread_label and self.opened_at is None)


class EmailDetailResponse(EmailListResponse):
    """Full detail view of an email, excluding body_html by default (§14)."""

    body_text: str = ""
    links: list[dict[str, str]] = Field(default_factory=list)
    raw_headers: list[HeaderPair] = Field(default_factory=list)
    attachment_meta: list[dict[str, Any]] = Field(default_factory=list)


class OpenEmailResponse(BaseModel):
    id: int
    gmail_id: str
    opened_at: dt.datetime
    message: str


class SyncResponse(BaseModel):
    mode: str
    added: int
    updated: int
    total: int
    message: str


class AuthStatusResponse(BaseModel):
    authenticated: bool
    mode: str
    oauth_in_progress: bool
    credentials_present: bool
    token_present: bool
    error: str | None = None
