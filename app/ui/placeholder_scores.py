"""Temporary placeholder score assignment for demo emails.

TODO: replace in Stages 3-4 with the real priority classifier (Stage 3)
and phishing detection pipeline (Stage 4).

Per Stage 2 specification:
- Applies ONLY to demo emails (`is_demo=True`).
- Real emails (`is_demo=False`) must NEVER receive placeholder scores and
  remain NULL to display the 'Not analyzed yet' state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models import Email


def assign_placeholder_scores(email: Email) -> None:
    """Assign plausible static scores to built-in demo emails.

    Has no effect if email is not a demo email (`is_demo=False`).
    """
    if not email.is_demo:
        # Real emails keep NULL scores until processed by Stages 3 & 4
        return

    gid = email.gmail_id

    # 1. Phishing sample emails
    if "phish-001" in gid:
        email.fraud_score = 0.94
        email.priority_score = 25.0
        email.priority_label = "Low"
    elif "phish-002" in gid:
        email.fraud_score = 0.91
        email.priority_score = 30.0
        email.priority_label = "Low"
    elif "phish-003" in gid:
        email.fraud_score = 0.88
        email.priority_score = 40.0
        email.priority_label = "Medium"
    elif "phish-004" in gid:
        email.fraud_score = 0.85
        email.priority_score = 20.0
        email.priority_label = "Low"
    elif "phish-005" in gid:
        # Phishing email that passes SPF (§14)
        email.fraud_score = 0.87
        email.priority_score = 35.0
        email.priority_label = "Low"

    # 2. Legit urgent email (§14)
    elif "legit-001" in gid:
        email.fraud_score = 0.02
        email.priority_score = 96.0
        email.priority_label = "High"

    # 3. Newsletters
    elif "news-001" in gid:
        email.fraud_score = 0.01
        email.priority_score = 25.0
        email.priority_label = "Low"
    elif "news-002" in gid:
        email.fraud_score = 0.02
        email.priority_score = 20.0
        email.priority_label = "Low"
    elif "news-003" in gid:
        email.fraud_score = 0.01
        email.priority_score = 30.0
        email.priority_label = "Low"

    # 4. Work emails
    elif "work-001" in gid:
        email.fraud_score = 0.03
        email.priority_score = 82.0
        email.priority_label = "High"
    elif "work-002" in gid:
        email.fraud_score = 0.04
        email.priority_score = 88.0
        email.priority_label = "High"
    elif "work-003" in gid:
        email.fraud_score = 0.05
        email.priority_score = 75.0
        email.priority_label = "High"

    # 5. Personal emails
    elif "pers-001" in gid:
        email.fraud_score = 0.02
        email.priority_score = 65.0
        email.priority_label = "Medium"
    elif "pers-002" in gid:
        email.fraud_score = 0.01
        email.priority_score = 55.0
        email.priority_label = "Medium"
    elif "pers-003" in gid:
        email.fraud_score = 0.02
        email.priority_score = 70.0
        email.priority_label = "High"

    # 6. Notifications
    elif "notif-001" in gid:
        email.fraud_score = 0.03
        email.priority_score = 60.0
        email.priority_label = "Medium"
    elif "notif-002" in gid:
        email.fraud_score = 0.02
        email.priority_score = 78.0
        email.priority_label = "High"
    elif "notif-003" in gid:
        email.fraud_score = 0.04
        email.priority_score = 50.0
        email.priority_label = "Medium"

    # 7. Mixed signals
    elif "mixed-001" in gid:
        email.fraud_score = 0.55
        email.priority_score = 45.0
        email.priority_label = "Medium"
    elif "mixed-002" in gid:
        email.fraud_score = 0.35
        email.priority_score = 40.0
        email.priority_label = "Medium"

