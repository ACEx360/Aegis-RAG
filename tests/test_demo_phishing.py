"""Tests verifying phishing detection behavior on built-in demo emails (§7, §14, Stage 4)."""

from __future__ import annotations

import json

from app.db.models import Email
from app.ingest.demo_emails import get_demo_emails
from app.phishing.detector import detect_phishing_for_email
from app.settings import settings


def _build_email_from_demo(item) -> Email:
    """Helper to convert DemoEmail to Email ORM instance for detector evaluation."""
    schema = item.schema
    raw_headers_dicts = [h.model_dump() for h in schema.raw_headers]
    links_data = [{"text": "", "href": href} for href in schema.links]
    return Email(
        gmail_id=schema.gmail_id,
        thread_id=schema.thread_id,
        subject=schema.subject,
        sender=schema.sender,
        recipients=json.dumps(schema.recipients),
        date=schema.date,
        body_text=schema.body_text,
        body_html=schema.body_html,
        links=json.dumps(links_data),
        snippet=schema.snippet,
        labels=json.dumps(schema.labels),
        raw_headers=json.dumps(raw_headers_dicts),
        has_attachments=schema.has_attachments,
        attachment_meta=json.dumps(schema.attachment_meta),
        is_read=schema.is_read,
        is_demo=True,
    )


def test_demo_phishing_emails_are_flagged():
    """All 5 demo phishing emails must be flagged with score >= fraud_threshold (§Pass 4a)."""
    demos = get_demo_emails()
    phish_demos = [d for d in demos if "phish" in d.schema.gmail_id]
    assert len(phish_demos) >= 5, "Expected at least 5 demo phishing emails"

    for item in phish_demos:
        em = _build_email_from_demo(item)
        res = detect_phishing_for_email(em, db=None, force_refresh=True)

        assert res.fraud_score is not None, f"Email {em.gmail_id} has None score"
        assert (
            res.fraud_score >= settings.fraud_threshold
        ), f"Email {em.gmail_id} scored {res.fraud_score}, expected >= {settings.fraud_threshold}"
        assert (
            "Likely phishing" in res.fraud_label
        ), f"Email {em.gmail_id} labeled '{res.fraud_label}', expected 'Likely phishing'"


def test_demo_phish_005_passing_spf_is_flagged():
    """demo-phish-005 passes SPF but must be flagged via header discrepancies (§14 & §Pass 4a)."""
    demos = get_demo_emails()
    phish_005 = next(d for d in demos if d.schema.gmail_id == "demo-phish-005")
    em = _build_email_from_demo(phish_005)

    # Verify SPF pass header is present
    raw_h = json.loads(em.raw_headers)
    auth_header = next(h["value"] for h in raw_h if h["name"] == "Authentication-Results")
    assert "spf=pass" in auth_header.lower(), "demo-phish-005 must have spf=pass per §14"

    res = detect_phishing_for_email(em, db=None, force_refresh=True)

    assert res.fraud_score is not None and res.fraud_score >= settings.fraud_threshold
    assert "Likely phishing" in res.fraud_label
    # Verify evidence highlights the Return-Path or DMARC failure
    evidence_str = " ".join(res.fraud_evidence)
    assert "Return-Path" in evidence_str or "DMARC" in evidence_str


def test_demo_newsletters_are_not_flagged():
    """Demo newsletters must NOT be flagged as phishing (§Pass 4a)."""
    demos = get_demo_emails()
    news_demos = [d for d in demos if "news" in d.schema.gmail_id]
    assert len(news_demos) >= 3

    for item in news_demos:
        em = _build_email_from_demo(item)
        res = detect_phishing_for_email(em, db=None, force_refresh=True)

        assert res.fraud_score is not None
        assert (
            res.fraud_score < settings.fraud_threshold
        ), f"Newsletter {em.gmail_id} unexpectedly scored {res.fraud_score}"
        assert "Likely phishing" not in res.fraud_label


def test_demo_legit_urgent_email_is_not_flagged():
    """demo-legit-001 (professor thesis draft review) must NOT be flagged (§14 & §Pass 4a)."""
    demos = get_demo_emails()
    legit_001 = next(d for d in demos if d.schema.gmail_id == "demo-legit-001")
    em = _build_email_from_demo(legit_001)

    res = detect_phishing_for_email(em, db=None, force_refresh=True)

    assert res.fraud_score is not None
    assert (
        res.fraud_score < settings.fraud_threshold
    ), f"Legit email {em.gmail_id} scored {res.fraud_score}"
    assert "Likely phishing" not in res.fraud_label
