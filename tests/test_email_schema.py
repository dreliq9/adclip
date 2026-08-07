import pytest
from pydantic import ValidationError

from adclip.email.schema import EmailBlock, EmailCampaignBrief, EmailMessage


def _brief(**overrides):
    values = {
        "name": "Launch",
        "product": "Widget",
        "value_prop": "Save setup time",
        "audience": "Small teams",
        "objective": "Drive trials",
        "sender_name": "Acme",
        "sender_email": "hello@example.com",
        "sequence_length": 2,
    }
    values.update(overrides)
    return EmailCampaignBrief(**values)


def test_brief_generates_default_cadence_and_compliance_placeholders():
    brief = _brief()
    assert brief.resolved_cadence() == [0, 2]
    assert brief.unsubscribe_url == "{{unsubscribe_url}}"
    assert brief.physical_address == "{{physical_address}}"


def test_brief_rejects_bad_sender_email():
    with pytest.raises(ValidationError):
        _brief(sender_email="not-an-email")


def test_message_requires_unique_block_ids():
    with pytest.raises(ValidationError):
        EmailMessage(
            id="email_01",
            name="Launch",
            subject="Try it",
            blocks=[
                EmailBlock(id="body", kind="paragraph", text="One"),
                EmailBlock(id="body", kind="paragraph", text="Two"),
            ],
        )
