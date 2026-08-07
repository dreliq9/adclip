import pytest

from adclip.email.edit import apply_html_patches, apply_message_patches
from adclip.email.render import render_email_html
from adclip.email.schema import (
    EmailBlock,
    EmailCampaignBrief,
    EmailHtmlPatch,
    EmailMessage,
)


def _brief():
    return EmailCampaignBrief(
        name="Launch",
        product="Widget",
        value_prop="Save time",
        audience="Teams",
        objective="Drive trials",
        sender_name="Acme",
        sender_email="hello@example.com",
    )


def _message():
    return EmailMessage(
        id="email_01",
        name="Launch",
        subject="Try it",
        blocks=[
            EmailBlock(id="body", kind="paragraph", text="Old body"),
            EmailBlock(
                id="cta",
                kind="button",
                text="Start",
                href="https://example.com/old",
            ),
        ],
    )


def test_html_and_structured_patches_share_block_ids():
    message = _message()
    patches = [
        EmailHtmlPatch(
            block_id="body",
            op="replace_text",
            find="Old body",
            value="New body",
        ),
        EmailHtmlPatch(
            block_id="cta",
            op="set_link",
            href="https://example.com/new",
        ),
    ]

    patched_message = apply_message_patches(message, patches)
    assert patched_message.blocks[0].text == "New body"
    assert patched_message.blocks[1].href == "https://example.com/new"

    html = render_email_html(_brief(), message)
    patched_html = apply_html_patches(html, patches)
    assert "New body" in patched_html
    assert 'href="https://example.com/new"' in patched_html


def test_raw_html_patch_rejects_script():
    html = render_email_html(_brief(), _message())
    with pytest.raises(ValueError, match="unsafe HTML tag"):
        apply_html_patches(
            html,
            [
                EmailHtmlPatch(
                    block_id="body",
                    op="replace_block_html",
                    value="<script>alert(1)</script>",
                )
            ],
        )
