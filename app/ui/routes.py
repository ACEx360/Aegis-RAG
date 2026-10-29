"""UI routes for the Gmail-like dashboard, tab filtering, and HTMX panels."""

from __future__ import annotations

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
        "embedding_model": settings.embedding_model,
        "is_analyzing": app_state.analysis_running,
        "is_interrupted": app_state.analysis_interrupted,
        "analysis_message": app_state.analysis_message,
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
        context["sync_window"] = {
            "sync_days": settings.sync_days,
            "sync_max": settings.sync_max,
            "sent_days": settings.sent_days,
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
    links = parse_json_safely(email_row.links)
    priority_evidence = parse_json_safely(email_row.priority_evidence)
    fraud_evidence = parse_json_safely(email_row.fraud_evidence)
    fraud_layers = parse_json_safely(email_row.fraud_layers)

    context = {
        "request": request,
        "email": email_row,
        "raw_headers": raw_headers,
        "recipients": recipients,
        "links": links,
        "priority_evidence": priority_evidence,
        "fraud_evidence": fraud_evidence,
        "fraud_layers": fraud_layers,
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
    links = parse_json_safely(email_row.links)
    priority_evidence = parse_json_safely(email_row.priority_evidence)
    fraud_evidence = parse_json_safely(email_row.fraud_evidence)
    fraud_layers = parse_json_safely(email_row.fraud_layers)

    context = {
        "request": request,
        "email": email_row,
        "raw_headers": raw_headers,
        "recipients": recipients,
        "links": links,
        "priority_evidence": priority_evidence,
        "fraud_evidence": fraud_evidence,
        "fraud_layers": fraud_layers,
        "style": get_email_styling(email_row),
        "counts": counts,
        "nli_model": settings.nli_model,
    }
    return templates.TemplateResponse(request=request, name="email_panel.html", context=context)


@router.get("/ui/analysis/status", response_class=HTMLResponse, include_in_schema=False)
def get_analysis_status(request: Request):
    """HTMX polling endpoint for background priority analysis progress (§Stage 3)."""
    if app_state.analysis_running:
        msg = app_state.analysis_message or "Analyzing email priorities..."
        return HTMLResponse(
            f"""<div id="analysis-progress-banner" hx-get="/ui/analysis/status" hx-trigger="every 2s" hx-swap="outerHTML" class="p-3 mb-3 rounded-xl bg-indigo-950/60 border border-indigo-800/80 flex items-center justify-between text-xs text-indigo-300 shadow-lg">
              <div class="flex items-center gap-2.5">
                <svg class="animate-spin w-4 h-4 text-indigo-400" viewBox="0 0 24 24" fill="none">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
                </svg>
                <span><strong>Priority Analysis:</strong> {msg}</span>
              </div>
              <span class="text-[11px] font-mono text-indigo-400 uppercase tracking-wider">Background Worker Active</span>
            </div>"""
        )
    if app_state.analysis_interrupted:
        return HTMLResponse(
            """<div id="analysis-progress-banner" class="p-3 mb-3 rounded-xl bg-amber-950/60 border border-amber-700/80 flex items-center justify-between text-xs text-amber-200 shadow-lg">
              <div class="flex items-center gap-2.5">
                <svg class="w-4 h-4 text-amber-400 flex-none" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <span><strong>Priority Analysis:</strong> Analysis interrupted - click to resume</span>
              </div>
              <button hx-post="/ui/analysis/start" hx-target="#analysis-progress-banner" hx-swap="outerHTML" class="px-3 py-1 bg-amber-600 hover:bg-amber-500 text-white font-semibold rounded-lg text-xs shadow transition-colors flex items-center gap-1.5 cursor-pointer">
                <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                Resume Analysis
              </button>
            </div>"""
        )
    return HTMLResponse('<div id="analysis-progress-banner" class="hidden"></div>')


@router.post("/ui/analysis/start", response_class=HTMLResponse, include_in_schema=False)
def trigger_analysis(request: Request):
    """Trigger background priority analysis worker on demand."""
    from app.priority.worker import start_priority_analysis
    started = start_priority_analysis(app_state.demo_mode)
    target = request.headers.get("hx-target", "")
    if target == "analysis-progress-banner":
        return HTMLResponse(
            """<div id="analysis-progress-banner" hx-get="/ui/analysis/status" hx-trigger="every 2s" hx-swap="outerHTML" class="p-3 mb-3 rounded-xl bg-indigo-950/60 border border-indigo-800/80 flex items-center justify-between text-xs text-indigo-300 shadow-lg">
              <div class="flex items-center gap-2.5">
                <svg class="animate-spin w-4 h-4 text-indigo-400" viewBox="0 0 24 24" fill="none">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
                </svg>
                <span><strong>Priority Analysis:</strong> Initializing priority analysis...</span>
              </div>
              <span class="text-[11px] font-mono text-indigo-400 uppercase tracking-wider">Background Worker Active</span>
            </div>"""
        )
    msg = "Priority analysis started in background." if started else "Analysis is already running."
    return HTMLResponse(f"<span class='text-xs text-indigo-300 font-mono'>{msg}</span>")
