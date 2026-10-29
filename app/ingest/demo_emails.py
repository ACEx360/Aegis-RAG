"""~20 built-in sample emails for demo mode.

Rules followed (§2, §14):
- Realistic Authentication-Results headers (mix of pass and fail).
- One legit-but-urgent email and one phishing email that passes SPF.
- 5 emails marked as already read (is_read=True, opened_at set).
- Dates relative to now (timedelta offsets).
- Fake/reserved domains (.example.com/.net/.org) for phishing.
- Never include real credentials or real domains.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from app.ingest.schemas import EmailSchema, HeaderPair


@dataclass
class DemoEmail:
    """Wraps an EmailSchema with an optional opened_at for pre-read emails."""

    schema: EmailSchema
    opened_at: dt.datetime | None = None


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _ago(**kwargs: float) -> dt.datetime:
    return _now() - dt.timedelta(**kwargs)


def _auth_results(
    domain: str,
    *,
    spf: str = "pass",
    dkim: str = "pass",
    dmarc: str = "pass",
) -> HeaderPair:
    """Build a realistic Authentication-Results header."""
    return HeaderPair(
        name="Authentication-Results",
        value=(
            f"mx.google.com; "
            f"spf={spf} (google.com: domain of sender@{domain}) smtp.mailfrom=sender@{domain}; "
            f"dkim={dkim} header.d={domain}; "
            f"dmarc={dmarc} (p=REJECT sp=REJECT dis=NONE) header.from={domain}"
        ),
    )


def _base_headers(
    from_addr: str,
    to_addr: str,
    subject: str,
    date: dt.datetime,
    *,
    extra: list[HeaderPair] | None = None,
    auth_result: HeaderPair | None = None,
) -> list[HeaderPair]:
    """Standard set of headers every email should have."""
    headers = [
        HeaderPair(name="Received", value=f"by mx.google.com; {date.strftime('%a, %d %b %Y %H:%M:%S %z')}"),
        HeaderPair(name="From", value=from_addr),
        HeaderPair(name="To", value=to_addr),
        HeaderPair(name="Subject", value=subject),
        HeaderPair(name="Date", value=date.strftime("%a, %d %b %Y %H:%M:%S %z")),
        HeaderPair(name="MIME-Version", value="1.0"),
        HeaderPair(name="Content-Type", value="text/plain; charset=UTF-8"),
    ]
    if auth_result:
        headers.append(auth_result)
    if extra:
        headers.extend(extra)
    return headers


TO = "user@example.com"


def get_demo_emails() -> list[DemoEmail]:
    """Return ~20 demo emails covering phishing, newsletters, normal, etc."""
    return [
        # ============================================================
        # PHISHING (5)
        # ============================================================

        # 1 — Account suspension, SPF/DKIM/DMARC all fail
        DemoEmail(
            schema=EmailSchema(
                gmail_id="demo-phish-001",
                thread_id="demo-thread-p001",
                subject="\u26a0\ufe0f Your account will be suspended in 24 hours",
                sender="Account Security Team <alert@security-alert.example.net>",
                recipients=[TO],
                date=_ago(hours=1),
                body_text=(
                    "Dear valued customer,\n\n"
                    "We have detected unusual activity on your account. Your account "
                    "will be suspended within 24 hours unless you verify your identity "
                    "immediately.\n\n"
                    "Click here to verify: http://login-verify.example.net/secure/auth\n\n"
                    "If you do not verify within 24 hours, your account and all "
                    "associated data will be permanently deleted.\n\n"
                    "Regards,\nAccount Security Team"
                ),
                snippet="We have detected unusual activity on your account...",
                labels=["INBOX", "UNREAD", "CATEGORY_PRIMARY"],
                raw_headers=_base_headers(
                    "Account Security Team <alert@security-alert.example.net>",
                    TO,
                    "\u26a0\ufe0f Your account will be suspended in 24 hours",
                    _ago(hours=1),
                    auth_result=_auth_results(
                        "security-alert.example.net", spf="fail", dkim="fail", dmarc="fail"
                    ),
                ),
                is_read=False,
            ),
        ),

        # 2 — Payment verification, lookalike domain
        DemoEmail(
            schema=EmailSchema(
                gmail_id="demo-phish-002",
                thread_id="demo-thread-p002",
                subject="Unusual activity detected - Verify your payment method",
                sender="PayPa1 Support <support@paypa1.example.com>",
                recipients=[TO],
                date=_ago(hours=3),
                body_text=(
                    "Hello,\n\n"
                    "We noticed suspicious activity on your PayPa1 account. "
                    "Please verify your payment method to avoid service disruption.\n\n"
                    "Verify now: http://paypa1-secure.example.com/verify?id=8834\n\n"
                    "You will need to confirm your card number and billing address.\n\n"
                    "Thank you,\nPayPa1 Support Team"
                ),
                snippet="We noticed suspicious activity on your PayPa1 account...",
                labels=["INBOX", "UNREAD", "CATEGORY_PRIMARY"],
                raw_headers=_base_headers(
                    "PayPa1 Support <support@paypa1.example.com>",
                    TO,
                    "Unusual activity detected - Verify your payment method",
                    _ago(hours=3),
                    auth_result=_auth_results(
                        "paypa1.example.com", spf="fail", dkim="fail", dmarc="fail"
                    ),
                ),
                is_read=False,
            ),
        ),

        # 3 — CEO impersonation / wire transfer
        DemoEmail(
            schema=EmailSchema(
                gmail_id="demo-phish-003",
                thread_id="demo-thread-p003",
                subject="Urgent: Wire Transfer Needed Today",
                sender="John Mitchell, CEO <j.mitchell@trusted-corp.example.com>",
                recipients=[TO],
                date=_ago(hours=2),
                body_text=(
                    "Hi,\n\n"
                    "I need you to process an urgent wire transfer of $14,500 to a "
                    "new vendor today. This is time-sensitive and confidential — "
                    "please do not discuss with anyone else.\n\n"
                    "I'll send the bank details in a follow-up email. Please confirm "
                    "you received this.\n\n"
                    "Best,\nJohn Mitchell\nCEO, TrustedCorp"
                ),
                snippet="I need you to process an urgent wire transfer...",
                labels=["INBOX", "UNREAD", "CATEGORY_PRIMARY"],
                raw_headers=_base_headers(
                    "John Mitchell, CEO <j.mitchell@trusted-corp.example.com>",
                    TO,
                    "Urgent: Wire Transfer Needed Today",
                    _ago(hours=2),
                    auth_result=_auth_results(
                        "random-spoof.example.net", spf="fail", dkim="fail", dmarc="fail"
                    ),
                    extra=[
                        HeaderPair(name="Reply-To", value="j.mitchell.ceo@freemail.example.org"),
                    ],
                ),
                is_read=False,
            ),
        ),

        # 4 — Package delivery scam, link to IP URL
        DemoEmail(
            schema=EmailSchema(
                gmail_id="demo-phish-004",
                thread_id="demo-thread-p004",
                subject="Your package could not be delivered - Action required",
                sender="Delivery Service <tracking@delivery-notice.example.org>",
                recipients=[TO],
                date=_ago(hours=5),
                body_text=(
                    "Dear Customer,\n\n"
                    "We attempted to deliver your package (tracking #DX-9928341) "
                    "but no one was available to sign for it.\n\n"
                    "Please reschedule your delivery by clicking the link below:\n"
                    "http://192.0.2.45/track?id=DX-9928341\n\n"
                    "If you do not reschedule within 48 hours, your package will "
                    "be returned to the sender.\n\n"
                    "— Delivery Service"
                ),
                snippet="We attempted to deliver your package...",
                labels=["INBOX", "UNREAD", "CATEGORY_PRIMARY"],
                raw_headers=_base_headers(
                    "Delivery Service <tracking@delivery-notice.example.org>",
                    TO,
                    "Your package could not be delivered - Action required",
                    _ago(hours=5),
                    auth_result=_auth_results(
                        "delivery-notice.example.org", spf="fail", dkim="fail", dmarc="fail"
                    ),
                ),
                is_read=False,
            ),
        ),

        # 5 — Phishing that PASSES SPF (tricky — §14)
        DemoEmail(
            schema=EmailSchema(
                gmail_id="demo-phish-005",
                thread_id="demo-thread-p005",
                subject="Security Alert: Please verify your identity",
                sender="Security Department <security@legit-bank.example.com>",
                recipients=[TO],
                date=_ago(hours=4),
                body_text=(
                    "Dear Customer,\n\n"
                    "As part of our ongoing security review, we require all customers "
                    "to re-verify their identity. Please provide the following:\n\n"
                    "- Full name\n- Date of birth\n- Account number\n"
                    "- Last 4 digits of your SSN\n\n"
                    "Reply to this email with the above information within 48 hours "
                    "to avoid account restrictions.\n\n"
                    "Sincerely,\nSecurity Department\nLegit Bank"
                ),
                snippet="As part of our ongoing security review...",
                labels=["INBOX", "UNREAD", "CATEGORY_PRIMARY"],
                raw_headers=_base_headers(
                    "Security Department <security@legit-bank.example.com>",
                    TO,
                    "Security Alert: Please verify your identity",
                    _ago(hours=4),
                    auth_result=HeaderPair(
                        name="Authentication-Results",
                        value=(
                            "mx.google.com; "
                            "spf=pass (google.com: domain of bounce@attacker-relay.example.org) smtp.mailfrom=bounce@attacker-relay.example.org; "
                            "dkim=fail header.d=legit-bank.example.com; "
                            "dmarc=fail (p=REJECT sp=REJECT dis=NONE) header.from=legit-bank.example.com"
                        ),
                    ),
                    extra=[
                        HeaderPair(name="Return-Path", value="<bounce@attacker-relay.example.org>"),
                        HeaderPair(name="Reply-To", value="Security Team <security-verify@attacker-relay.example.org>"),
                    ],
                ),
                is_read=False,
            ),
        ),

        # ============================================================
        # LEGIT URGENT (1) — §14: must include one
        # ============================================================

        # 6 — Professor with real deadline
        DemoEmail(
            schema=EmailSchema(
                gmail_id="demo-legit-001",
                thread_id="demo-thread-l001",
                subject="URGENT: Thesis draft review \u2014 deadline extended to Friday",
                sender="Dr. Sarah Chen <s.chen@university.example.edu>",
                recipients=[TO],
                date=_ago(hours=6),
                body_text=(
                    "Hi,\n\n"
                    "Good news \u2014 I spoke with the committee and they agreed to "
                    "extend the submission deadline to this Friday at 5 PM.\n\n"
                    "However, I still need your revised draft by Wednesday so I have "
                    "time to review before the final submission. Please prioritise "
                    "the methodology section.\n\n"
                    "Let me know if you have any questions.\n\n"
                    "Best regards,\nDr. Sarah Chen\nDepartment of Computer Science"
                ),
                snippet="Good news \u2014 I spoke with the committee...",
                labels=["INBOX", "UNREAD", "CATEGORY_PRIMARY"],
                raw_headers=_base_headers(
                    "Dr. Sarah Chen <s.chen@university.example.edu>",
                    TO,
                    "URGENT: Thesis draft review \u2014 deadline extended to Friday",
                    _ago(hours=6),
                    auth_result=_auth_results("university.example.edu"),
                ),
                is_read=False,
            ),
        ),

        # ============================================================
        # NEWSLETTERS (3) — List-Unsubscribe / Precedence: bulk
        # ============================================================

        # 7 — Tech Weekly
        DemoEmail(
            schema=EmailSchema(
                gmail_id="demo-news-001",
                thread_id="demo-thread-n001",
                subject="This Week in AI: Breakthroughs in Language Models",
                sender="Tech Weekly Digest <digest@techweekly.example.com>",
                recipients=[TO],
                date=_ago(hours=8),
                body_text=(
                    "TECH WEEKLY DIGEST \u2014 Issue #247\n"
                    "================================\n\n"
                    "1. New open-weight model surpasses GPT-4 on coding benchmarks\n"
                    "2. Anthropic publishes safety research on model interpretability\n"
                    "3. EU AI Act enforcement begins next quarter\n"
                    "4. Tutorial: Building RAG pipelines with local models\n\n"
                    "Read the full articles on our website.\n\n"
                    "Unsubscribe: https://techweekly.example.com/unsub?id=12345"
                ),
                snippet="TECH WEEKLY DIGEST \u2014 Issue #247...",
                labels=["INBOX", "UNREAD", "CATEGORY_PROMOTIONS"],
                raw_headers=_base_headers(
                    "Tech Weekly Digest <digest@techweekly.example.com>",
                    TO,
                    "This Week in AI: Breakthroughs in Language Models",
                    _ago(hours=8),
                    auth_result=_auth_results("techweekly.example.com"),
                    extra=[
                        HeaderPair(name="List-Unsubscribe", value="<https://techweekly.example.com/unsub?id=12345>"),
                        HeaderPair(name="Precedence", value="bulk"),
                    ],
                ),
                is_read=False,
            ),
        ),

        # 8 — Product updates
        DemoEmail(
            schema=EmailSchema(
                gmail_id="demo-news-002",
                thread_id="demo-thread-n002",
                subject="What's New in DevTools v4.2 \u2014 Dark Mode & Performance",
                sender="DevTools Updates <updates@devtools.example.com>",
                recipients=[TO],
                date=_ago(days=1, hours=2),
                body_text=(
                    "Hi there,\n\n"
                    "DevTools v4.2 is here! Here's what's new:\n\n"
                    "\u2022 Dark mode across all panels\n"
                    "\u2022 50% faster initial load time\n"
                    "\u2022 New network waterfall view\n"
                    "\u2022 Built-in accessibility audit\n\n"
                    "Update now from the Extensions page.\n\n"
                    "Happy debugging,\nThe DevTools Team"
                ),
                snippet="DevTools v4.2 is here! Here's what's new...",
                labels=["INBOX", "UNREAD", "CATEGORY_UPDATES"],
                raw_headers=_base_headers(
                    "DevTools Updates <updates@devtools.example.com>",
                    TO,
                    "What's New in DevTools v4.2 \u2014 Dark Mode & Performance",
                    _ago(days=1, hours=2),
                    auth_result=_auth_results("devtools.example.com"),
                    extra=[
                        HeaderPair(name="List-Unsubscribe", value="<mailto:unsub@devtools.example.com>"),
                    ],
                ),
                is_read=False,
            ),
        ),

        # 9 — Daily developer digest
        DemoEmail(
            schema=EmailSchema(
                gmail_id="demo-news-003",
                thread_id="demo-thread-n003",
                subject="Top 10 Python Libraries You Should Know in 2026",
                sender="Dev Daily <daily@devdigest.example.com>",
                recipients=[TO],
                date=_ago(days=1, hours=5),
                body_text=(
                    "DEV DAILY DIGEST\n"
                    "================\n\n"
                    "Today's top article:\n\n"
                    "Top 10 Python Libraries You Should Know in 2026\n"
                    "1. Polars \u2014 blazing-fast DataFrames\n"
                    "2. Pydantic v3 \u2014 even faster validation\n"
                    "3. UV \u2014 the Rust-powered package manager\n"
                    "... and 7 more.\n\n"
                    "Read the full list at devdigest.example.com"
                ),
                snippet="Top 10 Python Libraries You Should Know...",
                labels=["INBOX", "UNREAD", "CATEGORY_PROMOTIONS"],
                raw_headers=_base_headers(
                    "Dev Daily <daily@devdigest.example.com>",
                    TO,
                    "Top 10 Python Libraries You Should Know in 2026",
                    _ago(days=1, hours=5),
                    auth_result=_auth_results("devdigest.example.com"),
                    extra=[
                        HeaderPair(name="List-Unsubscribe", value="<https://devdigest.example.com/unsub>"),
                        HeaderPair(name="Precedence", value="bulk"),
                    ],
                ),
                is_read=False,
            ),
        ),

        # ============================================================
        # NORMAL WORK (3) — two pre-read
        # ============================================================

        # 10 — Meeting notes (READ)
        DemoEmail(
            schema=EmailSchema(
                gmail_id="demo-work-001",
                thread_id="demo-thread-w001",
                subject="Re: Sprint Planning Notes \u2014 Oct 25",
                sender="Priya Sharma <priya@workspace.example.com>",
                recipients=[TO],
                date=_ago(days=1, hours=8),
                body_text=(
                    "Hi team,\n\n"
                    "Here are the notes from today's sprint planning:\n\n"
                    "\u2022 Sprint goal: Complete email ingestion pipeline\n"
                    "\u2022 Carry-over: Fix OAuth token refresh bug\n"
                    "\u2022 New: Add demo mode with sample emails\n"
                    "\u2022 Blocked: Waiting on API key for Safe Browsing\n\n"
                    "Next sync: Wednesday 10 AM.\n\n"
                    "Thanks,\nPriya"
                ),
                snippet="Here are the notes from today's sprint planning...",
                labels=["INBOX", "CATEGORY_PRIMARY"],
                raw_headers=_base_headers(
                    "Priya Sharma <priya@workspace.example.com>",
                    TO,
                    "Re: Sprint Planning Notes \u2014 Oct 25",
                    _ago(days=1, hours=8),
                    auth_result=_auth_results("workspace.example.com"),
                ),
                is_read=True,
            ),
            opened_at=_ago(days=1, hours=7),
        ),

        # 11 — Code review request (READ)
        DemoEmail(
            schema=EmailSchema(
                gmail_id="demo-work-002",
                thread_id="demo-thread-w002",
                subject="PR #347: Refactor authentication middleware \u2014 Review requested",
                sender="Alex Rodriguez <alex.r@workspace.example.com>",
                recipients=[TO],
                date=_ago(days=2, hours=3),
                body_text=(
                    "Hey,\n\n"
                    "I've opened PR #347 to refactor the auth middleware. Key changes:\n\n"
                    "- Split monolithic middleware into per-route guards\n"
                    "- Add token refresh retry logic\n"
                    "- Improve error messages for expired sessions\n\n"
                    "Would appreciate your review when you get a chance.\n\n"
                    "Cheers,\nAlex"
                ),
                snippet="I've opened PR #347 to refactor the auth middleware...",
                labels=["INBOX", "CATEGORY_PRIMARY"],
                raw_headers=_base_headers(
                    "Alex Rodriguez <alex.r@workspace.example.com>",
                    TO,
                    "PR #347: Refactor authentication middleware \u2014 Review requested",
                    _ago(days=2, hours=3),
                    auth_result=_auth_results("workspace.example.com"),
                ),
                is_read=True,
            ),
            opened_at=_ago(days=2, hours=1),
        ),

        # 12 — Project update (unread)
        DemoEmail(
            schema=EmailSchema(
                gmail_id="demo-work-003",
                thread_id="demo-thread-w003",
                subject="Q4 Roadmap Update \u2014 New priorities",
                sender="Team Lead <lead@workspace.example.com>",
                recipients=[TO],
                date=_ago(hours=10),
                body_text=(
                    "Team,\n\n"
                    "After the leadership review, we're shifting Q4 priorities:\n\n"
                    "1. Phishing detection MVP \u2014 must ship by Nov 15\n"
                    "2. RAG pipeline optimisation \u2014 reduce latency to <2s\n"
                    "3. Dashboard v2 \u2014 moved to Q1\n\n"
                    "Let's discuss in tomorrow's standup.\n\n"
                    "Best,\nTeam Lead"
                ),
                snippet="After the leadership review, we're shifting Q4 priorities...",
                labels=["INBOX", "UNREAD", "CATEGORY_PRIMARY"],
                raw_headers=_base_headers(
                    "Team Lead <lead@workspace.example.com>",
                    TO,
                    "Q4 Roadmap Update \u2014 New priorities",
                    _ago(hours=10),
                    auth_result=_auth_results("workspace.example.com"),
                ),
                is_read=False,
            ),
        ),

        # ============================================================
        # NORMAL PERSONAL (3) — one pre-read
        # ============================================================

        # 13 — Friend (READ)
        DemoEmail(
            schema=EmailSchema(
                gmail_id="demo-pers-001",
                thread_id="demo-thread-pe001",
                subject="Weekend plans \u2014 hiking trip?",
                sender="Ravi Kumar <ravi.k@personal.example.com>",
                recipients=[TO],
                date=_ago(days=1, hours=12),
                body_text=(
                    "Hey!\n\n"
                    "Are you free this weekend? A few of us are planning a hike "
                    "to the ridge trail \u2014 leaving Saturday at 6 AM.\n\n"
                    "Let me know if you're in so I can book the cab.\n\n"
                    "Cheers,\nRavi"
                ),
                snippet="Are you free this weekend? A few of us are planning...",
                labels=["INBOX", "CATEGORY_PRIMARY"],
                raw_headers=_base_headers(
                    "Ravi Kumar <ravi.k@personal.example.com>",
                    TO,
                    "Weekend plans \u2014 hiking trip?",
                    _ago(days=1, hours=12),
                    auth_result=_auth_results("personal.example.com"),
                ),
                is_read=True,
            ),
            opened_at=_ago(days=1, hours=10),
        ),

        # 14 — Family (unread)
        DemoEmail(
            schema=EmailSchema(
                gmail_id="demo-pers-002",
                thread_id="demo-thread-pe002",
                subject="Recipe for the dinner next week",
                sender="Mom <mom@family.example.com>",
                recipients=[TO],
                date=_ago(hours=14),
                body_text=(
                    "Hi sweetheart,\n\n"
                    "Here's the recipe for the paneer tikka you asked about:\n\n"
                    "Ingredients:\n"
                    "- 400g paneer, cubed\n"
                    "- 1 cup yogurt\n"
                    "- 2 tbsp tikka masala\n"
                    "- 1 tbsp ginger-garlic paste\n\n"
                    "Marinate for 2 hours, then grill at 200\u00b0C for 15 minutes.\n\n"
                    "Love,\nMom"
                ),
                snippet="Here's the recipe for the paneer tikka you asked about...",
                labels=["INBOX", "UNREAD", "CATEGORY_PRIMARY"],
                raw_headers=_base_headers(
                    "Mom <mom@family.example.com>",
                    TO,
                    "Recipe for the dinner next week",
                    _ago(hours=14),
                    auth_result=_auth_results("family.example.com"),
                ),
                is_read=False,
            ),
        ),

        # 15 — Travel plans (unread)
        DemoEmail(
            schema=EmailSchema(
                gmail_id="demo-pers-003",
                thread_id="demo-thread-pe003",
                subject="Re: Goa trip itinerary \u2014 flights booked!",
                sender="Anita Desai <anita@personal.example.com>",
                recipients=[TO],
                date=_ago(hours=18),
                body_text=(
                    "Great news! I booked the flights:\n\n"
                    "DEL \u2192 GOI: Nov 15, 08:30 AM (IndiGo 6E-204)\n"
                    "GOI \u2192 DEL: Nov 19, 07:00 PM (IndiGo 6E-521)\n\n"
                    "Total per person: \u20b97,200\n\n"
                    "Can you look into Airbnb options near Baga Beach?\n\n"
                    "\u2014 Anita"
                ),
                snippet="Great news! I booked the flights...",
                labels=["INBOX", "UNREAD", "CATEGORY_PRIMARY"],
                raw_headers=_base_headers(
                    "Anita Desai <anita@personal.example.com>",
                    TO,
                    "Re: Goa trip itinerary \u2014 flights booked!",
                    _ago(hours=18),
                    auth_result=_auth_results("personal.example.com"),
                ),
                is_read=False,
            ),
        ),

        # ============================================================
        # NOTIFICATIONS (3) — two pre-read
        # ============================================================

        # 16 — GitHub PR notification (READ)
        DemoEmail(
            schema=EmailSchema(
                gmail_id="demo-notif-001",
                thread_id="demo-thread-nt001",
                subject="[aegisrag/main] Fix: Handle empty email bodies gracefully (#42)",
                sender="GitHub <notifications@github.example.com>",
                recipients=[TO],
                date=_ago(days=2, hours=6),
                body_text=(
                    "merged 1 commit into main from fix/empty-body\n\n"
                    "Fix: Handle empty email bodies gracefully (#42)\n\n"
                    "Previously the normalizer would crash on emails with no text "
                    "or HTML body. This patch adds fallback handling and a test.\n\n"
                    "Files changed: 2 | +34 -3"
                ),
                snippet="merged 1 commit into main from fix/empty-body...",
                labels=["INBOX", "CATEGORY_UPDATES"],
                raw_headers=_base_headers(
                    "GitHub <notifications@github.example.com>",
                    TO,
                    "[aegisrag/main] Fix: Handle empty email bodies gracefully (#42)",
                    _ago(days=2, hours=6),
                    auth_result=_auth_results("github.example.com"),
                ),
                is_read=True,
            ),
            opened_at=_ago(days=2, hours=5),
        ),

        # 17 — Calendar reminder (READ)
        DemoEmail(
            schema=EmailSchema(
                gmail_id="demo-notif-002",
                thread_id="demo-thread-nt002",
                subject="Reminder: Project sync meeting tomorrow at 10 AM",
                sender="Google Calendar <calendar@calendar.example.com>",
                recipients=[TO],
                date=_ago(days=1, hours=20),
                body_text=(
                    "Reminder: Project sync meeting\n\n"
                    "When: Tomorrow, 10:00 AM \u2013 10:30 AM\n"
                    "Where: Conference Room B / Google Meet\n"
                    "Who: You, Priya, Alex, Team Lead\n\n"
                    "Agenda: Sprint progress, blockers, Q4 priorities."
                ),
                snippet="Reminder: Project sync meeting...",
                labels=["INBOX", "CATEGORY_UPDATES"],
                raw_headers=_base_headers(
                    "Google Calendar <calendar@calendar.example.com>",
                    TO,
                    "Reminder: Project sync meeting tomorrow at 10 AM",
                    _ago(days=1, hours=20),
                    auth_result=_auth_results("calendar.example.com"),
                ),
                is_read=True,
            ),
            opened_at=_ago(days=1, hours=18),
        ),

        # 18 — Order receipt (unread)
        DemoEmail(
            schema=EmailSchema(
                gmail_id="demo-notif-003",
                thread_id="demo-thread-nt003",
                subject="Order confirmed: Wireless headphones \u2014 \u20b92,499",
                sender="Flipkart <orders@flipkart.example.com>",
                recipients=[TO],
                date=_ago(hours=20),
                body_text=(
                    "Hi,\n\n"
                    "Your order has been confirmed!\n\n"
                    "Product: SoundCore Q40 Wireless Headphones\n"
                    "Quantity: 1\n"
                    "Total: \u20b92,499\n"
                    "Expected delivery: Oct 30, 2026\n\n"
                    "Track your order at flipkart.example.com/orders"
                ),
                snippet="Your order has been confirmed!...",
                labels=["INBOX", "UNREAD", "CATEGORY_UPDATES"],
                raw_headers=_base_headers(
                    "Flipkart <orders@flipkart.example.com>",
                    TO,
                    "Order confirmed: Wireless headphones \u2014 \u20b92,499",
                    _ago(hours=20),
                    auth_result=_auth_results("flipkart.example.com"),
                ),
                is_read=False,
            ),
        ),

        # ============================================================
        # MIXED SIGNALS (2)
        # ============================================================

        # 19 — New sender promotional (no List-Unsubscribe)
        DemoEmail(
            schema=EmailSchema(
                gmail_id="demo-mixed-001",
                thread_id="demo-thread-m001",
                subject="Exclusive: 60% off your first 3 months of cloud hosting",
                sender="CloudStack Pro <offers@cloudstack.example.com>",
                recipients=[TO],
                date=_ago(hours=22),
                body_text=(
                    "Hi there,\n\n"
                    "We’re offering an exclusive deal for new customers:\n\n"
                    "🚀 60% off your first 3 months of CloudStack Pro\n\n"
                    "Features included:\n"
                    "\u2022 10 TB storage\n"
                    "\u2022 Unlimited bandwidth\n"
                    "\u2022 24/7 support\n\n"
                    "Claim your offer: https://cloudstack.example.com/promo\n\n"
                    "Offer expires in 7 days."
                ),
                snippet="We\u2019re offering an exclusive deal for new customers...",
                labels=["INBOX", "UNREAD", "CATEGORY_PROMOTIONS"],
                raw_headers=_base_headers(
                    "CloudStack Pro <offers@cloudstack.example.com>",
                    TO,
                    "Exclusive: 60% off your first 3 months of cloud hosting",
                    _ago(hours=22),
                    auth_result=_auth_results("cloudstack.example.com"),
                ),
                is_read=False,
            ),
        ),

        # 20 — Subscription confirmation (borderline)
        DemoEmail(
            schema=EmailSchema(
                gmail_id="demo-mixed-002",
                thread_id="demo-thread-m002",
                subject="Please confirm your subscription to DataPipe Weekly",
                sender="DataPipe Newsletter <confirm@datapipe.example.com>",
                recipients=[TO],
                date=_ago(days=1),
                body_text=(
                    "Hi,\n\n"
                    "You (or someone using your email) subscribed to DataPipe "
                    "Weekly. Please confirm by clicking the link below:\n\n"
                    "https://datapipe.example.com/confirm?token=abc123def456\n\n"
                    "If you did not subscribe, you can safely ignore this email.\n\n"
                    "Thanks,\nDataPipe Team"
                ),
                snippet="You (or someone using your email) subscribed...",
                labels=["INBOX", "UNREAD", "CATEGORY_PRIMARY"],
                raw_headers=_base_headers(
                    "DataPipe Newsletter <confirm@datapipe.example.com>",
                    TO,
                    "Please confirm your subscription to DataPipe Weekly",
                    _ago(days=1),
                    auth_result=_auth_results("datapipe.example.com"),
                ),
                is_read=False,
            ),
        ),
    ]
