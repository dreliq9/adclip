import asyncio
import json
from email import policy
from email.parser import BytesParser
from pathlib import Path

import pytest

from adclip.email.edit import apply_email_patch
from adclip.email.generate import generate_email_documents, scaffold_email_documents
from adclip.email.package import edit_email_campaign_variant, write_email_campaign_package
from adclip.email.render import build_email_headers, render_email_html, render_email_text
from adclip.email.schema import (
    EmailBlock,
    EmailBlockInsertion,
    EmailCampaignBrief,
    EmailCampaignPatch,
)
from adclip.email.validate import validate_email_document, validate_email_html


def _brief(tmp_path: Path, **overrides):
    data = {
        "campaign_name": "launch-week",
        "product": "Atlas Power Station",
        "value_prop": "Test ideas before scaling spend.",
        "audience": "Practical product teams",
        "objective": "Introduce the launch and drive qualified visits.",
        "tone": "clear and credible",
        "cta": "Explore Atlas",
        "landing_url": "https://example.com/atlas",
        "sender": {
            "name": "Atlas Team",
            "email": "hello@example.com",
            "reply_to": "support@example.com",
            "physical_address": "123 Main Street, Boise, ID 83702",
        },
        "output_dir": str(tmp_path / "email"),
        "offer": "Launch pricing is available this week.",
        "subject": "Meet Atlas",
        "preview_text": "A practical power platform for product teams.",
        "headline": "Power the next useful experiment",
        "body_paragraphs": ["Atlas is designed for teams that build and test."],
    }
    data.update(overrides)
    return EmailCampaignBrief.model_validate(data)


def test_scaffold_renders_compliant_package(tmp_path):
    brief = _brief(tmp_path)
    result = write_email_campaign_package(brief, scaffold_email_documents(brief))
    assert result["ok"] is True
    root = Path(result["campaign_dir"])
    variant = root / "variants" / "v01"
    for name in (
        "campaign.json",
        "email.html",
        "email.txt",
        "headers.json",
        "message.eml",
        "validation.json",
    ):
        assert (variant / name).exists()

    html = (variant / "email.html").read_text()
    assert 'data-adclip-block="headline"' in html
    assert "Unsubscribe" in html
    assert "123 Main Street" in html

    parsed = BytesParser(policy=policy.default).parsebytes(
        (variant / "message.eml").read_bytes()
    )
    assert parsed.is_multipart()
    assert parsed["List-Unsubscribe"]
    assert parsed["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"


def test_structured_patch_updates_and_rerenders(tmp_path):
    brief = _brief(tmp_path)
    write_email_campaign_package(brief, scaffold_email_documents(brief))
    patch = EmailCampaignPatch(
        subject="A more specific Atlas launch",
        theme={"accent_color": "#0F766E"},
        block_updates={
            "headline": {"text": "Build, test, and learn with Atlas"},
            "primary-cta": {"text": "See Atlas in action"},
        },
        insert_blocks=[
            EmailBlockInsertion(
                after_id="body-1",
                block=EmailBlock(
                    id="proof-point",
                    kind="paragraph",
                    text="Portable, modular, and built for repeatable testing.",
                ),
            )
        ],
    )
    result = edit_email_campaign_variant(brief.output_dir, "v01", patch)
    assert result["ok"] is True
    document = json.loads(
        (Path(brief.output_dir) / "variants" / "v01" / "campaign.json").read_text()
    )
    assert document["subject"] == "A more specific Atlas launch"
    assert document["theme"]["accent_color"] == "#0F766E"
    assert any(block["id"] == "proof-point" for block in document["blocks"])
    html = (Path(brief.output_dir) / "variants" / "v01" / "email.html").read_text()
    assert "Build, test, and learn with Atlas" in html
    assert "See Atlas in action" in html


def test_patch_rejects_unknown_block(tmp_path):
    document = scaffold_email_documents(_brief(tmp_path))[0]
    with pytest.raises(ValueError, match="unknown block"):
        apply_email_patch(
            document,
            EmailCampaignPatch(block_updates={"missing": {"text": "No"}}),
        )


def test_validator_rejects_unsafe_raw_html():
    report = validate_email_html(
        "<html><body><script>alert(1)</script><a href='javascript:x'>Click</a></body></html>",
        message_type="marketing",
    )
    assert report.ok is False
    codes = {issue.code for issue in report.issues}
    assert "html.forbidden_tag" in codes
    assert "link.javascript" in codes
    assert "compliance.unsubscribe_visible" in codes


def test_renderer_tracks_cta_and_builds_plain_text(tmp_path):
    document = scaffold_email_documents(_brief(tmp_path))[0]
    html = render_email_html(document)
    text = render_email_text(document)
    assert "utm_source=email" in html
    assert "utm_campaign=launch-week" in html
    assert "Explore Atlas:" in text
    report = validate_email_document(
        document,
        html_source=html,
        text_source=text,
        headers=build_email_headers(document),
    )
    assert report.ok is True


class _EmailProvider:
    async def generate(self, prompt: str, n: int) -> str:
        assert "lifecycle and email marketing" in prompt
        return json.dumps(
            {
                "variants": [
                    {
                        "subject": f"Subject {index}",
                        "preview_text": "Useful preview",
                        "eyebrow": "Launch",
                        "headline": "A useful email",
                        "paragraphs": ["A clear, grounded paragraph."],
                        "cta_label": "Learn more",
                        "footer_note": None,
                    }
                    for index in range(1, n + 1)
                ]
            }
        )


def test_generation_is_provider_neutral(tmp_path):
    brief = _brief(tmp_path, variants=2)
    documents = asyncio.run(
        generate_email_documents(
            brief,
            provider=_EmailProvider(),
            provider_name="fixture",
            model_name="fixture-model",
        )
    )
    assert [document.variant_id for document in documents] == ["v01", "v02"]
    assert documents[0].metadata["generation"]["provider"] == "fixture"


def test_transactional_message_omits_unsubscribe_headers(tmp_path):
    document = scaffold_email_documents(_brief(tmp_path, message_type="transactional"))[0]
    headers = build_email_headers(document)
    assert "List-Unsubscribe" not in headers
