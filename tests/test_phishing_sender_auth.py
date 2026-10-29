"""Tests for sender authentication provider (§7, §14, Stage 4)."""

from __future__ import annotations

from app.phishing.providers.sender_auth import evaluate_sender_auth


def test_sender_auth_valid_passes():
    """Legitimate email with all passing auth results and aligned domains scores 0.0."""
    headers = [
        {
            "name": "Authentication-Results",
            "value": (
                "mx.google.com; "
                "spf=pass (google.com: domain of user@example.com) smtp.mailfrom=user@example.com; "
                "dkim=pass header.d=example.com; "
                "dmarc=pass (p=REJECT) header.from=example.com"
            ),
        },
        {"name": "From", "value": "Example User <user@example.com>"},
        {"name": "Return-Path", "value": "<user@example.com>"},
    ]
    res = evaluate_sender_auth(headers, "Example User <user@example.com>")

    assert res.available is True
    assert res.score == 0.0
    assert any("SPF check result: pass" in ev for ev in res.evidence)
    assert any("DKIM check result: pass" in ev for ev in res.evidence)
    assert any("DMARC check result: pass" in ev for ev in res.evidence)


def test_sender_auth_forged_header_ignored():
    """Forged Authentication-Results header (not mx.google.com) is ignored (§Change 1 & 8)."""
    headers = [
        # Forged/fake header injected by attacker
        {
            "name": "Authentication-Results",
            "value": "fake-relayer.net; spf=pass; dkim=pass; dmarc=pass",
        },
        # Legitimate Google MX header
        {
            "name": "Authentication-Results",
            "value": (
                "mx.google.com; "
                "spf=fail smtp.mailfrom=attacker.org; "
                "dkim=fail header.d=example.com; "
                "dmarc=fail header.from=example.com"
            ),
        },
        {"name": "From", "value": "Service <alert@example.com>"},
    ]
    res = evaluate_sender_auth(headers, "Service <alert@example.com>")

    assert res.available is True
    assert res.score >= 0.50  # Real mx.google.com result (fail) was used
    # Evidence notes that the forged header was ignored
    assert any("Ignored untrusted/extra Authentication-Results header" in ev for ev in res.evidence)


def test_sender_auth_no_trusted_header_abstains():
    """Email with no mx.google.com Authentication-Results header returns available=False (§Change 3)."""
    headers = [
        {"name": "From", "value": "User <user@example.com>"},
        {"name": "Subject", "value": "Hello"},
    ]
    res = evaluate_sender_auth(headers, "User <user@example.com>")

    assert res.available is False
    assert res.score == 0.0
    assert "No trusted Authentication-Results header" in res.reason


def test_sender_auth_return_path_mismatch():
    """From domain mismatching Return-Path domain when DMARC fails is flagged (§Fix 1)."""
    headers = [
        {
            "name": "Authentication-Results",
            "value": (
                "mx.google.com; "
                "spf=pass (google.com: domain of bounce@attacker.net) smtp.mailfrom=bounce@attacker.net; "
                "dkim=fail; dmarc=fail header.from=bank.com"
            ),
        },
        {"name": "From", "value": "Bank Security <security@bank.com>"},
        {"name": "Return-Path", "value": "<bounce@attacker.net>"},
    ]
    res = evaluate_sender_auth(headers, "Bank Security <security@bank.com>")

    assert res.available is True
    assert res.score >= 0.60
    assert any("does not match Return-Path" in ev for ev in res.evidence)


def test_sender_auth_return_path_mismatch_with_dmarc_pass_is_info():
    """When dmarc=pass, Return-Path mismatch (e.g. bounce domain) is normal and scores 0.0 (§Fix 1)."""
    headers = [
        {
            "name": "Authentication-Results",
            "value": (
                "mx.google.com; "
                "spf=pass (google.com: domain of scoutcamp.bounces.google.com) smtp.mailfrom=scoutcamp.bounces.google.com; "
                "dkim=pass header.d=kaggle.com; "
                "dmarc=pass (p=REJECT) header.from=kaggle.com"
            ),
        },
        {"name": "From", "value": "Kaggle <no-reply@kaggle.com>"},
        {"name": "Return-Path", "value": "<scoutcamp.bounces.google.com>"},
    ]
    res = evaluate_sender_auth(headers, "Kaggle <no-reply@kaggle.com>")

    assert res.available is True
    assert res.score == 0.0
    assert res.has_strong_signal is False
    assert res.is_fully_clean is True
    assert any("[INFO]" in ev for ev in res.evidence)


def test_sender_auth_reply_to_mismatch():
    """From domain mismatching Reply-To domain is flagged."""
    headers = [
        {
            "name": "Authentication-Results",
            "value": "mx.google.com; spf=pass; dkim=pass; dmarc=pass",
        },
        {"name": "From", "value": "CEO <ceo@company.com>"},
        {"name": "Reply-To", "value": "CEO Direct <ceo.direct@freemail.net>"},
    ]
    res = evaluate_sender_auth(headers, "CEO <ceo@company.com>")

    assert res.available is True
    assert res.score >= 0.40
    assert any("does not match Reply-To domain" in ev for ev in res.evidence)


def test_sender_auth_display_name_spoofing():
    """Display name embedding a foreign address or brand is flagged."""
    headers = [
        {
            "name": "Authentication-Results",
            "value": "mx.google.com; spf=pass; dkim=pass; dmarc=pass",
        },
        {"name": "From", "value": '"security@paypal.com" <phisher@malicious.com>'},
    ]
    res = evaluate_sender_auth(headers, '"security@paypal.com" <phisher@malicious.com>')

    assert res.available is True
    assert res.score >= 0.35
    assert any("foreign address" in ev or "brand" in ev for ev in res.evidence)

