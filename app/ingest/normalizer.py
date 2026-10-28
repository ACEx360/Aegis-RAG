"""Converts a raw Gmail API message dict into a clean EmailSchema.

Why a separate module: the normalizer is the only place that knows the
Gmail API response shape.  Everything downstream works with EmailSchema,
which makes testing and demo-mode trivial.
"""

from __future__ import annotations

import base64
import datetime as dt
from email.utils import parsedate_to_datetime

from app.ingest.schemas import EmailSchema, HeaderPair


def normalize_message(raw: dict) -> EmailSchema:
    """Convert a Gmail API message resource into an EmailSchema.

    Handles multipart bodies, base64 decoding, attachment metadata,
    and preserves ALL headers as a list of {name, value} pairs.
    """
    payload = raw.get("payload", {})
    headers_raw: list[dict] = payload.get("headers", [])

    # Preserve every header as a {name, value} pair (duplicates kept, §14)
    raw_headers = [
        HeaderPair(name=h["name"], value=h["value"]) for h in headers_raw
    ]

    # Build a first-occurrence lookup for common fields
    header_lookup: dict[str, str] = {}
    for h in headers_raw:
        key = h["name"].lower()
        if key not in header_lookup:
            header_lookup[key] = h["value"]

    subject = header_lookup.get("subject", "")
    sender = header_lookup.get("from", "")
    to_raw = header_lookup.get("to", "")
    recipients = [r.strip() for r in to_raw.split(",") if r.strip()]
    date = _parse_date(header_lookup.get("date", ""))

    labels: list[str] = raw.get("labelIds", [])
    is_read = "UNREAD" not in labels

    body_text, body_html = _extract_body(payload)
    attachments = _extract_attachments(payload)

    return EmailSchema(
        gmail_id=raw["id"],
        thread_id=raw.get("threadId"),
        subject=subject,
        sender=sender,
        recipients=recipients,
        date=date,
        body_text=body_text,
        body_html=body_html,
        snippet=raw.get("snippet", ""),
        labels=labels,
        raw_headers=raw_headers,
        has_attachments=len(attachments) > 0,
        attachment_meta=attachments,
        is_read=is_read,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_date(date_str: str) -> dt.datetime | None:
    """Parse an RFC-2822 date string into a timezone-aware datetime."""
    if not date_str:
        return None
    try:
        parsed = parsedate_to_datetime(date_str)
        # Ensure timezone-aware
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed
    except (ValueError, TypeError):
        return None


def _extract_body(payload: dict) -> tuple[str, str]:
    """Walk the MIME tree and return (plain_text, html) bodies."""
    text = ""
    html = ""

    mime_type = payload.get("mimeType", "")

    if mime_type == "text/plain":
        text = _decode_body_data(payload.get("body", {}))
    elif mime_type == "text/html":
        html = _decode_body_data(payload.get("body", {}))
    elif mime_type.startswith("multipart/"):
        for part in payload.get("parts", []):
            part_text, part_html = _extract_body(part)
            if part_text and not text:
                text = part_text
            if part_html and not html:
                html = part_html

    return text, html


def _decode_body_data(body: dict) -> str:
    """Decode a Gmail body.data field (URL-safe base64)."""
    data = body.get("data", "")
    if not data:
        return ""
    # Gmail uses URL-safe base64 without padding
    try:
        return base64.urlsafe_b64decode(data + "==").decode(
            "utf-8", errors="replace"
        )
    except Exception:
        return ""


def _extract_attachments(payload: dict) -> list[dict]:
    """Collect attachment metadata from the MIME tree."""
    attachments: list[dict] = []
    _walk_parts(payload, attachments)
    return attachments


def _walk_parts(part: dict, attachments: list[dict]) -> None:
    """Recursively walk MIME parts looking for attachments."""
    filename = part.get("filename", "")
    if filename:
        attachments.append(
            {
                "filename": filename,
                "mimeType": part.get("mimeType", ""),
                "size": part.get("body", {}).get("size", 0),
            }
        )
    for sub_part in part.get("parts", []):
        _walk_parts(sub_part, attachments)
