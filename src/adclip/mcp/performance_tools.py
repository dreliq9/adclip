"""MCP tools for read-only performance ingestion and creative experiments."""

from __future__ import annotations

import json

from adclip.application.experiment_services import ExperimentApplication
from adclip.application.performance_services import PerformanceApplication


def register(mcp) -> None:
    @mcp.tool()
    def adclip_performance_link_meta(
        campaign_dir: str,
        variant_id: str,
        account_id: str,
        ad_id: str,
        external_campaign_id: str | None = None,
        external_adset_id: str | None = None,
        external_creative_id: str | None = None,
        name: str | None = None,
    ) -> str:
        """Link an adclip variant to an existing Meta ad. Makes no API call."""
        result = PerformanceApplication().link_meta(
            campaign_dir,
            variant_id=variant_id,
            account_id=account_id,
            ad_id=ad_id,
            external_campaign_id=external_campaign_id,
            external_adset_id=external_adset_id,
            external_creative_id=external_creative_id,
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

    @mcp.tool()
    def adclip_experiment_create(
        campaign_dir: str,
        name: str,
        hypothesis: str,
        changed_factor: str,
        control_variant_id: str,
        treatment_variant_id: str,
        control_value: str,
        treatment_value: str,
        primary_metric: str = "ctr",
        action_type: str | None = None,
        expected_direction: str = "higher",
        design: str = "controlled_single_factor",
        min_denominator_per_arm: int | None = None,
        min_events_per_arm: int | None = None,
        confidence_level: float | None = None,
    ) -> str:
        """Declare one changed-factor hypothesis against exact creative artifacts."""
        result = ExperimentApplication().create(
            campaign_dir,
            name=name,
            hypothesis=hypothesis,
            changed_factor=changed_factor,
            control_variant_id=control_variant_id,
            treatment_variant_id=treatment_variant_id,
            control_value=control_value,
            treatment_value=treatment_value,
            primary_metric=primary_metric,
            action_type=action_type,
            expected_direction=expected_direction,
            design=design,
            min_denominator_per_arm=min_denominator_per_arm,
            min_events_per_arm=min_events_per_arm,
            confidence_level=confidence_level,
        )
        return json.dumps(result)

    @mcp.tool()
    def adclip_experiments(campaign_dir: str) -> str:
        """List declared creative experiments."""
        return json.dumps(ExperimentApplication().list(campaign_dir))

    @mcp.tool()
    def adclip_experiment_evaluate(
        campaign_dir: str,
        experiment_id: str,
        since: str,
        until: str,
    ) -> str:
        """Evaluate a hypothesis against one exact stored observation window."""
        return json.dumps(
            ExperimentApplication().evaluate(
                campaign_dir,
                experiment_id=experiment_id,
                since=since,
                until=until,
            )
        )

    @mcp.tool()
    def adclip_experiment_next_test(
        campaign_dir: str,
        experiment_id: str,
        since: str,
        until: str,
    ) -> str:
        """Recommend the next controlled test from recorded evidence."""
        return json.dumps(
            ExperimentApplication().next_test(
                campaign_dir,
                experiment_id=experiment_id,
                since=since,
                until=until,
            )
        )
