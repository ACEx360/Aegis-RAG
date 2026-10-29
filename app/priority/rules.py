"""Rule-based priority scoring and feature fact generation (§Stage 3).

Computes baseline priority score (0-100), rule facts, and enforces hard rule caps
(e.g. bulk and promotional emails can never be rated High).
"""

from __future__ import annotations

import email.utils as email_utils
import json
import re
from typing import Any

from app.db.models import Email

URGENCY_PATTERN = re.compile(
    r"\b(urgent|asap|deadline|action required|immediate|today|tomorrow|by eod|by cob|time-sensitive|reminder|final notice|due date)\b",
    re.IGNORECASE,
)
COLLAB_PATTERN = re.compile(
    r"\b(sync|meeting|review|agenda|proposal|contract|invoice|payment|interview|offer letter|schedule)\b",
    re.IGNORECASE,
)


def evaluate_priority_rules(
    email: Email,
    known_contacts: set[str],
) -> dict[str, Any]:
    """Evaluate baseline rules and return structured scoring results.

    Returns:
    {
        "rule_score": float (0-100),
        "rule_facts": list[str] (plain-text factual statements),
        "is_clearly_low": bool (whether LLM call can be safely skipped),
        "is_bulk_or_promo": bool,
        "max_score_cap": float | None (enforces hard cap, e.g. 40.0 for bulk/promo),
    }
    """
    rule_score = 50.0
    rule_facts: list[str] = []

    # 1. Known contact evaluation
    sender_addr = ""
    if email.sender:
        _, addr = email_utils.parseaddr(email.sender)
        sender_addr = addr.lower().strip()

    if sender_addr and sender_addr in known_contacts:
        rule_score += 25.0
        rule_facts.append(
            f"Sender '{sender_addr}' is a known contact you have previously corresponded with."
        )
    elif sender_addr:
        rule_facts.append(f"Sender '{sender_addr}' is not in your frequent sent contacts list.")

    # 2. Gmail labels evaluation
    labels: list[str] = []
    if email.labels:
        try:
            labels = json.loads(email.labels)
        except Exception:
            labels = []

    if "IMPORTANT" in labels:
        rule_score += 20.0
        rule_facts.append("Email carries the Gmail 'IMPORTANT' priority label.")

    is_promo = "CATEGORY_PROMOTIONS" in labels
    is_social = "CATEGORY_SOCIAL" in labels
    is_updates = "CATEGORY_UPDATES" in labels

    if is_promo:
        rule_score -= 30.0
        rule_facts.append("Email is categorized under Gmail Promotions.")
    if is_social:
        rule_score -= 20.0
        rule_facts.append("Email is categorized under Gmail Social.")
    if is_updates:
        rule_score -= 15.0
        rule_facts.append("Email is categorized under Gmail Updates (automated transactional notice).")

    # 3. Header check: List-Unsubscribe / bulk precedence
    is_bulk = False
    raw_headers = []
    if email.raw_headers:
        try:
            raw_headers = json.loads(email.raw_headers)
        except Exception:
            raw_headers = []

    for h in raw_headers:
        name = h.get("name", "").lower()
        val = h.get("value", "").lower()
        if name == "list-unsubscribe" or name == "precedence" and val in ("bulk", "list", "junk"):
            is_bulk = True

    if is_bulk:
        rule_score -= 30.0
        rule_facts.append("Email headers contain automated bulk/mailing-list indicators (List-Unsubscribe/Precedence).")

    # 4. Deadlines & Urgency keyword analysis
    subject_text = email.subject or ""
    body_head = (email.body_text or "")[:1500]
    combined_search_text = f"{subject_text} {body_head}"

    urgent_matches = URGENCY_PATTERN.findall(combined_search_text)
    if urgent_matches:
        unique_matches = sorted({m.lower() for m in urgent_matches})[:3]
        rule_score += 20.0
        rule_facts.append(
            f"Subject or body contains time-sensitive urgency keywords: {', '.join(unique_matches)}."
        )

    # 5. Work / collaboration terms
    collab_matches = COLLAB_PATTERN.findall(subject_text)
    if collab_matches:
        unique_collab = sorted({m.lower() for m in collab_matches})[:2]
        rule_score += 10.0
        rule_facts.append(
            f"Subject contains collaboration / project keywords: {', '.join(unique_collab)}."
        )

    # Clamp baseline rule score
    rule_score = max(0.0, min(100.0, rule_score))

    is_bulk_or_promo = is_promo or is_bulk
    max_score_cap = 40.0 if is_bulk_or_promo else None
    if max_score_cap is not None and rule_score > max_score_cap:
        rule_score = max_score_cap

    is_clearly_low = is_bulk_or_promo or rule_score <= 30.0

    return {
        "rule_score": round(rule_score, 1),
        "rule_facts": rule_facts,
        "is_clearly_low": is_clearly_low,
        "is_bulk_or_promo": is_bulk_or_promo,
        "max_score_cap": max_score_cap,
    }
