"""FastAPI application entry point for AegisRAG.

Setup:
- Lifespan initializes database tables and seeds demo emails on first startup.
- Serves `/login` with Jinja2 template and `/docs` via Swagger UI.
- Mounts `/api` router with endpoints for emails, OAuth, sync, and health.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.api.routes import router as api_router
from app.api.routes import sync_emails
from app.db.models import Email
from app.db.session import init_db
from app.ingest.gmail_client import gmail_client, is_oauth_in_progress
from app.settings import settings
from app.state import app_state
from app.ui.routes import router as ui_router

TEMPLATES_DIR = Path(__file__).resolve().parent / "ui" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle hook: initialize tables and auto-seed demo data if empty."""
    init_db()

    # Restore interrupted analysis state if previous run terminated unexpectedly
    from app.priority.worker import check_and_restore_analysis_state
    check_and_restore_analysis_state()

    # Seed demo emails automatically if DB has no demo emails yet
    from app.db.session import SessionLocal, reprocess_stored_emails

    db = SessionLocal()
    try:
        count = db.query(Email).count()
        if count == 0 and app_state.demo_mode:
            sync_emails(db)
        else:
            # Reprocess existing stored emails once on startup (idempotent, §Part A)
            reprocess_stored_emails(db)
    finally:
        db.close()

    yield


app = FastAPI(
    title="AegisRAG",
    description=(
        "Local, self-hosted agentic email assistant for Gmail with RAG prioritization, "
        "phishing detection, and claim-level explanation verification."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# API routes
app.include_router(api_router, prefix="/api")

# UI routes (Tabs: /priority, /previous, /feed, /flagged, /settings, and panels)
app.include_router(ui_router)


@app.get("/login", response_class=HTMLResponse, include_in_schema=False)
def login_page(request: Request):
    """Interactive authentication & gateway dashboard."""
    auth_status = gmail_client.get_auth_status()
    creds_exist = settings.credentials_path.exists() and settings.credentials_path.stat().st_size > 0
    token_exist = settings.token_path.exists() and settings.token_path.stat().st_size > 0

    status_data = {
        "authenticated": auth_status.authenticated,
        "mode": app_state.mode,
        "oauth_in_progress": is_oauth_in_progress(),
        "credentials_present": creds_exist,
        "token_present": token_exist,
        "error": auth_status.error,
    }
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"status": status_data},
    )
