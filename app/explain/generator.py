"""Explanation synthesis and atomic claim decomposition (§8, §16, Stage 5).

Key responsibilities:
1. build_verdict_line: Creates the system verdict line (priority + fraud band)
   from DB fields. It is NOT verified or removed.
2. assemble_evidence_set: Merges and canonically numbers [1]..[N] factual evidence items.
3. generate_combined_explanation: Synthesizes a unified explanation grounded in evidence.
4. decompose_claims: Splits explanation into at most 6 atomic, self-contained claims.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Email
from app.llm.gemini_client import gemini_client
from app.settings import settings

logger = logging.getLogger(__name__)


def _parse_json_list(val: Any) -> list[str]:
    """Parse JSON string into a list of strings safely."""
    if isinstance(val, list):
        return [str(x) for x in val if x]
    if not val:
        return []
    try:
        data = json.loads(val)
        if isinstance(data, list):
            return [str(x) for x in data if x]
    except Exception:
        pass
    return []


def build_verdict_line(email: Email) -> str:
    """Build system verdict line from DB fields.

    Per spec: The user-facing explanation starts with this system verdict.
    It is NOT verified or removed. Only factual claims are verified.
    """
    if email.priority_score is None:
        priority_part = "Priority: not analyzed"
    else:
        priority_part = f"{email.priority_label or 'Normal'} Priority ({int(email.priority_score)}/100)"

    if email.fraud_score is None:
        fraud_part = "Threat Band: not analyzed"
    else:
        fraud_part = f"Threat Band: {email.fraud_label or 'Low risk'} ({int(email.fraud_score * 100)}%)"

    return f"Verdict: {priority_part} | {fraud_part}"


def assemble_evidence_set(email: Email) -> list[str]:
    """Assemble all system-verified evidence items from Stage 3 and Stage 4.

    Merges priority_evidence and fraud_evidence, strips existing bracket prefixes,
    deduplicates while preserving order, and numbers them cleanly [1], [2], ...
    """
    p_ev = _parse_json_list(email.priority_evidence)
    f_ev = _parse_json_list(email.fraud_evidence)

    combined_raw = p_ev + f_ev
    seen = set()
    cleaned_items: list[str] = []

    for item in combined_raw:
        # Strip existing brackets like [1], [Auth], [URL], etc.
        text = re.sub(r"^\s*\[[^\]]+\]\s*", "", item).strip()
        text = re.sub(r"^\s*\d+[\.\)]\s*", "", text).strip()
        if not text:
            continue
        norm = text.lower()
        if norm not in seen:
            seen.add(norm)
            cleaned_items.append(text)

    # Number cleanly as [1] ... [N]
    return [f"[{i + 1}] {item}" for i, item in enumerate(cleaned_items)]


def generate_combined_explanation(email: Email, db: Session | None = None) -> str:
    """Generate a single unified natural-language explanation.

    Combines priority triage and fraud security findings, grounded strictly in
    the system-built numbered evidence items.
    """
    evidence_items = assemble_evidence_set(email)
    evidence_text = "\n".join(evidence_items) if evidence_items else "No specific evidence items recorded."

    prompt = f"""You are an expert email analysis assistant. Write one concise, coherent, natural-language explanation summarizing why this email was given its priority ranking and fraud assessment.

Email Metadata:
- Subject: {email.subject or '(No subject)'}
- Sender: {email.sender or '(Unknown)'}
- Priority Score: {email.priority_score if email.priority_score is not None else 'N/A'}/100 ({email.priority_label or 'Normal'})
- Fraud Confidence: {int(email.fraud_score * 100) if email.fraud_score is not None else 'N/A'}% ({email.fraud_label or 'Low risk'})

SYSTEM EVIDENCE ITEMS:
<evidence>
{evidence_text}
</evidence>

STRICT RULES:
1. Write 2 to 4 sentences total.
2. Ground your statements ONLY in the system evidence items above.
3. Do not invent facts, sender history, or domain reputations not mentioned in the evidence.
4. Output ONLY the raw explanation text (no JSON, no markdown formatting, no bullet points).
"""
    try:
        res = gemini_client.generate(
            prompt=prompt,
            gmail_id=email.gmail_id,
            task_type="explanation",
            prompt_version=settings.explanation_prompt_version,
            db=db,
        )
        # Check if returned as dict with explanation or raw text
        if isinstance(res, dict):
            text = res.get("explanation") or res.get("text") or res.get("response") or ""
            if text:
                return text.strip()
            # If dict was parsed from JSON string or contains single string value
            for v in res.values():
                if isinstance(v, str) and len(v) > 10:
                    return v.strip()
    except Exception as exc:
        logger.debug("Gemini explanation generation fallback: %s", exc)

    # Deterministic fallback when Gemini is unavailable or returns empty
    parts = []
    if email.priority_reason:
        parts.append(email.priority_reason.strip())
    if email.fraud_reason:
        parts.append(email.fraud_reason.strip())
    fallback = " ".join(parts).strip()
    return fallback or "Email analyzed by automated rules."


def decompose_claims(
    explanation: str,
    email: Email,
    db: Session | None = None,
) -> list[str]:
    """Decompose an explanation into at most 6 atomic, self-contained claims.

    Rules:
    - Each claim must be self-contained: no pronouns ('it', 'they', 'he'), no [N] references.
    - Explicitly name the sender, link/domain, header, or attachment.
    - At most 6 claims per email.
    """
    if not explanation.strip():
        return []

    prompt = f"""Break the following email analysis explanation into atomic, verifiable factual claims.

EXPLANATION:
\"\"\"{explanation}\"\"\"

Email Context:
- Sender: {email.sender or 'unknown'}
- Subject: {email.subject or 'no subject'}

CRITICAL RULES:
1. Break into atomic facts. Each claim must contain exactly ONE factual proposition.
2. Make every claim completely SELF-CONTAINED:
   - Do NOT use pronouns ('it', 'this', 'they', 'he', 'she'). Replace them with the actual entity name (e.g., 'The email', '{email.sender}').
   - Do NOT include citation markers like '[1]' or '[2]'.
   - Explicitly name the sender, specific link/domain, authentication header, or attachment when referenced.
3. Maximum {settings.max_claims_per_email} claims total.
4. Return strictly JSON with the key "claims" containing an array of strings.

Example format:
{{
  "claims": [
    "The email sender domain matches the display name.",
    "The SPF authentication check passed."
  ]
}}
"""
    try:
        res = gemini_client.generate(
            prompt=prompt,
            gmail_id=email.gmail_id,
            task_type="claim_decomposition",
            prompt_version=settings.claim_decomposition_prompt_version,
            db=db,
        )
        if isinstance(res, dict) and "claims" in res and isinstance(res["claims"], list):
            claims = [str(c).strip() for c in res["claims"] if str(c).strip()]
            # Cap at max_claims_per_email
            return claims[: settings.max_claims_per_email]
    except Exception as exc:
        logger.debug("Gemini claim decomposition fallback: %s", exc)

    # Deterministic fallback: split by sentence boundary
    raw_sentences = re.split(r"(?<=[.!?])\s+", explanation)
    fallback_claims: list[str] = []
    for s in raw_sentences:
        clean = re.sub(r"\[\d+\]", "", s).strip()
        if len(clean) > 8:
            fallback_claims.append(clean)
        if len(fallback_claims) >= settings.max_claims_per_email:
            break

    return fallback_claims

