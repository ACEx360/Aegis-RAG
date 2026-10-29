"""Phishing detection pipeline orchestrator (§7, §16, Stage 4).

Coordinates:
1. Sender authentication evaluation (app/phishing/providers/sender_auth.py)
2. URL heuristics evaluation (app/phishing/providers/url_heuristics.py)
3. Sent-contacts trust verification
4. Risk fusion and database field persistence
"""

from __future__ import annotations

import email.utils
import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Email
from app.phishing.fusion import FusionResult, fuse_phishing_layers
from app.phishing.providers.sender_auth import evaluate_sender_auth
from app.phishing.providers.url_heuristics import evaluate_url_heuristics
from app.rag.history import get_known_contacts
from app.settings import settings

logger = logging.getLogger(__name__)


def _parse_json_safely(val: Any) -> list:
    """Parse JSON string safely or return empty list."""
    if isinstance(val, list):
        return val
    if not val:
        return []
    try:
        res = json.loads(val)
        return res if isinstance(res, list) else []
    except Exception:
        return []


def _extract_sender_email(sender_str: str) -> str:
    """Extract strictly the email address part from a sender string."""
    _, addr = email.utils.parseaddr(sender_str)
    return addr.strip().lower()


def detect_phishing_for_email(
    email_obj: Email,
    db: Session | None = None,
    force_refresh: bool = False,
) -> FusionResult:
    """Run active phishing detection layers, perform risk fusion, and store results on email_obj."""
    # Skip if already evaluated at current version unless force_refresh is True (§Change 7)
    if (
        not force_refresh
        and email_obj.fraud_score is not None
        and email_obj.fraud_version == settings.fraud_version
    ):
        return FusionResult(
            fraud_score=email_obj.fraud_score,
            fraud_label=email_obj.fraud_label or "Low risk",
            fraud_reason=email_obj.fraud_reason or "",
            fraud_evidence=_parse_json_safely(email_obj.fraud_evidence),
            layers_data=_parse_json_safely(email_obj.fraud_layers),
        )

    raw_headers = _parse_json_safely(email_obj.raw_headers)
    links_data = _parse_json_safely(email_obj.links)
    body_text = email_obj.body_text or ""
    sender_addr = _extract_sender_email(email_obj.sender)
    sender_domain = sender_addr.split("@")[-1] if "@" in sender_addr else ""

    # 1. Run sender_auth layer (§Pass 4a)
    auth_result = evaluate_sender_auth(raw_headers, email_obj.sender)

    # Inspect auth results for trust signal and tracker redirect checks
    spf_pass = any("spf check result: pass" in ev.lower() for ev in auth_result.evidence)
    dkim_pass = any("dkim check result: pass" in ev.lower() for ev in auth_result.evidence)
    dmarc_pass = any("dmarc check result: pass" in ev.lower() for ev in auth_result.evidence)
    has_reply_to_mismatch = any("reply-to" in ev.lower() and "does not match" in ev.lower() for ev in auth_result.evidence)
    is_auth_clean = getattr(auth_result, "is_fully_clean", False)

    # 2. Run url_heuristics layer (§Pass 4a)
    url_result = evaluate_url_heuristics(
        links_data,
        body_text,
        sender_domain=sender_domain,
        dmarc_pass=dmarc_pass,
    )
    has_anchor_mismatch = getattr(url_result, "has_anchor_mismatch", False)

    layers = [auth_result, url_result]

    # 3. Known contacts (§Trust Signal)
    known_contacts = get_known_contacts(email_obj.is_demo)

    # 4. Fuse layers
    fusion_result = fuse_phishing_layers(
        layers=layers,
        sender_email=sender_addr,
        known_contacts=known_contacts,
        spf_pass=spf_pass,
        dkim_pass=dkim_pass,
        has_reply_to_mismatch=has_reply_to_mismatch,
        has_anchor_mismatch=has_anchor_mismatch,
        is_auth_clean=is_auth_clean,
    )

    # 5. Persist to email model
    email_obj.fraud_score = fusion_result.fraud_score
    email_obj.fraud_label = fusion_result.fraud_label
    email_obj.fraud_reason = fusion_result.fraud_reason
    email_obj.fraud_layers = json.dumps(fusion_result.layers_data)
    email_obj.fraud_evidence = json.dumps(fusion_result.fraud_evidence)
    email_obj.fraud_version = settings.fraud_version

    if db is not None:
        try:
            db.commit()
            db.refresh(email_obj)
        except Exception as exc:
            logger.debug("Failed committing fraud detection for email %s: %s", email_obj.gmail_id, exc)

    return fusion_result

