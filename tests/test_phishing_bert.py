"""Unit tests for BERT phishing classification layer (§Pass 4b)."""

from __future__ import annotations

from unittest.mock import patch

from app.db.models import Email
from app.phishing.providers.bert_phishing import evaluate_bert_phishing
from app.settings import settings


def test_bert_phishing_empty_content():
    """BERT classifier returns available=False when email has no subject and no body."""
    email = Email(
        id=1,
        gmail_id="test_empty",
        subject="",
        body_text="",
        sender="test@example.com",
    )
    res = evaluate_bert_phishing(email)
    assert not res.available
    assert (
        "no text content" in res.reason.lower()
        or "not downloaded" in res.reason.lower()
        or "not configured" in res.reason.lower()
    )
    assert res.score == 0.0


def test_bert_phishing_evaluates_text_and_records_latency():
    """BERT classifies text, records positive latency, and clamps score to [0, 1]."""
    email = Email(
        id=2,
        gmail_id="test_phish",
        subject="Urgent: Update your banking credentials now",
        body_text="Your account has been locked. Click here to verify your identity immediately.",
        sender="security@suspicious-bank.com",
    )
    res = evaluate_bert_phishing(email)
    if res.available:
        assert 0.0 <= res.score <= 1.0
        assert any("latency" in ev.lower() for ev in res.evidence)
        assert res.name == "bert_phishing"
    else:
        # If cache not present in environment
        assert "model not downloaded" in res.reason


def test_bert_phishing_handles_512_token_limit():
    """BERT classifier handles emails far exceeding the 512 token limit without crashing."""
    long_body = "word " * 1500
    email = Email(
        id=3,
        gmail_id="test_long",
        subject="Long document analysis",
        body_text=long_body,
        sender="newsletter@example.com",
    )
    res = evaluate_bert_phishing(email)
    if res.available:
        assert 0.0 <= res.score <= 1.0
        assert res.name == "bert_phishing"


def test_bert_phishing_missing_model_graceful_degradation():
    """When HF_PHISHING_MODEL is empty or invalid, returns available=False with instructions."""
    with (
        patch.object(settings, "hf_phishing_model", ""),
        patch("app.phishing.providers.bert_phishing._load_attempted", False),
    ):
        email = Email(
            id=4,
            gmail_id="test_missing_model",
            subject="Test",
            body_text="Test body",
            sender="test@example.com",
        )
        res = evaluate_bert_phishing(email)
        assert not res.available
        assert "not configured" in res.reason or "not downloaded" in res.reason
