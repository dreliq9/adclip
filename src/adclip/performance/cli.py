"""CLI adapter for deployment lineage, performance sync, and experiments."""

from __future__ import annotations

import json

import click

from adclip.application.experiment_services import ExperimentApplication
from adclip.application.performance_services import PerformanceApplication


@click.group("performance")
def performance_group() -> None:
    """Link creatives, sync metrics, compare performance, and test hypotheses."""


@performance_group.command("link-meta")
@click.argument("campaign_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--variant-id", required=True)
@click.option("--account-id", required=True)
@click.option("--ad-id", required=True)
@click.option("--external-campaign-id", default=None, help="Optional Meta campaign ID.")
@click.option("--external-adset-id", default=None, help="Optional Meta ad set ID.")
@click.option("--external-creative-id", default=None, help="Optional Meta creative ID.")
@click.option("--name", default=None, help="Optional external ad name.")
def link_meta_cmd(
    campaign_dir: str,
    variant_id: str,
    account_id: str,
    ad_id: str,
    external_campaign_id: str | None,
    external_adset_id: str | None,
    external_creative_id: str | None,
    name: str | None,
) -> None:
    """Link one local creative variant to an existing Meta ad without API writes."""

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
    click.echo(json.dumps(result, indent=2))


@performance_group.command("deployments")
@click.argument("campaign_dir", type=click.Path(exists=True, file_okay=False))
def deployments_cmd(campaign_dir: str) -> None:
    """List local-to-platform deployment mappings."""

    click.echo(json.dumps(PerformanceApplication().deployments(campaign_dir), indent=2))


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

    result = PerformanceApplication().report(campaign_dir, since=since, until=until)
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


@performance_group.command("experiment-create")
@click.argument("campaign_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--name", required=True)
@click.option("--hypothesis", required=True)
@click.option("--changed-factor", required=True)
@click.option("--control-variant", required=True)
@click.option("--treatment-variant", required=True)
@click.option("--control-value", required=True)
@click.option("--treatment-value", required=True)
@click.option(
    "--metric",
    "primary_metric",
    type=click.Choice(["ctr", "outbound_ctr", "action_rate", "cost_per_action", "roas"]),
    default="ctr",
    show_default=True,
)
@click.option("--action-type", default=None)
@click.option(
    "--expected-direction",
    type=click.Choice(["higher", "lower"]),
    default="higher",
    show_default=True,
)
@click.option(
    "--design",
    type=click.Choice(["controlled_single_factor", "observational_comparison"]),
    default="controlled_single_factor",
    show_default=True,
)
@click.option("--min-denominator", type=click.IntRange(min=1), default=None)
@click.option("--min-events", type=click.IntRange(min=1), default=None)
@click.option("--confidence", type=click.FloatRange(min=0.5, max=0.999), default=None)
def experiment_create_cmd(
    campaign_dir: str,
    name: str,
    hypothesis: str,
    changed_factor: str,
    control_variant: str,
    treatment_variant: str,
    control_value: str,
    treatment_value: str,
    primary_metric: str,
    action_type: str | None,
    expected_direction: str,
    design: str,
    min_denominator: int | None,
    min_events: int | None,
    confidence: float | None,
) -> None:
    """Declare a hypothesis against two exact creative artifacts."""

    result = ExperimentApplication().create(
        campaign_dir,
        name=name,
        hypothesis=hypothesis,
        changed_factor=changed_factor,
        control_variant_id=control_variant,
        treatment_variant_id=treatment_variant,
        control_value=control_value,
        treatment_value=treatment_value,
        primary_metric=primary_metric,
        action_type=action_type,
        expected_direction=expected_direction,
        design=design,
        min_denominator_per_arm=min_denominator,
        min_events_per_arm=min_events,
        confidence_level=confidence,
    )
    click.echo(json.dumps(result, indent=2))


@performance_group.command("experiments")
@click.argument("campaign_dir", type=click.Path(exists=True, file_okay=False))
def experiments_cmd(campaign_dir: str) -> None:
    """List declared creative experiments."""

    click.echo(json.dumps(ExperimentApplication().list(campaign_dir), indent=2))


@performance_group.command("experiment-evaluate")
@click.argument("campaign_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--experiment-id", required=True)
@click.option("--since", required=True)
@click.option("--until", required=True)
def experiment_evaluate_cmd(
    campaign_dir: str,
    experiment_id: str,
    since: str,
    until: str,
) -> None:
    """Evaluate one hypothesis against an exact stored measurement window."""

    result = ExperimentApplication().evaluate(
        campaign_dir,
        experiment_id=experiment_id,
        since=since,
        until=until,
    )
    click.echo(json.dumps(result, indent=2))


@performance_group.command("next-test")
@click.argument("campaign_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--experiment-id", required=True)
@click.option("--since", required=True)
@click.option("--until", required=True)
def next_test_cmd(
    campaign_dir: str,
    experiment_id: str,
    since: str,
    until: str,
) -> None:
    """Recommend the next controlled action from recorded experiment evidence."""

    result = ExperimentApplication().next_test(
        campaign_dir,
        experiment_id=experiment_id,
        since=since,
        until=until,
    )
    click.echo(json.dumps(result, indent=2))
