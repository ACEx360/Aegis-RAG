"""Gmail client — OAuth Desktop login flow + message fetching.

Design decisions:
- OAuth flow runs inside a threading.Lock so only one flow can run at a time.
- run_local_server is given a timeout so it doesn't hang forever.
- Every failure path returns a GmailAuthStatus instead of raising, so the
  API layer can show a helpful message.
"""

from __future__ import annotations

import email.utils
import json
import logging
import threading
from dataclasses import dataclass, field
from typing import Any

from app.settings import settings

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
OAUTH_TIMEOUT_SECONDS = 120


@dataclass
class GmailAuthStatus:
    """Result of an auth check or login attempt."""

    authenticated: bool = False
    error: str | None = None


# Module-level lock — prevents concurrent OAuth browser flows
_oauth_lock = threading.Lock()
_oauth_in_progress: bool = False


def is_oauth_in_progress() -> bool:
    return _oauth_in_progress


class GmailClient:
    """Thin wrapper around the Gmail API with managed OAuth lifecycle."""

    def __init__(self) -> None:
        self._service = None

    # ------------------------------------------------------------------
    # Auth helpers
    # ------------------------------------------------------------------

    def get_auth_status(self) -> GmailAuthStatus:
        """Non-destructive check: do we have a valid token right now?"""
        try:
            creds = self._load_credentials()
            if creds and creds.valid:
                return GmailAuthStatus(authenticated=True)
            return GmailAuthStatus(authenticated=False)
        except Exception as exc:
            return GmailAuthStatus(authenticated=False, error=str(exc))

    def _load_credentials(self):
        """Load and refresh the stored OAuth token.  Returns None on any problem."""
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        token_path = settings.token_path
        if not token_path.exists() or token_path.stat().st_size == 0:
            return None

        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        except (json.JSONDecodeError, ValueError, KeyError):
            return None

        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                token_path.write_text(creds.to_json())
            except Exception:
                return None

        return creds if creds.valid else None

    def start_login(self) -> GmailAuthStatus:
        """Run the OAuth Desktop flow.

        Acquires a lock (non-blocking) so only one flow runs at a time.
        Uses a timeout so the server isn't blocked forever if the user
        never finishes the consent screen.
        """
        global _oauth_in_progress

        if not _oauth_lock.acquire(blocking=False):
            return GmailAuthStatus(
                authenticated=False, error="OAuth flow already in progress"
            )

        try:
            _oauth_in_progress = True
            creds_path = settings.credentials_path

            if not creds_path.exists() or creds_path.stat().st_size == 0:
                return GmailAuthStatus(
                    authenticated=False,
                    error="credentials.json not found or empty — place a valid "
                    "OAuth client-secrets file at the project root.",
                )

            from google_auth_oauthlib.flow import InstalledAppFlow

            flow = InstalledAppFlow.from_client_secrets_file(
                str(creds_path), SCOPES
            )
            creds = flow.run_local_server(
                port=0,
                timeout_seconds=OAUTH_TIMEOUT_SECONDS,
                open_browser=True,
            )
            settings.token_path.write_text(creds.to_json())
            # Invalidate cached service so the next call rebuilds it
            self._service = None
            return GmailAuthStatus(authenticated=True)

        except Exception as exc:
            return GmailAuthStatus(authenticated=False, error=str(exc))
        finally:
            _oauth_in_progress = False
            _oauth_lock.release()

    # ------------------------------------------------------------------
    # Gmail API wrappers
    # ------------------------------------------------------------------

    def _get_service(self):
        """Lazily build the Gmail API service object."""
        if self._service is not None:
            return self._service

        from googleapiclient.discovery import build

        creds = self._load_credentials()
        if not creds:
            raise RuntimeError("Not authenticated — call start_login first")

        self._service = build("gmail", "v1", credentials=creds)
        return self._service

    def list_message_ids(
        self,
        max_results: int | None = None,
        sync_days: int | None = None,
        query: str | None = None,
    ) -> list[dict]:
        """Return a list of {id, threadId} stubs from Gmail within the sync window."""
        service = self._get_service()
        max_res = max_results if max_results is not None else settings.sync_max
        days = sync_days if sync_days is not None else settings.sync_days

        q_parts: list[str] = []
        if days:
            q_parts.append(f"newer_than:{days}d")
        if query:
            q_parts.append(query)
        q = " ".join(q_parts) if q_parts else None

        params: dict[str, Any] = {"userId": "me", "maxResults": max_res}
        if q:
            params["q"] = q

        result = service.users().messages().list(**params).execute()
        return result.get("messages", [])

    def fetch_sent_contacts(self, days: int | None = None) -> set[str]:
        """Fetch recipients of sent emails from the last `days` days.

        Uses Gmail query 'in:sent newer_than:{days}d', fetches minimal metadata
        (To and Cc headers only), and extracts unique lowercased email addresses.
        Runs separately from inbox sync so it does NOT consume SYNC_MAX.
        """
        days_window = days if days is not None else settings.sent_days
        service = self._get_service()
        query = f"in:sent newer_than:{days_window}d"

        contacts: set[str] = set()
        try:
            resp = (
                service.users()
                .messages()
                .list(userId="me", q=query, maxResults=500)
                .execute()
            )
            messages = resp.get("messages", [])
            for m in messages:
                msg_id = m.get("id")
                if not msg_id:
                    continue
                try:
                    msg = (
                        service.users()
                        .messages()
                        .get(
                            userId="me",
                            id=msg_id,
                            format="metadata",
                            metadataHeaders=["To", "Cc"],
                        )
                        .execute()
                    )
                    headers = msg.get("payload", {}).get("headers", [])
                    for h in headers:
                        if h.get("name", "").lower() in ("to", "cc"):
                            val = h.get("value", "")
                            for _, addr in email.utils.getaddresses([val]):
                                if addr and "@" in addr:
                                    contacts.add(addr.strip().lower())
                except Exception as exc:
                    logger.debug("Failed to fetch sent contact metadata for %s: %s", msg_id, exc)
        except Exception as exc:
            logger.warning("Failed to list sent messages for contacts: %s", exc)

        return contacts

    def get_message(self, msg_id: str) -> dict:
        """Fetch a single message in full format (headers + body)."""
        service = self._get_service()
        return (
            service.users()
            .messages()
            .get(userId="me", id=msg_id, format="full")
            .execute()
        )

    def get_message_metadata(self, msg_id: str) -> dict:
        """Fetch only id, threadId, labelIds, snippet (for refresh sync)."""
        service = self._get_service()
        return (
            service.users()
            .messages()
            .get(userId="me", id=msg_id, format="minimal")
            .execute()
        )


# Singleton — imported by the API layer
gmail_client = GmailClient()
