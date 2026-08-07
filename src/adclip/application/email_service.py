"""Transport-neutral email campaign application service."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from adclip.email.generate import generate_email_documents, scaffold_email_documents
from adclip.email.package import (
    edit_email_campaign_variant,
    load_email_document,
    write_email_campaign_package,
)
from adclip.email.render import build_email_headers, render_email_html, render_email_text
from adclip.email.schema import (
    EmailCampaignBrief,
    EmailCampaignPatch,
    EmailDeliveryPlan,
)
from adclip.email.validate import summarize_issues, validate_email_document, validate_email_html
from adclip.providers.registry import TextProviderRegistry, default_text_registry
from adclip.runtime import RuntimePolicy


class EmailCampaignApplication:
    """Standalone facade shared by CLI, MCP, and the future browser editor."""

    def __init__(
        self,
        *,
        text_registry: TextProviderRegistry | None = None,
        runtime_policy: RuntimePolicy | None = None,
    ) -> None:
        self.text_registry = text_registry or default_text_registry()
        self.runtime_policy = runtime_policy or RuntimePolicy.from_env()

    @staticmethod
    def parse_brief_json(brief_json: str) -> EmailCampaignBrief:
        return EmailCampaignBrief.model_validate_json(brief_json)

    @staticmethod
    def validate_brief_json(brief_json: str) -> dict[str, object]:
        try:
            brief = EmailCampaignBrief.model_validate_json(brief_json)
        except (ValidationError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "brief": brief.model_dump(mode="json")}

    def scaffold_email_json(
        self,
        brief_json: str,
        *,
        delivery_plan_json: str | None = None,
    ) -> dict[str, object]:
        try:
            brief = self.parse_brief_json(brief_json)
            plan = (
                EmailDeliveryPlan.model_validate_json(delivery_plan_json)
                if delivery_plan_json
                else None
            )
            documents = scaffold_email_documents(brief)
            result = write_email_campaign_package(brief, documents, delivery_plan=plan)
            result["generation"] = {"mode": "deterministic-scaffold"}
            return result
        except (ValidationError, ValueError, OSError) as exc:
            return {"ok": False, "error": str(exc)}

    async def generate_email_json(
        self,
        brief_json: str,
        *,
        provider_name: str = "default",
        model_name: str | None = None,
        session: Any | None = None,
        delivery_plan_json: str | None = None,
    ) -> dict[str, object]:
        try:
            brief = self.parse_brief_json(brief_json)
            plan = (
                EmailDeliveryPlan.model_validate_json(delivery_plan_json)
                if delivery_plan_json
                else None
            )
            provider, selection = self.text_registry.resolve_with_selection(
                provider_name,
                model=model_name,
                session=session,
                policy=self.runtime_policy,
            )
            documents = await generate_email_documents(
                brief,
                provider=provider,
                provider_name=selection.provider,
                model_name=selection.model,
            )
            result = write_email_campaign_package(brief, documents, delivery_plan=plan)
            result["generation"] = selection.as_dict()
            return result
        except (ValidationError, ValueError, RuntimeError, OSError) as exc:
            return {"ok": False, "error": str(exc)}

    @staticmethod
    def edit_email_json(
        campaign_dir: str,
        variant_id: str,
        patch_json: str,
    ) -> dict[str, object]:
        try:
            patch = EmailCampaignPatch.model_validate_json(patch_json)
            return edit_email_campaign_variant(campaign_dir, variant_id, patch)
        except (ValidationError, ValueError, OSError) as exc:
            return {"ok": False, "error": str(exc)}

    @staticmethod
    def validate_html_json(
        html_source: str,
        *,
        message_type: str = "marketing",
        physical_address: str | None = None,
        unsubscribe_url: str | None = None,
    ) -> dict[str, object]:
        if message_type not in {"marketing", "transactional"}:
            return {"ok": False, "error": "message_type must be marketing or transactional"}
        report = validate_email_html(
            html_source,
            message_type=message_type,
            physical_address=physical_address,
            unsubscribe_url=unsubscribe_url,
        )
        return {
            **report.model_dump(mode="json"),
            "issue_summary": summarize_issues(report.issues),
        }

    @staticmethod
    def validate_html_file(path: str) -> dict[str, object]:
        try:
            html_source = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            return {"ok": False, "error": str(exc)}
        return EmailCampaignApplication.validate_html_json(html_source)

    @staticmethod
    def validate_variant(campaign_dir: str, variant_id: str) -> dict[str, object]:
        try:
            document = load_email_document(campaign_dir, variant_id)
            html_source = render_email_html(document)
            text_source = render_email_text(document)
            report = validate_email_document(
                document,
                html_source=html_source,
                text_source=text_source,
                headers=build_email_headers(document),
            )
            return {
                **report.model_dump(mode="json"),
                "variant_id": variant_id,
                "issue_summary": summarize_issues(report.issues),
            }
        except (ValidationError, ValueError, OSError) as exc:
            return {"ok": False, "error": str(exc)}

    @staticmethod
    def campaign_status(campaign_dir: str) -> dict[str, object]:
        manifest_path = Path(campaign_dir) / "email_manifest.json"
        if not manifest_path.exists():
            return {"ok": False, "error": f"email_manifest.json not found in {campaign_dir}"}
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return {"ok": False, "error": str(exc)}
        return {
            "ok": True,
            "manifest": manifest,
            "campaign_dir": str(Path(campaign_dir).resolve()),
        }
