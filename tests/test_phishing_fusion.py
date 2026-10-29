"""Tests for risk fusion and trust signal logic (§7, §16, Stage 4)."""

from __future__ import annotations

from app.phishing.fusion import fuse_phishing_layers
from app.phishing.providers.base import LayerResult


def test_fusion_renormalization_when_layer_unavailable():
    """Unavailable layer drops out and remaining available layers re-normalize (§Change 3)."""
    # sender_auth available=True, score=0.60
    l1 = LayerResult(name="sender_auth", score=0.60, reason="Auth fail", available=True)
    # url_heuristics available=False (no links in email)
    l2 = LayerResult(name="url_heuristics", score=0.0, reason="No links", available=False)

    res = fuse_phishing_layers([l1, l2], "sender@example.com", set())
    # Since url_heuristics is unavailable, it does NOT vote 0.0. sender_auth weight re-normalizes to 1.0!
    assert res.fraud_score == 0.60
    assert "Likely phishing" in res.fraud_label


def test_fusion_strong_layer_floor():
    """If any available layer >= 0.8 with a STRONG signal, final score >= 0.6 floor (§Change 3)."""
    # l1 scores 0.85 with strong signal (e.g. IP host), l2 scores 0.0
    l1 = LayerResult(name="url_heuristics", score=0.85, reason="IP URL", available=True, has_strong_signal=True)
    l2 = LayerResult(name="sender_auth", score=0.0, reason="Auth pass", available=True, has_strong_signal=False)

    res = fuse_phishing_layers([l1, l2], "sender@example.com", set())
    # Strong layer floor elevates it to >= 0.60
    assert res.fraud_score is not None and res.fraud_score >= 0.60
    assert "Likely phishing" in res.fraud_label


def test_fusion_strong_layer_floor_requires_strong_signal():
    """Strong layer floor does NOT apply if layer has no strong signal (§Change 3)."""
    # Layer has high score but only weak signals
    l1 = LayerResult(name="url_heuristics", score=0.80, reason="Many weak links", available=True, has_strong_signal=False)
    l2 = LayerResult(name="sender_auth", score=0.0, reason="Auth pass", available=True, has_strong_signal=False)

    res = fuse_phishing_layers([l1, l2], "sender@example.com", set())
    # Weighted average: (0.80 * 0.35 + 0.0) / 0.70 = 0.40, floor does NOT trigger 0.60!
    assert res.fraud_score == 0.40
    assert res.fraud_label == "Suspicious"


def test_fusion_clean_auth_caps_weak_url_below_suspicious():
    """If sender_auth is fully clean and URL evidence is weak, final score stays below Suspicious (§Change 4)."""
    l1 = LayerResult(name="sender_auth", score=0.0, reason="All pass", available=True, is_fully_clean=True)
    l2 = LayerResult(name="url_heuristics", score=0.40, reason="Weak links", available=True, has_strong_signal=False)

    res = fuse_phishing_layers([l1, l2], "sender@example.com", set(), is_auth_clean=True)
    # Must stay below suspicious threshold (<0.30)
    assert res.fraud_score is not None and res.fraud_score < 0.30
    assert res.fraud_label == "Low risk"


def test_fusion_bands_low_risk_never_safe():
    """Low scores are labeled 'Low risk' and never 'Safe' (§Change 5)."""
    l1 = LayerResult(name="sender_auth", score=0.05, reason="Clear", available=True)
    l2 = LayerResult(name="url_heuristics", score=0.0, reason="Clear", available=True)

    res = fuse_phishing_layers([l1, l2], "sender@example.com", set())
    assert res.fraud_score is not None and res.fraud_score < 0.30
    assert res.fraud_label == "Low risk"
    assert "Safe" not in res.fraud_label


def test_fusion_bands_suspicious():
    """Scores between 0.30 and 0.50 are labeled 'Suspicious'."""
    l1 = LayerResult(name="sender_auth", score=0.40, reason="Mismatch", available=True)
    l2 = LayerResult(name="url_heuristics", score=0.40, reason="Insecure link", available=True)

    res = fuse_phishing_layers([l1, l2], "sender@example.com", set())
    assert res.fraud_score is not None and 0.30 <= res.fraud_score < 0.50
    assert res.fraud_label == "Suspicious"


def test_trust_signal_applied():
    """Trust discount reduces fraud score when sender in sent contacts and all checks pass (§Change 6)."""
    l1 = LayerResult(name="sender_auth", score=0.35, reason="Minor note", available=True)
    known = {"colleague@workspace.example.com"}

    res = fuse_phishing_layers(
        [l1],
        "colleague@workspace.example.com",
        known,
        spf_pass=True,
        dkim_pass=True,
        has_reply_to_mismatch=False,
        has_anchor_mismatch=False,
    )

    assert res.trust_discount_applied is True
    # 0.35 - 0.30 = 0.05
    assert res.fraud_score == 0.05
    assert res.fraud_label == "Low risk"
    assert any("trust discount" in ev.lower() for ev in res.fraud_evidence)


def test_trust_signal_denied_on_reply_to_mismatch():
    """Trust discount is DENIED if there is a Reply-To mismatch (§Change 6)."""
    l1 = LayerResult(name="sender_auth", score=0.35, reason="Minor note", available=True)
    known = {"colleague@workspace.example.com"}

    res = fuse_phishing_layers(
        [l1],
        "colleague@workspace.example.com",
        known,
        spf_pass=True,
        dkim_pass=True,
        has_reply_to_mismatch=True,  # Reply-To mismatch!
        has_anchor_mismatch=False,
    )

    assert res.trust_discount_applied is False
    assert res.fraud_score == 0.35
    assert any("Reply-To mismatch was detected" in ev for ev in res.fraud_evidence)


def test_trust_signal_denied_on_anchor_mismatch():
    """Trust discount is DENIED if there is an anchor-text mismatch (§Change 6)."""
    l1 = LayerResult(name="url_heuristics", score=0.40, reason="Link issue", available=True)
    known = {"colleague@workspace.example.com"}

    res = fuse_phishing_layers(
        [l1],
        "colleague@workspace.example.com",
        known,
        spf_pass=True,
        dkim_pass=True,
        has_reply_to_mismatch=False,
        has_anchor_mismatch=True,  # Anchor mismatch!
    )

    assert res.trust_discount_applied is False
    assert res.fraud_score == 0.40
    assert any("anchor-text vs href mismatch was detected" in ev for ev in res.fraud_evidence)


def test_trust_signal_denied_on_auth_failure():
    """Trust discount is DENIED if SPF or DKIM failed (§Change 6)."""
    l1 = LayerResult(name="sender_auth", score=0.40, reason="Auth fail", available=True)
    known = {"colleague@workspace.example.com"}

    res = fuse_phishing_layers(
        [l1],
        "colleague@workspace.example.com",
        known,
        spf_pass=False,  # Failed SPF!
        dkim_pass=True,
        has_reply_to_mismatch=False,
        has_anchor_mismatch=False,
    )

    assert res.trust_discount_applied is False
    assert res.fraud_score == 0.40
    assert any("SPF or DKIM failed verification" in ev for ev in res.fraud_evidence)

