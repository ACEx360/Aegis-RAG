"""Tests for category-based phishing detection improvements (§Stage 4 Tuning).

Categories:
1. Brand shown in link text with unrelated target
2. First-time sender plus brand in display name
3. Deceptive brand embedded in root domain
4. Credential request with unauthenticated sender
5. Risky attachment types (.html, .exe, .scr)
6. Corroboration rule: BERT on clean auth vs missing/failed auth
"""

from __future__ import annotations

from app.phishing.fusion import fuse_phishing_layers
from app.phishing.providers.base import LayerResult
from app.phishing.providers.sender_auth import evaluate_sender_auth
from app.phishing.providers.url_heuristics import evaluate_url_heuristics


def test_anchor_brand_mismatch_unrelated_target():
    """Anchor text naming PayPal pointing to an unrelated domain triggers strong anchor mismatch."""
    links = [
        {"url": "https://secure-verify-update.com/signin", "text": "Log in to PayPal"}
    ]
    res = evaluate_url_heuristics(links, "", sender_domain="secure-verify-update.com", dmarc_pass=False)
    assert res.available
    assert res.has_strong_signal
    assert res.score >= 0.70
    assert any("paypal" in ev.lower() and "unrelated" in ev.lower() for ev in res.evidence)


def test_anchor_full_domain_brand_mismatch():
    """Anchor text displaying https://www.paypal.com/signin pointing to attacker domain triggers strong anchor mismatch."""
    links = [
        {"url": "https://secure-verify-update.com/signin", "text": "https://www.paypal.com/signin"}
    ]
    res = evaluate_url_heuristics(links, "", sender_domain="secure-verify-update.com", dmarc_pass=True)
    assert res.available
    assert res.has_strong_signal
    assert res.score >= 0.80
    assert any("points to 'secure-verify-update.com'" in ev for ev in res.evidence)


def test_display_name_brand_spoofing():
    """Display name claiming 'Amazon Fraud Department' with sender amazon-order-verification.co triggers strong brand spoofing."""
    raw_headers = [
        {
            "name": "Authentication-Results",
            "value": "mx.google.com; spf=pass smtp.mailfrom=amazon-order-verification.co; dkim=none; dmarc=none",
        },
        {"name": "From", "value": "Amazon Fraud Department <order-update@amazon-order-verification.co>"},
    ]
    res = evaluate_sender_auth(raw_headers, "Amazon Fraud Department <order-update@amazon-order-verification.co>")
    assert res.available
    assert res.has_strong_signal
    assert res.score >= 0.50
    assert any("claims brand 'amazon'" in ev.lower() for ev in res.evidence)


def test_deceptive_brand_root_domain():
    """Domain deceptively embedding netflix (netflix-billing-alert.com) triggers strong deceptive brand domain."""
    links = [
        {"url": "http://netflix-billing-alert.com/account", "text": "Update Payment Method"}
    ]
    res = evaluate_url_heuristics(links, "", sender_domain="netflix-billing-alert.com", dmarc_pass=False)
    assert res.available
    assert res.has_strong_signal
    assert res.score >= 0.80
    assert any("deceptively contains brand 'netflix'" in ev for ev in res.evidence)


def test_risky_attachment_extension():
    """Email with an .html or .pdf.exe attachment triggers strong risky attachment threat."""
    attachments = [{"filename": "invoice_october.pdf.exe", "size": 10240}]
    res = evaluate_url_heuristics([], "Please review invoice", sender_domain="vendor.com", attachments=attachments)
    assert res.available
    assert res.has_strong_signal
    assert res.score >= 0.80
    assert any("risky attachment" in ev.lower() or "dangerous file extension" in ev.lower() for ev in res.evidence)


def test_credential_solicitation_unauthenticated():
    """Sender asking for password & MFA token with no DMARC pass triggers strong credential solicitation signal."""
    raw_headers = [
        {
            "name": "Authentication-Results",
            "value": "mx.google.com; spf=none; dkim=none; dmarc=none",
        },
        {"name": "From", "value": "IT Helpdesk <support@viit-support.net>"},
    ]
    res = evaluate_sender_auth(
        raw_headers,
        "IT Helpdesk <support@viit-support.net>",
        subject="Password Expiration Notice",
        body_text="Your college password will expire. Please reply with your password and active MFA token.",
    )
    assert res.available
    assert res.has_strong_signal
    assert res.score >= 0.50
    assert any("solicits sensitive credentials" in ev.lower() for ev in res.evidence)


def test_corroboration_bert_alone_clean_auth_is_low_risk():
    """When SPF, DKIM, and DMARC all pass cleanly, and links are clean, BERT alone cannot flag the email."""
    auth_res = LayerResult("sender_auth", score=0.0, reason="All pass", available=True, is_fully_clean=True)
    url_res = LayerResult("url_heuristics", score=0.0, reason="Clean links", available=True)
    bert_res = LayerResult("bert_phishing", score=1.0, reason="High BERT semantic score", available=True)

    fusion = fuse_phishing_layers(
        layers=[auth_res, url_res, bert_res],
        sender_email="alerts@chase.com",
        known_contacts=set(),
        is_auth_clean=True,
    )
    assert fusion.fraud_score < 0.30
    assert fusion.fraud_label == "Low risk"


def test_corroboration_bert_with_missing_auth_is_flagged():
    """When authentication headers are absent (e.g. internal or missing header spoof), high BERT score is corroborated."""
    bert_res = LayerResult("bert_phishing", score=1.0, reason="High BERT semantic score", available=True)

    fusion = fuse_phishing_layers(
        layers=[bert_res],
        sender_email="user@viit.ac.in",
        known_contacts=set(),
        is_auth_clean=False,
    )
    assert fusion.fraud_score >= 0.60
    assert "Likely phishing" in fusion.fraud_label

