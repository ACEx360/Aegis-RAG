"""Tests for Stage 2 UI shell, tab filtering, Swagger rows, HTMX panels, and security escaping."""

from __future__ import annotations

import json
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Email
from app.ingest.gmail_client import GmailAuthStatus
from app.settings import settings
from app.state import app_state


def test_root_redirect_to_priority(client: TestClient):
    """Root path / redirects to /priority in demo mode."""
    app_state.demo_mode = True
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/priority"


def test_real_mode_unauthenticated_redirects_to_login(client: TestClient):
    """In real mode, if not authenticated with Gmail, redirect to /login (Change 5)."""
    app_state.demo_mode = False
    with patch("app.ui.routes.gmail_client.get_auth_status", return_value=GmailAuthStatus(authenticated=False)):
        response = client.get("/priority", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"

    # Reset
    app_state.demo_mode = True


def test_tabs_render_and_partitioning(client: TestClient):
    """Verify tabs correctly partition emails into Priority, Previous, Feed, and Flagged (Change 4)."""
    app_state.demo_mode = True
    # Seed demo emails
    client.post("/api/emails/sync")

    # 1. Priority tab: unread, excludes newsletters, excludes likely fraud
    resp_p = client.get("/priority")
    assert resp_p.status_code == 200
    assert "Priority Inbox" in resp_p.text
    # Should contain legit urgent email
    assert "Thesis draft review" in resp_p.text
    # Should NOT contain newsletters
    assert "Tech Weekly Digest" not in resp_p.text
    # Should NOT contain phishing email (routed to Flagged/Fraud)
    assert "Your account will be suspended in 24 hours" not in resp_p.text
    # Should display banner for flagged items
    assert "flagged as potential phishing/fraud" in resp_p.text

    # 2. Previous tab: opened/read mail, excludes newsletters
    resp_prev = client.get("/previous")
    assert resp_prev.status_code == 200
    assert "Previous Messages" in resp_prev.text
    # Pre-read work/personal emails appear here
    assert "Sprint Planning Notes" in resp_prev.text
    # Newsletters should NOT appear here
    assert "Tech Weekly Digest" not in resp_prev.text

    # 3. Feed tab: newsletters only
    resp_feed = client.get("/feed")
    assert resp_feed.status_code == 200
    assert "Feed" in resp_feed.text
    assert "Tech Weekly Digest" in resp_feed.text
    assert "Top 10 Python Libraries" in resp_feed.text
    # Normal emails should NOT appear in Feed
    assert "Thesis draft review" not in resp_feed.text

    # 4. Flagged / Fraud tab: fraud_score >= threshold
    resp_flag = client.get("/flagged")
    assert resp_flag.status_code == 200
    assert "Flagged / Fraud" in resp_flag.text
    assert "Your account will be suspended in 24 hours" in resp_flag.text
    assert "PayPa1 Support" in resp_flag.text


def test_settings_tab_renders_thresholds_and_status(client: TestClient):
    """Settings tab renders mode badge, auth status, thresholds from settings.py (Change 6)."""
    app_state.demo_mode = True
    resp = client.get("/settings")
    assert resp.status_code == 200
    assert "Application Settings" in resp.text
    assert "Current Mode: demo" in resp.text
    assert f"{int(settings.fraud_threshold * 100)}%" in resp.text
    assert f"{int(settings.priority_high_threshold)}" in resp.text
    assert f"{settings.sync_days} days" in resp.text
    assert f"{settings.sync_max} emails" in resp.text


def test_panel_get_is_readonly_and_does_not_set_opened_at(client: TestClient, db_session: Session):
    """GET /ui/emails/{id}/panel is strictly read-only and does NOT set opened_at (Change 1 & 9)."""
    app_state.demo_mode = True
    client.post("/api/emails/sync")

    unopened = db_session.query(Email).filter(Email.opened_at == None, Email.is_read == False).first()
    assert unopened is not None
    email_id = unopened.id

    # Perform GET request
    resp = client.get(f"/ui/emails/{email_id}/panel")
    assert resp.status_code == 200
    assert "Summary" in resp.text
    assert "Verified Explanation" in resp.text
    assert "Detection Layers" in resp.text
    assert "Headers" in resp.text
    assert "Body" in resp.text

    # Verify opened_at remains None
    db_session.refresh(unopened)
    assert unopened.opened_at is None


def test_panel_post_marks_opened_and_updates_state(client: TestClient, db_session: Session):
    """POST /ui/emails/{id}/panel marks opened_at and returns panel HTML (Change 1 & 9)."""
    app_state.demo_mode = True
    client.post("/api/emails/sync")

    unopened = db_session.query(Email).filter(Email.opened_at == None, Email.is_read == False).first()
    assert unopened is not None
    email_id = unopened.id

    # Perform POST request
    resp = client.post(f"/ui/emails/{email_id}/panel")
    assert resp.status_code == 200
    assert "Summary" in resp.text

    # Verify opened_at is now set!
    db_session.refresh(unopened)
    assert unopened.opened_at is not None


def test_placeholder_notices_shown_not_simulated_data(client: TestClient):
    """Verified Explanation shows placeholder for Stage 5; Detection Layers shows live providers (§8, §9)."""
    app_state.demo_mode = True
    client.post("/api/emails/sync")

    resp = client.get("/ui/emails/1/panel")
    assert resp.status_code == 200
    assert "Claim-Level Explanation Verification Coming in Stage 5" in resp.text
    assert "Sender Authentication" in resp.text
    assert "URL & Domain Heuristics" in resp.text


def test_headers_tab_shows_all_headers_including_duplicates(client: TestClient, db_session: Session):
    """Headers tab displays all raw headers including duplicate Received headers (§14)."""
    email = Email(
        gmail_id="test-dup-headers-001",
        subject="Dup Test",
        sender="sender@example.com",
        raw_headers=json.dumps([
            {"name": "Received", "value": "by mx1.example.com"},
            {"name": "Received", "value": "by mx2.example.com"},
            {"name": "X-Custom", "value": "custom-val"},
        ]),
        is_demo=True,
    )
    db_session.add(email)
    db_session.commit()

    resp = client.get(f"/ui/emails/{email.id}/panel")
    assert resp.status_code == 200
    assert "by mx1.example.com" in resp.text
    assert "by mx2.example.com" in resp.text
    assert "X-Custom" in resp.text


def test_security_autoescaping_and_plain_text_links(client: TestClient, db_session: Session):
    """Ensure <script> tags are autoescaped and links are plain text, not <a href> (Change 3)."""
    xss_subject = "<script>alert('xss-subject')</script>"
    xss_body = "Click here http://phish-site.example.com/login <script>alert('xss-body')</script>"
    email = Email(
        gmail_id="test-xss-001",
        subject=xss_subject,
        sender="attacker@example.com",
        body_text=xss_body,
        is_demo=True,
    )
    db_session.add(email)
    db_session.commit()

    # 1. Row view
    resp_row = client.get("/priority")
    assert resp_row.status_code == 200
    # Must NOT contain unescaped script tag
    assert "<script>alert('xss-subject')</script>" not in resp_row.text
    assert "&lt;script&gt;alert(&#39;xss-subject&#39;)&lt;/script&gt;" in resp_row.text or "&lt;script&gt;" in resp_row.text

    # 2. Panel view
    resp_panel = client.get(f"/ui/emails/{email.id}/panel")
    assert resp_panel.status_code == 200
    assert "<script>alert('xss-body')</script>" not in resp_panel.text
    # Links must not be rendered as active anchor tags
    assert '<a href="http://phish-site.example.com/login"' not in resp_panel.text


def test_real_emails_keep_null_scores_and_show_not_analyzed_badge(client: TestClient, db_session: Session):
    """Real emails (is_demo=False) keep NULL scores and display 'Not analyzed yet' (Change 2)."""
    real_email = Email(
        gmail_id="real-gmail-msg-001",
        subject="Important Client Discussion",
        sender="client@corp.example.com",
        is_demo=False,
        priority_score=None,
        priority_label=None,
        fraud_score=None,
    )
    db_session.add(real_email)
    db_session.commit()

    app_state.demo_mode = False
    with patch("app.ui.routes.gmail_client.get_auth_status", return_value=GmailAuthStatus(authenticated=True)):
        resp = client.get("/priority")
        assert resp.status_code == 200
        assert "Important Client Discussion" in resp.text
        assert "Not analyzed yet" in resp.text

    # Reset
    app_state.demo_mode = True


def test_search_and_pagination(client: TestClient):
    """Search query filters emails, and skip/limit paginate results (Change 8)."""
    app_state.demo_mode = True
    client.post("/api/emails/sync")

    # Search for specific keyword
    resp_search = client.get("/priority?q=thesis")
    assert resp_search.status_code == 200
    assert "Thesis draft review" in resp_search.text

    # Search with non-matching query
    resp_empty = client.get("/priority?q=nonexistentqueryxyz")
    assert resp_empty.status_code == 200
    assert "No emails found in Priority Inbox" in resp_empty.text

    # Pagination test
    resp_page = client.get("/priority?skip=0&limit=2")
    assert resp_page.status_code == 200

    # HTMX pagination chunk test (skip > 0 with HX-Request)
    resp_chunk = client.get("/priority?skip=2&limit=2", headers={"HX-Request": "true"})
    assert resp_chunk.status_code == 200
    assert "email-row-" in resp_chunk.text


def test_panel_renders_extracted_links(client: TestClient, db_session: Session):
    """Panel renders extracted links in the Body tab safely without active links."""
    import json
    email = Email(
        gmail_id="msg_test_links_render",
        subject="Link rendering test",
        sender="sender@example.com",
        body_text="Click below:\nhttps://paypal.com",
        links=json.dumps([
            {"text": "https://paypal.com", "href": "https://paypa1-phish.net"},
            {"text": "Docs", "href": "https://docs.example.com"},
        ]),
        is_demo=True,
    )
    db_session.add(email)
    db_session.commit()

    resp = client.get(f"/ui/emails/{email.id}/panel")
    assert resp.status_code == 200
    assert "Extracted Links (2)" in resp.text
    assert "https://paypal.com" in resp.text
    assert "https://paypa1-phish.net" in resp.text
    assert "Display Mismatch" in resp.text
    assert "<!DOCTYPE html>" not in resp.text
