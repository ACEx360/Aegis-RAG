"""MiniCheck claim verification provider (§8, §16, Stage 5).

Key properties:
- Uses lytang/MiniCheck-RoBERTa-Large with local_files_only=True and HF_HUB_OFFLINE=1.
- Auto-detects device (CUDA if available, otherwise CPU).
- Lazy-loads model on first use directly via AutoModelForSequenceClassification.
- Two labels only: 'supported' (confidence >= threshold) or 'unsupported'.
- Maps each supported claim to its best supporting evidence item index [N].
- Filters unsupported claims from user-facing narrative.
- If model files are missing, fails with explicit manual download instructions.
"""

from __future__ import annotations

import os

# Prevent any silent remote HuggingFace network requests or thread hangs
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import json
import logging
from typing import Any

import numpy as np
import torch
from sqlalchemy.orm import Session
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from app.db.models import Email
from app.explain.generator import (
    assemble_evidence_set,
    build_verdict_line,
    decompose_claims,
    generate_combined_explanation,
)
from app.settings import settings

logger = logging.getLogger(__name__)

HF_MODEL_REPO = "lytang/MiniCheck-RoBERTa-Large"
_GLOBAL_VERIFIER: MiniCheckVerifier | None = None


class MiniCheckVerifier:
    """Offline MiniCheck-RoBERTa-Large verifier using local_files_only."""

    def __init__(self, model_name: str = "roberta-large") -> None:
        self.model_name = model_name
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tokenizer: Any = None
        self.model: Any = None
        self._load_error: str | None = None
        self._initialized = False

    def _ensure_loaded(self) -> bool:
        """Lazy load MiniCheck RoBERTa-Large directly from local HuggingFace cache."""
        if self._initialized:
            return self.model is not None

        self._initialized = True
        try:
            logger.info("Loading '%s' offline with local_files_only=True on %s...", HF_MODEL_REPO, self.device)
            self.tokenizer = AutoTokenizer.from_pretrained(
                HF_MODEL_REPO,
                local_files_only=True,
                use_fast=True,
            )
            self.model = AutoModelForSequenceClassification.from_pretrained(
                HF_MODEL_REPO,
                local_files_only=True,
            )
            self.model.to(self.device)
            self.model.eval()
            logger.info("MiniCheck model loaded successfully from local cache on %s.", self.device)
            return True
        except Exception as exc:
            msg = (
                f"MiniCheck model files missing in local cache for '{HF_MODEL_REPO}'. "
                f"To download manually, run: uv run hf download {HF_MODEL_REPO}"
            )
            logger.warning("%s (Detail: %s)", msg, exc)
            self._load_error = msg
            self.model = None
            self.tokenizer = None
            return False

    def is_available(self) -> bool:
        """Return True if MiniCheck model is operational from local cache."""
        return self._ensure_loaded()

    def score_pairs(self, docs: list[str], claims: list[str]) -> tuple[list[int], list[float]]:
        """Score parallel doc-claim pairs directly using the offline classification model.

        Returns (pred_labels, raw_probs).
        """
        if not self._ensure_loaded() or self.model is None or self.tokenizer is None:
            raise RuntimeError(self._load_error or "MiniCheck verifier unavailable")

        assert len(docs) == len(claims), "docs and claims must have the same length"
        if not docs:
            return [], []

        # Construct doc </s> claim inputs
        eos = self.tokenizer.eos_token or "</s>"
        texts = [f"{d} {eos} {c}" for d, c in zip(docs, claims)]

        inputs = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits
            probs_tensor = torch.softmax(logits, dim=-1)

        # Index 1 corresponds to 'supported'
        support_probs = probs_tensor[:, 1].cpu().tolist()
        pred_labels = [1 if p >= 0.5 else 0 for p in support_probs]
        return pred_labels, [float(p) for p in support_probs]

    def verify_single_claim(
        self,
        claim: str,
        evidence_items: list[str],
        threshold: float = 0.5,
    ) -> dict[str, Any]:
        """Verify one claim against individual evidence items and overall context in a single batch.

        Returns a dictionary with:
        - claim: str
        - label: 'supported' | 'unsupported'
        - confidence: float
        - evidence_index: int | None (1-based index)
        - evidence_text: str | None
        """
        if not evidence_items:
            return {
                "claim": claim,
                "label": "unsupported",
                "confidence": 0.0,
                "evidence_index": None,
                "evidence_text": None,
            }

        # Combine full doc and individual evidence items in a single forward pass batch
        full_doc = " ".join(evidence_items)
        docs_batch = [full_doc] + evidence_items
        claims_batch = [claim] * len(docs_batch)
        _, probs_batch = self.score_pairs(docs=docs_batch, claims=claims_batch)

        full_prob = float(probs_batch[0]) if probs_batch else 0.0
        individual_probs = probs_batch[1:] if len(probs_batch) > 1 else [full_prob]
        best_idx = int(np.argmax(individual_probs)) if len(individual_probs) > 0 else 0
        best_prob = float(individual_probs[best_idx]) if len(individual_probs) > 0 else full_prob
        best_text = evidence_items[best_idx] if best_idx < len(evidence_items) else evidence_items[0]
        best_evidence_num = best_idx + 1

        final_prob = max(best_prob, full_prob)
        is_supported = final_prob >= threshold

        return {
            "claim": claim,
            "label": "supported" if is_supported else "unsupported",
            "confidence": round(final_prob, 3),
            "evidence_index": best_evidence_num if is_supported else None,
            "evidence_text": best_text if is_supported else None,
        }

    def verify_claims_list(
        self,
        claims: list[str],
        evidence_items: list[str],
        threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        """Verify a list of claims against the evidence set."""
        results = []
        for claim in claims:
            res = self.verify_single_claim(claim, evidence_items, threshold=threshold)
            results.append(res)
        return results


def get_verifier() -> MiniCheckVerifier:
    """Return the global MiniCheckVerifier singleton."""
    global _GLOBAL_VERIFIER
    if _GLOBAL_VERIFIER is None:
        _GLOBAL_VERIFIER = MiniCheckVerifier(model_name=settings.minicheck_model_name)
    return _GLOBAL_VERIFIER


def explain_and_verify_email(
    email: Email,
    db: Session,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Execute Stage 5 explanation synthesis, decomposition, and claim verification.

    Updates the Email object in place and commits to SQLite.
    """
    # 1. System verdict line (always preserved, never removed or verified)
    verdict_line = build_verdict_line(email)
    email.verdict_line = verdict_line

    # 2. Assemble canonical evidence items [1]..[N]
    evidence_items = assemble_evidence_set(email)

    # 3. Combined explanation synthesis (Gemini or deterministic fallback)
    explanation = generate_combined_explanation(email, db=db)
    email.explanation = explanation

    # 4. Atomic claim decomposition (max 6, self-contained)
    claims = decompose_claims(explanation, email, db=db)
    email.claims = json.dumps(claims)

    verifier = get_verifier()
    if not verifier.is_available():
        logger.warning("MiniCheck verifier unavailable for email %s", email.gmail_id)
        email.verified_claims = "[]"
        email.verified_explanation = None
        email.verification_version = None
        db.commit()
        return {
            "verdict_line": verdict_line,
            "explanation": explanation,
            "claims": claims,
            "verified_claims": [],
            "verified_explanation": None,
            "verifier_available": False,
        }

    # 5. NLI Verification via MiniCheck
    verified_results = verifier.verify_claims_list(
        claims=claims,
        evidence_items=evidence_items,
        threshold=settings.minicheck_threshold,
    )
    email.verified_claims = json.dumps(verified_results)
    email.verification_version = settings.verification_version

    # 6. Format user-facing verified explanation
    # Only supported claims are included, linked to their [N] evidence citations
    supported_claims = [c for c in verified_results if c.get("label") == "supported"]
    supported_texts = []
    for c in supported_claims:
        idx = c.get("evidence_index")
        citation = f" [{idx}]" if idx is not None else ""
        supported_texts.append(f"{c['claim']}{citation}")

    if supported_texts:
        verified_narrative = " ".join(supported_texts)
    else:
        verified_narrative = "(No additional factual claims were verified against system evidence.)"

    email.verified_explanation = verified_narrative
    db.commit()

    return {
        "verdict_line": verdict_line,
        "explanation": explanation,
        "claims": claims,
        "verified_claims": verified_results,
        "verified_explanation": verified_narrative,
        "verifier_available": True,
    }

