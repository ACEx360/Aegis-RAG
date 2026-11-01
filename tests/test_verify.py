"""Tests for Stage 5 claim verification, filtering, and template XSS safety."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from app.db.models import Email
from app.ui.helpers import highlight_citations
from app.ui.routes import templates
from app.verify.minicheck_verifier import (
    MiniCheckVerifier,
    explain_and_verify_email,
)


def test_highlight_citations_xss_safety():
    """Requirement 4: Verify <script> in claims or evidence is escaped safely while [N] is highlighted."""
    malicious_claim = '<script>alert("pwned")</script> Verified sender identity [1].'
    rendered_markup = highlight_citations(malicious_claim)
    rendered_str = str(rendered_markup)

    # <script> must be sanitized into entity codes
    assert "<script>" not in rendered_str
    assert "&lt;script&gt;alert(&#34;pwned&#34;)&lt;/script&gt;" in rendered_str or "&lt;script&gt;" in rendered_str

    # [1] must be safely wrapped in styled pill
    assert '<span class="inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded text-[10px] font-mono font-bold bg-indigo-950 text-indigo-300 border border-indigo-700/60">[1]</span>' in rendered_str


def test_jinja_template_escapes_claim_script_tag():
    """Verify that Jinja autoescape prevents script injection inside claims."""
    template_str = "{{ claim|highlight_citations }}"
    t = templates.env.from_string(template_str)

    malicious_input = '<img src=x onerror=alert(1)> [2] Link target confirmed.'
    result = t.render(claim=malicious_input)

    assert "<img" not in result
    assert "&lt;img" in result
    assert "[2]" in result


def test_verify_single_claim_links_best_evidence(monkeypatch):
    """Verify claim scoring links to the best supporting evidence index [N]."""
    verifier = MiniCheckVerifier(model_name="roberta-large")
    monkeypatch.setattr(verifier, "_ensure_loaded", lambda: True)

    # Mock score_pairs: full doc -> 0.85, item 1 -> 0.15, item 2 -> 0.92
    def mock_score_pairs(docs, claims):
        if len(docs) == 3:
            return [1, 0, 1], [0.85, 0.15, 0.92]
        if len(docs) == 2:
            return [0, 1], [0.15, 0.92]
        return [1], [0.85]

    monkeypatch.setattr(verifier, "score_pairs", mock_score_pairs)

    evidence_items = [
        "[1] Sender is not in the historical contacts database.",
        "[2] The email authentication header confirmed SPF pass for company.com.",
    ]
    claim = "The sender passed SPF authentication."
    res = verifier.verify_single_claim(claim, evidence_items, threshold=0.5)

    assert res["label"] == "supported"
    assert res["confidence"] == 0.92
    assert res["evidence_index"] == 2
    assert "[2]" in res["evidence_text"]


def test_explain_and_verify_email_pipeline(db_session, monkeypatch):
    """Verify complete verification pipeline: verdict line, supported filtering, removed claims."""
    email = Email(
        gmail_id="test-verify-pipe-01",
        subject="Urgent payroll update",
        sender="payroll@corp.com",
        priority_score=85.0,
        priority_label="High",
        priority_reason="Urgent internal update.",
        fraud_score=0.10,
        fraud_label="Low risk",
        fraud_reason="Sender authenticated.",
        priority_evidence=json.dumps(["[1] Sender is verified payroll admin."]),
        fraud_evidence=json.dumps(["[2] SPF check: pass"]),
    )
    db_session.add(email)
    db_session.commit()

    # Mock Gemini explanation and decomposition
    monkeypatch.setattr(
        "app.explain.generator.generate_combined_explanation",
        lambda e, db=None: "payroll@corp.com is an authenticated admin. The sender demanded gift cards.",
    )
    monkeypatch.setattr(
        "app.explain.generator.decompose_claims",
        lambda exp, e, db=None: [
            "payroll@corp.com is an authenticated admin.",
            "The sender demanded retail gift cards.",
        ],
    )

    # Mock MiniCheck verifier
    mock_verifier = MagicMock()
    mock_verifier.is_available.return_value = True
    mock_verifier.verify_claims_list.return_value = [
        {
            "claim": "payroll@corp.com is an authenticated admin.",
            "label": "supported",
            "confidence": 0.95,
            "evidence_index": 1,
            "evidence_text": "[1] Sender is verified payroll admin.",
        },
        {
            "claim": "The sender demanded retail gift cards.",
            "label": "unsupported",
            "confidence": 0.05,
            "evidence_index": None,
            "evidence_text": None,
        },
    ]
    monkeypatch.setattr("app.verify.minicheck_verifier.get_verifier", lambda: mock_verifier)

    result = explain_and_verify_email(email, db=db_session)

    # 1. Verdict line must be present
    assert "Verdict: High Priority" in result["verdict_line"]
    assert "Low risk" in result["verdict_line"]

    # 2. Supported claim retained with [1] citation
    assert "payroll@corp.com is an authenticated admin. [1]" in result["verified_explanation"]

    # 3. Unsupported claim must NOT appear in verified_explanation
    assert "gift cards" not in result["verified_explanation"]

    # 4. Verified claims JSON records both
    stored_claims = json.loads(email.verified_claims)
    assert len(stored_claims) == 2
    assert stored_claims[0]["label"] == "supported"
    assert stored_claims[1]["label"] == "unsupported"


def test_explain_and_verify_email_when_verifier_unavailable(db_session, monkeypatch):
    """Requirement 6: If MiniCheck is unavailable, unverified explanation is NOT shown as verified."""
    email = Email(
        gmail_id="test-verify-pipe-02",
        subject="Meeting",
        sender="bob@company.com",
        priority_score=50.0,
        fraud_score=0.1,
    )
    db_session.add(email)
    db_session.commit()

    mock_verifier = MagicMock()
    mock_verifier.is_available.return_value = False
    monkeypatch.setattr("app.verify.minicheck_verifier.get_verifier", lambda: mock_verifier)

    result = explain_and_verify_email(email, db=db_session)

    assert result["verifier_available"] is False
    assert result["verified_explanation"] is None
    assert email.verified_explanation is None
    assert email.verification_version is None

