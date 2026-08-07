"""Transport-neutral application service for email campaign authoring."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from adclip.application.services import AdclipApplication
from adclip.email.edit import apply_html_patches, apply_message_patches
from adclip.email.generate import generate_email_messages
from adclip.email.lint import (
    lint_email_html,
    lint_rendered_message,
    merge_lint_reports,
)
from adclip.email.render import (
    build_email_headers,
    render_email_html,
    render_email_text,
    write_rendered_message,
)
from adclip.email.schema import (
    EmailCampaignBrief,
    EmailHtmlPatch,
    EmailLintContext,
    EmailMessage,
)


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "email"


class EmailApplication:
    """Standalone email campaign generation, rendering, editing, and linting."""

    def __init__(
        self,
        *,
        creative_application: AdclipApplication | None = None,
    ) -> None:
        self.creative_application = creative_application or AdclipApplication()

    @staticmethod
    def parse_brief_json(brief_json: str) -> EmailCampaignBrief:
        value = json.loads(brief_json)
        if not isinstance(value, dict):
            raise ValueError("EmailCampaignBrief JSON must be an object")
        return EmailCampaignBrief.model_validate(value)

    @staticmethod
    def parse_message_json(message_json: str) -> EmailMessage:
        value = json.loads(message_json)
        if not isinstance(value, dict):
            raise ValueError("EmailMessage JSON must be an object")
        return EmailMessage.model_validate(value)

    @staticmethod
    def parse_patches_json(patches_json: str) -> list[EmailHtmlPatch]:
        values = json.loads(patches_json)
        if not isinstance(values, list):
            raise ValueError("email patches JSON must be an array")
        return [EmailHtmlPatch.model_validate(value) for value in values]

    @staticmethod
    def parse_lint_context_json(context_json: str) -> EmailLintContext:
        value = json.loads(context_json)
        if not isinstance(value, dict):
            raise ValueError("email lint context JSON must be an object")
        return EmailLintContext.model_validate(value)

    def render(
        self,
        brief: EmailCampaignBrief,
        message: EmailMessage,
    ) -> dict[str, object]:
        html_source = render_email_html(brief, message)
        plain_text = render_email_text(brief, message)
        headers = build_email_headers(brief, message)
        lint = lint_rendered_message(
            brief,
            message,
            html_source=html_source,
            plain_text=plain_text,
            headers=headers,
        )
        return {
            "ok": bool(lint["ok"]),
            "html": html_source,
            "text": plain_text,
            "headers": headers,
            "lint": lint,
        }

    def render_json(
        self,
        brief_json: str,
        message_json: str,
    ) -> dict[str, object]:
        try:
            brief = self.parse_brief_json(brief_json)
            message = self.parse_message_json(message_json)
            return self.render(brief, message)
        except (
            json.JSONDecodeError,
            ValidationError,
            ValueError,
        ) as exc:
            return {"ok": False, "error": str(exc)}

    def lint_html_json(
        self,
        html_source: str,
        context_json: str = "{}",
        plain_text: str | None = None,
    ) -> dict[str, object]:
        try:
            context = self.parse_lint_context_json(context_json)
            return lint_email_html(
                html_source,
                context=context,
                plain_text=plain_text,
            )
        except (
            json.JSONDecodeError,
            ValidationError,
            ValueError,
        ) as exc:
            return {"ok": False, "error": str(exc)}

    def patch_html_json(
        self,
        html_source: str,
        patches_json: str,
        context_json: str = "{}",
    ) -> dict[str, object]:
        try:
            patches = self.parse_patches_json(patches_json)
            context = self.parse_lint_context_json(context_json)
            patched = apply_html_patches(html_source, patches)
            lint = lint_email_html(patched, context=context)
            return {
                "ok": bool(lint["ok"]),
                "html": patched,
                "lint": lint,
            }
        except (
            json.JSONDecodeError,
            ValidationError,
            ValueError,
        ) as exc:
            return {"ok": False, "error": str(exc)}

    def patch_message_json(
        self,
        message_json: str,
        patches_json: str,
    ) -> dict[str, object]:
        try:
            message = self.parse_message_json(message_json)
            patches = self.parse_patches_json(patches_json)
            patched = apply_message_patches(message, patches)
            return {"ok": True, "message": patched.model_dump()}
        except (
            json.JSONDecodeError,
            ValidationError,
            ValueError,
        ) as exc:
            return {"ok": False, "error": str(exc)}

    async def generate_campaign(
        self,
        brief: EmailCampaignBrief,
        *,
        provider_name: str = "default",
        model_name: str | None = None,
        session: Any | None = None,
    ) -> dict[str, object]:
        provider, selection = (
            self.creative_application.resolve_text_provider_with_selection(
                provider_name,
                model=model_name,
                session=session,
            )
        )
        messages = await generate_email_messages(brief, provider=provider)
        root = Path(brief.output_dir)
        root.mkdir(parents=True, exist_ok=True)

        (root / "campaign.json").write_text(
            json.dumps(brief.model_dump(), indent=2),
            encoding="utf-8",
        )

        entries: list[dict[str, object]] = []
        reports: list[dict[str, object]] = []
        for index, message in enumerate(messages, start=1):
            html_source = render_email_html(brief, message)
            plain_text = render_email_text(brief, message)
            headers = build_email_headers(brief, message)
            lint = lint_rendered_message(
                brief,
                message,
                html_source=html_source,
                plain_text=plain_text,
                headers=headers,
            )
            reports.append(lint)
            directory = root / "emails" / f"{index:02d}-{_slug(message.id)}"
            paths = write_rendered_message(
                directory,
                brief,
                message,
                lint_report=lint,
            )
            entries.append(
                {
                    "index": index,
                    "id": message.id,
                    "name": message.name,
                    "delay_days": message.delay_days,
                    "subject": message.subject,
                    "preheader": message.preheader,
                    "lint_ok": bool(lint["ok"]),
                    "paths": {
                        name: str(Path(path).relative_to(root))
                        for name, path in paths.items()
                    },
                }
            )

        manifest = {
            "schema_version": "email-campaign-v1",
            "name": brief.name,
            "campaign_type": brief.campaign_type,
            "model": selection.as_dict(),
            "messages": entries,
            "lint": merge_lint_reports(reports),
        }
        (root / "manifest.json").write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )

        return {
            "ok": bool(manifest["lint"]["ok"]),
            "campaign_dir": str(root.resolve()),
            "model": selection.as_dict(),
            "messages": entries,
            "lint": manifest["lint"],
        }

    async def generate_campaign_json(
        self,
        brief_json: str,
        *,
        provider_name: str = "default",
        model_name: str | None = None,
        session: Any | None = None,
    ) -> dict[str, object]:
        try:
            brief = self.parse_brief_json(brief_json)
            return await self.generate_campaign(
                brief,
                provider_name=provider_name,
                model_name=model_name,
                session=session,
            )
        except (
            json.JSONDecodeError,
            ValidationError,
            RuntimeError,
            ValueError,
        ) as exc:
            return {"ok": False, "error": str(exc)}
