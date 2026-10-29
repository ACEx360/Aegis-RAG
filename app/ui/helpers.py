"""UI helper utilities for newsletter detection and Swagger-style styling."""

from __future__ import annotations

import json
from typing import Any

from app.settings import settings


def parse_json_safely(val: Any) -> list:
    """Parse JSON string into Python list, returning empty list on failure."""
    if isinstance(val, list):
        return val
    if not val:
        return []
    try:
        res = json.loads(val)
        return res if isinstance(res, list) else []
    except Exception:
        return []


def is_newsletter_email(raw_headers: Any, labels: Any) -> bool:
    """Determine if an email is a newsletter per §9.

    Signals:
    - 'List-Unsubscribe' header present
    - 'Precedence: bulk' header
    - Gmail labels: 'CATEGORY_PROMOTIONS' or 'CATEGORY_UPDATES'
    """
    label_list = parse_json_safely(labels)
    for lbl in label_list:
        if lbl in ("CATEGORY_PROMOTIONS", "CATEGORY_UPDATES"):
            return True

    header_list = parse_json_safely(raw_headers)
    for h in header_list:
        if isinstance(h, dict):
            name = str(h.get("name", "")).strip().lower()
            val = str(h.get("value", "")).strip().lower()
            if name == "list-unsubscribe":
                return True
            if name == "precedence" and val == "bulk":
                return True

    return False


def get_email_styling(email: Any) -> dict[str, Any]:
    """Calculate border colors and badge descriptors for an email row.

    Colors (§9):
    - Red = likely fraud (fraud_score >= threshold)
    - Amber = high priority (priority_label == 'High' or priority_score >= threshold)
    - Grey = newsletter
    - Green = low/medium priority
    - Slate/Grey = unanalyzed real email
    """
    raw_h = getattr(email, "raw_headers", "[]")
    lbls = getattr(email, "labels", "[]")
    newsletter = is_newsletter_email(raw_h, lbls)

    fraud_score = getattr(email, "fraud_score", None)
    fraud_label = getattr(email, "fraud_label", None)
    priority_score = getattr(email, "priority_score", None)
    priority_label = getattr(email, "priority_label", None)

    is_fraud = fraud_score is not None and fraud_score >= settings.fraud_threshold
    is_suspicious = (
        fraud_score is not None
        and settings.fraud_suspicious_threshold <= fraud_score < settings.fraud_threshold
    )
    if not fraud_label:
        if fraud_score is not None:
            if fraud_score >= settings.fraud_threshold:
                fraud_label = f"Likely phishing - {int(fraud_score * 100)}% confidence"
            elif fraud_score >= settings.fraud_suspicious_threshold:
                fraud_label = "Suspicious"
            else:
                fraud_label = "Low risk"
        else:
            fraud_label = "Not analyzed yet"
    is_high_priority = (
        priority_label == "High"
        or (priority_score is not None and priority_score >= settings.priority_high_threshold)
    )

    # Border color
    if is_fraud:
        border_class = "border-l-rose-500 hover:border-l-rose-400 bg-rose-950/10"
        tag_color = "rose"
    elif is_high_priority:
        border_class = "border-l-amber-500 hover:border-l-amber-400 bg-amber-950/10"
        tag_color = "amber"
    elif newsletter:
        border_class = "border-l-slate-500 hover:border-l-slate-400 bg-slate-900/40"
        tag_color = "slate"
    elif priority_score is not None:
        border_class = "border-l-emerald-500 hover:border-l-emerald-400 bg-emerald-950/10"
        tag_color = "emerald"
    else:
        # Real email without analysis yet (Change 2)
        border_class = "border-l-slate-700 hover:border-l-slate-600 bg-slate-900/30"
        tag_color = "neutral"

    return {
        "is_newsletter": newsletter,
        "is_fraud": is_fraud,
        "is_suspicious": is_suspicious,
        "is_high_priority": is_high_priority,
        "border_class": border_class,
        "tag_color": tag_color,
        "fraud_pct": int(fraud_score * 100) if fraud_score is not None else None,
        "fraud_label": fraud_label,
        "priority_score": int(priority_score) if priority_score is not None else None,
        "priority_label": priority_label,
        "is_unanalyzed": priority_score is None and fraud_score is None,
    }

