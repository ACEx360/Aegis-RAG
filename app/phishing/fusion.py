"""Risk fusion engine (§7, §16, Stage 4).

Combines scores from all available phishing detection layers via:
1. Re-normalized weighted average over available layers only (§Change 3).
2. Strong layer floor: if any available layer >= strong_layer_threshold (0.8),
   the final score is floored at strong_layer_floor (0.6) (§Change 4).
3. Threat intelligence critical floor: if any threat feed reports a known bad URL, floor at 0.90.
4. Trust signal: if sender is in sent-contacts AND SPF/DKIM pass AND no Reply-To mismatch
   AND no anchor-text mismatch, reduce fraud score by trust_score_reduction (§Change 6).
5. Confidence bands:
   - Score >= fraud_threshold (0.50) -> "Likely phishing - N% confidence"
   - Score >= fraud_suspicious_threshold (0.30) -> "Suspicious"
   - Score < fraud_suspicious_threshold -> "Low risk" (§Change 5).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.phishing.providers.base import LayerResult
from app.settings import settings


@dataclass
class FusionResult:
    """Result of combining all available phishing detection providers."""

    fraud_score: float | None
    fraud_label: str
    fraud_reason: str
    fraud_evidence: list[str]
    layers_data: list[dict[str, Any]]
    trust_discount_applied: bool = False


def fuse_phishing_layers(
    layers: list[LayerResult],
    sender_email: str,
    known_contacts: set[str],
    *,
    spf_pass: bool = False,
    dkim_pass: bool = False,
    has_reply_to_mismatch: bool = False,
    has_anchor_mismatch: bool = False,
    has_threat_intel_hit: bool = False,
    is_auth_clean: bool = False,
) -> FusionResult:
    """Fuse layer outputs into a single fraud score, band label, and evidence list."""
    available_layers = [l for l in layers if l.available]

    # Build layers data representation for UI & DB
    layers_data = [l.to_dict() for l in layers]

    # Gather all evidence items across layers
    all_raw_evidence: list[str] = []
    for l in layers:
        for ev in l.evidence:
            if ev not in all_raw_evidence:
                all_raw_evidence.append(ev)

    if not available_layers:
        numbered_evidence = [f"[{i + 1}] {ev}" for i, ev in enumerate(all_raw_evidence)]
        return FusionResult(
            fraud_score=0.0,
            fraud_label="Low risk",
            fraud_reason="No evaluatable threat indicators present (no links or external authentication headers)",
            fraud_evidence=numbered_evidence,
            layers_data=layers_data,
            trust_discount_applied=False,
        )

    # 1. Configured weights (§16)
    weights_map = {
        "sender_auth": settings.weight_sender_auth,
        "url_heuristics": settings.weight_url_heuristics,
        "bert_phishing": settings.weight_bert_phishing,
        "gemini_social": settings.weight_gemini_social,
    }

    # 2. Re-normalize weights across available layers
    total_avail_weight = sum(weights_map.get(l.name, 0.25) for l in available_layers)
    if total_avail_weight > 0:
        weighted_score = sum(
            l.score * (weights_map.get(l.name, 0.25) / total_avail_weight)
            for l in available_layers
        )
    else:
        weighted_score = sum(l.score for l in available_layers) / len(available_layers)

    final_score = weighted_score

    # 3. Strong layer floor (§Change 3)
    # Applies ONLY when the layer has at least one STRONG signal
    strong_hits = [
        l.name
        for l in available_layers
        if l.score >= settings.strong_layer_threshold and getattr(l, "has_strong_signal", False)
    ]
    if strong_hits:
        final_score = max(final_score, settings.strong_layer_floor)

    # 4. Critical indicator / threat intelligence floor (§16)
    if has_threat_intel_hit:
        final_score = max(final_score, 0.90)

    # 5. Clean sender_auth + weak URL evidence safeguard (§Change 4)
    # If sender_auth is fully clean (all pass, aligned) and the only URL evidence is weak,
    # final score must stay below the "Suspicious" threshold.
    url_layer = next((l for l in available_layers if l.name == "url_heuristics"), None)
    has_strong_url = bool(url_layer and getattr(url_layer, "has_strong_signal", False))
    if is_auth_clean and not has_strong_url:
        final_score = min(final_score, max(0.0, settings.fraud_suspicious_threshold - 0.05))

    # 6. Trust signal discount (§Change 6)
    # Strictly email address in sent contacts + SPF/DKIM pass + NO Reply-To mismatch + NO anchor mismatch
    clean_sender_email = sender_email.strip().lower()
    is_known_contact = clean_sender_email in known_contacts
    trust_discount_applied = False

    if is_known_contact:
        if has_reply_to_mismatch:
            all_raw_evidence.append(
                "Trust discount denied: sender matches sent-contacts, but a Reply-To mismatch was detected"
            )
        elif has_anchor_mismatch:
            all_raw_evidence.append(
                "Trust discount denied: sender matches sent-contacts, but an anchor-text vs href mismatch was detected"
            )
        elif not (spf_pass and dkim_pass):
            all_raw_evidence.append(
                "Trust discount denied: sender matches sent-contacts, but SPF or DKIM failed verification"
            )
        else:
            trust_discount_applied = True
            final_score = max(0.0, final_score - settings.trust_score_reduction)
            all_raw_evidence.append(
                f"Sender address ({clean_sender_email}) is in user's sent contacts with passing SPF/DKIM and no mismatches (-{int(settings.trust_score_reduction * 100)}% trust discount)"
            )

    final_score = min(max(final_score, 0.0), 1.0)
    score_rounded = round(final_score, 3)

    # 7. Confidence Band (§Change 5)
    if score_rounded >= settings.fraud_threshold:
        pct = round(score_rounded * 100)
        fraud_label = f"Likely phishing - {pct}% confidence"
    elif score_rounded >= settings.fraud_suspicious_threshold:
        fraud_label = "Suspicious"
    else:
        fraud_label = "Low risk"

    # Number the combined evidence
    numbered_evidence = [f"[{i + 1}] {ev}" for i, ev in enumerate(all_raw_evidence)]

    # Build concise reason
    reasons_summary = [f"{l.name}: {l.reason}" for l in available_layers if l.score > 0.1]
    if reasons_summary:
        fraud_reason = " | ".join(reasons_summary)
    else:
        fraud_reason = "No significant threat indicators found across available detection layers."

    if trust_discount_applied:
        fraud_reason += " (Trusted contact discount applied)."

    return FusionResult(
        fraud_score=score_rounded,
        fraud_label=fraud_label,
        fraud_reason=fraud_reason,
        fraud_evidence=numbered_evidence,
        layers_data=layers_data,
        trust_discount_applied=trust_discount_applied,
    )
