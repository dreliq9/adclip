"""Compatibility, safety, accessibility, and compliance linting for email HTML."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from typing import Iterable

from adclip.email.schema import (
    EmailCampaignBrief,
    EmailLintContext,
    EmailMessage,
)


@dataclass(frozen=True)
class EmailLintIssue:
    code: str
    severity: str
    message: str
    location: str | None = None


class _EmailInspector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self.text_parts: list[str] = []
        self.style_parts: list[str] = []
        self._in_style = False

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        lowered = tag.lower()
        values = {name.lower(): value for name, value in attrs}
        self.tags.append((lowered, values))
        if lowered == "style":
            self._in_style = True

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() == "style":
            self._in_style = False

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "style":
            self._in_style = False

    def handle_data(self, data: str) -> None:
        if self._in_style:
            self.style_parts.append(data)
        else:
            self.text_parts.append(data)


_BLOCKED_TAGS = {
    "script",
    "iframe",
    "object",
    "embed",
    "form",
    "input",
    "textarea",
    "select",
    "video",
    "audio",
    "applet",
    "base",
}
_RISKY_CSS = {
    "display:flex": "CSS flexbox is inconsistently supported by email clients",
    "display:grid": "CSS grid is inconsistently supported by email clients",
    "position:fixed": "fixed positioning is unsafe in email clients",
    "position:absolute": "absolute positioning is fragile in email clients",
    "javascript:": "javascript URLs are forbidden in email",
}


def _normalized(value: str) -> str:
    return re.sub(r"\s+", "", value.lower())


def lint_email_html(
    html_source: str,
    *,
    context: EmailLintContext | None = None,
    plain_text: str | None = None,
) -> dict[str, object]:
    """Lint rendered or imported email HTML without executing it."""

    active = context or EmailLintContext()
    inspector = _EmailInspector()
    inspector.feed(html_source)

    issues: list[EmailLintIssue] = []

    def add(
        code: str,
        severity: str,
        message: str,
        location: str | None = None,
    ) -> None:
        issues.append(EmailLintIssue(code, severity, message, location))

    tags = inspector.tags
    tag_names = [tag for tag, _attrs in tags]
    visible_text = " ".join(inspector.text_parts)
    visible_text_folded = re.sub(r"\s+", " ", visible_text).strip().lower()

    for tag in sorted(_BLOCKED_TAGS.intersection(tag_names)):
        add(
            "unsafe_tag",
            "error",
            f"<{tag}> is not allowed in email HTML",
            tag,
        )

    html_tags = [attrs for tag, attrs in tags if tag == "html"]
    if not html_tags:
        add("missing_html", "error", "document has no <html> element")
    elif not html_tags[0].get("lang"):
        add(
            "missing_language",
            "warning",
            "the <html> element should include a language",
            "html",
        )

    tables = [attrs for tag, attrs in tags if tag == "table"]
    if not tables:
        add(
            "missing_layout_table",
            "warning",
            "cross-client email layouts should include presentation tables",
        )
    elif not any((attrs.get("role") or "").lower() == "presentation" for attrs in tables):
        add(
            "missing_presentation_role",
            "warning",
            "layout tables should use role=\"presentation\"",
            "table",
        )

    for index, attrs in enumerate(
        (attrs for tag, attrs in tags if tag == "img"),
        start=1,
    ):
        if not attrs.get("src"):
            add("image_missing_src", "error", "image is missing src", f"img[{index}]")
        if "alt" not in attrs:
            add(
                "image_missing_alt",
                "warning",
                "image is missing an alt attribute",
                f"img[{index}]",
            )
        src = attrs.get("src") or ""
        if src.startswith("http://"):
            add(
                "insecure_image",
                "warning",
                "remote email images should use HTTPS",
                f"img[{index}]",
            )
        if src.lower().startswith("javascript:"):
            add(
                "unsafe_url",
                "error",
                "javascript: image URL is forbidden",
                f"img[{index}]",
            )

    for index, attrs in enumerate(
        (attrs for tag, attrs in tags if tag == "a"),
        start=1,
    ):
        href = attrs.get("href")
        if not href:
            add("link_missing_href", "error", "link is missing href", f"a[{index}]")
        elif href.lower().startswith("javascript:"):
            add(
                "unsafe_url",
                "error",
                "javascript: link is forbidden",
                f"a[{index}]",
            )
        elif href.startswith("http://"):
            add(
                "insecure_link",
                "warning",
                "external links should normally use HTTPS",
                f"a[{index}]",
            )

    inline_styles = [
        attrs.get("style") or ""
        for _tag, attrs in tags
        if attrs.get("style")
    ]
    css = _normalized("\n".join([*inspector.style_parts, *inline_styles]))
    for token, message in _RISKY_CSS.items():
        if token in css:
            severity = "error" if token == "javascript:" else "warning"
            add("risky_css", severity, message)

    if not active.subject.strip():
        add("subject_missing", "error", "subject is required")
    elif len(active.subject) > 60:
        add(
            "subject_long",
            "warning",
            "subject is longer than 60 characters",
        )

    if not active.preheader.strip():
        add(
            "preheader_missing",
            "warning",
            "preheader is empty",
        )
    elif len(active.preheader) > 120:
        add(
            "preheader_long",
            "warning",
            "preheader is longer than 120 characters",
        )

    if active.campaign_type == "marketing":
        expected_unsubscribe = active.unsubscribe_url.strip()
        has_unsubscribe = "unsubscribe" in visible_text_folded
        if expected_unsubscribe:
            has_unsubscribe = has_unsubscribe or expected_unsubscribe in html_source
        if not has_unsubscribe:
            add(
                "unsubscribe_missing",
                "error",
                "marketing email needs a visible unsubscribe link",
            )

        expected_address = active.physical_address.strip()
        if expected_address and expected_address not in html_source:
            if "physical_address" not in html_source:
                add(
                    "physical_address_missing",
                    "error",
                    "marketing email needs a sender postal-address field",
                )

        header_names = {name.lower(): value for name, value in active.headers.items()}
        if "list-unsubscribe" not in header_names:
            add(
                "list_unsubscribe_missing",
                "error",
                "marketing export needs a List-Unsubscribe header",
            )
        if "list-unsubscribe-post" not in header_names:
            add(
                "one_click_unsubscribe_missing",
                "error",
                "marketing export needs List-Unsubscribe-Post for one-click opt-out",
            )

    if plain_text is not None and not plain_text.strip():
        add(
            "plain_text_missing",
            "error",
            "multipart campaigns need a non-empty plain-text alternative",
        )

    unresolved = sorted(set(re.findall(r"\{\{[^{}]+\}\}", html_source)))
    for token in unresolved:
        add(
            "template_token",
            "info",
            f"unresolved template token: {token}",
        )

    error_count = sum(issue.severity == "error" for issue in issues)
    warning_count = sum(issue.severity == "warning" for issue in issues)
    return {
        "ok": error_count == 0,
        "summary": {
            "errors": error_count,
            "warnings": warning_count,
            "info": len(issues) - error_count - warning_count,
        },
        "issues": [asdict(issue) for issue in issues],
        "html_bytes": len(html_source.encode("utf-8")),
    }


def lint_rendered_message(
    brief: EmailCampaignBrief,
    message: EmailMessage,
    *,
    html_source: str,
    plain_text: str,
    headers: dict[str, str],
) -> dict[str, object]:
    return lint_email_html(
        html_source,
        context=EmailLintContext(
            campaign_type=brief.campaign_type,
            subject=message.subject,
            preheader=message.preheader,
            unsubscribe_url=brief.unsubscribe_url,
            physical_address=brief.physical_address,
            headers=headers,
        ),
        plain_text=plain_text,
    )


def merge_lint_reports(reports: Iterable[dict[str, object]]) -> dict[str, object]:
    materialized = list(reports)
    return {
        "ok": all(bool(report.get("ok")) for report in materialized),
        "messages": len(materialized),
        "errors": sum(
            int((report.get("summary") or {}).get("errors", 0))  # type: ignore[union-attr]
            for report in materialized
        ),
        "warnings": sum(
            int((report.get("summary") or {}).get("warnings", 0))  # type: ignore[union-attr]
            for report in materialized
        ),
    }
