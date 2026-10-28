"""Pydantic schemas for email data flowing through the ingestion pipeline.

These are the *internal* data structures used between ingestion and the DB.
API response schemas live in app/api/schemas.py.
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class HeaderPair(BaseModel):
    """A single email header — kept as a pair to preserve duplicates
    like multiple Received headers (§14)."""

    name: str
    value: str


class EmailSchema(BaseModel):
    """Normalised email ready for storage.  Produced by the normalizer from
    a raw Gmail API message dict, or by the demo-email generator."""

    gmail_id: str
    thread_id: str | None = None
    subject: str = ""
    sender: str = ""
    recipients: list[str] = []
    date: dt.datetime | None = None
    body_text: str = ""
    body_html: str = ""
    snippet: str = ""
    labels: list[str] = []
    raw_headers: list[HeaderPair] = []
    has_attachments: bool = False
    attachment_meta: list[dict] = []
    is_read: bool = False
