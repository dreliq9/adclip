"""Native, table-based HTML rendering for portable marketing email packages."""

from __future__ import annotations

import html
import json
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from adclip.email.schema import EmailBlock, EmailCampaignDocument


def _esc(value: str | None, *, quote: bool = True) -> str:
    return html.escape(value or "", quote=quote)


def _tracked_url(document: EmailCampaignDocument, url: str, block_id: str) -> str:
    """Append UTM parameters to ordinary HTTP links, preserving templates."""

    if not document.tracking.enabled:
        return url
    if url.startswith("{{") or not url.startswith(("http://", "https://")):
        return url
    parsed = urlsplit(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.setdefault("utm_source", document.tracking.source)
    query.setdefault("utm_medium", document.tracking.medium)
    query.setdefault("utm_campaign", document.tracking.campaign or document.campaign_name)
    query.setdefault("utm_content", document.tracking.content or block_id)
    return urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment)
    )


def _padding(block: EmailBlock) -> str:
    return (
        f"{block.padding_top}px {block.padding_right}px "
        f"{block.padding_bottom}px {block.padding_left}px"
    )


def _render_block(document: EmailCampaignDocument, block: EmailBlock) -> str:
    theme = document.theme
    marker = _esc(block.id)
    align = _esc(block.align)
    padding = _padding(block)

    if block.kind == "spacer":
        height = block.spacer_height or 24
        return (
            f'<tr data-adclip-block="{marker}"><td height="{height}" '
            f'style="height:{height}px;line-height:{height}px;font-size:0;">&nbsp;</td></tr>'
        )

    if block.kind == "divider":
        return (
            f'<tr data-adclip-block="{marker}"><td style="padding:{padding};">'
            '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">'
            '<tr><td style="border-top:1px solid #E5E7EB;font-size:0;line-height:0;">&nbsp;</td></tr>'
            "</table></td></tr>"
        )

    if block.kind in {"logo", "image"}:
        width_attr = f' width="{block.width}"' if block.width else ""
        width_style = f"width:{block.width}px;max-width:100%;" if block.width else "max-width:100%;"
        height_attr = f' height="{block.height}"' if block.height else ""
        return (
            f'<tr data-adclip-block="{marker}"><td align="{align}" style="padding:{padding};">'
            f'<img src="{_esc(block.src)}" alt="{_esc(block.alt)}"{width_attr}{height_attr} '
            f'style="display:block;border:0;outline:none;text-decoration:none;{width_style}height:auto;" />'
            "</td></tr>"
        )

    if block.kind == "button":
        href = _tracked_url(document, block.href or "", block.id)
        font_size = block.font_size or 16
        return (
            f'<tr data-adclip-block="{marker}"><td align="{align}" style="padding:{padding};">'
            '<table role="presentation" cellspacing="0" cellpadding="0" border="0">'
            f'<tr><td bgcolor="{theme.accent_color}" '
            f'style="border-radius:{theme.border_radius}px;text-align:center;">'
            f'<a href="{_esc(href)}" target="_blank" '
            f'style="display:inline-block;padding:14px 24px;font-family:{_esc(theme.font_family)};'
            f'font-size:{font_size}px;font-weight:700;line-height:20px;color:{theme.button_text_color};'
            f'text-decoration:none;border-radius:{theme.border_radius}px;">{_esc(block.text)}</a>'
            "</td></tr></table></td></tr>"
        )

    if block.kind == "eyebrow":
        font_size = block.font_size or 12
        return (
            f'<tr data-adclip-block="{marker}"><td align="{align}" style="padding:{padding};'
            f'font-family:{_esc(theme.font_family)};font-size:{font_size}px;line-height:18px;'
            f'font-weight:700;letter-spacing:1.2px;text-transform:uppercase;color:{theme.accent_color};">'
            f'{_esc(block.text)}</td></tr>'
        )

    if block.kind == "heading":
        font_size = block.font_size or 32
        return (
            f'<tr data-adclip-block="{marker}"><td align="{align}" style="padding:{padding};'
            f'font-family:{_esc(theme.font_family)};font-size:{font_size}px;line-height:{font_size + 8}px;'
            f'font-weight:700;color:{theme.text_color};">{_esc(block.text)}</td></tr>'
        )

    font_size = block.font_size or 16
    return (
        f'<tr data-adclip-block="{marker}"><td align="{align}" style="padding:{padding};'
        f'font-family:{_esc(theme.font_family)};font-size:{font_size}px;line-height:{font_size + 8}px;'
        f'color:{theme.text_color};">{_esc(block.text)}</td></tr>'
    )


def render_email_html(document: EmailCampaignDocument) -> str:
    """Render an editable document into conservative responsive email HTML."""

    theme = document.theme
    blocks = "".join(_render_block(document, block) for block in document.blocks)
    preferences = ""
    if document.preferences_url:
        preferences = (
            f' &nbsp;|&nbsp; <a href="{_esc(document.preferences_url)}" '
            f'style="color:{theme.muted_text_color};text-decoration:underline;">Manage preferences</a>'
        )

    footer = (
        '<tr data-adclip-block="compliance-footer"><td align="center" '
        f'style="padding:24px 32px 32px;font-family:{_esc(theme.font_family)};font-size:12px;'
        f'line-height:18px;color:{theme.muted_text_color};">'
        f'{_esc(document.sender.physical_address)}<br />'
        f'<a href="{_esc(document.unsubscribe_url)}" '
        f'style="color:{theme.muted_text_color};text-decoration:underline;">Unsubscribe</a>'
        f'{preferences}</td></tr>'
    )

    return f"""<!doctype html>
<html lang="{_esc(document.locale)}">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="x-apple-disable-message-reformatting" />
  <title>{_esc(document.subject)}</title>
  <style>
    body {{ margin:0 !important; padding:0 !important; background:{theme.background_color}; }}
    table {{ border-collapse:collapse !important; }}
    img {{ border:0; height:auto; line-height:100%; outline:none; text-decoration:none; }}
    @media screen and (max-width: 640px) {{
      .adclip-shell {{ width:100% !important; max-width:100% !important; }}
      .adclip-content td {{ padding-left:20px !important; padding-right:20px !important; }}
    }}
  </style>
</head>
<body>
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;line-height:1px;font-size:1px;">
    {_esc(document.preview_text)}&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;
  </div>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" bgcolor="{theme.background_color}">
    <tr>
      <td align="center" style="padding:24px 12px;">
        <table role="presentation" class="adclip-shell adclip-content" width="{theme.content_width}" cellspacing="0" cellpadding="0" border="0" bgcolor="{theme.content_background_color}" style="width:{theme.content_width}px;max-width:{theme.content_width}px;border-radius:{theme.border_radius}px;overflow:hidden;">
          {blocks}
          {footer}
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def render_email_text(document: EmailCampaignDocument) -> str:
    """Render the multipart/alternative plain-text fallback."""

    lines: list[str] = [document.subject, "", document.preview_text, ""]
    for block in document.blocks:
        if block.kind in {"eyebrow", "heading", "paragraph"} and block.text:
            lines.extend([block.text, ""])
        elif block.kind == "button" and block.text and block.href:
            lines.extend([f"{block.text}: {_tracked_url(document, block.href, block.id)}", ""])
        elif block.kind in {"image", "logo"} and block.alt:
            lines.extend([f"[{block.alt}]", ""])
        elif block.kind == "divider":
            lines.extend(["---", ""])

    lines.extend(
        [
            document.sender.physical_address,
            f"Unsubscribe: {document.unsubscribe_url}",
        ]
    )
    if document.preferences_url:
        lines.append(f"Manage preferences: {document.preferences_url}")
    return "\n".join(lines).strip() + "\n"


def build_email_headers(document: EmailCampaignDocument) -> dict[str, str]:
    """Build provider-neutral headers required for modern marketing email."""

    headers = {
        "From": f"{document.sender.name} <{document.sender.email}>",
        "Subject": document.subject,
        "MIME-Version": "1.0",
    }
    if document.sender.reply_to:
        headers["Reply-To"] = document.sender.reply_to
    if document.message_type == "marketing":
        headers["List-Unsubscribe"] = f"<{document.unsubscribe_url}>"
        if document.unsubscribe_url.startswith(("http://", "https://", "{{")):
            headers["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    return headers


def build_email_message(document: EmailCampaignDocument) -> EmailMessage:
    """Build a portable .eml message with HTML and plain-text alternatives."""

    message = EmailMessage()
    for key, value in build_email_headers(document).items():
        if key == "MIME-Version":
            continue
        message[key] = value
    message.set_content(render_email_text(document))
    message.add_alternative(render_email_html(document), subtype="html")
    return message


def write_rendered_email(document: EmailCampaignDocument, output_dir: str | Path) -> dict[str, str]:
    """Write HTML, text, headers, and EML artifacts for one variant."""

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    html_path = root / "email.html"
    text_path = root / "email.txt"
    headers_path = root / "headers.json"
    eml_path = root / "message.eml"

    html_path.write_text(render_email_html(document), encoding="utf-8")
    text_path.write_text(render_email_text(document), encoding="utf-8")
    headers_path.write_text(
        json.dumps(build_email_headers(document), indent=2), encoding="utf-8"
    )
    eml_path.write_bytes(build_email_message(document).as_bytes())
    return {
        "html": str(html_path),
        "text": str(text_path),
        "headers": str(headers_path),
        "eml": str(eml_path),
    }
