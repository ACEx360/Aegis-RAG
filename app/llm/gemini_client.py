"""Gemini API client wrapper with SQLite caching, multi-key rotation, and retry handling (§5, §14).

Why: Gemini is used for priority reasoning (§6) and social-engineering
analysis (§7). External API calls are costly and rate-limited. We cache
every response keyed by (gmail_id, task_type, prompt_version) to avoid
duplicate calls on previously processed emails.

Multi-Key Failover:
Supports rotating across multiple API keys (GEMINI_API_KEY, GEMINI_API_KEY_1..5)
to eliminate rate-limit bottlenecks (RPM/RPD). When a key hits a 429/quota limit,
the client automatically switches to the next available key immediately.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import LLMCache
from app.db.session import SessionLocal
from app.settings import settings

logger = logging.getLogger(__name__)


class GeminiClient:
    """Wrapper around Google GenAI client with cache and multi-key rotation."""

    def __init__(self) -> None:
        self.model_name = settings.gemini_model
        self._clients: list[tuple[str, Any]] = []
        self._lock = threading.Lock()
        self._current_idx = 0
        self._init_clients()

    def _init_clients(self) -> None:
        """Discover and initialize all available Gemini API keys."""
        if not settings.gemini_api_key:
            return

        from dotenv import load_dotenv
        load_dotenv(override=False)

        from google import genai

        keys: list[tuple[str, str]] = []
        # Primary key from settings / env
        if settings.gemini_api_key:
            keys.append(("GEMINI_API_KEY", settings.gemini_api_key.strip("\"'")))

        # Check numbered / auxiliary keys
        for key_name in ["GEMINI_API_KEY_1", "GEMINI_API_KEY_2", "GEMINI_API_KEY_3", "GEMINI_API_KEY_4", "GEMINI_API_KEY_5"]:
            val = os.getenv(key_name)
            if val and (key_name, val.strip("\"'")) not in keys:
                keys.append((key_name, val.strip("\"'")))

        for env_k, env_v in os.environ.items():
            if env_k.startswith("GEMINI_API_KEY") and env_v:
                clean_v = env_v.strip("\"'")
                if not any(k[1] == clean_v for k in keys):
                    keys.append((env_k, clean_v))

        for k_name, k_val in keys:
            try:
                client = genai.Client(api_key=k_val)
                self._clients.append((k_name, client))
            except Exception as e:
                logger.warning("Failed to initialize GenAI client for %s: %s", k_name, e)

        logger.info("Initialized Gemini client pool with %d API key(s)", len(self._clients))

    @property
    def _client(self) -> Any:
        return self._clients[0][1] if self._clients else None

    @_client.setter
    def _client(self, val: Any) -> None:
        if val is None:
            self._clients = []
        else:
            self._clients = [("MOCK_KEY", val)]

    @property
    def is_available(self) -> bool:
        """Returns True if at least one client key is configured and initialized."""
        return len(self._clients) > 0

    def _get_next_client(self) -> tuple[str, Any]:
        """Get the current client and advance round-robin index."""
        with self._lock:
            client_tuple = self._clients[self._current_idx % len(self._clients)]
            self._current_idx = (self._current_idx + 1) % len(self._clients)
            return client_tuple

    def generate(
        self,
        prompt: str,
        *,
        gmail_id: str,
        task_type: str,
        prompt_version: str = "v1",
        db: Session | None = None,
        max_retries: int = 3,
        initial_backoff: float = 1.0,
    ) -> dict[str, Any] | None:
        """Synchronously generate structured text/JSON from Gemini.

        Checks SQLite LLMCache first. If missed, calls Gemini API with
        automatic multi-key failover and exponential backoff, then caches response.
        """
        # 1. Check SQLite cache
        close_db_after = False
        if db is None:
            db = SessionLocal()
            close_db_after = True

        try:
            cached = (
                db.query(LLMCache)
                .filter(
                    LLMCache.gmail_id == gmail_id,
                    LLMCache.task_type == task_type,
                    LLMCache.prompt_version == prompt_version,
                )
                .first()
            )
            if cached:
                try:
                    return json.loads(cached.response_json)
                except Exception:
                    return {"raw_text": cached.response_json}

            # 2. Check availability
            if not self.is_available:
                logger.info("Gemini API key not configured or client pool empty. Skipping.")
                return None

            # 3. Call Gemini with multi-key failover and retry/backoff
            response_text = ""
            total_attempts = max(len(self._clients) * 2, max_retries)
            backoff = initial_backoff

            for attempt in range(total_attempts):
                k_name, client = self._get_next_client()
                try:
                    response = client.models.generate_content(
                        model=self.model_name,
                        contents=prompt,
                    )
                    response_text = response.text or ""
                    if response_text:
                        break
                except Exception as exc:
                    err_msg = str(exc).lower()
                    is_rate_or_quota = (
                        "429" in err_msg
                        or "resource_exhausted" in err_msg
                        or "rate" in err_msg
                        or "quota" in err_msg
                    )
                    is_unavailable = "503" in err_msg or "unavailable" in err_msg

                    if is_rate_or_quota or is_unavailable:
                        logger.warning(
                            "Key %s hit rate/quota/503 on attempt %d/%d (%s). Rotating key...",
                            k_name,
                            attempt + 1,
                            total_attempts,
                            "quota/429" if is_rate_or_quota else "503",
                        )
                        # Switch immediately without sleeping if other keys exist
                        if len(self._clients) > 1:
                            continue
                        else:
                            time.sleep(backoff)
                            backoff *= 2
                            continue

                    logger.error("Gemini API error on %s attempt %d: %s", k_name, attempt + 1, exc)
                    # For other errors, continue to try next key if available
                    if attempt < total_attempts - 1 and len(self._clients) > 1:
                        continue
                    return None

            if not response_text:
                return None

            # 4. Save to cache
            parsed_result: dict[str, Any]
            try:
                parsed_result = json.loads(response_text)
            except Exception:
                parsed_result = {"raw_text": response_text}

            new_cache = LLMCache(
                gmail_id=gmail_id,
                task_type=task_type,
                prompt_version=prompt_version,
                response_json=json.dumps(parsed_result),
                model_name=self.model_name,
            )
            db.add(new_cache)
            db.commit()

            return parsed_result
        finally:
            if close_db_after:
                db.close()


gemini_client = GeminiClient()
