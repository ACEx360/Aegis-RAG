"""Tests for Priority Classifier, Rule Engine, RAG context, and Gemini caching (§Stage 3)."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.db.models import Email
from app.llm.gemini_client import gemini_client
from app.priority.classifier import classify_email_priority


@pytest.fixture
def sample_urgent_email():
    """Legit urgent email from known colleague with deadline (§14)."""
    return Email(
        gmail_id="demo-legit-001",
        subject="Urgent: Thesis draft review needed by tomorrow 10am",
        sender="Dr. Sarah Chen <s.chen@university.example.edu>",
        body_text="Hi Alpesh,\nPlease review the final thesis chapter today before our deadline tomorrow morning.\nBest,\nDr. Chen",
        snippet="Please review the final thesis chapter today...",
        labels=json.dumps(["INBOX", "UNREAD", "IMPORTANT"]),
        raw_headers=json.dumps([{"name": "From", "value": "s.chen@university.example.edu"}]),
        is_demo=True,
    )


@pytest.fixture
def sample_newsletter_email():
    """Newsletter email with bulk headers and promotional labels."""
    return Email(
        gmail_id="demo-news-001",
        subject="Tech Weekly Digest: Latest AI releases and tools",
        sender="Tech Weekly <digest@techweekly.example.com>",
        body_text="Here is your weekly summary of tech news and upcoming developer tools.",
        snippet="Here is your weekly summary of tech news...",
        labels=json.dumps(["CATEGORY_PROMOTIONS", "UNREAD"]),
        raw_headers=json.dumps([
            {"name": "List-Unsubscribe", "value": "<mailto:unsub@techweekly.example.com>"},
            {"name": "Precedence", "value": "bulk"},
        ]),
        is_demo=True,
    )


def test_priority_legit_urgent_scores_high(db_session: Session, sample_urgent_email: Email):
    """Legit urgent email from known contact with deadline scores High (>= 70)."""
    db_session.add(sample_urgent_email)
    db_session.commit()

    # Mock Gemini to return high relevance score citing system evidence
    mock_llm_result = {
        "relevance_score": 95,
        "justification": "Urgent thesis draft review requested by known academic contact [1] with tomorrow deadline [3].",
        "cited_evidence_indices": [1, 3],
    }

    with patch.object(type(gemini_client), "is_available", new_callable=lambda: property(lambda self: True)), \
         patch("app.priority.classifier.gemini_client.generate", return_value=mock_llm_result) as mock_gen:

        res = classify_email_priority(sample_urgent_email, db=db_session, force_refresh=True)

        assert res["priority_score"] >= 70.0
        assert res["priority_label"] == "High"
        assert "[1]" in res["priority_reason"]
        assert len(res["priority_evidence"]) > 0
        mock_gen.assert_called_once()


def test_priority_newsletter_scores_low_and_skips_gemini(db_session: Session, sample_newsletter_email: Email):
    """Newsletter/promotions email scores Low (<= 30) and skips Gemini call entirely."""
    db_session.add(sample_newsletter_email)
    db_session.commit()

    with patch("app.priority.classifier.gemini_client.generate") as mock_gen:
        res = classify_email_priority(sample_newsletter_email, db=db_session, force_refresh=True)

        assert res["priority_score"] <= 30.0
        assert res["priority_label"] == "Low"
        assert "bulk" in res["priority_reason"].lower() or "promotional" in res["priority_reason"].lower()
        mock_gen.assert_not_called()


def test_priority_cache_prevents_duplicate_gemini_call(db_session: Session, sample_urgent_email: Email):
    """Evaluating the same email a second time hits SQLite LLMCache and does not call Gemini."""
    db_session.add(sample_urgent_email)
    db_session.commit()

    mock_llm_result = {
        "relevance_score": 88,
        "justification": "Time-sensitive review needed [1].",
        "cited_evidence_indices": [1],
    }

    with patch.object(type(gemini_client), "is_available", new_callable=lambda: property(lambda self: True)), \
         patch("app.priority.classifier.gemini_client.generate", return_value=mock_llm_result) as mock_gen:

        # First call: computes and saves to DB
        res1 = classify_email_priority(sample_urgent_email, db=db_session, force_refresh=True)
        assert res1["priority_score"] >= 70.0
        assert mock_gen.call_count == 1

        # Second call without force_refresh: returns cached fields directly without calling Gemini
        res2 = classify_email_priority(sample_urgent_email, db=db_session, force_refresh=False)
        assert res2["priority_score"] == res1["priority_score"]
        assert mock_gen.call_count == 1  # No second call!


def test_priority_fallback_when_gemini_unavailable(db_session: Session, sample_urgent_email: Email):
    """When Gemini API key is missing, priority is evaluated via rules and shows 'AI scoring unavailable'."""
    db_session.add(sample_urgent_email)
    db_session.commit()

    with patch.object(type(gemini_client), "is_available", new_callable=lambda: property(lambda self: False)):
        res = classify_email_priority(sample_urgent_email, db=db_session, force_refresh=True)

        assert res["priority_score"] >= 70.0  # Rules alone detect known contact + urgent keyword
        assert "AI scoring unavailable" in res["priority_reason"]
        assert len(res["priority_evidence"]) > 0


def test_priority_rule_cap_promo_never_high(db_session: Session):
    """Even if Gemini returns 100, promotional/bulk email cannot exceed 40 and can never be High."""
    promo_email = Email(
        gmail_id="test-promo-override",
        subject="Exclusive 50% discount today only",
        sender="Promotions <promo@shop.example.com>",
        body_text="Buy now before midnight!",
        labels=json.dumps(["CATEGORY_PROMOTIONS"]),
        is_demo=False,
    )
    db_session.add(promo_email)
    db_session.commit()

    mock_llm = {
        "relevance_score": 100,
        "justification": "Seems urgent [1].",
        "cited_evidence_indices": [1],
    }

    with patch("app.priority.classifier.settings.priority_skip_gemini_promo", False), \
         patch.object(type(gemini_client), "is_available", new_callable=lambda: property(lambda self: True)), \
         patch("app.priority.classifier.gemini_client.generate", return_value=mock_llm):

        res = classify_email_priority(promo_email, db=db_session, force_refresh=True)

        # Cap must hold: max score is 40.0
        assert res["priority_score"] <= 40.0
        assert res["priority_label"] != "High"


def test_worker_interrupted_and_resumable(tmp_path, monkeypatch):
    """Worker tracks interrupted state, skips finished emails, and shows resume UI (§Stage 3)."""
    from fastapi.testclient import TestClient

    from app.main import app
    from app.priority import worker
    from app.state import app_state

    status_file = tmp_path / ".analysis_status.json"
    monkeypatch.setattr(worker, "_STATUS_FILE", status_file)

    # 1. Simulate server killed mid-run (status was 'running')
    status_file.write_text(json.dumps({"status": "running"}), encoding="utf-8")
    worker.check_and_restore_analysis_state()

    assert app_state.analysis_interrupted is True
    assert "Analysis interrupted - click to resume" in app_state.analysis_message

    # 2. Check UI endpoint returns the interrupted resume banner
    client = TestClient(app)
    resp = client.get("/ui/analysis/status")
    assert resp.status_code == 200
    assert "Analysis interrupted - click to resume" in resp.text
    assert "Resume Analysis" in resp.text

    # 3. Resume analysis via start_priority_analysis
    with patch("app.priority.worker._run_analysis_worker"):
        started = worker.start_priority_analysis(is_demo=True)
        assert started is True
        assert app_state.analysis_interrupted is False
        assert app_state.analysis_running is True

    # Cleanup
    app_state.analysis_running = False
    app_state.analysis_interrupted = False

