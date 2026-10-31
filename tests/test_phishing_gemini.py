"""Unit tests for Gemini social engineering layer (§Pass 4b)."""

from __future__ import annotations

from unittest.mock import patch

from app.db.models import Email
from app.phishing.providers.gemini_social import evaluate_gemini_social


def test_gemini_social_skipped_when_preliminary_score_low():
    """Gemini social call is skipped to save quota when preliminary score < threshold."""
    email = Email(
        id=1,
        gmail_id="low_risk_email",
        subject="Normal meeting",
        body_text="Hi team, see you at 3pm.",
        sender="colleague@example.com",
    )
    res = evaluate_gemini_social(email, preliminary_score=0.10)
    assert not res.available
    assert "skipped to save quota" in res.reason


def test_gemini_social_triggers_when_threshold_met():
    """Gemini social runs when preliminary score >= trigger threshold."""
    email = Email(
        id=2,
        gmail_id="high_risk_email",
        subject="Urgent wire transfer",
        body_text="Wire funds immediately to the attached account.",
        sender="ceo@example.com",
    )
    mock_response = {
        "social_engineering_score": 0.88,
        "indicators": {
            "urgency": 0.95,
            "authority_impersonation": 0.90,
            "credential_harvesting": 0.10,
            "financial_coercion": 0.85,
        },
        "reason": "High urgency financial coercion detected.",
        "evidence": ["Demands immediate wire transfer", "Executive impersonation"],
    }

    with patch("app.phishing.providers.gemini_social.gemini_client") as mock_client:
        mock_client.is_available = True
        mock_client.generate.return_value = mock_response

        res = evaluate_gemini_social(email, preliminary_score=0.40)
        assert res.available
        assert res.score == 0.88
        assert res.has_strong_signal
        assert len(res.evidence) >= 2
        assert any("financial coercion" in ev.lower() or "wire transfer" in ev.lower() for ev in res.evidence)


def test_gemini_social_score_clamping():
    """Raw scores outside [0, 1] are clamped safely."""
    email = Email(
        id=3,
        gmail_id="clamp_test",
        subject="Test",
        body_text="Test",
        sender="test@example.com",
    )
    with patch("app.phishing.providers.gemini_social.gemini_client") as mock_client:
        mock_client.is_available = True
        mock_client.generate.return_value = {
            "social_engineering_score": 1.5,
            "reason": "Overly high score",
            "evidence": [],
        }
        res = evaluate_gemini_social(email, preliminary_score=0.50)
        assert res.score == 1.0


def test_gemini_social_handles_unavailable_client():
    """Returns available=False when Gemini client is not configured."""
    email = Email(
        id=4,
        gmail_id="no_key_test",
        subject="Test",
        body_text="Test",
        sender="test@example.com",
    )
    with patch("app.phishing.providers.gemini_social.gemini_client") as mock_client:
        mock_client.is_available = False
        res = evaluate_gemini_social(email, preliminary_score=0.50)
        assert not res.available
        assert "not configured" in res.reason
