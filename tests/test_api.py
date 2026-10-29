"""Tests for FastAPI endpoints, Swagger docs, /login template, and email operations."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.state import app_state


def test_swagger_docs(client: TestClient):
    """FastAPI Swagger documentation must load at /docs."""
    response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger-ui" in response.text.lower() or "openapi" in response.text.lower()


def test_login_page_renders(client: TestClient):
    """GET /login renders the HTML template with status and action buttons."""
    response = client.get("/login")
    assert response.status_code == 200
    assert "AegisRAG" in response.text
    assert "Connect Gmail" in response.text
    assert "Use Demo Mode" in response.text
    assert "Sync Now" in response.text


def test_demo_sync_and_list_emails(client: TestClient):
    """Syncing demo emails populates the database and list endpoint returns them."""
    app_state.demo_mode = True

    # 1. Sync
    sync_resp = client.post("/api/emails/sync")
    assert sync_resp.status_code == 200
    data = sync_resp.json()
    assert data["mode"] == "demo"
    assert data["added"] >= 18

    # 2. List
    list_resp = client.get("/api/emails")
    assert list_resp.status_code == 200
    emails = list_resp.json()
    assert len(emails) >= 18

    first = emails[0]
    assert "gmail_id" in first
    assert "subject" in first
    assert "is_unread" in first  # Computed field
    assert "body_html" not in first


def test_email_detail_and_open_tracking(client: TestClient):
    """GET /api/emails/{id} returns details (no body_html). POST .../open updates opened_at."""
    app_state.demo_mode = True
    client.post("/api/emails/sync")

    emails = client.get("/api/emails").json()
    first_id = emails[0]["id"]

    # 1. Detail view
    detail_resp = client.get(f"/api/emails/{first_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert "body_text" in detail
    assert "raw_headers" in detail
    assert isinstance(detail["raw_headers"], list)
    assert "body_html" not in detail  # §14: Never render or return HTML by default

    # 2. Mark as opened
    open_resp = client.post(f"/api/emails/{first_id}/open")
    assert open_resp.status_code == 200
    open_data = open_resp.json()
    assert open_data["opened_at"] is not None

    # Check detail again — opened_at is set, is_unread is now False
    updated_detail = client.get(f"/api/emails/{first_id}").json()
    assert updated_detail["opened_at"] is not None
    assert updated_detail["is_unread"] is False


def test_mode_isolation(client: TestClient):
    """Emails from demo mode are hidden when in real mode, and vice versa."""
    app_state.demo_mode = True
    client.post("/api/emails/sync")

    # In demo mode, we see demo emails
    demo_emails = client.get("/api/emails").json()
    assert len(demo_emails) > 0
    assert all(e["is_demo"] is True for e in demo_emails)

    # Switch to real mode
    mode_resp = client.post("/api/mode?mode=real")
    assert mode_resp.status_code == 200

    # In real mode, demo emails are filtered out
    real_emails = client.get("/api/emails").json()
    assert len(real_emails) == 0

    # Switch back to demo mode
    client.post("/api/mode?mode=demo")


def test_auth_status_endpoint(client: TestClient):
    """GET /api/auth/status returns auth and file states."""
    resp = client.get("/api/auth/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "authenticated" in data
    assert "mode" in data
    assert "oauth_in_progress" in data
    assert "credentials_present" in data
    assert "token_present" in data


def test_sync_twice_against_already_stored_emails(client: TestClient):
    """Syncing twice against stored emails must update without 500 error (tests extract_all_links)."""
    from unittest.mock import patch

    app_state.demo_mode = False

    mock_raw_msg = {
        "id": "msg_real_1",
        "threadId": "th_1",
        "snippet": "First sync snippet",
        "labelIds": ["INBOX", "UNREAD"],
        "internalDate": "1700000000000",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Real Test Email"},
                {"name": "From", "value": "alice@example.com"},
                {"name": "To", "value": "me@example.com"},
                {"name": "Date", "value": "Wed, 15 Nov 2023 12:00:00 +0000"},
            ],
            "mimeType": "text/html",
            "body": {
                "data": "PHA+SGVyZSBpcyBhIDxhIGhyZWY9Imh0dHBzOi8vZXhhbXBsZS5jb20iPmxpbms8L2E+PC9wPg=="
            },
        },
    }
    mock_metadata = {
        "id": "msg_real_1",
        "labelIds": ["INBOX"],
        "snippet": "Updated snippet &amp; notes",
    }

    with patch("app.api.routes.gmail_client.list_message_ids", return_value=[{"id": "msg_real_1"}]), \
         patch("app.api.routes.gmail_client.get_message", return_value=mock_raw_msg), \
         patch("app.api.routes.gmail_client.get_message_metadata", return_value=mock_metadata):

        # First sync: adds the message
        resp1 = client.post("/api/emails/sync")
        assert resp1.status_code == 200, resp1.text
        data1 = resp1.json()
        assert data1["added"] == 1
        assert data1["updated"] == 0

        # Second sync: updates the stored message (calls extract_all_links)
        resp2 = client.post("/api/emails/sync")
        assert resp2.status_code == 200, resp2.text
        data2 = resp2.json()
        assert data2["added"] == 0
        assert data2["updated"] == 1

    # Cleanup mode
    client.post("/api/mode?mode=demo")

