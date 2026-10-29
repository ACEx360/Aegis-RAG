"""URL heuristics provider (§7, §16, Stage 4).

Checks:
1. IP address in URL host (STRONG).
2. Lookalike / typosquatting domains and brand in foreign subdomain (STRONG).
3. Punycode domains (STRONG).
4. Deceptive embedded domain in subdomains (STRONG).
5. Anchor-text host vs real href host mismatch (STRONG).
6. URL shorteners (WEAK).
7. Excessive subdomains (>3 levels) (WEAK).
8. Insecure HTTP on auth/verification links (WEAK).
9. Redirect/forwarding parameters on allowlisted tracker/ESP domain when DMARC passes
   are low-weight; destination is evaluated for threat indicators.
   Redirects from non-tracker domains to external hosts are flagged (WEAK).
10. Deduplication: each signal type is counted once per email (deduped by type and host).
11. Weak signals are capped at weak_signal_cap (0.40).
"""

from __future__ import annotations

import re
import urllib.parse

from app.phishing.providers.base import LayerResult
from app.settings import settings

ESP_ALLOWLIST = {
    "naukri.com",
    "sendgrid.net",
    "mailchimp.com",
    "list-manage.com",
    "substack.com",
    "constantcontact.com",
}

URL_SHORTENERS = {
    "bit.ly",
    "tinyurl.com",
    "t.co",
    "ow.ly",
    "is.gd",
    "buff.ly",
    "goo.gl",
    "cutt.ly",
}

COMMON_BRANDS = [
    "paypal",
    "google",
    "microsoft",
    "apple",
    "amazon",
    "netflix",
    "bankofamerica",
    "chase",
    "wellsfargo",
    "naukri",
]

LOOKALIKE_PATTERNS = [
    (r"paypa[l1i]", "paypal"),
    (r"micros[o0]ft", "microsoft"),
    (r"g[o0]{2}g[l1]e", "google"),
    (r"app[l1]e", "apple"),
    (r"am[a4]z[o0]n", "amazon"),
    (r"netfl[i1]x", "netflix"),
]


def _get_root_domain(domain: str) -> str:
    """Extract root domain, handling common two-part ccTLDs."""
    parts = domain.lower().split(".")
    if len(parts) <= 2:
        return domain.lower()
    second_level_tlds = {"co", "com", "org", "net", "gov", "edu", "ac"}
    if len(parts) >= 3 and parts[-2] in second_level_tlds and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def _is_esp_allowlisted(host: str, sender_domain: str) -> bool:
    """Verify if host is an allowlisted ESP domain and matches sender organization."""
    host_lower = host.lower()
    for esp in ESP_ALLOWLIST:
        if host_lower == esp or host_lower.endswith("." + esp):
            sender_root = _get_root_domain(sender_domain) if sender_domain else ""
            if esp == "naukri.com":
                return sender_root == "naukri.com"
            return True
    return False


def _is_ip_address(host: str) -> bool:
    """Check if host is an IPv4 or IPv6 address."""
    if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", host):
        return True
    return bool(":" in host and not re.search(r"[a-z]", host))


def _extract_apparent_domain_from_anchor(text: str) -> str | None:
    """Extract apparent domain from anchor text ONLY if the WHOLE text represents a URL or hostname (§Fix 2a).

    Must have no spaces. Must start with http://, https://, or www., or strictly match a domain name with a valid TLD.
    Phrases like 'OR_B.Tech Course Name' or 'B.Tech' are NOT domains.
    """
    text_clean = text.strip().lower()
    if not text_clean or " " in text_clean:
        return None

    # If it contains underscores, parentheses, quotes, it's not a standard domain
    if re.search(r"[_()\"'<>]", text_clean):
        return None

    # If it starts with http://, https://, or www.
    if text_clean.startswith(("http://", "https://", "www.")):
        try:
            url_str = text_clean if text_clean.startswith(("http://", "https://")) else "http://" + text_clean
            netloc = urllib.parse.urlparse(url_str).netloc.split(":")[0]
            if netloc and "." in netloc:
                return netloc
        except Exception:
            return None

    # Strict domain regex: label.label.tld (no paths or simple path)
    m = re.match(r"^([a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,})(?:/.*)?$", text_clean)
    if m:
        candidate = m.group(1)
        # Avoid treating common abbreviations like b.tech, m.tech, e.g., i.e. as domains
        non_domain_acronyms = {"b.tech", "m.tech", "e.g.", "i.e.", "ph.d", "u.s.", "u.k."}
        if candidate in non_domain_acronyms or (candidate.endswith(".tech") and ("b.tech" in candidate or "m.tech" in candidate)):
            return None
        return candidate

    return None


def _check_host_threats(
    host: str,
    href: str,
    is_esp: bool,
) -> list[tuple[str, str, bool, float, str, str]]:
    """Check a hostname for structural and typosquatting threats.

    Returns list of tuples: (signal_type, host, is_strong, score_points, anomaly_msg, evidence_msg).
    """
    signals = []
    root_domain = _get_root_domain(host)

    # 1. IP address in host (STRONG)
    if _is_ip_address(host):
        signals.append((
            "ip_host",
            host,
            True,
            0.80,
            f"Direct IP address host: {host}",
            f"[STRONG] Link uses direct IP address host: {host}",
        ))

    # 2. Punycode check (STRONG)
    if host.startswith("xn--") or ".xn--" in host:
        signals.append((
            "punycode",
            host,
            True,
            0.50,
            f"Punycode domain: {host}",
            f"[STRONG] Link uses punycode/IDN homograph domain: {host}",
        ))

    # 3. Lookalike domain check (STRONG)
    for pattern, brand in LOOKALIKE_PATTERNS:
        if re.search(pattern, host) and brand not in root_domain:
            signals.append((
                "lookalike",
                host,
                True,
                0.65,
                f"Lookalike domain resembling '{brand}': {host}",
                f"[STRONG] Lookalike domain detected: {host} resembles {brand}.com",
            ))
            break

    # Brand embedded in foreign subdomain (STRONG)
    for brand in COMMON_BRANDS:
        if brand in host and brand not in root_domain:
            signals.append((
                "subdomain_brand",
                host,
                True,
                0.55,
                f"Brand '{brand}' in foreign subdomain: {host}",
                f"[STRONG] Brand '{brand}' spoofed in subdomain of foreign host '{host}'",
            ))
            break

    # Deceptive embedded TLD in subdomain (STRONG)
    subdomains = host[: -len(root_domain)].rstrip(".") if host != root_domain else ""
    if subdomains and re.search(r"\.(com|net|org|edu|gov|io|co)\b", subdomains):
        signals.append((
            "deceptive_subdomain",
            host,
            True,
            0.60,
            f"Deceptive subdomain embedding domain name: {host}",
            f"[STRONG] Deceptive host '{host}' embeds full domain name within subdomains",
        ))

    # 4. Shorteners (WEAK)
    if host in URL_SHORTENERS:
        signals.append((
            "shortener",
            host,
            False,
            0.25,
            f"URL shortener: {host}",
            f"[WEAK] Known URL shortener detected: {host}",
        ))

    # 5. Excessive subdomains (exempted for allowlisted ESPs) (WEAK)
    subdomain_parts = host.split(".")
    if len(subdomain_parts) > 4 and not is_esp:
        signals.append((
            "excessive_subdomains",
            host,
            False,
            0.20,
            f"Excessive subdomains: {host}",
            f"[WEAK] Suspiciously excessive subdomains ({len(subdomain_parts)} levels) in host: {host}",
        ))

    # 6. Insecure HTTP on auth/action link (WEAK)
    if href.lower().startswith("http://"):
        try:
            parsed = urllib.parse.urlparse(href)
            path_and_query = (parsed.path + " " + parsed.query).lower()
            sensitive_keywords = ["login", "verify", "auth", "secure", "account", "update", "bank"]
            if any(k in path_and_query for k in sensitive_keywords):
                signals.append((
                    "insecure_http",
                    host,
                    False,
                    0.25,
                    f"Insecure HTTP for sensitive path: {href}",
                    f"[WEAK] Insecure HTTP protocol used in sensitive action link: {href}",
                ))
        except Exception:
            pass

    return signals


def evaluate_url_heuristics(
    links_data: list[dict[str, str]],
    body_text: str,
    sender_domain: str = "",
    dmarc_pass: bool = False,
) -> LayerResult:
    """Analyze all URLs in links and body text for phishing indicators with signal deduplication."""
    all_links: list[tuple[str, str]] = []  # (text, href)

    for item in links_data:
        if isinstance(item, dict):
            href = str(item.get("href", "")).strip()
            text = str(item.get("text", "")).strip()
            if href:
                all_links.append((text, href))

    body_urls = re.findall(r"https?://[^\s<>\"']+", body_text)
    seen_hrefs = {href for _, href in all_links}
    for u in body_urls:
        if u not in seen_hrefs:
            all_links.append(("", u))
            seen_hrefs.add(u)

    if not all_links:
        return LayerResult(
            name="url_heuristics",
            score=0.0,
            reason="No URLs found in email body",
            evidence=["No links detected in email"],
            available=False,
            has_strong_signal=False,
        )

    seen_signal_keys: set[tuple[str, str]] = set()
    strong_points = 0.0
    weak_points = 0.0
    anomalies: list[str] = []
    evidence: list[str] = []
    has_anchor_mismatch = False

    def add_signal(sig_type: str, sig_host: str, is_strong: bool, pts: float, anomaly_msg: str, evidence_msg: str):
        key = (sig_type, sig_host.lower())
        if key in seen_signal_keys:
            return
        seen_signal_keys.add(key)
        anomalies.append(anomaly_msg)
        evidence.append(evidence_msg)
        nonlocal strong_points, weak_points
        if is_strong:
            strong_points += pts
        else:
            weak_points += pts

    for text, href in all_links:
        try:
            parsed = urllib.parse.urlparse(href)
        except Exception:
            continue

        if not parsed.scheme or not parsed.netloc:
            continue

        host = parsed.netloc.lower().split(":")[0]
        root_domain = _get_root_domain(host)
        is_esp = _is_esp_allowlisted(host, sender_domain)

        # Evaluate host threats
        host_threats = _check_host_threats(host, href, is_esp)
        for sig_type, sig_host, is_strong, pts, anom, evid in host_threats:
            add_signal(sig_type, sig_host, is_strong, pts, anom, evid)

        # Check anchor-text vs real href host mismatch (§Fix 2)
        if text:
            apparent_host = _extract_apparent_domain_from_anchor(text)
            if apparent_host:
                apparent_root = _get_root_domain(apparent_host)
                if apparent_root != root_domain:
                    sender_root = _get_root_domain(sender_domain) if sender_domain else ""
                    is_sender_text = bool(sender_root and apparent_root == sender_root)
                    is_sender_target = bool(sender_root and root_domain == sender_root)

                    # 2b. If text domain equals sender's From domain AND dmarc=pass:
                    # different target is a weak signal only (tracking/shortener like c.gle)
                    # ALSO if target is the sender's own domain AND dmarc=pass (e.g. roadmap.sh linking to updates.roadmap.sh)
                    if dmarc_pass and (is_sender_text or is_sender_target):
                        add_signal(
                            "anchor_tracker",
                            host,
                            False,
                            0.15,
                            f"Anchor text '{text}' points to tracking host '{host}'",
                            f"[WEAK] Link text '{text}' points to tracking/shortener host '{host}'",
                        )
                    else:
                        # 2c. STRONG when text shows a brand/domain NOT sender's own and target is unrelated
                        has_anchor_mismatch = True
                        add_signal(
                            "anchor_mismatch",
                            host,
                            True,
                            0.70,
                            f"Anchor text '{text}' points to '{host}'",
                            f"[STRONG] Link text shows '{text}' but points to '{host}'",
                        )

        # Check redirect / forwarding parameters
        if parsed.query:
            query_params = urllib.parse.parse_qs(parsed.query)
            redirect_param_names = ["url", "redirect", "redirect_url", "dest", "destination", "target", "next", "q"]
            for param in redirect_param_names:
                if param in query_params:
                    for target_val in query_params[param]:
                        if target_val.startswith(("http://", "https://")):
                            try:
                                target_host = urllib.parse.urlparse(target_val).netloc.lower().split(":")[0]
                                target_root = _get_root_domain(target_host)
                                if target_root and target_root != root_domain:
                                    # Always check destination host for structural/typosquatting threats
                                    dest_threats = _check_host_threats(target_host, target_val, is_esp=False)
                                    for sig_type, sig_host, is_strong, pts, anom, evid in dest_threats:
                                        add_signal(sig_type, sig_host, is_strong, pts, anom, evid)

                                    # Redirect on allowlisted tracker with DMARC pass is benign/low-weight if destination is clean
                                    if is_esp and dmarc_pass:
                                        pass
                                    else:
                                        # Non-tracker open redirect is suspicious (WEAK)
                                        add_signal(
                                            "redirect",
                                            host,
                                            False,
                                            0.35,
                                            f"Redirect parameter in {host} points to external {target_host}",
                                            f"[WEAK] Redirect/forwarding parameter '{param}' in link points to external domain '{target_host}'",
                                        )
                            except Exception:
                                pass

    # Apply weak signal cap (§Change 2)
    capped_weak_points = min(weak_points, settings.weak_signal_cap)
    has_strong = strong_points > 0.0

    if has_strong:
        raw_score = min(1.0, strong_points + capped_weak_points)
    else:
        raw_score = capped_weak_points

    score = min(max(raw_score, 0.0), 1.0)

    if anomalies:
        reason = f"Suspicious URL characteristics detected: {'; '.join(anomalies)}"
    else:
        reason = "All links verified against heuristic rules; no suspicious patterns found"
        evidence.append("No heuristic threat indicators found in extracted links")

    result = LayerResult(
        name="url_heuristics",
        score=round(score, 3),
        reason=reason,
        evidence=evidence,
        available=True,
        has_strong_signal=has_strong,
    )
    result.has_anchor_mismatch = has_anchor_mismatch  # type: ignore[attr-defined]
    return result
