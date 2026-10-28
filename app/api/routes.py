"""API endpoints for email operations, Gmail OAuth, and sync."""

from __future__ import annotations

import datetime as dt
import json
import logging
import threading
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.schemas import (
    AuthStatusResponse,
    EmailDetailResponse,
    EmailListResponse,
    OpenEmailResponse,
    SyncResponse,
)
from app.db.models import Email
from app.db.session import get_db
from app.ingest.demo_emails import get_demo_emails
from app.ingest.gmail_client import gmail_client, is_oauth_in_progress
from app.ingest.normalizer import normalize_message
from app.settings import settings
from app.state import app_state
from app.ui.placeholder_scores import assign_placeholder_scores

logger = logging.getLogger(__name__)

router = APIRouter()


def _row_to_dict(row: Email) -> dict[str, Any]:
    """Helper to deserialize JSON text fields from SQLite into Python structures."""
    return {
        "id": row.id,
        "gmail_id": row.gmail_id,
        "thread_id": row.thread_id,
        "subject": row.subject,
        "sender": row.sender,
        "recipients": json.loads(row.recipients or "[]"),
        "date": row.date,
        "body_text": row.body_text,
        "snippet": row.snippet,
        "labels": json.loads(row.labels or "[]"),
        "raw_headers": json.loads(row.raw_headers or "[]"),
        "has_attachments": row.has_attachments,
        "attachment_meta": json.loads(row.attachment_meta or "[]"),
        "is_read": row.is_read,
        "is_demo": row.is_demo,
        "opened_at": row.opened_at,
        "ingested_at": row.ingested_at,
        "priority_score": row.priority_score,
        "priority_label": row.priority_label,
        "fraud_score": row.fraud_score,
    }


# ---------------------------------------------------------------------------
# Emails
# ---------------------------------------------------------------------------


@router.get(
    "/emails",
    tags=["Emails"],
    summary="List emails",
    description="Returns ingested emails for the current active mode (demo or real).",
    response_model=list[EmailListResponse],
)
def list_emails(
    mode: str | None = Query(None, description="Filter by mode: 'demo' or 'real'. Defaults to current mode."),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[EmailListResponse]:
    target_mode = mode if mode in ("demo", "real") else app_state.mode
    is_demo = target_mode == "demo"

    rows = (
        db.query(Email)
        .filter(Email.is_demo == is_demo)
        .order_by(Email.date.desc().nullslast(), Email.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return [EmailListResponse.model_validate(_row_to_dict(r)) for r in rows]


@router.get(
    "/emails/{email_id}",
    tags=["Emails"],
    summary="Get email details",
    description="Returns detailed email data including body_text and raw_headers. Excludes body_html.",
    response_model=EmailDetailResponse,
)
def get_email(email_id: int, db: Session = Depends(get_db)) -> EmailDetailResponse:
    row = db.query(Email).filter(Email.id == email_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email not found")

    return EmailDetailResponse.model_validate(_row_to_dict(row))


def mark_email_as_opened_in_db(email_id: int, db: Session) -> Email | None:
    """Helper to mark opened_at on an email row (reused by POST /api/emails/{id}/open)."""
    row = db.query(Email).filter(Email.id == email_id).first()
    if not row:
        return None

    if row.opened_at is None:
        row.opened_at = dt.datetime.now(dt.timezone.utc)
        db.commit()
        db.refresh(row)
    return row


@router.post(
    "/emails/{email_id}/open",
    tags=["Emails"],
    summary="Mark email as opened",
    description="Sets opened_at timestamp. GET endpoints never mutate data (§14).",
    response_model=OpenEmailResponse,
)
def mark_email_opened(email_id: int, db: Session = Depends(get_db)) -> OpenEmailResponse:
    row = mark_email_as_opened_in_db(email_id, db)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email not found")

    return OpenEmailResponse(
        id=row.id,
        gmail_id=row.gmail_id,
        opened_at=row.opened_at or dt.datetime.now(dt.timezone.utc),
        message="Email marked as opened.",
    )


# ---------------------------------------------------------------------------
# Sync & Seed
# ---------------------------------------------------------------------------


@router.post(
    "/emails/sync",
    tags=["Emails"],
    summary="Sync emails",
    description="Syncs emails from Gmail if authenticated, otherwise seeds demo emails. Refreshes labels and read state.",
    response_model=SyncResponse,
)
def sync_emails(db: Session = Depends(get_db)) -> SyncResponse:
    auth_status = gmail_client.get_auth_status()

    # Determine whether to sync real Gmail or demo emails
    if auth_status.authenticated and not app_state.demo_mode:
        return _sync_gmail(db)
    else:
        return _sync_demo(db)


def _sync_demo(db: Session) -> SyncResponse:
    """Seed or refresh demo emails."""
    demo_items = get_demo_emails()
    added = 0
    updated = 0

    for item in demo_items:
        schema = item.schema
        existing = db.query(Email).filter(Email.gmail_id == schema.gmail_id).first()
        if existing:
            # Refresh labels and read state per §14
            existing.labels = json.dumps(schema.labels)
            existing.is_read = schema.is_read
            existing.snippet = schema.snippet
            if existing.priority_score is None:
                assign_placeholder_scores(existing)
            updated += 1
        else:
            raw_headers_dicts = [h.model_dump() for h in schema.raw_headers]
            new_email = Email(
                gmail_id=schema.gmail_id,
                thread_id=schema.thread_id,
                subject=schema.subject,
                sender=schema.sender,
                recipients=json.dumps(schema.recipients),
                date=schema.date,
                body_text=schema.body_text,
                body_html=schema.body_html,
                snippet=schema.snippet,
                labels=json.dumps(schema.labels),
                raw_headers=json.dumps(raw_headers_dicts),
                has_attachments=schema.has_attachments,
                attachment_meta=json.dumps(schema.attachment_meta),
                is_read=schema.is_read,
                is_demo=True,
                opened_at=item.opened_at,
            )
            assign_placeholder_scores(new_email)
            db.add(new_email)
            added += 1

    db.commit()
    total = db.query(Email).filter(Email.is_demo == True).count()
    return SyncResponse(
        mode="demo",
        added=added,
        updated=updated,
        total=total,
        message=f"Demo sync complete: {added} added, {updated} updated (total {total} demo emails).",
    )


def _sync_gmail(db: Session) -> SyncResponse:
    """Sync from Gmail API: ingest new and refresh labels/read-status of existing."""
    try:
        messages = gmail_client.list_message_ids(max_results=50)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch messages from Gmail: {exc}",
        )

    added = 0
    updated = 0

    for msg_meta in messages:
        msg_id = msg_meta.get("id")
        if not msg_id:
            continue

        existing = db.query(Email).filter(Email.gmail_id == msg_id).first()
        if existing:
            # Refresh labels & read state
            try:
                min_info = gmail_client.get_message_metadata(msg_id)
                new_labels = min_info.get("labelIds", [])
                existing.labels = json.dumps(new_labels)
                existing.is_read = "UNREAD" not in new_labels
                if min_info.get("snippet"):
                    existing.snippet = min_info["snippet"]
                updated += 1
            except Exception as e:
                logger.warning("Failed to refresh metadata for %s: %s", msg_id, e)
        else:
            # Ingest full message
            try:
                full_raw = gmail_client.get_message(msg_id)
                schema = normalize_message(full_raw)
                raw_headers_dicts = [h.model_dump() for h in schema.raw_headers]
                new_email = Email(
                    gmail_id=schema.gmail_id,
                    thread_id=schema.thread_id,
                    subject=schema.subject,
                    sender=schema.sender,
                    recipients=json.dumps(schema.recipients),
                    date=schema.date,
                    body_text=schema.body_text,
                    body_html=schema.body_html,
                    snippet=schema.snippet,
                    labels=json.dumps(schema.labels),
                    raw_headers=json.dumps(raw_headers_dicts),
                    has_attachments=schema.has_attachments,
                    attachment_meta=json.dumps(schema.attachment_meta),
                    is_read=schema.is_read,
                    is_demo=False,
                    opened_at=None,
                )
                db.add(new_email)
                added += 1
            except Exception as e:
                logger.warning("Failed to ingest message %s: %s", msg_id, e)

    db.commit()
    total = db.query(Email).filter(Email.is_demo == False).count()
    return SyncResponse(
        mode="real",
        added=added,
        updated=updated,
        total=total,
        message=f"Gmail sync complete: {added} new ingested, {updated} refreshed (total {total} emails).",
    )


# ---------------------------------------------------------------------------
# Auth & Mode
# ---------------------------------------------------------------------------


@router.get(
    "/auth/status",
    tags=["Auth"],
    summary="Check authentication and system status",
    response_model=AuthStatusResponse,
)
def get_auth_status() -> AuthStatusResponse:
    status_info = gmail_client.get_auth_status()
    creds_exist = settings.credentials_path.exists() and settings.credentials_path.stat().st_size > 0
    token_exist = settings.token_path.exists() and settings.token_path.stat().st_size > 0

    return AuthStatusResponse(
        authenticated=status_info.authenticated,
        mode=app_state.mode,
        oauth_in_progress=is_oauth_in_progress(),
        credentials_present=creds_exist,
        token_present=token_exist,
        error=status_info.error,
    )


@router.post(
    "/auth/login",
    tags=["Auth"],
    summary="Initiate Gmail OAuth login flow",
    description="Starts the Desktop OAuth flow in a background thread (§14).",
)
def start_oauth_login() -> dict[str, Any]:
    if is_oauth_in_progress():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="OAuth flow already in progress.",
        )

    creds_exist = settings.credentials_path.exists() and settings.credentials_path.stat().st_size > 0
    if not creds_exist:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"credentials.json not found or empty at {settings.credentials_path}.",
        )

    # Launch OAuth flow in background thread so server remains unblocked (§14)
    thread = threading.Thread(target=gmail_client.start_login, daemon=True)
    thread.start()

    return {
        "status": "started",
        "message": "OAuth flow started in background. Complete login in your browser.",
    }


@router.post(
    "/mode",
    tags=["System"],
    summary="Switch app mode",
    description="Set mode to 'demo' or 'real'.",
)
def set_mode(mode: str = Query(..., pattern="^(demo|real)$")) -> dict[str, str]:
    app_state.demo_mode = (mode == "demo")
    return {"mode": app_state.mode, "message": f"Active mode set to '{app_state.mode}'."}


@router.get(
    "/health",
    tags=["System"],
    summary="Health check",
)
def health_check() -> dict[str, str]:
    return {"status": "ok", "mode": app_state.mode}
