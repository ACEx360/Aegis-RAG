"""Tests for Stage 5 explanation generation and claim decomposition."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from app.db.models import Email
from app.explain.generator import (
    assemble_evidence_set,
    build_verdict_line,
    decompose_claims,
    generate_combined_explanation,
)


def test_build_verdict_line():
    """Verify verdict line is system-built correctly from priority and fraud fields."""
    email = Email(
        priority_score=85.0,
        priority_label="High",
        fraud_score=0.88,
        fraud_label="Likely phishing",
    )
    verdict = build_verdict_line(email)
    assert "High Priority (85/100)" in verdict
    assert "Likely phishing (88%)" in verdict
    assert verdict.startswith("Verdict:")

    # When priority_score is None
    email_unrated = Email(priority_score=None, fraud_score=None)
    verdict_unrated = build_verdict_line(email_unrated)
    assert "Priority: not analyzed" in verdict_unrated
    assert "Threat Band: not analyzed" in verdict_unrated


def test_assemble_evidence_set():
    """Verify evidence merging, bracket cleanup, deduplication, and sequential numbering."""
    email = Email(
        priority_evidence=json.dumps([
            "[1] Sender alice@company.com is an authenticated employee.",
            "[2] Discusses internal sprint planning meeting.",
        ]),
        fraud_evidence=json.dumps([
            "[Auth] SPF check result: pass",
            "[URL] No external links detected.",
            # Duplicate text with different tag
            "[3] Discusses internal sprint planning meeting.",
        ]),
    )
    evidence = assemble_evidence_set(email)
    assert len(evidence) == 4  # 5 items total minus 1 duplicate
    assert evidence[0] == "[1] Sender alice@company.com is an authenticated employee."
    assert evidence[1] == "[2] Discusses internal sprint planning meeting."
    assert evidence[2] == "[3] SPF check result: pass"
    assert evidence[3] == "[4] No external links detected."


def test_generate_combined_explanation_mock_gemini(monkeypatch):
    """Verify Gemini explanation generation when API returns valid response."""
    email = Email(
        gmail_id="test-exp-01",
        subject="Sprint Planning",
        sender="alice@company.com",
        priority_score=80.0,
        priority_label="High",
        fraud_score=0.05,
        fraud_label="Low risk",
        priority_evidence=json.dumps(["[1] Authenticated sender"]),
        fraud_evidence=json.dumps(["[2] Clean headers"]),
    )

    mock_client = MagicMock()
    mock_client.generate.return_value = {
        "explanation": "This email is high priority because it covers internal sprint planning from a verified sender."
    }
    monkeypatch.setattr("app.explain.generator.gemini_client", mock_client)

    explanation = generate_combined_explanation(email)
    assert "high priority because it covers internal sprint planning" in explanation
    assert mock_client.generate.called


def test_generate_combined_explanation_fallback(monkeypatch):
    """Verify deterministic fallback when Gemini client raises an exception."""
    email = Email(
        gmail_id="test-exp-02",
        subject="Server alert",
        sender="ops@internal.net",
        priority_score=90.0,
        priority_reason="Urgent infrastructure alert requiring immediate patching.",
        fraud_reason="Sender passed authentication and matches known internal monitoring server.",
    )

    mock_client = MagicMock()
    mock_client.generate.side_effect = RuntimeError("API unavailable")
    monkeypatch.setattr("app.explain.generator.gemini_client", mock_client)

    explanation = generate_combined_explanation(email)
    assert "Urgent infrastructure alert" in explanation
    assert "Sender passed authentication" in explanation


def test_decompose_claims_mock_gemini(monkeypatch):
    """Verify atomic claim decomposition caps at 6 claims and handles structured JSON."""
    email = Email(gmail_id="test-claims-01", sender="alice@company.com")
    explanation = "alice@company.com is an authenticated coworker. The meeting is scheduled for 10 AM. No external links were found."

    mock_client = MagicMock()
    mock_client.generate.return_value = {
        "claims": [
            f"Atomic claim number {i} regarding alice@company.com" for i in range(10)
        ]
    }
    monkeypatch.setattr("app.explain.generator.gemini_client", mock_client)

    claims = decompose_claims(explanation, email)
    # Must cap at max 6 claims per email
    assert len(claims) == 6
    assert claims[0] == "Atomic claim number 0 regarding alice@company.com"


def test_decompose_claims_fallback(monkeypatch):
    """Verify regex sentence decomposition fallback when Gemini fails."""
    email = Email(gmail_id="test-claims-02", sender="alice@company.com")
    explanation = "Sender alice@company.com passed SPF. [1] The meeting is scheduled for 10 AM! All links point to internal servers."

    mock_client = MagicMock()
    mock_client.generate.side_effect = RuntimeError("Offline")
    monkeypatch.setattr("app.explain.generator.gemini_client", mock_client)

    claims = decompose_claims(explanation, email)
    assert len(claims) == 3
    # [1] bracket must be stripped in fallback
    assert "[1]" not in claims[1]
    assert "meeting is scheduled for 10 AM" in claims[1]

