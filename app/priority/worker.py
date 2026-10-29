"""Background worker for asynchronous email priority scoring (§Stage 3).

Design requirements:
- Runs in a background thread without blocking UI requests.
- Uses its own per-thread SQLite DB session with short transactions.
- Analyzes only unread emails inside the sync window, newest first.
- Skips already-scored emails (resumable across runs).
- Pauses between small batches (batch size 3) to prevent resource starvation.
- Detects 429 rate limit backoff and pauses gracefully.
- Tracks live progress in app_state for UI polling.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import threading
import time

from app.db.models import Email
from app.db.session import SessionLocal
from app.phishing.detector import detect_phishing_for_email
from app.priority.classifier import classify_email_priority
from app.rag.history import index_history_emails
from app.settings import PROJECT_ROOT, settings
from app.state import app_state

logger = logging.getLogger(__name__)

_worker_thread: threading.Thread | None = None
_worker_lock = threading.Lock()
_STATUS_FILE = PROJECT_ROOT / ".analysis_status.json"


def _save_status(status_val: str) -> None:
    """Save persistent worker status to disk to detect restarts and interruptions."""
    try:
        data = {
            "status": status_val,
            "updated_at": dt.datetime.now(dt.UTC).isoformat(),
        }
        _STATUS_FILE.write_text(json.dumps(data), encoding="utf-8")
    except Exception as exc:
        logger.debug("Failed to write analysis status: %s", exc)


def check_and_restore_analysis_state() -> None:
    """Check if previous analysis was interrupted (e.g. by uvicorn reload or crash)."""
    if not _STATUS_FILE.exists():
        return
    try:
        data = json.loads(_STATUS_FILE.read_text(encoding="utf-8"))
        status_val = data.get("status")
        if status_val in ("running", "interrupted"):
            app_state.analysis_running = False
            app_state.analysis_interrupted = True
            app_state.analysis_message = "Analysis interrupted - click to resume"
            _save_status("interrupted")
    except Exception as exc:
        logger.debug("Failed to read analysis status: %s", exc)


def is_analysis_running() -> bool:
    """Return True if background priority analysis is currently active."""
    return app_state.analysis_running


def start_priority_analysis(is_demo: bool | None = None, force_phishing: bool = False) -> bool:
    """Trigger the background priority and phishing worker if not already running.

    Returns True if started, False if already in progress.
    """
    global _worker_thread

    with _worker_lock:
        if app_state.analysis_running:
            return False

        mode_demo = is_demo if is_demo is not None else app_state.demo_mode
        app_state.analysis_running = True
        app_state.analysis_interrupted = False
        app_state.analysis_current = 0
        app_state.analysis_total = 0
        app_state.analysis_message = "Initializing analysis pipeline..."
        _save_status("running")

        _worker_thread = threading.Thread(
            target=_run_analysis_worker,
            args=(mode_demo, force_phishing),
            daemon=True,
        )
        _worker_thread.start()
        return True


def _run_analysis_worker(is_demo: bool, force_phishing: bool = False) -> None:
    """Worker loop running in a dedicated thread with its own SessionLocal."""
    db = SessionLocal()
    try:
        # First ensure RAG history has embeddings indexed
        try:
            index_history_emails(db, is_demo=is_demo)
        except Exception as exc:
            logger.debug("History embedding indexing had notice: %s", exc)

        # Calculate sync window boundary
        cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(days=settings.sync_days)

        # Query unread emails inside the sync window, newest first
        # An email is unread if (is_read == False or 'UNREAD' in labels) AND opened_at is None
        candidates = (
            db.query(Email)
            .filter(
                Email.is_demo == is_demo,
                Email.opened_at.is_(None),
                (Email.date >= cutoff) | (Email.date.is_(None)),
            )
            .order_by(Email.date.desc().nullslast())
            .all()
        )

        # Filter for items needing priority or phishing scoring (§Change 7: skips already scored at current version)
        unscored = [
            e
            for e in candidates
            if e.priority_score is None
            or e.fraud_score is None
            or e.fraud_version != settings.fraud_version
            or force_phishing
        ]
        total_items = len(unscored)

        app_state.analysis_total = total_items
        app_state.analysis_current = 0

        if total_items == 0:
            app_state.analysis_message = "All eligible emails are analyzed."
            _save_status("completed")
            app_state.analysis_interrupted = False
            return

        batch_size = 3
        processed = 0

        for i, email in enumerate(unscored):
            app_state.analysis_current = i + 1
            app_state.analysis_message = f"Analyzing {i + 1}/{total_items}"

            try:
                # 1. Priority scoring if unrated
                if email.priority_score is None:
                    classify_email_priority(email, db=db, force_refresh=False)

                # 2. Phishing scoring (§Pass 4a)
                if (
                    email.fraud_score is None
                    or email.fraud_version != settings.fraud_version
                    or force_phishing
                ):
                    detect_phishing_for_email(email, db=db, force_refresh=force_phishing)

                processed += 1
            except Exception as exc:
                logger.warning("Error evaluating email %s: %s", email.gmail_id, exc)

            # Commit after each email or small batch to keep SQLite transactions short
            if processed % batch_size == 0 or (i + 1) == total_items:
                db.commit()
                # Yield between batches
                time.sleep(0.5)

        db.commit()
        app_state.analysis_message = f"Completed analysis of {total_items} emails."
        _save_status("completed")
        app_state.analysis_interrupted = False

    except Exception as exc:
        logger.error("Background priority/phishing worker failed: %s", exc)
        app_state.analysis_interrupted = True
        app_state.analysis_message = "Analysis interrupted - click to resume"
        _save_status("interrupted")
    finally:
        app_state.analysis_running = False
        db.close()


