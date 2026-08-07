"""MCP tools for email campaign generation, rendering, linting, and editing."""

from __future__ import annotations

import json

from mcp.server.fastmcp import Context

from adclip.application.email_services import EmailApplication


def register(mcp) -> None:
    @mcp.tool()
    async def adclip_email_generate_campaign(
        brief_json: str,
        ctx: Context,
        provider: str = "default",
        model: str | None = None,
    ) -> str:
        """Generate and export an email campaign through any text provider."""

        result = await EmailApplication().generate_campaign_json(
            brief_json,
            provider_name=provider,
            model_name=model,
            session=ctx.request_context.session,
        )
        return json.dumps(result)

    @mcp.tool()
    def adclip_email_render(
        brief_json: str,
        message_json: str,
    ) -> str:
        """Render one structured message to HTML, text, headers, and lint."""

        return json.dumps(
            EmailApplication().render_json(brief_json, message_json)
        )

    @mcp.tool()
    def adclip_email_lint(
        html_source: str,
        context_json: str = "{}",
        plain_text: str | None = None,
    ) -> str:
        """Lint imported or rendered email HTML without executing it."""

        return json.dumps(
            EmailApplication().lint_html_json(
                html_source,
                context_json,
                plain_text,
            )
        )

    @mcp.tool()
    def adclip_email_patch_html(
        html_source: str,
        patches_json: str,
        context_json: str = "{}",
    ) -> str:
        """Apply marker-targeted HTML patches and lint the result."""

        return json.dumps(
            EmailApplication().patch_html_json(
                html_source,
                patches_json,
                context_json,
            )
        )

    @mcp.tool()
    def adclip_email_patch_message(
        message_json: str,
        patches_json: str,
    ) -> str:
        """Apply structural patches to an EmailMessage JSON document."""

        return json.dumps(
            EmailApplication().patch_message_json(
                message_json,
                patches_json,
            )
        )
