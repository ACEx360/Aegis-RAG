"""Tests for demo email dataset compliance with project specifications (§2, §14)."""

from __future__ import annotations

import datetime as dt

from app.ingest.demo_emails import get_demo_emails


def test_demo_emails_count():
    """Verify around 20 demo emails are provided."""
    demos = get_demo_emails()
    assert 18 <= len(demos) <= 25, f"Expected ~20 demo emails, got {len(demos)}"


def test_demo_emails_auth_results_presence():
    """All demo emails must contain realistic Authentication-Results headers (§14)."""
    demos = get_demo_emails()
    has_pass = False
    has_fail = False

    for item in demos:
        auth_headers = [h for h in item.schema.raw_headers if h.name == "Authentication-Results"]
        assert len(auth_headers) >= 1, f"Missing Authentication-Results in {item.schema.gmail_id}"
        val = auth_headers[0].value.lower()
        if "spf=pass" in val:
            has_pass = True
        if "spf=fail" in val:
            has_fail = True

    assert has_pass, "Expected at least one Authentication-Results with spf=pass"
    assert has_fail, "Expected at least one Authentication-Results with spf=fail"


def test_demo_phishing_that_passes_spf():
    """Section 14 requirement: include one phishing email that passes SPF."""
    demos = get_demo_emails()
    found = False

    for item in demos:
        if "phish" in item.schema.gmail_id:
            auth_val = next(
                (h.value for h in item.schema.raw_headers if h.name == "Authentication-Results"),
                "",
            )
            if "spf=pass" in auth_val.lower():
                found = True
                break

    assert found, "Section 14 requirement: must include one phishing email that passes SPF"


def test_demo_legit_urgent_email():
    """Section 14 requirement: include one legit-but-urgent email."""
    demos = get_demo_emails()
    legit_urgent = [
        item for item in demos
        if "legit" in item.schema.gmail_id and "urgent" in item.schema.subject.lower()
    ]
    assert len(legit_urgent) >= 1, "Section 14 requirement: must include one legit-but-urgent email"


def test_demo_read_emails_count():
    """Section 14 requirement: mark 4-5 as already read (is_read=True, opened_at set)."""
    demos = get_demo_emails()
    read_items = [item for item in demos if item.schema.is_read and item.opened_at is not None]
    assert 4 <= len(read_items) <= 6, f"Expected 4-5 pre-read emails, got {len(read_items)}"


def test_demo_domains_are_reserved():
    """Phishing emails must use fake/reserved domains (.example.*) (§14)."""
    demos = get_demo_emails()
    for item in demos:
        if "phish" in item.schema.gmail_id:
            sender = item.schema.sender.lower()
            assert any(
                domain in sender
                for domain in [".example.com", ".example.net", ".example.org"]
            ), f"Phishing email sender {sender} does not use reserved example domain"


def test_demo_dates_are_recent_and_tzaware():
    """Dates should be timezone-aware and relative to now."""
    demos = get_demo_emails()
    now = dt.datetime.now(dt.UTC)

    for item in demos:
        d = item.schema.date
        assert d is not None
        assert d.tzinfo is not None, f"Date {d} is not timezone-aware"
        # Must be within the last 7 days
        diff = now - d
        assert dt.timedelta(seconds=0) <= diff <= dt.timedelta(days=7)
