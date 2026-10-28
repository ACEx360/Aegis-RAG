"""Tests for Gemini client wrapper caching and retry mechanisms."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.db.models import LLMCache
from app.llm.gemini_client import GeminiClient


def test_gemini_client_availability_without_key():
    """Client is marked unavailable when API key is missing."""
    with patch("app.llm.gemini_client.settings.gemini_api_key", ""):
        client = GeminiClient()
        assert client.is_available is False
        # Generate returns None gracefully without raising
        result = client.generate("test prompt", gmail_id="m1", task_type="priority")
        assert result is None


def test_gemini_client_cache_hit(db_session: Session):
    """When a cached entry exists for (gmail_id, task_type, prompt_version), return it directly."""
    # Pre-populate cache
    cached_data = {"score": 75, "reason": "deadline mentioned"}
    cache_entry = LLMCache(
        gmail_id="msg_test_cache_hit",
        task_type="priority",
        prompt_version="v1",
        response_json=json.dumps(cached_data),
        model_name="test-model",
    )
    db_session.add(cache_entry)
    db_session.commit()

    client = GeminiClient()
    # Mock _client so if it were called it would fail
    client._client = MagicMock()
    client._client.models.generate_content.side_effect = AssertionError("Should not be called on cache hit!")

    result = client.generate(
        "dummy prompt",
        gmail_id="msg_test_cache_hit",
        task_type="priority",
        prompt_version="v1",
        db=db_session,
    )

    assert result == cached_data
    client._client.models.generate_content.assert_not_called()


def test_gemini_client_cache_miss_and_storage(db_session: Session):
    """On cache miss, API is called and result is stored in SQLite LLMCache."""
    client = GeminiClient()
    mock_genai_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps({"verdict": "phishing", "confidence": 0.95})
    mock_genai_client.models.generate_content.return_value = mock_response
    client._client = mock_genai_client

    result = client.generate(
        "Analyze this email",
        gmail_id="msg_test_miss",
        task_type="phishing",
        prompt_version="v1",
        db=db_session,
    )

    assert result == {"verdict": "phishing", "confidence": 0.95}

    # Verify it was saved to DB
    saved = (
        db_session.query(LLMCache)
        .filter(
            LLMCache.gmail_id == "msg_test_miss",
            LLMCache.task_type == "phishing",
            LLMCache.prompt_version == "v1",
        )
        .first()
    )
    assert saved is not None
    assert json.loads(saved.response_json) == result


def test_gemini_client_retry_on_429(db_session: Session):
    """Client retries with backoff on 429 rate limit errors."""
    client = GeminiClient()
    mock_genai_client = MagicMock()

    # First call raises 429, second succeeds
    mock_success = MagicMock()
    mock_success.text = '{"success": true}'

    mock_genai_client.models.generate_content.side_effect = [
        Exception("429 ResourceExhausted: rate limit exceeded"),
        mock_success,
    ]
    client._client = mock_genai_client

    with patch("time.sleep") as mock_sleep:
        result = client.generate(
            "prompt",
            gmail_id="msg_retry",
            task_type="test",
            prompt_version="v1",
            db=db_session,
            initial_backoff=0.01,
        )

        assert result == {"success": True}
        assert mock_genai_client.models.generate_content.call_count == 2
        mock_sleep.assert_called_once_with(0.01)
