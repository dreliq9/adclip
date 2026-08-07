import asyncio
import json

from adclip.email.generate import generate_email_messages
from adclip.email.schema import EmailCampaignBrief


class Provider:
    async def generate(self, prompt: str, n: int) -> str:
        assert "Sequence length: 2" in prompt
        assert n == 2
        return json.dumps(
            {
                "emails": [
                    {
                        "id": "email_01",
                        "name": "Introduce",
                        "delay_days": 99,
                        "subject": "A better workflow",
                        "preheader": "Test before scaling.",
                        "blocks": [
                            {
                                "id": "headline",
                                "kind": "heading",
                                "text": "Test before scaling",
                            },
                            {
                                "id": "cta",
                                "kind": "button",
                                "text": "Learn more",
                                "href": "https://example.com",
                            },
                        ],
                    },
                    {
                        "id": "email_02",
                        "name": "Proof",
                        "delay_days": 99,
                        "subject": "What changes",
                        "preheader": "A concrete second step.",
                        "blocks": [
                            {
                                "id": "body",
                                "kind": "paragraph",
                                "text": "A useful explanation.",
                            },
                            {
                                "id": "cta",
                                "kind": "button",
                                "text": "See details",
                                "href": "https://example.com",
                            },
                        ],
                    },
                ]
            }
        )


def test_generation_uses_brief_cadence_not_model_invented_delays():
    brief = EmailCampaignBrief(
        name="Launch",
        product="Widget",
        value_prop="Save time",
        audience="Teams",
        objective="Drive trials",
        sender_name="Acme",
        sender_email="hello@example.com",
        sequence_length=2,
        cadence_days=[0, 5],
    )
    messages = asyncio.run(generate_email_messages(brief, provider=Provider()))
    assert [message.delay_days for message in messages] == [0, 5]
