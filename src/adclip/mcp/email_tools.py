"""MCP tools for standalone email campaign authoring and HTML editing."""

from __future__ import annotations

import json

from mcp.server.fastmcp import Context

from adclip.application.email_service import EmailCampaignApplication


def register(mcp) -> None:
    @mcp.tool()
    def adclip_email_brief_validate(brief_json: str) -> str:
        """Validate an EmailCampaignBrief JSON object without generating."""

        return json.dumps(EmailCampaignApplication.validate_brief_json(brief_json))

    @mcp.tool()
    def adclip_email_scaffold(
        brief_json: str,
        delivery_plan_json: str | None = None,
    ) -> str:
        """Create responsive HTML, text, and EML without a model call."""

        result = EmailCampaignApplication().scaffold_email_json(
            brief_json,
            delivery_plan_json=delivery_plan_json,
        )
        return json.dumps(result)

    @mcp.tool()
    async def adclip_email_generate(
        brief_json: str,
        ctx: Context,
        provider: str = "default",
        model: str | None = None,
        delivery_plan_json: str | None = None,
    ) -> str:
        """Generate email variants through any registered text model and package them."""

        result = await EmailCampaignApplication().generate_email_json(
            brief_json,
            provider_name=provider,
            model_name=model,
            session=ctx.request_context.session,
            delivery_plan_json=delivery_plan_json,
        )
        return json.dumps(result)

    @mcp.tool()
    def adclip_email_edit(
        campaign_dir: str,
        variant_id: str,
        patch_json: str,
    ) -> str:
        """Apply a stable-block patch and regenerate HTML, text, headers, and EML."""

        return json.dumps(
            EmailCampaignApplication.edit_email_json(
                campaign_dir,
                variant_id,
                patch_json,
            )
        )

    @mcp.tool()
    def adclip_email_validate(campaign_dir: str, variant_id: str = "v01") -> str:
        """Validate HTML, MIME, accessibility, and unsubscribe requirements."""

        return json.dumps(
            EmailCampaignApplication.validate_variant(campaign_dir, variant_id)
        )

    @mcp.tool()
    def adclip_email_validate_html(
        html: str,
        message_type: str = "marketing",
        physical_address: str | None = None,
        unsubscribe_url: str | None = None,
    ) -> str:
        """Audit arbitrary email HTML without importing it into a campaign package."""

        return json.dumps(
            EmailCampaignApplication.validate_html_json(
                html,
                message_type=message_type,
                physical_address=physical_address,
                unsubscribe_url=unsubscribe_url,
            )
        )

    @mcp.tool()
    def adclip_email_campaign_status(campaign_dir: str) -> str:
        """Read the email campaign manifest and variant validation state."""

        return json.dumps(EmailCampaignApplication.campaign_status(campaign_dir))
