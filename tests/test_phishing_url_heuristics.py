"""Tests for URL heuristics provider (§7, §16, Stage 4)."""

from __future__ import annotations

from app.phishing.providers.url_heuristics import evaluate_url_heuristics


def test_url_heuristics_no_links_abstains():
    """Email with zero URLs returns available=False (§Change 3 & 8)."""
    res = evaluate_url_heuristics(links_data=[], body_text="Hello, please call me back.")
    assert res.available is False
    assert res.score == 0.0
    assert "No URLs found" in res.reason


def test_url_heuristics_ip_address_host():
    """Direct IP address in link host is flagged as a high threat."""
    links = [{"text": "Track Package", "href": "http://192.0.2.45/track?id=123"}]
    res = evaluate_url_heuristics(links, "")
    assert res.available is True
    assert res.score >= 0.75
    assert any("direct IP address" in ev for ev in res.evidence)


def test_url_heuristics_lookalike_domain():
    """Lookalike / typosquatting domain like paypa1 is flagged."""
    links = [{"text": "Verify", "href": "http://paypa1-secure.example.com/login"}]
    res = evaluate_url_heuristics(links, "")
    assert res.available is True
    assert res.score >= 0.60
    assert any("Lookalike domain" in ev for ev in res.evidence)


def test_url_heuristics_anchor_text_mismatch():
    """Anchor text displaying paypal.com but pointing to malicious host is flagged."""
    links = [
        {
            "text": "https://paypal.com/signin",
            "href": "http://paypa1-secure.example.com/auth",
        }
    ]
    res = evaluate_url_heuristics(links, "")
    assert res.available is True
    assert res.score >= 0.70
    assert getattr(res, "has_anchor_mismatch", False) is True
    assert any("Link text shows" in ev for ev in res.evidence)


def test_url_heuristics_open_redirect_not_exempt():
    """Forwarding parameter like google.com/url?q=evil.com is NOT exempt (§Change 2 & 8)."""
    links = [
        {
            "text": "Click Here",
            "href": "https://google.com/url?q=https://phishing-site.example.net/login",
        }
    ]
    res = evaluate_url_heuristics(links, "", sender_domain="google.com")
    assert res.available is True
    assert res.score >= 0.35
    assert any("Redirect/forwarding parameter" in ev for ev in res.evidence)


def test_url_heuristics_weak_signals_capped_and_deduped():
    """Weak-only signals (shortener, excessive subdomains, redirect) are deduped and capped at 0.40."""
    links = [
        {"text": "Link 1", "href": "https://bit.ly/3xZ9abc"},
        {"text": "Link 2", "href": "https://bit.ly/3xZ9abc"},  # Duplicate host
        {"text": "Link 3", "href": "https://tinyurl.com/another"},
        {"text": "Link 4", "href": "https://t.co/third"},
    ]
    res = evaluate_url_heuristics(links, "")
    assert res.available is True
    assert res.has_strong_signal is False
    # Capped at weak_signal_cap (0.40)
    assert res.score <= 0.40


def test_naukri_social_redirects_regression():
    """Anonymized regression: Naukri marketing email with redirect= to facebook/twitter/instagram has Low risk."""
    import json

    from app.db.models import Email
    from app.phishing.detector import detect_phishing_for_email

    raw_headers = [
        {
            "name": "Authentication-Results",
            "value": (
                "mx.google.com; "
                "spf=pass (google.com: domain of info@naukri.com) smtp.mailfrom=info@naukri.com; "
                "dkim=pass header.d=naukri.com; "
                "dmarc=pass (p=REJECT) header.from=naukri.com"
            ),
        },
        {"name": "From", "value": "Naukri Job Alerts <info@naukri.com>"},
        {"name": "Return-Path", "value": "<info@naukri.com>"},
    ]
    links = [
        {"text": "Recommended Jobs", "href": "https://tr.naukri.com/track?id=123&url=https://www.naukri.com/jobs"},
        {"text": "Facebook", "href": "https://tr.naukri.com/track?redirect=https://www.facebook.com/naukri"},
        {"text": "Twitter", "href": "https://tr.naukri.com/track?redirect=https://www.twitter.com/naukri"},
        {"text": "Instagram", "href": "https://tr.naukri.com/track?redirect=https://www.instagram.com/naukri"},
    ]

    em = Email(
        gmail_id="test-naukri-regression",
        sender="Naukri Job Alerts <info@naukri.com>",
        subject="Top job recommendations for you",
        raw_headers=json.dumps(raw_headers),
        links=json.dumps(links),
        body_text="Here are your latest job recommendations.\nFollow us on social media.",
        is_demo=False,
    )

    res = detect_phishing_for_email(em, db=None, force_refresh=True)
    assert res.fraud_score is not None
    assert res.fraud_score < 0.30, f"Expected Low risk score < 0.30, got {res.fraud_score}"
    assert res.fraud_label == "Low risk"


def test_kaggle_tracking_shortener_regression():
    """Anonymized regression: Kaggle newsletter with c.gle shortener link and bounce Return-Path has Low risk."""
    import json

    from app.db.models import Email
    from app.phishing.detector import detect_phishing_for_email

    raw_headers = [
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
    links = [
        {"text": "kaggle.com", "href": "https://c.gle/competition123"},
        {"text": "View Competition", "href": "https://c.gle/details456"},
    ]

    em = Email(
        gmail_id="test-kaggle-regression",
        sender="Kaggle <no-reply@kaggle.com>",
        subject="Competition Launch: Google Quantum AI",
        raw_headers=json.dumps(raw_headers),
        links=json.dumps(links),
        body_text="New competition launched on kaggle.com. Participate now at https://c.gle/competition123",
        is_demo=False,
    )

    res = detect_phishing_for_email(em, db=None, force_refresh=True)
    assert res.fraud_score is not None
    assert res.fraud_score < 0.30, f"Expected Low risk score < 0.30, got {res.fraud_score}"
    assert res.fraud_label == "Low risk"


def test_roadmap_tracking_redirect_regression():
    """Anonymized regression: roadmap.sh newsletter routing to updates.roadmap.sh with Hubspot bounce has Low risk."""
    import json

    from app.db.models import Email
    from app.phishing.detector import detect_phishing_for_email

    raw_headers = [
        {
            "name": "Authentication-Results",
            "value": (
                "mx.google.com; "
                "spf=pass (google.com: domain of bf57x.hubspotemail.net) smtp.mailfrom=bf57x.hubspotemail.net; "
                "dkim=pass header.d=roadmap.sh; "
                "dmarc=pass (p=REJECT) header.from=roadmap.sh"
            ),
        },
        {"name": "From", "value": "Kamran Ahmed <newsletter@email.roadmap.sh>"},
        {"name": "Return-Path", "value": "<bf57x.hubspotemail.net>"},
    ]
    links = [
        {"text": "time.fyi", "href": "https://updates.roadmap.sh/e3t/Ctc/L2+113/d5qLSh04/redirect_target"},
        {"text": "roadmap.sh", "href": "https://updates.roadmap.sh/e3t/Ctc/L2+113/d5qLSh04/home"},
    ]

    em = Email(
        gmail_id="test-roadmap-regression",
        sender="Kamran Ahmed <newsletter@email.roadmap.sh>",
        subject="One prompt won't design your landing page",
        raw_headers=json.dumps(raw_headers),
        links=json.dumps(links),
        body_text="Check out my new tool time.fyi for tracking.",
        is_demo=False,
    )

    res = detect_phishing_for_email(em, db=None, force_refresh=True)
    assert res.fraud_score is not None
    assert res.fraud_score < 0.30, f"Expected Low risk score < 0.30, got {res.fraud_score}"
    assert res.fraud_label == "Low risk"


def test_google_classroom_course_code_regression():
    """Anonymized regression: Google Classroom notification with course code anchor text has Low risk."""
    import json

    from app.db.models import Email
    from app.phishing.detector import detect_phishing_for_email

    raw_headers = [
        {
            "name": "Authentication-Results",
            "value": (
                "mx.google.com; "
                "spf=pass (google.com: domain of 3jK8b...bounces.google.com) smtp.mailfrom=bounces.google.com; "
                "dkim=pass header.d=classroom.google.com; "
                "dmarc=pass (p=REJECT) header.from=classroom.google.com"
            ),
        },
        {"name": "From", "value": "Prof. Smith (Classroom) <no-reply@classroom.google.com>"},
        {"name": "Return-Path", "value": "<bounces.google.com>"},
    ]
    links = [
        {"text": "OR_B.Tech_206-27_DS_SEM-1", "href": "https://accounts.google.com/AccountChooser?continue=https://classroom.google.com"},
        {"text": "Open Assignment", "href": "https://classroom.google.com/c/MzcxOTU2NDU1NzM5"},
    ]

    em = Email(
        gmail_id="test-classroom-regression",
        sender="Prof. Smith (Classroom) <no-reply@classroom.google.com>",
        subject='New announcement: "Notes PPT / Study material"',
        raw_headers=json.dumps(raw_headers),
        links=json.dumps(links),
        body_text="Prof. Smith posted a new announcement in OR_B.Tech_206-27_DS_SEM-1.",
        is_demo=False,
    )

    res = detect_phishing_for_email(em, db=None, force_refresh=True)
    assert res.fraud_score is not None
    assert res.fraud_score < 0.30, f"Expected Low risk score < 0.30, got {res.fraud_score}"
    assert res.fraud_label == "Low risk"


def test_url_heuristics_evil_subdomain_not_allowlisted():
    """naukri.com.evil.net must NOT match naukri allowlist (§Change 2 & 8)."""
    links = [
        {
            "text": "View Jobs",
            "href": "https://naukri.com.evil.net/jobs/apply",
        }
    ]
    res = evaluate_url_heuristics(links, "", sender_domain="naukri.com")
    assert res.available is True
    # evil.net has foreign subdomain with brand naukri, so it should be flagged!
    assert res.score >= 0.50
    assert any("spoofed in subdomain" in ev or "Suspiciously excessive" in ev for ev in res.evidence)


def test_url_heuristics_legit_naukri_tracking_allowed():
    """Legitimate Naukri tracking link from Naukri sender is NOT penalized (§Change 2)."""
    links = [
        {
            "text": "Apply to Software Engineer",
            "href": "https://tr.naukri.com/track?jobId=982341&src=daily_digest",
        }
    ]
    res = evaluate_url_heuristics(links, "", sender_domain="naukri.com")
    assert res.available is True
    assert res.score == 0.0
    assert any("no suspicious patterns found" in res.reason.lower() for _ in [1])


def test_url_heuristics_shortener_flagged():
    """URL shortener like bit.ly is flagged."""
    links = [{"text": "Special Offer", "href": "https://bit.ly/3xZ9abc"}]
    res = evaluate_url_heuristics(links, "")
    assert res.available is True
    assert res.score >= 0.25
    assert any("URL shortener" in ev for ev in res.evidence)

