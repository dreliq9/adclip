import asyncio
import json
from pathlib import Path

from adclip.application.email_services import EmailApplication
from adclip.providers.contracts import ModelSelection


class Provider:
    async def generate(self, prompt: str, n: int) -> str:
        return json.dumps(
            {
                "emails": [
                    {
                        "id": "email_01",
                        "name": "Launch",
                        "subject": "Try the workflow",
                        "preheader": "A useful preview.",
                        "blocks": [
                            {
                                "id": "body",
                                "kind": "paragraph",
                                "text": "Test before scaling.",
                            },
                            {
                                "id": "cta",
                                "kind": "button",
                                "text": "Start",
                                "href": "https://example.com",
                            },
                        ],
                    }
                ]
            }
        )


class CreativeApplication:
    def resolve_text_provider_with_selection(self, *args, **kwargs):
        return Provider(), ModelSelection(provider="fixture", model="email-v1")


def test_email_application_exports_html_text_headers_and_manifest(tmp_path):
    brief = {
        "name": "Launch",
        "product": "Widget",
        "value_prop": "Save time",
        "audience": "Teams",
        "objective": "Drive trials",
        "sender_name": "Acme",
        "sender_email": "hello@example.com",
        "output_dir": str(tmp_path / "campaign"),
    }
    app = EmailApplication(creative_application=CreativeApplication())
    result = asyncio.run(app.generate_campaign_json(json.dumps(brief)))

    assert result["ok"] is True
    campaign = Path(result["campaign_dir"])
    assert (campaign / "manifest.json").exists()
    assert (campaign / "emails" / "01-email-01" / "email.html").exists()
    manifest = json.loads((campaign / "manifest.json").read_text())
    assert manifest["model"] == {"provider": "fixture", "model": "email-v1"}
