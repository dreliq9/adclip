"""Standards-aware validation for email documents and arbitrary email HTML."""

from __future__ import annotations

import html as html_module
import re
from html.parser import HTMLParser
from typing import Iterable

from adclip.email.schema import (
    EmailCampaignDocument,
    EmailValidationIssue,
    EmailValidationReport,
)


_FORBIDDEN_TAGS = {"script", "iframe", "object", "embed", "form", "input", "textarea"}
_TEMPLATE_TOKEN_RE = re.compile(r"\{\{[A-Za-z0-9_.-]+\}\}")


class _EmailHtmlInspector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[str] = []
        self.forbidden: list[str] = []
        self.missing_alt: int = 0
        self.links: list[str] = []
        self.external_stylesheets: int = 0
        self.has_html_lang = False
        self.has_viewport = False
        self.has_title = False
        self.has_presentation_table = False
        self.has_preheader = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        self.tags.append(lowered)
        attr = {key.lower(): (value or "") for key, value in attrs}
        if lowered in _FORBIDDEN_TAGS:
            self.forbidden.append(lowered)
        if lowered == "html" and attr.get("lang"):
            self.has_html_lang = True
        if lowered == "meta" and attr.get("name", "").lower() == "viewport":
            self.has_viewport = True
        if lowered == "title":
            self.has_title = True
        if lowered == "table" and attr.get("role", "").lower() == "presentation":
            self.has_presentation_table = True
        if lowered == "img" and not attr.get("alt", "").strip():
            self.missing_alt += 1
        if lowered == "a":
            self.links.append(attr.get("href", ""))
        if lowered == "link" and attr.get("rel", "").lower() == "stylesheet":
            self.external_stylesheets += 1
        if "max-height:0" in attr.get("style", "").replace(" ", "").lower():
            self.has_preheader = True


def _issue(
    severity: str,
    code: str,
    message: str,
    location: str | None = None,
) -> EmailValidationIssue:
    return EmailValidationIssue(
        severity=severity,  # type: ignore[arg-type]
        code=code,
        message=message,
        location=location,
    )


def inspect_email_html(html_source: str) -> tuple[_EmailHtmlInspector, list[EmailValidationIssue]]:
    inspector = _EmailHtmlInspector()
    issues: list[EmailValidationIssue] = []
    try:
        inspector.feed(html_source)
        inspector.close()
    except Exception as exc:
        issues.append(_issue("error", "html.parse", f"HTML parser failed: {exc}"))
        return inspector, issues

    for tag in sorted(set(inspector.forbidden)):
        issues.append(
            _issue(
                "error",
                "html.forbidden_tag",
                f"Email HTML contains unsupported or unsafe <{tag}> markup.",
                tag,
            )
        )
    if inspector.missing_alt:
        issues.append(
            _issue(
                "error",
                "accessibility.image_alt",
                f"{inspector.missing_alt} image(s) are missing non-empty alt text.",
            )
        )
    if not inspector.has_html_lang:
        issues.append(
            _issue("warning", "accessibility.lang", "The <html> element has no lang attribute.")
        )
    if not inspector.has_viewport:
        issues.append(
            _issue("warning", "html.viewport", "A mobile viewport meta tag is missing.")
        )
    if not inspector.has_title:
        issues.append(_issue("warning", "html.title", "The HTML document has no <title>."))
    if not inspector.has_presentation_table:
        issues.append(
            _issue(
                "warning",
                "html.presentation_tables",
                "No role=\"presentation\" table was found; complex layouts may be read incorrectly by assistive technology.",
            )
        )
    if not inspector.has_preheader:
        issues.append(
            _issue("warning", "html.preheader", "No hidden inbox preview/preheader was detected.")
        )
    if inspector.external_stylesheets:
        issues.append(
            _issue(
                "warning",
                "css.external_stylesheet",
                "External stylesheets are unreliable in email clients; inline or embedded styles are preferred.",
            )
        )

    for index, href in enumerate(inspector.links):
        location = f"link[{index}]"
        if not href:
            issues.append(_issue("error", "link.empty", "A link has an empty href.", location))
        elif href.lower().startswith("javascript:"):
            issues.append(
                _issue("error", "link.javascript", "javascript: links are not allowed.", location)
            )
        elif href.startswith("http://"):
            issues.append(
                _issue("warning", "link.insecure", "Use HTTPS for campaign links.", location)
            )
        elif not href.startswith(("https://", "mailto:", "tel:", "{{", "#")):
            issues.append(
                _issue(
                    "warning",
                    "link.relative",
                    "Relative URLs are fragile in email; use an absolute URL or template token.",
                    location,
                )
            )

    byte_size = len(html_source.encode("utf-8"))
    if byte_size > 100_000:
        issues.append(
            _issue(
                "warning",
                "html.size",
                f"HTML is {byte_size} bytes; large messages may be clipped by mailbox providers.",
            )
        )
    return inspector, issues


def validate_email_html(
    html_source: str,
    *,
    message_type: str = "marketing",
    physical_address: str | None = None,
    unsubscribe_url: str | None = None,
) -> EmailValidationReport:
    """Validate arbitrary email HTML without requiring an adclip campaign package."""

    inspector, issues = inspect_email_html(html_source)
    lowered = html_source.lower()
    if message_type == "marketing":
        has_unsubscribe = (
            "unsubscribe" in lowered
            or bool(unsubscribe_url and unsubscribe_url in html_source)
            or bool(_TEMPLATE_TOKEN_RE.search(html_source) and "unsubscribe" in lowered)
        )
        if not has_unsubscribe:
            issues.append(
                _issue(
                    "error",
                    "compliance.unsubscribe_visible",
                    "Marketing email requires a clearly visible unsubscribe link.",
                )
            )
        if physical_address:
            escaped_address = html_module.escape(physical_address, quote=True)
            if physical_address not in html_source and escaped_address not in html_source:
                issues.append(
                    _issue(
                        "error",
                        "compliance.physical_address",
                        "The sender physical address is not present in the HTML body.",
                    )
                )

    metrics = {
        "html_bytes": len(html_source.encode("utf-8")),
        "tag_count": len(inspector.tags),
        "link_count": len(inspector.links),
        "image_count": inspector.tags.count("img"),
    }
    return EmailValidationReport.from_issues(issues, metrics=metrics)


def validate_email_document(
    document: EmailCampaignDocument,
    *,
    html_source: str,
    text_source: str,
    headers: dict[str, str],
) -> EmailValidationReport:
    """Validate the canonical document and all rendered delivery artifacts."""

    report = validate_email_html(
        html_source,
        message_type=document.message_type,
        physical_address=document.sender.physical_address,
        unsubscribe_url=document.unsubscribe_url,
    )
    issues = list(report.issues)

    if len(document.subject) > 70:
        issues.append(
            _issue(
                "warning",
                "copy.subject_length",
                f"Subject is {len(document.subject)} characters; test truncation across inboxes.",
            )
        )
    if len(document.preview_text) > 160:
        issues.append(
            _issue(
                "warning",
                "copy.preview_length",
                f"Preview text is {len(document.preview_text)} characters; many inboxes show substantially less.",
            )
        )
    if not text_source.strip():
        issues.append(
            _issue(
                "error",
                "mime.plain_text",
                "A non-empty text/plain alternative is required.",
            )
        )

    if document.message_type == "marketing":
        if "List-Unsubscribe" not in headers:
            issues.append(
                _issue(
                    "error",
                    "header.list_unsubscribe",
                    "Marketing email is missing the List-Unsubscribe header.",
                )
            )
        if document.unsubscribe_url.startswith(("http://", "https://", "{{")) and (
            headers.get("List-Unsubscribe-Post") != "List-Unsubscribe=One-Click"
        ):
            issues.append(
                _issue(
                    "error",
                    "header.one_click_unsubscribe",
                    "HTTPS marketing unsubscribe requires the RFC 8058 one-click header.",
                )
            )

    button_count = sum(block.kind == "button" for block in document.blocks)
    if not button_count:
        issues.append(
            _issue("warning", "content.no_cta", "No button CTA is present in the email document.")
        )

    metrics = {
        **report.metrics,
        "text_bytes": len(text_source.encode("utf-8")),
        "block_count": len(document.blocks),
        "button_count": button_count,
        "has_one_click_unsubscribe": "List-Unsubscribe-Post" in headers,
    }
    return EmailValidationReport.from_issues(issues, metrics=metrics)


def summarize_issues(issues: Iterable[EmailValidationIssue]) -> dict[str, int]:
    summary = {"error": 0, "warning": 0, "info": 0}
    for issue in issues:
        summary[issue.severity] += 1
    return summary
