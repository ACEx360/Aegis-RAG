"""Script to verify body_text extraction across real stored emails (§STEP 2 GATE)."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.db.models import Email
from app.db.session import SessionLocal, reprocess_stored_emails


def main() -> int:
    db = SessionLocal()
    try:
        # Re-process stored emails
        reprocessed = reprocess_stored_emails(db)

        real_emails = db.query(Email).filter(Email.is_demo == False).all()
        total_real = len(real_emails)

        with_html = [e for e in real_emails if e.body_html and e.body_html.strip()]
        total_with_html = len(with_html)

        empty_body = [e for e in real_emails if not e.body_text or not e.body_text.strip()]
        total_empty = len(empty_body)
        empty_ids = [e.gmail_id for e in empty_body]

        pct_empty_of_html = (total_empty / total_with_html * 100.0) if total_with_html > 0 else 0.0

        print("=" * 60)
        print("AEGIS REAL EMAIL BODY_TEXT EXTRACTION AUDIT")
        print("=" * 60)
        print(f"Reprocessed on this run:              {reprocessed}")
        print(f"Total real emails:                    {total_real}")
        print(f"Real emails with body_html:           {total_with_html}")
        print(f"Real emails with empty body_text:     {total_empty}")
        print(f"Percentage empty (of HTML emails):    {pct_empty_of_html:.2f}%")
        print(f"Empty body_text Gmail IDs:            {empty_ids}")
        print("=" * 60)

        if pct_empty_of_html > 5.0:
            print(f"GATE FAILED: {pct_empty_of_html:.2f}% > 5.0% threshold.")
            return 1
        else:
            print("GATE PASSED: Empty body_text rate is under 5.0% threshold.")
            return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

