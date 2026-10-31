"""BERT-based phishing text classifier layer (§7, §16).

Why BERT: Phishing emails often use distinctive rhetorical patterns
(artificial urgency, generic greetings, suspicious calls to action) that
lexical heuristics miss. ealvaradob/bert-finetuned-phishing provides a
semantic scoring baseline directly from email subject + body text.

Design constraints:
- Must run locally on CPU without silent downloads (local_files_only=True).
- Enforces strict 512-token truncation limit.
- Measures per-email inference latency for evaluation reporting.
- Lazy-loads model on first invocation to keep startup fast.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from app.phishing.providers.base import LayerResult
from app.settings import settings

if TYPE_CHECKING:
    from app.db.models import Email

logger = logging.getLogger(__name__)

# Module-level singleton caches for lazy loading
_tokenizer: Any = None
_model: Any = None
_load_attempted: bool = False
_load_error_message: str | None = None


def _get_model_and_tokenizer() -> tuple[Any, Any, str | None]:
    """Lazy-load the HuggingFace model and tokenizer from local cache only.

    Returns:
        (tokenizer, model, error_message)
    """
    global _tokenizer, _model, _load_attempted, _load_error_message

    if _load_attempted:
        return _tokenizer, _model, _load_error_message

    _load_attempted = True
    model_name = settings.hf_phishing_model.strip()
    if not model_name:
        _load_error_message = "HF_PHISHING_MODEL not configured"
        return None, None, _load_error_message

    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        logger.info("Lazy-loading BERT phishing model: %s (local cache only)", model_name)
        # Ensure local_files_only=True so nothing is silently downloaded
        tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=True)
        model = AutoModelForSequenceClassification.from_pretrained(
            model_name,
            local_files_only=True,
        )
        model.to(torch.device("cpu"))
        model.eval()

        _tokenizer = tokenizer
        _model = model
        _load_error_message = None
        return _tokenizer, _model, None
    except Exception as exc:
        logger.warning("Failed to load local BERT model '%s': %s", model_name, exc)
        _load_error_message = (
            f"model not downloaded, run: uv run hf download {model_name}"
        )
        return None, None, _load_error_message


def evaluate_bert_phishing(email: Email) -> LayerResult:
    """Classify email text using the local fine-tuned BERT model.

    Evaluates Subject + Body text, handles the 512-token limit, and
    records CPU inference latency in milliseconds.
    """
    tokenizer, model, load_err = _get_model_and_tokenizer()
    if load_err or tokenizer is None or model is None:
        return LayerResult(
            name="bert_phishing",
            score=0.0,
            reason=load_err or "BERT model unavailable",
            evidence=[],
            available=False,
            has_strong_signal=False,
            is_fully_clean=False,
        )

    # Combine subject and body text
    subject = (email.subject or "").strip()
    body = (email.body_text or "").strip()
    text = f"Subject: {subject}\n\n{body}".strip() if subject else body

    if not text:
        return LayerResult(
            name="bert_phishing",
            score=0.0,
            reason="No text content to evaluate with BERT",
            evidence=["[INFO] Email contains no subject or body text for BERT analysis"],
            available=False,
            has_strong_signal=False,
            is_fully_clean=False,
        )

    import torch

    t0 = time.perf_counter()
    # Explicitly truncate to 512 tokens to adhere to BERT positional limits
    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=512,
        padding=False,
    )

    with torch.no_grad():
        outputs = model(**inputs)
        # Model config id2label: {0: 'benign', 1: 'phishing'}
        probs = torch.softmax(outputs.logits, dim=1)[0]
        phishing_prob = float(probs[1].item())

    latency_ms = (time.perf_counter() - t0) * 1000.0
    score = round(phishing_prob, 4)
    # Text-only classification does not constitute a deterministic threat indicator (§16)
    has_strong = False
    is_clean = score <= 0.15

    evidence = [
        f"BERT semantic classifier: {score:.1%} phishing probability (latency: {latency_ms:.1f}ms)"
    ]
    reason = f"BERT classified email text as {score:.1%} phishing probability ({latency_ms:.1f}ms)"

    return LayerResult(
        name="bert_phishing",
        score=score,
        reason=reason,
        evidence=evidence,
        available=True,
        has_strong_signal=has_strong,
        is_fully_clean=is_clean,
    )
