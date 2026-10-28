"""Converts a raw Gmail API message dict into a clean EmailSchema.

Why a separate module: the normalizer is the only place that knows the
Gmail API response shape.  Everything downstream works with EmailSchema,
which makes testing and demo-mode trivial.
"""

from __future__ import annotations

import base64
import datetime as dt
from email.utils import parsedate_to_datetime
import html
from html.parser import HTMLParser
import re
from typing import Any

from app.ingest.schemas import EmailSchema, HeaderPair

URL_REGEX = re.compile(r'https?://[^\s<>"\'`()]+|www\.[^\s<>"\'`()]+')


class SafeHTMLToTextParser(HTMLParser):
    """Safely extracts plain text and anchor links from HTML.

    - Drops script, style, head, noscript, and meta tags.
    - Converts block elements into newlines.
    - Preserves anchor display text within the plain-text stream.
    - Extracts anchor links as {"text": anchor_text, "href": href} pairs.
    """

    IGNORED_TAGS = {"script", "style", "head", "title", "meta", "noscript"}
    BLOCK_TAGS = {
        "p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6",
        "hr", "blockquote", "table", "section", "article", "header", "footer"
    }

    def __init__(self) -> None:
        super().__init__()
        self.text_parts: list[str] = []
        self.links: list[dict[str, str]] = []
        self.tag_stack: list[str] = []
        self.current_anchor: dict[str, Any] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        self.tag_stack.append(tag_lower)
        if tag_lower in self.BLOCK_TAGS:
            self.text_parts.append("\n")
        if tag_lower == "a":
            href = ""
            for attr_name, attr_val in attrs:
                if attr_name.lower() == "href" and attr_val:
                    href = attr_val.strip()
                    break
            self.current_anchor = {"text_parts": [], "href": href}

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if self.tag_stack and self.tag_stack[-1] == tag_lower:
            self.tag_stack.pop()
        elif tag_lower in self.tag_stack:
            self.tag_stack.remove(tag_lower)

        if tag_lower == "a" and self.current_anchor is not None:
            anchor_text = "".join(self.current_anchor["text_parts"]).strip()
            href = self.current_anchor["href"]
            if href:
                self.links.append({"text": anchor_text, "href": href})
            self.current_anchor = None
        elif tag_lower in self.BLOCK_TAGS:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if any(t in self.IGNORED_TAGS for t in self.tag_stack):
            return
        if self.current_anchor is not None:
            self.current_anchor["text_parts"].append(data)
        self.text_parts.append(data)

    def get_text(self) -> str:
        raw_text = "".join(self.text_parts)
        lines = [re.sub(r'[ \t\r\f\v]+', ' ', line).strip() for line in raw_text.split("\n")]
        cleaned: list[str] = []
        blank = False
        for line in lines:
            if line:
                cleaned.append(line)
                blank = False
            elif not blank and cleaned:
                cleaned.append("")
                blank = True
        return "\n".join(cleaned).strip()


def extract_links_from_plain_text(text: str) -> list[dict[str, str]]:
    """Extract bare URLs from plain text."""
    if not text:
        return []
    links: list[dict[str, str]] = []
    for match in URL_REGEX.finditer(text):
        raw_url = match.group(0).rstrip(".,;!?)>]\'\":")
        if not raw_url:
            continue
        href = raw_url if raw_url.startswith(("http://", "https://")) else f"https://{raw_url}"
        links.append({"text": raw_url, "href": href})
    return links


def extract_all_links(body_html: str = "", body_text: str = "") -> list[dict[str, str]]:
    """Extract and deduplicate links from HTML and plain text.

    Deduplicates strictly on exact (text, href) pairs so mismatched links
    (display-text != href) are never dropped (§Part A).
    """
    raw_links: list[dict[str, str]] = []
    if body_html:
        parser = SafeHTMLToTextParser()
        try:
            parser.feed(body_html)
            parser.close()
            raw_links.extend(parser.links)
        except Exception:
            pass

    if body_text:
        raw_links.extend(extract_links_from_plain_text(body_text))

    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, str]] = []
    for item in raw_links:
        key = (item["text"], item["href"])
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped


def derive_body_text_from_html(body_html: str) -> str:
    """Convert HTML body into clean plain text without rendering it."""
    if not body_html:
        return ""
    parser = SafeHTMLToTextParser()
    try:
        parser.feed(body_html)
        parser.close()
        return parser.get_text()
    except Exception:
        clean = re.sub(r'<[^>]+>', ' ', body_html)
        return re.sub(r'\s+', ' ', clean).strip()


def normalize_message(raw: dict) -> EmailSchema:
    """Convert a Gmail API message resource into an EmailSchema.

    Handles multipart bodies, base64 decoding, attachment metadata,
    and preserves ALL headers as a list of {name, value} pairs.
    """
    payload = raw.get("payload", {})
    headers_raw: list[dict] = payload.get("headers", [])

    # Preserve every header as a {name, value} pair (duplicates kept, §14)
    raw_headers = [
        HeaderPair(name=h["name"], value=h["value"]) for h in headers_raw
    ]

    # Build a first-occurrence lookup for common fields
    header_lookup: dict[str, str] = {}
    for h in headers_raw:
        key = h["name"].lower()
        if key not in header_lookup:
            header_lookup[key] = h["value"]

    subject = html.unescape(header_lookup.get("subject", ""))
    sender = header_lookup.get("from", "")
    to_raw = header_lookup.get("to", "")
    recipients = [r.strip() for r in to_raw.split(",") if r.strip()]
    date = _parse_date(header_lookup.get("date", ""))

    labels: list[str] = raw.get("labelIds", [])
    is_read = "UNREAD" not in labels

    body_text, body_html = _extract_body(payload)
    if not body_text or not body_text.strip():
        if body_html:
            body_text = derive_body_text_from_html(body_html)

    links = extract_all_links(body_html=body_html, body_text=body_text)
    attachments = _extract_attachments(payload)
    snippet = html.unescape(raw.get("snippet", ""))

    return EmailSchema(
        gmail_id=raw["id"],
        thread_id=raw.get("threadId"),
        subject=subject,
        sender=sender,
        recipients=recipients,
        date=date,
        body_text=body_text,
        body_html=body_html,
        links=links,
        snippet=snippet,
        labels=labels,
        raw_headers=raw_headers,
        has_attachments=len(attachments) > 0,
        attachment_meta=attachments,
        is_read=is_read,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_date(date_str: str) -> dt.datetime | None:
    """Parse an RFC-2822 date string into a timezone-aware datetime."""
    if not date_str:
        return None
    try:
        parsed = parsedate_to_datetime(date_str)
        # Ensure timezone-aware
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed
    except (ValueError, TypeError):
        return None


def _extract_body(payload: dict) -> tuple[str, str]:
    """Walk the MIME tree and return (plain_text, html) bodies."""
    text = ""
    html = ""

    mime_type = payload.get("mimeType", "")

    if mime_type == "text/plain":
        text = _decode_body_data(payload.get("body", {}))
    elif mime_type == "text/html":
        html = _decode_body_data(payload.get("body", {}))
    elif mime_type.startswith("multipart/"):
        for part in payload.get("parts", []):
            part_text, part_html = _extract_body(part)
            if part_text and not text:
                text = part_text
            if part_html and not html:
                html = part_html

    return text, html


def _decode_body_data(body: dict) -> str:
    """Decode a Gmail body.data field (URL-safe base64)."""
    data = body.get("data", "")
    if not data:
        return ""
    # Gmail uses URL-safe base64 without padding
    try:
        return base64.urlsafe_b64decode(data + "==").decode(
            "utf-8", errors="replace"
        )
    except Exception:
        return ""


def _extract_attachments(payload: dict) -> list[dict]:
    """Collect attachment metadata from the MIME tree."""
    attachments: list[dict] = []
    _walk_parts(payload, attachments)
    return attachments


def _walk_parts(part: dict, attachments: list[dict]) -> None:
    """Recursively walk MIME parts looking for attachments."""
    filename = part.get("filename", "")
    if filename:
        attachments.append(
            {
                "filename": filename,
                "mimeType": part.get("mimeType", ""),
                "size": part.get("body", {}).get("size", 0),
            }
        )
    for sub_part in part.get("parts", []):
        _walk_parts(sub_part, attachments)
