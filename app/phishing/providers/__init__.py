"""Phishing detection providers package."""

from app.phishing.providers.base import LayerResult
from app.phishing.providers.sender_auth import evaluate_sender_auth
from app.phishing.providers.url_heuristics import evaluate_url_heuristics

__all__ = [
    "LayerResult",
    "evaluate_sender_auth",
    "evaluate_url_heuristics",
]

