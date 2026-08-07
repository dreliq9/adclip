"""Marker-targeted structural and rendered-HTML editing for email messages."""

from __future__ import annotations

import html
import re

from adclip.email.safety import validate_safe_html_fragment
from adclip.email.schema import EmailBlock, EmailHtmlPatch, EmailMessage


def _marker_pattern(block_id: str) -> re.Pattern[str]:
    escaped = re.escape(block_id)
    return re.compile(
        rf"(<!--\s*adclip:block:{escaped}:start\s*-->)(.*?)"
        rf"(<!--\s*adclip:block:{escaped}:end\s*-->)",
        re.IGNORECASE | re.DOTALL,
    )


def _replace_first_attribute(
    segment: str,
    *,
    tag: str,
    attribute: str,
    value: str,
) -> str:
    tag_pattern = re.compile(
        rf"(<{tag}\b[^>]*\b{attribute}\s*=\s*)([\"'])(.*?)(\2)",
        re.IGNORECASE | re.DOTALL,
    )
    escaped = html.escape(value, quote=True)
    updated, count = tag_pattern.subn(
        lambda match: f"{match.group(1)}{match.group(2)}{escaped}{match.group(4)}",
        segment,
        count=1,
    )
    if count:
        return updated

    opening = re.compile(rf"<{tag}\b", re.IGNORECASE)
    updated, count = opening.subn(
        f'<{tag} {attribute}="{escaped}"',
        segment,
        count=1,
    )
    if not count:
        raise ValueError(f"target block contains no <{tag}> element")
    return updated


def apply_html_patches(
    html_source: str,
    patches: list[EmailHtmlPatch],
) -> str:
    """Patch adclip-rendered HTML while preserving stable block markers."""

    output = html_source
    for patch in patches:
        pattern = _marker_pattern(patch.block_id)
        match = pattern.search(output)
        if not match:
            raise ValueError(
                f"email HTML contains no editable block {patch.block_id!r}"
            )

        start, segment, end = match.groups()

        if patch.op == "replace_text":
            old = html.escape(patch.find or "", quote=False)
            new = html.escape(patch.value or "", quote=False)
            if old not in segment:
                raise ValueError(
                    f"text {patch.find!r} was not found in block {patch.block_id!r}"
                )
            segment = segment.replace(old, new, 1)
        elif patch.op == "set_link":
            href = patch.href or ""
            if href.lower().startswith("javascript:"):
                raise ValueError("javascript: URLs are not allowed")
            segment = _replace_first_attribute(
                segment,
                tag="a",
                attribute="href",
                value=href,
            )
        elif patch.op == "set_image":
            src = patch.src or ""
            if src.lower().startswith("javascript:"):
                raise ValueError("javascript: URLs are not allowed")
            segment = _replace_first_attribute(
                segment,
                tag="img",
                attribute="src",
                value=src,
            )
            if patch.alt is not None:
                segment = _replace_first_attribute(
                    segment,
                    tag="img",
                    attribute="alt",
                    value=patch.alt,
                )
        elif patch.op == "replace_block_html":
            fragment = patch.value or ""
            validate_safe_html_fragment(fragment)
            segment = f"\n{fragment}\n"
        elif patch.op == "remove_block":
            output = output[: match.start()] + output[match.end() :]
            continue
        else:  # pragma: no cover - pydantic guards this
            raise ValueError(f"unsupported email patch op {patch.op!r}")

        output = output[: match.start()] + start + segment + end + output[match.end() :]

    return output


def apply_message_patches(
    message: EmailMessage,
    patches: list[EmailHtmlPatch],
) -> EmailMessage:
    """Apply the same patch vocabulary to the structured message document."""

    blocks = [block.model_copy(deep=True) for block in message.blocks]

    for patch in patches:
        index = next(
            (i for i, block in enumerate(blocks) if block.id == patch.block_id),
            None,
        )
        if index is None:
            raise ValueError(f"message contains no block {patch.block_id!r}")
        block = blocks[index]

        if patch.op == "replace_text":
            if patch.find not in block.text:
                raise ValueError(
                    f"text {patch.find!r} was not found in block {patch.block_id!r}"
                )
            block.text = block.text.replace(
                patch.find or "",
                patch.value or "",
                1,
            )
        elif patch.op == "set_link":
            if block.kind != "button":
                raise ValueError("set_link requires a button block")
            if (patch.href or "").lower().startswith("javascript:"):
                raise ValueError("javascript: URLs are not allowed")
            block.href = patch.href
        elif patch.op == "set_image":
            if block.kind != "image":
                raise ValueError("set_image requires an image block")
            if (patch.src or "").lower().startswith("javascript:"):
                raise ValueError("javascript: URLs are not allowed")
            block.src = patch.src
            if patch.alt is not None:
                block.alt = patch.alt
        elif patch.op == "replace_block_html":
            validate_safe_html_fragment(patch.value or "")
            block = EmailBlock(
                id=block.id,
                kind="raw_html",
                raw_html=patch.value,
                padding=block.padding,
                background_color=block.background_color,
                align=block.align,
            )
            blocks[index] = block
        elif patch.op == "remove_block":
            blocks.pop(index)
        else:  # pragma: no cover
            raise ValueError(f"unsupported email patch op {patch.op!r}")

    if not blocks:
        raise ValueError("patches cannot remove every email block")
    payload = message.model_dump()
    payload["blocks"] = [block.model_dump() for block in blocks]
    return EmailMessage.model_validate(payload)
