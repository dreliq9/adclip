"""Safety checks shared by email rendering and HTML patching."""

from __future__ import annotations

import re


_BLOCKED_TAG_RE = re.compile(
    r"<\s*/?\s*(script|iframe|object|embed|form|input|textarea|select|"
    r"video|audio|applet|base)\b",
    re.IGNORECASE,
)
_JAVASCRIPT_URL_RE = re.compile(
    r"\b(?:href|src)\s*=\s*([\"'])\s*javascript:",
    re.IGNORECASE,
)


def validate_safe_html_fragment(fragment: str) -> None:
    """Reject active or form-capable markup from editable email fragments."""

    match = _BLOCKED_TAG_RE.search(fragment)
    if match:
        raise ValueError(f"unsafe HTML tag in email fragment: {match.group(1)}")
    if _JAVASCRIPT_URL_RE.search(fragment):
        raise ValueError("javascript: URLs are not allowed in email HTML")
