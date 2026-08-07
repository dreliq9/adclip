"""Responsive, editable HTML and plain-text rendering for email campaigns."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Iterable

from adclip.email.safety import validate_safe_html_fragment
from adclip.email.schema import EmailBlock, EmailCampaignBrief, EmailMessage


def _escape_text(value: str) -> str:
    return html.escape(value, quote=True).replace("\n", "<br>")


def _color(value: str | None, fallback: str) -> str:
    return value or fallback


def _block_marker(block_id: str, position: str) -> str:
    return f"<!-- adclip:block:{block_id}:{position} -->"


def _render_block(
    block: EmailBlock,
    *,
    primary_color: str,
    accent_color: str,
) -> str:
    background = _color(block.background_color, "#FFFFFF")
    text_color = _color(block.text_color, primary_color)
    align = block.align
    padding = f"{block.padding}px"

    if block.kind == "heading":
        font_size = block.font_size or 30
        content = (
            f'<h1 style="margin:0;color:{text_color};font-family:Arial,'
            f'Helvetica,sans-serif;font-size:{font_size}px;line-height:1.2;'
            f'font-weight:700;text-align:{align};">{_escape_text(block.text)}</h1>'
        )
    elif block.kind == "paragraph":
        font_size = block.font_size or 16
        content = (
            f'<div style="margin:0;color:{text_color};font-family:Arial,'
            f'Helvetica,sans-serif;font-size:{font_size}px;line-height:1.55;'
            f'text-align:{align};">{_escape_text(block.text)}</div>'
        )
    elif block.kind == "image":
        content = (
            f'<img src="{html.escape(block.src or "", quote=True)}" '
            f'alt="{html.escape(block.alt, quote=True)}" width="560" '
            'style="display:block;width:100%;max-width:560px;height:auto;'
            f'border:0;outline:none;text-decoration:none;margin:0 auto;text-align:{align};">'
        )
    elif block.kind == "button":
        button_color = _color(block.background_color, accent_color)
        button_text = _color(block.text_color, "#FFFFFF")
        content = (
            '<table role="presentation" border="0" cellpadding="0" cellspacing="0" '
            f'style="margin:0 {"auto" if align == "center" else "0"};">'
            "<tr><td "
            f'style="border-radius:6px;background:{button_color};text-align:center;">'
            f'<a href="{html.escape(block.href or "", quote=True)}" target="_blank" '
            'style="display:inline-block;padding:14px 24px;color:'
            f'{button_text};font-family:Arial,Helvetica,sans-serif;font-size:16px;'
            'font-weight:700;line-height:1;text-decoration:none;border-radius:6px;">'
            f"{_escape_text(block.text)}</a></td></tr></table>"
        )
    elif block.kind == "divider":
        divider_color = _color(block.background_color, "#D1D5DB")
        content = (
            f'<div style="height:1px;line-height:1px;background:{divider_color};'
            'font-size:1px;">&nbsp;</div>'
        )
    elif block.kind == "spacer":
        height = block.height or 24
        content = (
            f'<div style="height:{height}px;line-height:{height}px;font-size:1px;">'
            "&nbsp;</div>"
        )
    elif block.kind == "raw_html":
        fragment = block.raw_html or ""
        validate_safe_html_fragment(fragment)
        content = fragment
    else:  # pragma: no cover - guarded by pydantic
        raise ValueError(f"Unsupported email block kind: {block.kind!r}")

    return (
        f"{_block_marker(block.id, 'start')}\n"
        '<tr data-adclip-block-row="true"><td '
        f'data-adclip-block="{html.escape(block.id, quote=True)}" '
        f'align="{align}" style="background:{background};padding:{padding};">\n'
        f"{content}\n"
        "</td></tr>\n"
        f"{_block_marker(block.id, 'end')}"
    )


def build_email_headers(
    brief: EmailCampaignBrief,
    message: EmailMessage,
) -> dict[str, str]:
    """Build transport-neutral message headers for an ESP adapter."""

    headers = {
        "From": f"{brief.sender_name} <{brief.sender_email}>",
        "Subject": message.subject,
        "MIME-Version": "1.0",
        "Content-Type": 'multipart/alternative; charset="UTF-8"',
        "X-Adclip-Campaign": brief.name,
        "X-Adclip-Message": message.id,
    }
    if brief.reply_to:
        headers["Reply-To"] = brief.reply_to

    if brief.campaign_type == "marketing":
        headers["List-Unsubscribe"] = f"<{brief.unsubscribe_url}>"
        headers["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    return headers


def render_email_html(
    brief: EmailCampaignBrief,
    message: EmailMessage,
) -> str:
    """Render table-based responsive HTML with stable editable block markers."""

    primary = brief.brand_colors[0] if brief.brand_colors else "#111827"
    accent = brief.brand_colors[1] if len(brief.brand_colors) > 1 else "#2563EB"
    canvas = brief.brand_colors[2] if len(brief.brand_colors) > 2 else "#F3F4F6"

    logo = ""
    if brief.logo_url:
        logo = (
            '<tr><td align="center" style="padding:24px 20px 8px;">'
            f'<img src="{html.escape(brief.logo_url, quote=True)}" alt="'
            f'{html.escape(brief.sender_name, quote=True)}" width="160" '
            'style="display:block;width:auto;max-width:160px;height:auto;border:0;">'
            "</td></tr>"
        )

    blocks = "\n".join(
        _render_block(block, primary_color=primary, accent_color=accent)
        for block in message.blocks
    )

    footer = ""
    if brief.campaign_type == "marketing":
        footer = (
            '<tr><td align="center" style="padding:24px 20px 32px;'
            'color:#6B7280;font-family:Arial,Helvetica,sans-serif;'
            'font-size:12px;line-height:1.5;">'
            f"{html.escape(brief.sender_name)}<br>"
            f"{html.escape(brief.physical_address)}<br>"
            f'<a href="{html.escape(brief.unsubscribe_url, quote=True)}" '
            'style="color:#6B7280;text-decoration:underline;">Unsubscribe</a>'
            "</td></tr>"
        )
    elif brief.physical_address:
        footer = (
            '<tr><td align="center" style="padding:24px 20px 32px;'
            'color:#6B7280;font-family:Arial,Helvetica,sans-serif;'
            'font-size:12px;line-height:1.5;">'
            f"{html.escape(brief.sender_name)}<br>"
            f"{html.escape(brief.physical_address)}"
            "</td></tr>"
        )

    preheader = html.escape(message.preheader)
    title = html.escape(message.subject)

    return f"""<!doctype html>
<html lang="{html.escape(brief.language, quote=True)}" dir="{brief.direction}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="x-apple-disable-message-reformatting">
<title>{title}</title>
<style>
  body, table, td, a {{ -webkit-text-size-adjust:100%; -ms-text-size-adjust:100%; }}
  table, td {{ mso-table-lspace:0pt; mso-table-rspace:0pt; border-collapse:collapse; }}
  img {{ -ms-interpolation-mode:bicubic; }}
  @media screen and (max-width:620px) {{
    .adclip-container {{ width:100% !important; max-width:100% !important; }}
    .adclip-pad {{ padding-left:16px !important; padding-right:16px !important; }}
  }}
</style>
</head>
<body style="margin:0;padding:0;background:{canvas};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">
{preheader}
</div>
<table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0"
       style="width:100%;background:{canvas};">
<tr><td align="center" style="padding:24px 12px;">
<table role="presentation" class="adclip-container" width="600" border="0"
       cellpadding="0" cellspacing="0"
       style="width:600px;max-width:600px;background:#FFFFFF;border-radius:10px;
              overflow:hidden;">
{logo}
{blocks}
{footer}
</table>
</td></tr>
</table>
</body>
</html>
"""


def render_email_text(
    brief: EmailCampaignBrief,
    message: EmailMessage,
) -> str:
    """Render a readable plain-text alternative."""

    lines: list[str] = [message.subject, "=" * min(len(message.subject), 72), ""]
    if message.preheader:
        lines.extend([message.preheader, ""])

    for block in message.blocks:
        if block.kind in {"heading", "paragraph"}:
            lines.extend([block.text.strip(), ""])
        elif block.kind == "button":
            lines.extend([f"{block.text}: {block.href}", ""])
        elif block.kind == "image" and block.alt:
            lines.extend([f"[Image: {block.alt}]", ""])
        elif block.kind == "divider":
            lines.extend(["-" * 40, ""])
        elif block.kind == "raw_html":
            lines.extend(["[Rich HTML content]", ""])

    if brief.campaign_type == "marketing":
        lines.extend(
            [
                brief.sender_name,
                brief.physical_address,
                f"Unsubscribe: {brief.unsubscribe_url}",
            ]
        )
    elif brief.physical_address:
        lines.extend([brief.sender_name, brief.physical_address])

    return "\n".join(lines).strip() + "\n"


def write_rendered_message(
    root: Path,
    brief: EmailCampaignBrief,
    message: EmailMessage,
    *,
    lint_report: dict[str, object] | None = None,
) -> dict[str, str]:
    """Write one message bundle and return relative artifact paths."""

    root.mkdir(parents=True, exist_ok=True)
    html_source = render_email_html(brief, message)
    text_source = render_email_text(brief, message)
    headers = build_email_headers(brief, message)

    (root / "message.json").write_text(
        json.dumps(message.model_dump(), indent=2),
        encoding="utf-8",
    )
    (root / "email.html").write_text(html_source, encoding="utf-8")
    (root / "email.txt").write_text(text_source, encoding="utf-8")
    (root / "headers.json").write_text(
        json.dumps(headers, indent=2),
        encoding="utf-8",
    )
    if lint_report is not None:
        (root / "lint.json").write_text(
            json.dumps(lint_report, indent=2),
            encoding="utf-8",
        )

    return {
        "message": str(root / "message.json"),
        "html": str(root / "email.html"),
        "text": str(root / "email.txt"),
        "headers": str(root / "headers.json"),
        **({"lint": str(root / "lint.json")} if lint_report is not None else {}),
    }


def combined_plain_text(messages: Iterable[EmailMessage]) -> str:
    """Produce a compact sequence overview for review screens or exports."""

    return "\n\n".join(
        f"{message.delay_days}d — {message.subject}\n{message.preheader}"
        for message in messages
    )
