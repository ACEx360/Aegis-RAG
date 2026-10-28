"""Tests for the Gmail message normalizer (app/ingest/normalizer.py)."""

from __future__ import annotations

import base64

from app.ingest.normalizer import normalize_message


def _b64_url(text: str) -> str:
    """Helper to URL-safe base64 encode a string."""
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii").rstrip("=")


def test_normalizer_basic_message():
    """Test standard single-part message normalization."""
    body_content = "Hello, this is a test email body."
    raw = {
        "id": "msg_001",
        "threadId": "thread_001",
        "labelIds": ["INBOX", "UNREAD"],
        "snippet": "Hello, this is a test...",
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "Subject", "value": "Test Subject"},
                {"name": "From", "value": "Alice <alice@example.com>"},
                {"name": "To", "value": "bob@example.com, charlie@example.com"},
                {"name": "Date", "value": "Tue, 27 Oct 2026 10:00:00 +0000"},
            ],
            "body": {
                "size": len(body_content),
                "data": _b64_url(body_content),
            },
        },
    }

    schema = normalize_message(raw)

    assert schema.gmail_id == "msg_001"
    assert schema.thread_id == "thread_001"
    assert schema.subject == "Test Subject"
    assert schema.sender == "Alice <alice@example.com>"
    assert schema.recipients == ["bob@example.com", "charlie@example.com"]
    assert schema.body_text == body_content
    assert schema.snippet == "Hello, this is a test..."
    assert schema.is_read is False  # UNREAD label present
    assert schema.date is not None
    assert schema.date.year == 2026


def test_normalizer_preserves_duplicate_headers():
    """Duplicate headers (e.g. Received) must be preserved as a list (§14)."""
    raw = {
        "id": "msg_002",
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "Received", "value": "by mx1.example.com"},
                {"name": "Received", "value": "by mx2.example.com"},
                {"name": "Subject", "value": "Multi-hop email"},
            ],
            "body": {"data": _b64_url("body")},
        },
    }

    schema = normalize_message(raw)
    received_headers = [h for h in schema.raw_headers if h.name == "Received"]

    assert len(received_headers) == 2
    assert received_headers[0].value == "by mx1.example.com"
    assert received_headers[1].value == "by mx2.example.com"


def test_normalizer_multipart_with_attachments():
    """Walk multipart MIME tree to extract text, html, and attachment metadata."""
    plain_text = "Plain text content"
    html_text = "<p>HTML content</p>"
    raw = {
        "id": "msg_003",
        "labelIds": ["INBOX"],  # No UNREAD label -> is_read = True
        "payload": {
            "mimeType": "multipart/mixed",
            "headers": [
                {"name": "Subject", "value": "Document attached"},
                {"name": "From", "value": "sender@example.com"},
            ],
            "parts": [
                {
                    "mimeType": "multipart/alternative",
                    "parts": [
                        {"mimeType": "text/plain", "body": {"data": _b64_url(plain_text)}},
                        {"mimeType": "text/html", "body": {"data": _b64_url(html_text)}},
                    ],
                },
                {
                    "mimeType": "application/pdf",
                    "filename": "report.pdf",
                    "body": {"size": 2048, "attachmentId": "att_123"},
                },
            ],
        },
    }

    schema = normalize_message(raw)

    assert schema.is_read is True
    assert schema.body_text == plain_text
    assert schema.body_html == html_text
    assert schema.has_attachments is True
    assert len(schema.attachment_meta) == 1
    assert schema.attachment_meta[0]["filename"] == "report.pdf"
    assert schema.attachment_meta[0]["mimeType"] == "application/pdf"
    assert schema.attachment_meta[0]["size"] == 2048


def test_normalizer_handles_malformed_gracefully():
    """Empty payload or missing fields should not raise exceptions."""
    raw = {"id": "msg_empty", "payload": {}}
    schema = normalize_message(raw)

    assert schema.gmail_id == "msg_empty"
    assert schema.subject == ""
    assert schema.sender == ""
    assert schema.body_text == ""
    assert schema.body_html == ""
    assert schema.raw_headers == []
    assert schema.has_attachments is False
