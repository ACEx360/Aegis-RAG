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


def test_normalizer_html_only_derives_body_and_links():
    """If text/plain is missing or empty, derive body_text from HTML part safely."""
    html_content = (
        "<html><head><title>Ignored</title></head>"
        "<body>"
        "<script>evil_script();</script>"
        "<style>body { color: red; }</style>"
        "<h2>Important Notice</h2>"
        "<p>Please review your account at "
        "<a href=\"https://portal.example.com/dashboard\">Customer Portal</a> immediately.</p>"
        "</body></html>"
    )
    raw = {
        "id": "msg_html_only",
        "payload": {
            "mimeType": "text/html",
            "headers": [
                {"name": "Subject", "value": "HTML only message"},
                {"name": "From", "value": "service@example.com"},
            ],
            "body": {"data": _b64_url(html_content)},
        },
    }

    schema = normalize_message(raw)

    assert "Important Notice" in schema.body_text
    assert "Customer Portal" in schema.body_text
    # Script and style must be dropped
    assert "evil_script" not in schema.body_text
    assert "color: red" not in schema.body_text
    assert "<script>" not in schema.body_text
    # Links must be extracted
    assert any(
        link["text"] == "Customer Portal" and link["href"] == "https://portal.example.com/dashboard"
        for link in schema.links
    )


def test_normalizer_unescapes_subject_and_snippet():
    """html.unescape the snippet and subject."""
    raw = {
        "id": "msg_unescape",
        "snippet": "Let&#39;s review the &lt;metrics&gt; &amp; results",
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "Subject", "value": "Meeting &amp; Discussion: &quot;Q4 Goals&quot;"},
            ],
            "body": {"data": _b64_url("body")},
        },
    }

    schema = normalize_message(raw)

    assert schema.subject == 'Meeting & Discussion: "Q4 Goals"'
    assert schema.snippet == "Let's review the <metrics> & results"


def test_normalizer_captures_display_text_vs_href_mismatch():
    """Display-text vs href mismatch is captured without dropping."""
    html_content = (
        "<p>Your PayPal security alert. Visit "
        "<a href=\"https://paypa1-fraud.example.org/verify\">https://paypal.com/verify</a> "
        "to confirm.</p>"
    )
    raw = {
        "id": "msg_mismatch",
        "payload": {
            "mimeType": "text/html",
            "headers": [{"name": "Subject", "value": "Security Alert"}],
            "body": {"data": _b64_url(html_content)},
        },
    }

    schema = normalize_message(raw)

    mismatch = [
        link for link in schema.links
        if link["text"] == "https://paypal.com/verify"
        and link["href"] == "https://paypa1-fraud.example.org/verify"
    ]
    assert len(mismatch) == 1, "Mismatched link pair was not preserved"


def test_normalizer_extracts_bare_urls_from_plain_text():
    """Extract bare URLs from plain text into links."""
    plain_content = "Please visit https://portal.example.com and check www.helpdesk.org/faq for info."
    raw = {
        "id": "msg_bare_urls",
        "payload": {
            "mimeType": "text/plain",
            "headers": [{"name": "Subject", "value": "Info"}],
            "body": {"data": _b64_url(plain_content)},
        },
    }

    schema = normalize_message(raw)

    hrefs = [link["href"] for link in schema.links]
    assert "https://portal.example.com" in hrefs
    assert "https://www.helpdesk.org/faq" in hrefs


def test_reprocess_stored_emails_is_idempotent(db_session):
    """reprocess_stored_emails updates existing stored emails and is strictly idempotent."""
    import json
    from app.db.models import Email
    from app.db.session import reprocess_stored_emails

    # Create an old email row with unescaped entities, missing body_text, and no links
    email = Email(
        gmail_id="msg_old_stored",
        subject="Rock &amp; Roll",
        snippet="Q&amp;A Session",
        body_text="",
        body_html="<p>Derived <b>text</b></p><a href='https://example.com/test'>Test Link</a>",
        links="[]",
        is_demo=False,
    )
    db_session.add(email)
    db_session.commit()

    # First run: updates the row
    updated_1 = reprocess_stored_emails(db_session)
    assert updated_1 == 1

    refreshed = db_session.query(Email).filter(Email.gmail_id == "msg_old_stored").first()
    assert refreshed.subject == "Rock & Roll"
    assert refreshed.snippet == "Q&A Session"
    assert "Derived text" in refreshed.body_text
    links = json.loads(refreshed.links)
    assert any(l["text"] == "Test Link" and l["href"] == "https://example.com/test" for l in links)

    # Second run: must be idempotent and update 0 rows
    updated_2 = reprocess_stored_emails(db_session)
    assert updated_2 == 0

