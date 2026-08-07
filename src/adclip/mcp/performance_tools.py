"""MCP tools for read-only performance ingestion and creative comparison."""

from __future__ import annotations

import json

from adclip.application.performance_services import PerformanceApplication


def register(mcp) -> None:
    @mcp.tool()
    def adclip_performance_link_meta(
        campaign_dir: str,
        variant_id: str,
        account_id: str,
        ad_id: str,
        campaign_id: str | None = None,
        adset_id: str | None = None,
        creative_id: str | None = None,
        name: str | None = None,
    ) -> str:
        """Link an adclip variant to an existing Meta ad. Makes no API call."""
        result = PerformanceApplication().link_meta(
            campaign_dir,
            variant_id=variant_id,
            account_id=account_id,
            ad_id=ad_id,
            campaign_id=campaign_id,
            adset_id=adset_id,
            creative_id=creative_id,
            name=name,
        )
        return json.dumps(result)

    @mcp.tool()
    def adclip_performance_deployments(campaign_dir: str) -> str:
        """List local creative to external deployment mappings."""
        return json.dumps(PerformanceApplication().deployments(campaign_dir))

    @mcp.tool()
    def adclip_performance_sync_meta(
        campaign_dir: str,
        since: str,
        until: str,
        account_id: str | None = None,
        action_report_time: str = "conversion",
    ) -> str:
        """Read Meta ad insights for linked ads; never creates or edits ads."""
        result = PerformanceApplication().sync_meta(
            campaign_dir,
            since=since,
            until=until,
            account_id=account_id,
            action_report_time=action_report_time,
        )
        return json.dumps(result)

    @mcp.tool()
    def adclip_performance_report(
        campaign_dir: str,
        since: str | None = None,
        until: str | None = None,
    ) -> str:
        """Summarize the latest or an exact stored performance window."""
        return json.dumps(
            PerformanceApplication().report(
                campaign_dir,
                since=since,
                until=until,
            )
        )

    @mcp.tool()
    def adclip_performance_compare(
        campaign_dir: str,
        since: str,
        until: str,
        metric: str = "ctr",
        action_type: str | None = None,
    ) -> str:
        """Rank creatives descriptively; does not claim causal significance."""
        return json.dumps(
            PerformanceApplication().compare(
                campaign_dir,
                since=since,
                until=until,
                metric=metric,
                action_type=action_type,
            )
        )
