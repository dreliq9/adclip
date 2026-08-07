"""CLI adapter for deployment lineage and read-only performance sync."""

from __future__ import annotations

import json

import click

from adclip.application.performance_services import PerformanceApplication


@click.group("performance")
def performance_group() -> None:
    """Link deployed creatives, sync metrics, and compare creative performance."""


@performance_group.command("link-meta")
@click.argument("campaign_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--variant-id", required=True)
@click.option("--account-id", required=True)
@click.option("--ad-id", required=True)
@click.option("--campaign-id", default=None, help="Optional Meta campaign ID.")
@click.option("--adset-id", default=None, help="Optional Meta ad set ID.")
@click.option("--creative-id", default=None, help="Optional Meta creative ID.")
@click.option("--name", default=None, help="Optional external ad name.")
def link_meta_cmd(
    campaign_dir: str,
    variant_id: str,
    account_id: str,
    ad_id: str,
    campaign_id: str | None,
    adset_id: str | None,
    creative_id: str | None,
    name: str | None,
) -> None:
    """Link one local creative variant to an existing Meta ad without API writes."""

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
    click.echo(json.dumps(result, indent=2))


@performance_group.command("deployments")
@click.argument("campaign_dir", type=click.Path(exists=True, file_okay=False))
def deployments_cmd(campaign_dir: str) -> None:
    """List local-to-platform deployment mappings."""

    click.echo(
        json.dumps(PerformanceApplication().deployments(campaign_dir), indent=2)
    )


@performance_group.command("sync-meta")
@click.argument("campaign_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--since", required=True, help="Inclusive YYYY-MM-DD start date.")
@click.option("--until", required=True, help="Inclusive YYYY-MM-DD end date.")
@click.option("--account-id", default=None, help="Optional linked account filter.")
@click.option(
    "--action-report-time",
    default="conversion",
    show_default=True,
    help="Meta action attribution reporting time.",
)
def sync_meta_cmd(
    campaign_dir: str,
    since: str,
    until: str,
    account_id: str | None,
    action_report_time: str,
) -> None:
    """Read Meta Insights for linked ads and persist normalized observations."""

    result = PerformanceApplication().sync_meta(
        campaign_dir,
        since=since,
        until=until,
        account_id=account_id,
        action_report_time=action_report_time,
    )
    click.echo(json.dumps(result, indent=2))


@performance_group.command("report")
@click.argument("campaign_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--since", default=None)
@click.option("--until", default=None)
def report_cmd(campaign_dir: str, since: str | None, until: str | None) -> None:
    """Summarize an exact performance window, or the latest stored window."""

    result = PerformanceApplication().report(
        campaign_dir,
        since=since,
        until=until,
    )
    click.echo(json.dumps(result, indent=2))


@performance_group.command("compare")
@click.argument("campaign_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--since", required=True)
@click.option("--until", required=True)
@click.option(
    "--metric",
    type=click.Choice([
        "ctr",
        "outbound_ctr",
        "cpc",
        "cpm",
        "impressions",
        "clicks",
        "action_rate",
        "cost_per_action",
        "roas",
    ]),
    default="ctr",
    show_default=True,
)
@click.option(
    "--action-type",
    default=None,
    help="Required for action_rate, cost_per_action, and roas.",
)
def compare_cmd(
    campaign_dir: str,
    since: str,
    until: str,
    metric: str,
    action_type: str | None,
) -> None:
    """Rank linked creatives descriptively for one exact measurement window."""

    result = PerformanceApplication().compare(
        campaign_dir,
        since=since,
        until=until,
        metric=metric,
        action_type=action_type,
    )
    click.echo(json.dumps(result, indent=2))
