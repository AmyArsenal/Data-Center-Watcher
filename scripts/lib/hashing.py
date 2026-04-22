"""URL canonicalization and content hashing for cross-source dedup."""

from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_name", "utm_reader", "utm_cid",
    "fbclid", "gclid", "gclsrc", "dclid", "msclkid", "yclid",
    "mc_cid", "mc_eid", "mkt_tok", "_ga", "_hsenc", "_hsmi",
    "ref", "ref_src", "ref_url", "referrer", "share_id", "igshid",
    "cmp", "cmpid", "cid", "ncid",
    "amp", "amp_js_v", "amp_gsa",
}

# Headline prefixes that don't carry meaning for dedup
_HEADLINE_NOISE = re.compile(
    r"^\s*(breaking|update(d)?|exclusive|watch|video|live|opinion|analysis|report)\s*[:\-|]\s*",
    re.IGNORECASE,
)

# Collapse runs of whitespace
_WHITESPACE = re.compile(r"\s+")


def canonicalize_url(url: str) -> str:
    """Return a normalized URL suitable for hashing.

    - lowercases host
    - drops common tracking/ref params
    - strips `www.`, trailing slash, fragment
    - sorts remaining query params for determinism
    """
    if not url:
        return ""
    url = url.strip()
    parsed = urlparse(url)

    scheme = (parsed.scheme or "https").lower()
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if parsed.port and not (
        (scheme == "http" and parsed.port == 80)
        or (scheme == "https" and parsed.port == 443)
    ):
        netloc = f"{host}:{parsed.port}"
    else:
        netloc = host

    path = parsed.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    kept = [
        (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=False)
        if k.lower() not in _TRACKING_PARAMS
    ]
    kept.sort()
    query = urlencode(kept)

    return urlunparse((scheme, netloc, path, "", query, ""))


def url_hash(url: str) -> str:
    """Stable 16-char hex hash of the canonical URL."""
    return hashlib.sha1(canonicalize_url(url).encode("utf-8")).hexdigest()[:16]


def _normalize_text(text: str) -> str:
    text = _HEADLINE_NOISE.sub("", text or "")
    text = _WHITESPACE.sub(" ", text).strip().lower()
    return text


def content_hash(title: str, snippet: str | None = None) -> str:
    """Hash of normalized title plus (optional) first 200 chars of snippet.

    Catches cross-source duplicates where URLs differ but the story is the
    same (e.g., GDELT vs Reddit vs an outlet RSS republish).
    """
    t = _normalize_text(title)
    s = _normalize_text(snippet or "")[:200]
    payload = t + "|" + s
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]
