"""Gemini client wrapper with SQLite caching and retry/backoff.

Requirements:
- Read GEMINI_API_KEY from settings (from .env).
- Synchronous generate method: `def generate(...) -> dict | None`.
- Cache every LLM output in SQLite keyed by (gmail_id, task_type, prompt_version).
- Handle 429/rate-limit errors with exponential backoff retry.
- Graceful degradation if key is missing or invalid.
- No analysis logic yet (Stage 1).
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import LLMCache
from app.db.session import SessionLocal
from app.settings import settings

logger = logging.getLogger(__name__)


class GeminiClient:
    """Wrapper around Google GenAI client with cache and retry handling."""

    def __init__(self) -> None:
        self.api_key = settings.gemini_api_key
        self.model_name = settings.gemini_model
        self._client: Any = None
        if self.api_key:
            try:
                from google import genai

                self._client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning("Failed to initialize Google GenAI client: %s", e)
                self._client = None

    @property
    def is_available(self) -> bool:
        """Returns True if the client is configured and initialized."""
        return self._client is not None

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
        exponential backoff on rate limits (429), then caches response.
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
                logger.info("Gemini API key not configured or client unavailable. Skipping.")
                return None

            # 3. Call Gemini with retry/backoff
            backoff = initial_backoff
            response_text = ""
            for attempt in range(max_retries):
                try:
                    response = self._client.models.generate_content(
                        model=self.model_name,
                        contents=prompt,
                    )
                    response_text = response.text or ""
                    break
                except Exception as exc:
                    err_msg = str(exc).lower()
                    if "429" in err_msg or "resource_exhausted" in err_msg or "rate" in err_msg:
                        if attempt < max_retries - 1:
                            logger.warning(
                                "Rate limited by Gemini. Retrying in %.1fs (attempt %d/%d)...",
                                backoff,
                                attempt + 1,
                                max_retries,
                            )
                            time.sleep(backoff)
                            backoff *= 2
                            continue
                    logger.error("Gemini API error on attempt %d: %s", attempt + 1, exc)
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
