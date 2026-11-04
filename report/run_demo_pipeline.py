"""run_demo_pipeline.py — Run the full analysis pipeline for all 20 demo emails.

Calls classify_email_priority, detect_phishing_for_email, and
explain_and_verify_email for each demo email that still needs it.
Processes one email at a time with a 3-second pause between each to
avoid 429 rate-limit errors.  Stops and reports if a 429 is received
twice in a row on the same email.

Run from the project root:
    uv run python report/run_demo_pipeline.py
"""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.models import Email
from app.db.session import SessionLocal
from app.phishing.detector import detect_phishing_for_email
from app.priority.classifier import classify_email_priority
from app.rag.history import index_history_emails
from app.settings import settings
from app.ui.helpers import is_newsletter_email
from app.verify.minicheck_verifier import explain_and_verify_email

logging.basicConfig(level=logging.WARNING)  # suppress chatty logs; errors still show

PAUSE_BETWEEN_EMAILS = 3.0  # seconds
MAX_CONSECUTIVE_429 = 2


def main() -> None:
    db = SessionLocal()
    try:
        # Index demo history embeddings (needed for RAG priority scoring)
        print("Indexing demo history embeddings...")
        index_history_emails(db, is_demo=True)

        demo_emails = db.query(Email).filter(Email.is_demo.is_(True)).all()
        print(f"Found {len(demo_emails)} demo emails.\n")

        consecutive_429 = 0
        results: list[dict] = []

        for email in demo_emails:
            print(f"--- {email.gmail_id} ---")
            email_429 = False

            # 1. Priority
            if email.priority_score is None or (
                email.priority_reason and "AI scoring unavailable" in email.priority_reason
            ):
                print("  priority: running...")
                try:
                    classify_email_priority(email, db=db)
                    db.commit()
                    print(f"  priority: done (score={email.priority_score:.1f}, label={email.priority_label})")
                    consecutive_429 = 0
                except Exception as exc:
                    msg = str(exc)
                    if "429" in msg or "rate" in msg.lower():
                        consecutive_429 += 1
                        print(f"  priority: 429 rate limit ({consecutive_429})")
                        email_429 = True
                    else:
                        print(f"  priority: ERROR {exc}")
            else:
                print(f"  priority: already set (score={email.priority_score:.1f})")

            # 2. Phishing
            needs_fraud = (
                email.fraud_score is None
                or email.fraud_version != settings.fraud_version
            )
            if needs_fraud:
                print(f"  phishing: running (fraud_version needed: {settings.fraud_version})...")
                try:
                    detect_phishing_for_email(email, db=db)
                    db.commit()
                    print(f"  phishing: done (fraud={email.fraud_score:.3f}, version={email.fraud_version})")
                    if not email_429:
                        consecutive_429 = 0
                except Exception as exc:
                    msg = str(exc)
                    if "429" in msg or "rate" in msg.lower():
                        consecutive_429 += 1
                        print(f"  phishing: 429 rate limit ({consecutive_429})")
                        email_429 = True
                    else:
                        print(f"  phishing: ERROR {exc}")
            else:
                print(f"  phishing: already set (fraud={email.fraud_score:.3f}, v={email.fraud_version})")

            # 3. Explanation + verification (only for unread non-newsletter or flagged)
            is_nl = is_newsletter_email(email.raw_headers, email.labels)
            is_flagged = email.fraud_score is not None and email.fraud_score >= settings.fraud_threshold
            needs_verify = (
                ((not is_nl) or is_flagged)
                and email.priority_score is not None
                and email.fraud_score is not None
                and email.verification_version != settings.verification_version
            )
            if needs_verify:
                print(f"  verify: running (is_newsletter={is_nl}, is_flagged={is_flagged})...")
                try:
                    explain_and_verify_email(email, db=db)
                    db.commit()
                    has_claims = bool(email.claims and email.claims not in ("[]", ""))
                    print(f"  verify: done (vv={email.verification_version}, has_claims={has_claims})")
                    if not email_429:
                        consecutive_429 = 0
                except Exception as exc:
                    msg = str(exc)
                    if "429" in msg or "rate" in msg.lower():
                        consecutive_429 += 1
                        print(f"  verify: 429 rate limit ({consecutive_429})")
                        email_429 = True
                    else:
                        print(f"  verify: ERROR {exc}")
            elif is_nl and not is_flagged:
                print("  verify: skipped (newsletter, not flagged)")
                # Stamp v3 on newsletters: nothing to verify
                if email.verification_version != settings.verification_version:
                    email.verification_version = settings.verification_version
                    db.commit()
            else:
                print(f"  verify: already at {email.verification_version}")

            results.append({
                "gmail_id": email.gmail_id,
                "priority_score": email.priority_score,
                "fraud_score": email.fraud_score,
                "fraud_version": email.fraud_version,
                "has_explanation": bool(email.explanation),
                "has_claims": bool(email.claims and email.claims not in ("[]", "")),
                "has_verified": bool(email.verified_claims and email.verified_claims not in ("[]", "")),
                "verification_version": email.verification_version,
                "is_newsletter": is_nl,
            })

            if consecutive_429 >= MAX_CONSECUTIVE_429:
                print(f"\nSTOPPED: {MAX_CONSECUTIVE_429} consecutive 429 errors. "
                      "Re-run after waiting a few minutes.")
                break

            print(f"  pausing {PAUSE_BETWEEN_EMAILS}s...")
            time.sleep(PAUSE_BETWEEN_EMAILS)

        # Final summary
        print("\n=== FINAL SUMMARY ===")
        print(f"{'gmail_id':>22} | pri | frau | fv | expl | clm | vcl | vv")
        print("-" * 90)
        for r in results:
            print(
                f"  {r['gmail_id']:>20} | "
                f"{'Y' if r['priority_score'] is not None else 'N'}   | "
                f"{'Y' if r['fraud_score'] is not None else 'N'}    | "
                f"{(r['fraud_version'] or '  '):2} | "
                f"{'Y' if r['has_explanation'] else 'N'}    | "
                f"{'Y' if r['has_claims'] else 'N'}   | "
                f"{'Y' if r['has_verified'] else 'N'}   | "
                f"{r['verification_version'] or '   '}"
            )

        all_complete = all(
            r["fraud_version"] == settings.fraud_version
            and (r["verification_version"] == settings.verification_version
                 or r["is_newsletter"])
            for r in results
        )
        print()
        if all_complete:
            print("All demo emails complete under fraud_version=v3 and verification_version=v3.")
        else:
            incomplete = [r["gmail_id"] for r in results if
                          r["fraud_version"] != settings.fraud_version
                          or (r["verification_version"] != settings.verification_version
                              and not r["is_newsletter"])]
            print(f"Incomplete: {incomplete}")

    finally:
        db.close()


if __name__ == "__main__":
    main()

