"""Sender authentication provider (§7, §14, Stage 4).

Checks:
1. Trusts ONLY the Authentication-Results header whose authserv-id is mx.google.com (topmost).
   Ignores others and adds an evidence line if extra/untrusted ones exist.
2. Parses SPF, DKIM, DMARC results (pass/fail/softfail/neutral/none).
3. Detects From vs Return-Path vs Reply-To domain mismatches.
4. Detects display-name vs address mismatches (e.g. brand impersonation or embedded email).
5. If no trusted auth header exists, returns available=False.
"""

from __future__ import annotations

import email.utils
import re

from app.phishing.providers.base import LayerResult


def _extract_domain(addr: str) -> str:
    """Extract lowercase domain from an email address or string."""
    if "@" in addr:
        return addr.rsplit("@", 1)[-1].strip().lower().strip(">")
    return addr.strip().lower()


def _get_root_domain(domain: str) -> str:
    """Simple registered domain approximation for common 2-level TLDs."""
    parts = domain.lower().split(".")
    if len(parts) <= 2:
        return domain.lower()
    # Check for known two-part ccTLDs like co.uk, com.au, co.in, etc.
    second_level_tlds = {"co", "com", "org", "net", "gov", "edu", "ac"}
    if len(parts) >= 3 and parts[-2] in second_level_tlds and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def evaluate_sender_auth(
    raw_headers: list[dict[str, str]],
    sender_str: str,
) -> LayerResult:
    """Analyze sender authentication using the topmost mx.google.com Authentication-Results header."""
    auth_headers: list[str] = []
    return_path: str = ""
    reply_to: str = ""
    from_header: str = sender_str

    for h in raw_headers:
        if not isinstance(h, dict):
            continue
        name = str(h.get("name", "")).strip().lower()
        val = str(h.get("value", "")).strip()
        if name == "authentication-results":
            auth_headers.append(val)
        elif name == "return-path" and not return_path:
            return_path = val
        elif name == "reply-to" and not reply_to:
            reply_to = val
        elif name == "from" and not from_header:
            from_header = val

    evidence: list[str] = []

    # Trust ONLY the header whose authserv-id is mx.google.com
    trusted_auth: str | None = None
    extra_auth_ignored: list[str] = []

    for hdr in auth_headers:
        # Authserv-id is the first token before semicolon
        parts = hdr.split(";", 1)
        authserv_id = parts[0].strip().split()[0].lower() if parts and parts[0].strip() else ""
        if authserv_id == "mx.google.com":
            if trusted_auth is None:
                trusted_auth = hdr
            else:
                extra_auth_ignored.append(authserv_id)
        else:
            extra_auth_ignored.append(authserv_id or "unknown")

    for ignored in extra_auth_ignored:
        evidence.append(f"Ignored untrusted/extra Authentication-Results header (authserv-id: {ignored})")

    if not trusted_auth:
        return LayerResult(
            name="sender_auth",
            score=0.0,
            reason="No trusted Authentication-Results header found (authserv-id mx.google.com missing)",
            evidence=evidence if evidence else ["No Authentication-Results header from mx.google.com present"],
            available=False,
        )

    # Parse SPF, DKIM, DMARC from trusted_auth
    spf_match = re.search(r"\bspf=(\w+)", trusted_auth, re.IGNORECASE)
    dkim_match = re.search(r"\bdkim=(\w+)", trusted_auth, re.IGNORECASE)
    dmarc_match = re.search(r"\bdmarc=(\w+)", trusted_auth, re.IGNORECASE)

    spf_status = spf_match.group(1).lower() if spf_match else "none"
    dkim_status = dkim_match.group(1).lower() if dkim_match else "none"
    dmarc_status = dmarc_match.group(1).lower() if dmarc_match else "none"

    # Extract smtp.mailfrom if present in Authentication-Results
    mailfrom_match = re.search(r"smtp\.mailfrom=([^\s;]+)", trusted_auth, re.IGNORECASE)
    auth_mailfrom = mailfrom_match.group(1).strip() if mailfrom_match else ""

    # Parse From address and display name
    from_display, from_addr = email.utils.parseaddr(from_header)
    from_domain = _extract_domain(from_addr)

    # Return-Path domain
    rp_addr = email.utils.parseaddr(return_path)[1] if return_path else auth_mailfrom
    rp_domain = _extract_domain(rp_addr) if rp_addr else ""

    # Reply-To domain
    reply_to_addr = email.utils.parseaddr(reply_to)[1] if reply_to else ""
    reply_to_domain = _extract_domain(reply_to_addr) if reply_to_addr else ""

    score = 0.0
    anomalies: list[str] = []
    has_strong_signal = False

    # 1. Auth statuses
    evidence.append(f"SPF check result: {spf_status} (mx.google.com)")
    evidence.append(f"DKIM check result: {dkim_status} (mx.google.com)")
    evidence.append(f"DMARC check result: {dmarc_status} (mx.google.com)")

    if dmarc_status in ("fail", "permerror"):
        score += 0.50
        has_strong_signal = True
        anomalies.append("DMARC failed")
    elif dmarc_status == "none" and (spf_status == "fail" or dkim_status == "fail"):
        score += 0.35
        has_strong_signal = True

    if spf_status == "fail":
        score += 0.40
        has_strong_signal = True
        anomalies.append("SPF failed")
    elif spf_status == "softfail":
        score += 0.20
        anomalies.append("SPF softfail")

    if dkim_status == "fail":
        score += 0.35
        has_strong_signal = True
        anomalies.append("DKIM failed")

    # 2. From vs Return-Path / smtp.mailfrom domain mismatch (§Fix 1)
    if rp_domain and from_domain:
        if _get_root_domain(from_domain) != _get_root_domain(rp_domain):
            # When Gmail's Authentication-Results shows dmarc=pass,
            # From vs Return-Path mismatch is normal for ESP bounce domains (bounces.google.com, hubspotemail.net, etc.)
            if dmarc_status == "pass":
                evidence.append(
                    f"[INFO] Return-Path bounce domain ({rp_domain}) differs from From domain ({from_domain}) (aligned via passing DMARC)"
                )
            else:
                score += 0.45
                has_strong_signal = True
                anomalies.append(f"From domain ({from_domain}) mismatches Return-Path ({rp_domain})")
                evidence.append(
                    f"[STRONG] From domain ({from_domain}) does not match Return-Path / mailfrom domain ({rp_domain})"
                )

    # 3. From vs Reply-To domain mismatch
    if reply_to_domain and from_domain:
        if _get_root_domain(from_domain) != _get_root_domain(reply_to_domain):
            has_strong_signal = True
            anomalies.append(f"From domain ({from_domain}) mismatches Reply-To ({reply_to_domain})")
            evidence.append(
                f"From domain ({from_domain}) does not match Reply-To domain ({reply_to_domain})"
            )
            score += 0.45

    # 4. Display-name vs address spoofing
    if from_display:
        # Check if display name contains an embedded email address
        embedded_email = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", from_display)
        if embedded_email:
            emb_domain = _extract_domain(embedded_email.group(0))
            if _get_root_domain(emb_domain) != _get_root_domain(from_domain):
                has_strong_signal = True
                anomalies.append(f"Display name embeds address {embedded_email.group(0)} differing from actual {from_domain}")
                evidence.append(
                    f"Display name embeds foreign address '{embedded_email.group(0)}' mismatching sender domain '{from_domain}'"
                )
                score += 0.40

        # Brand name impersonation in display name
        common_targets = ["paypal", "google", "microsoft", "apple", "netflix", "amazon", "chase", "wellsfargo", "bank"]
        disp_lower = from_display.lower()
        for target in common_targets:
            if target in disp_lower and target not in from_domain:
                has_strong_signal = True
                anomalies.append(f"Display name mentions '{target}' but sender domain is '{from_domain}'")
                evidence.append(
                    f"Display name mentions brand '{target}' while actual sender domain is '{from_domain}'"
                )
                score += 0.35
                break

    score = min(max(score, 0.0), 1.0)
    is_fully_clean = not anomalies and spf_status == "pass" and dkim_status == "pass" and dmarc_status == "pass"

    if anomalies:
        reason = f"Sender auth anomalies detected: {'; '.join(anomalies)}"
    else:
        reason = "Sender authentication passed (SPF, DKIM, DMARC valid and domains aligned)"

    return LayerResult(
        name="sender_auth",
        score=round(score, 3),
        reason=reason,
        evidence=evidence,
        available=True,
        has_strong_signal=has_strong_signal,
        is_fully_clean=is_fully_clean,
    )
