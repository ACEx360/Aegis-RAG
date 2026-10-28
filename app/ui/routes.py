"""UI routes for the Gmail-like dashboard, tab filtering, and HTMX panels."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.routes import mark_email_as_opened_in_db
from app.db.models import Email
from app.db.session import get_db
from app.ingest.gmail_client import gmail_client, is_oauth_in_progress
from app.settings import settings
from app.state import app_state
from app.ui.helpers import get_email_styling, is_newsletter_email, parse_json_safely

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Ensure Jinja2 autoescaping is strictly enforced (§14 & Change 3)
templates.env.autoescape = True

router = APIRouter()


def _get_tab_counts(db: Session, is_demo: bool) -> dict[str, int]:
    """Calculate unread and badge counts for sidebar navigation."""
    all_rows = db.query(Email).filter(Email.is_demo == is_demo).all()

    priority_cnt = 0
    previous_cnt = 0
    feed_cnt = 0
    flagged_cnt = 0

    for r in all_rows:
        labels = parse_json_safely(r.labels)
        raw_h = parse_json_safely(r.raw_headers)
        newsletter = is_newsletter_email(raw_h, labels)
        is_fraud = r.fraud_score is not None and r.fraud_score >= settings.fraud_threshold
        is_opened = r.opened_at is not None or r.is_read

        if is_fraud:
            flagged_cnt += 1

        if newsletter:
            if not is_opened:
                feed_cnt += 1
        elif not is_opened:
            if not is_fraud:
                priority_cnt += 1
        else:
            previous_cnt += 1

    return {
        "priority": priority_cnt,
        "previous": previous_cnt,
        "feed": feed_cnt,
        "flagged": flagged_cnt,
    }


def _fetch_tab_emails(
    db: Session,
    tab: str,
    is_demo: bool,
    query: str | None = None,
) -> list[Email]:
    """Retrieve and filter emails for the active tab per §9 and Change 4."""
    rows = db.query(Email).filter(Email.is_demo == is_demo).all()
    filtered: list[Email] = []

    for r in rows:
        labels = parse_json_safely(r.labels)
        raw_h = parse_json_safely(r.raw_headers)
        newsletter = is_newsletter_email(raw_h, labels)
        is_fraud = r.fraud_score is not None and r.fraud_score >= settings.fraud_threshold
        is_opened = r.opened_at is not None or r.is_read

        # Optional search filtering
        if query:
            q_lower = query.lower()
            subject_match = q_lower in (r.subject or "").lower()
            sender_match = q_lower in (r.sender or "").lower()
            snippet_match = q_lower in (r.snippet or "").lower()
            if not (subject_match or sender_match or snippet_match):
                continue

        # Tab specific partitioning per Change 4:
        if tab == "priority":
            # Unread only, exclude newsletters and likely fraud
            if (not is_opened) and (not newsletter) and (not is_fraud):
                filtered.append(r)
        elif tab == "previous":
            # Opened/read only, exclude newsletters
            if is_opened and (not newsletter):
                filtered.append(r)
        elif tab == "feed":
            # Newsletters only
            if newsletter:
                filtered.append(r)
        elif tab == "flagged":
            # Likely fraud only
            if is_fraud:
                filtered.append(r)

    # Sorting logic per Change 4:
    if tab == "priority":
        # Scored mail sorted by priority_score DESC; unscored sorts by date DESC after scored
        def priority_sort_key(e: Email):
            has_score = 1 if e.priority_score is not None else 0
            score = e.priority_score if e.priority_score is not None else 0.0
            dt_ts = e.date.timestamp() if e.date else 0.0
            return (has_score, score, dt_ts)

        filtered.sort(key=priority_sort_key, reverse=True)
    elif tab == "flagged":
        # Sorted by fraud_score DESC, then date DESC
        filtered.sort(
            key=lambda e: (e.fraud_score or 0.0, e.date.timestamp() if e.date else 0.0),
            reverse=True,
        )
    else:
        # Previous & Feed: Newest first (date DESC)
        filtered.sort(key=lambda e: e.date.timestamp() if e.date else 0.0, reverse=True)

    return filtered


def _check_real_mode_auth():
    """Redirect to /login if mode is real and Gmail is not authenticated (Change 5)."""
    if not app_state.demo_mode:
        auth = gmail_client.get_auth_status()
        if not auth.authenticated:
            return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    return None


@router.get("/", include_in_schema=False)
def root_redirect():
    """Redirect root path to Priority tab (or login if real mode unauthenticated)."""
    auth_redirect = _check_real_mode_auth()
    if auth_redirect:
        return auth_redirect
    return RedirectResponse(url="/priority", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/priority", response_class=HTMLResponse, include_in_schema=False)
@router.get("/previous", response_class=HTMLResponse, include_in_schema=False)
@router.get("/feed", response_class=HTMLResponse, include_in_schema=False)
@router.get("/flagged", response_class=HTMLResponse, include_in_schema=False)
@router.get("/settings", response_class=HTMLResponse, include_in_schema=False)
def render_tab(
    request: Request,
    q: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    hx_request: str | None = Header(None, alias="HX-Request"),
    db: Session = Depends(get_db),
):
    """Serve tab views with Swagger-style email rows, pagination, and search."""
    auth_redirect = _check_real_mode_auth()
    if auth_redirect:
        return auth_redirect

    path = request.url.path.strip("/")
    active_tab = path if path in ("priority", "previous", "feed", "flagged", "settings") else "priority"

    is_demo = app_state.demo_mode
    counts = _get_tab_counts(db, is_demo)

    tab_metadata = {
        "priority": ("Priority Inbox", "Unread emails prioritized with RAG relevance scoring."),
        "previous": ("Previous Messages", "Read and opened email archive."),
        "feed": ("Feed", "Subscribed newsletters and bulk notifications."),
        "flagged": ("Flagged / Fraud", "Suspicious emails identified by multi-layer detection."),
        "settings": ("Settings", "Integration status, mode selection, and pipeline thresholds."),
    }
    title, desc = tab_metadata.get(active_tab, ("Inbox", ""))

    context: dict[str, Any] = {
        "request": request,
        "mode": app_state.mode,
        "active_tab": active_tab,
        "active_tab_title": title,
        "active_tab_desc": desc,
        "counts": counts,
        "query": q,
        "nli_model": settings.nli_model,
    }

    if active_tab == "settings":
        auth_status = gmail_client.get_auth_status()
        creds_exist = settings.credentials_path.exists() and settings.credentials_path.stat().st_size > 0
        token_exist = settings.token_path.exists() and settings.token_path.stat().st_size > 0
        context["auth_status"] = {
            "authenticated": auth_status.authenticated,
            "oauth_in_progress": is_oauth_in_progress(),
            "credentials_present": creds_exist,
            "token_present": token_exist,
            "error": auth_status.error,
        }
        context["thresholds"] = {
            "fraud_threshold": settings.fraud_threshold,
            "priority_high_threshold": settings.priority_high_threshold,
            "priority_low_threshold": settings.priority_low_threshold,
        }
    else:
        all_tab_emails = _fetch_tab_emails(db, active_tab, is_demo, query=q)
        total_count = len(all_tab_emails)
        paged_emails = all_tab_emails[skip : skip + limit]

        # Wrap with computed styling
        wrapped = []
        for em in paged_emails:
            # Computed is_unread property for UI
            em_dict = {
                "id": em.id,
                "gmail_id": em.gmail_id,
                "sender": em.sender,
                "subject": em.subject,
                "snippet": em.snippet,
                "date": em.date,
                "has_attachments": em.has_attachments,
                "is_unread": bool((not em.is_read or "UNREAD" in parse_json_safely(em.labels)) and em.opened_at is None),
                "priority_score": em.priority_score,
                "priority_label": em.priority_label,
                "fraud_score": em.fraud_score,
            }
            wrapped.append({"email": em_dict, "style": get_email_styling(em)})

        context["emails"] = wrapped
        context["total_count"] = total_count
        context["has_more"] = (skip + limit) < total_count
        context["next_skip"] = skip + limit
        context["flagged_banner_count"] = counts["flagged"]

    # HTMX partial rendering vs full page load
    if hx_request == "true":
        if active_tab == "settings":
            return templates.TemplateResponse(request=request, name="settings_tab.html", context=context)
        if skip > 0:
            return templates.TemplateResponse(request=request, name="email_rows_chunk.html", context=context)
        return templates.TemplateResponse(request=request, name="email_list.html", context=context)

    return templates.TemplateResponse(request=request, name="dashboard.html", context=context)


# ---------------------------------------------------------------------------
# Lazy-loaded Inner Panel Endpoints (Change 1 & 9)
# ---------------------------------------------------------------------------


@router.get("/ui/emails/{email_id}/panel", response_class=HTMLResponse, include_in_schema=False)
def get_email_panel_readonly(
    email_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """GET panel is strictly read-only: returns panel HTML and NEVER sets opened_at (Change 1 & 9)."""
    email_row = db.query(Email).filter(Email.id == email_id).first()
    if not email_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email not found")

    counts = _get_tab_counts(db, app_state.demo_mode)
    raw_headers = parse_json_safely(email_row.raw_headers)
    recipients = parse_json_safely(email_row.recipients)

    context = {
        "request": request,
        "email": email_row,
        "raw_headers": raw_headers,
        "recipients": recipients,
        "style": get_email_styling(email_row),
        "counts": counts,
        "nli_model": settings.nli_model,
    }
    return templates.TemplateResponse(request=request, name="email_panel.html", context=context)


@router.post("/ui/emails/{email_id}/panel", response_class=HTMLResponse, include_in_schema=False)
def open_and_get_email_panel(
    email_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """POST panel: marks email as opened (sets opened_at) and returns panel HTML with updated tab counts."""
    email_row = mark_email_as_opened_in_db(email_id, db)
    if not email_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email not found")

    counts = _get_tab_counts(db, app_state.demo_mode)
    raw_headers = parse_json_safely(email_row.raw_headers)
    recipients = parse_json_safely(email_row.recipients)

    context = {
        "request": request,
        "email": email_row,
        "raw_headers": raw_headers,
        "recipients": recipients,
        "style": get_email_styling(email_row),
        "counts": counts,
        "nli_model": settings.nli_model,
    }
    return templates.TemplateResponse(request=request, name="email_panel.html", context=context)
