"""Converts a raw Gmail API message dict into a clean EmailSchema.

Why a separate module: the normalizer is the only place that knows the
Gmail API response shape.  Everything downstream works with EmailSchema,
which makes testing and demo-mode trivial.
"""

from __future__ import annotations

import base64
import datetime as dt
import html
import re
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any, ClassVar
from urllib.parse import parse_qs, unquote, urlparse

from app.ingest.schemas import EmailSchema, HeaderPair

URL_REGEX = re.compile(r'https?://[^\s<>"\'`()]+|www\.[^\s<>"\'`()]+')


def _parse_link_info(text: str, href: str) -> dict[str, str]:
    """Build structured link dictionary with hostname and decoded redirect destination."""
    parsed = urlparse(href)
    hostname = parsed.netloc.lower()

    # Check for redirect / url parameter
    final_url = href
    if parsed.query:
        try:
            qs = parse_qs(parsed.query)
            for param in (
                "url", "q", "u", "target", "dest", "destination",
                "redirect", "redirect_url", "link"
            ):
                if qs.get(param):
                    cand = unquote(qs[param][0]).strip()
                    if cand.startswith(("http://", "https://")):
                        final_url = cand
                        break
        except Exception:
            pass

    clean_text = text.strip() if text else ""
    if not clean_text:
        clean_text = "(image link)"

    return {
        "text": clean_text,
        "href": href,
        "hostname": hostname,
        "final_url": final_url,
    }


class SafeHTMLToTextParser(HTMLParser):
    """Safely extracts plain text and anchor links from HTML.

    - Drops script, style, noscript, and svg content.
    - NEVER treats void tags (<meta>, <link>, <br>, <img>) as container skip tags.
    - Tracks skip stack ONLY for tags with valid closing tags (§BUG 2).
    - If <body> starts, any unclosed header skip tags are cleared.
    - Extracts image alt text for text fallback and image-based anchors.
    - Extracts anchor links with hostname and decoded redirect destination.
    """

    SKIP_TAGS: ClassVar[set[str]] = {"script", "style", "noscript", "svg", "canvas"}
    VOID_TAGS: ClassVar[set[str]] = {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr"
    }
    BLOCK_TAGS: ClassVar[set[str]] = {
        "p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6",
        "hr", "blockquote", "table", "section", "article", "header", "footer"
    }

    def __init__(self) -> None:
        super().__init__()
        self.text_parts: list[str] = []
        self.links: list[dict[str, str]] = []
        self.skip_stack: list[str] = []
        self.img_alts: list[str] = []
        self.current_anchor: dict[str, Any] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()

        # Entering body resets any stale unclosed head tags
        if tag_lower == "body":
            self.skip_stack.clear()

        # Void tags have no end tags — never add them to skip_stack!
        if tag_lower in self.VOID_TAGS:
            if tag_lower == "img":
                for k, v in attrs:
                    if k.lower() == "alt" and v and v.strip():
                        alt_clean = v.strip()
                        self.img_alts.append(alt_clean)
                        if self.current_anchor is not None:
                            self.current_anchor["img_alts"].append(alt_clean)
            if tag_lower in self.BLOCK_TAGS:
                self.text_parts.append("\n")
            return

        if tag_lower in self.SKIP_TAGS:
            self.skip_stack.append(tag_lower)
            return

        if tag_lower in self.BLOCK_TAGS:
            self.text_parts.append("\n")

        if tag_lower == "a":
            href = ""
            for attr_name, attr_val in attrs:
                if attr_name.lower() == "href" and attr_val:
                    href = attr_val.strip()
                    break
            self.current_anchor = {"text_parts": [], "img_alts": [], "href": href}

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()

        if tag_lower in self.skip_stack:
            self.skip_stack.remove(tag_lower)
            return

        if tag_lower == "a" and self.current_anchor is not None:
            anchor_text = "".join(self.current_anchor["text_parts"]).strip()
            if not anchor_text and self.current_anchor["img_alts"]:
                anchor_text = " ".join(self.current_anchor["img_alts"])
            href = self.current_anchor["href"]
            if href:
                self.links.append(_parse_link_info(anchor_text, href))
            self.current_anchor = None
        elif tag_lower in self.BLOCK_TAGS:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.skip_stack:
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
        result = "\n".join(cleaned).strip()
        # Fallback to image alt text if text is otherwise empty
        if not result and self.img_alts:
            result = " ".join(self.img_alts)
        return result


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
        links.append(_parse_link_info(raw_url, href))
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
    clean_html = re.sub(r'^\s*```(?:html)?\s*', '', body_html, flags=re.IGNORECASE)
    clean_html = re.sub(r'\s*```\s*$', '', clean_html)
    parser = SafeHTMLToTextParser()
    try:
        parser.feed(clean_html)
        parser.close()
        text = parser.get_text()
        if text.strip():
            return text
    except Exception:
        pass
    clean = re.sub(r'<[^>]+>', ' ', clean_html)
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

    snippet = html.unescape(raw.get("snippet", ""))
    if not body_text or not body_text.strip():
        # Fallback to snippet if body text is still empty (§BUG 2)
        body_text = snippet

    links = extract_all_links(body_html=body_html, body_text=body_text)
    attachments = _extract_attachments(payload)

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
            parsed = parsed.replace(tzinfo=dt.UTC)
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
