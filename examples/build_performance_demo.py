"""Build an offline adclip performance/experiment demo.

This script creates two exact creative artifacts, synthetic deployment records,
normalized observations, and one explicit CTR experiment. It performs no
network requests and needs no API keys.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from adclip.application.experiment_services import ExperimentApplication
from adclip.campaign import ensure_manifest_identity, init_campaign_dir, write_manifest
from adclip.performance.identity import deployment_id_for, observation_id_for
from adclip.performance.schema import (
    DeploymentRecord,
    PerformanceMetrics,
    PerformanceObservation,
)
from adclip.performance.store import (
    find_creative_entry,
    upsert_deployment,
    upsert_observations,
)
from adclip.schema import AdBrief


START = date(2026, 8, 1)
END = date(2026, 8, 7)
ACTION_REPORT_TIME = "conversion"


def _svg(headline: str, subhead: str, accent: str) -> str:
    return f"""<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"1080\" height=\"1350\" viewBox=\"0 0 1080 1350\">
  <rect width=\"1080\" height=\"1350\" fill=\"#172033\"/>
  <rect x=\"72\" y=\"92\" width=\"936\" height=\"1166\" rx=\"36\" fill=\"#F4F1E8\"/>
  <rect x=\"72\" y=\"92\" width=\"18\" height=\"1166\" fill=\"{accent}\"/>
  <text x=\"140\" y=\"370\" font-family=\"Arial, sans-serif\" font-size=\"68\" font-weight=\"700\" fill=\"#172033\">{headline}</text>
  <text x=\"140\" y=\"470\" font-family=\"Arial, sans-serif\" font-size=\"34\" fill=\"#172033\">{subhead}</text>
  <text x=\"140\" y=\"1090\" font-family=\"Arial, sans-serif\" font-size=\"28\" fill=\"#172033\">Synthetic adclip learning-loop fixture</text>
</svg>
"""


def _write_creative(root: Path, variant_id: str, svg: str) -> str:
    relative = Path("variants") / variant_id / "meta_feed_4x5.svg"
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(svg, encoding="utf-8")
    return relative.as_posix()


def _deployment(campaign_id: str, entry: dict, ad_id: str) -> DeploymentRecord:
    account_id = "act_demo"
    return DeploymentRecord(
        id=deployment_id_for("meta", account_id, ad_id),
        campaign_id=campaign_id,
        creative_id=str(entry["creative_id"]),
        variant_id=str(entry["variant_id"]),
        format=str(entry["format"]),
        platform="meta",
        account_id=account_id,
        external_ad_id=ad_id,
        external_campaign_id="demo_campaign",
        external_adset_id="demo_adset",
        external_creative_id=f"meta_{ad_id}",
        external_name=f"Synthetic {entry['variant_id']}",
        status="ACTIVE",
        metadata={
            "synthetic": True,
            "artifact_path": entry.get("path"),
            "artifact_sha256": entry.get("artifact_sha256"),
        },
    )


def _observation(
    deployment: DeploymentRecord,
    *,
    impressions: int,
    clicks: int,
    outbound_clicks: int,
    spend: float,
    purchases: int,
    purchase_value: float,
) -> PerformanceObservation:
    return PerformanceObservation(
        id=observation_id_for(
            deployment.id,
            START,
            END,
            action_report_time=ACTION_REPORT_TIME,
        ),
        deployment_id=deployment.id,
        campaign_id=deployment.campaign_id,
        creative_id=deployment.creative_id,
        variant_id=deployment.variant_id,
        platform="meta",
        account_id=deployment.account_id,
        external_ad_id=deployment.external_ad_id,
        period_start=START,
        period_end=END,
        currency="USD",
        action_report_time=ACTION_REPORT_TIME,
        metrics=PerformanceMetrics(
            impressions=impressions,
            reach=int(impressions * 0.84),
            clicks=clicks,
            outbound_clicks=float(outbound_clicks),
            spend=spend,
            actions={"purchase": float(purchases)},
            action_values={"purchase": purchase_value},
            video={},
        ),
        source_api_version="synthetic-demo-v1",
        raw={"synthetic": True},
    )


def build(output_dir: Path) -> dict[str, object]:
    brief = AdBrief(
        product="Northstar 2 portable power station",
        value_prop="Quiet, modular backup power that can scale as needs grow.",
        audience="Homeowners preparing for short outages.",
        angles=["plain benefit", "contrarian outage hook"],
        tone="practical, calm, capable",
        cta="See the backup setup",
        formats=["meta_feed_4x5"],
        variants=2,
        pool_size=2,
        output_dir=str(output_dir),
    )
    root = init_campaign_dir(brief)

    control_path = _write_creative(
        root,
        "v01",
        _svg(
            "Quiet backup power",
            "Modular energy for the outages you actually plan for.",
            "#D97706",
        ),
    )
    treatment_path = _write_creative(
        root,
        "v02",
        _svg(
            "Your backup power should not wake the neighborhood",
            "Quiet, modular energy without a gasoline generator.",
            "#B45309",
        ),
    )

    write_manifest(
        brief,
        entries=[
            {
                "variant_id": "v01",
                "format": "meta_feed_4x5",
                "path": control_path,
                "score": 0.72,
            },
            {
                "variant_id": "v02",
                "format": "meta_feed_4x5",
                "path": treatment_path,
                "score": 0.74,
            },
        ],
        cost_usd=0.0,
        models={"text": {"provider": "synthetic", "model": "fixture-v1"}},
    )

    manifest = ensure_manifest_identity(root)
    campaign_id = str(manifest["campaign_id"])
    control = find_creative_entry(root, variant_id="v01")
    treatment = find_creative_entry(root, variant_id="v02")

    control_deployment = _deployment(campaign_id, control, "demo_ad_control")
    treatment_deployment = _deployment(campaign_id, treatment, "demo_ad_treatment")
    upsert_deployment(root, control_deployment)
    upsert_deployment(root, treatment_deployment)

    upsert_observations(
        root,
        [
            _observation(
                control_deployment,
                impressions=5000,
                clicks=250,
                outbound_clicks=210,
                spend=300.0,
                purchases=20,
                purchase_value=900.0,
            ),
            _observation(
                treatment_deployment,
                impressions=5000,
                clicks=400,
                outbound_clicks=350,
                spend=330.0,
                purchases=34,
                purchase_value=1530.0,
            ),
        ],
    )

    created = ExperimentApplication().create(
        str(root),
        name="Contrarian hook CTR test",
        hypothesis="A contrarian outage hook increases click-through rate.",
        changed_factor="hook",
        control_variant_id="v01",
        treatment_variant_id="v02",
        control_value="plain benefit",
        treatment_value="contrarian neighborhood hook",
        primary_metric="ctr",
        expected_direction="higher",
        design="controlled_single_factor",
    )
    if not created.get("ok"):
        raise RuntimeError(f"Could not create demo experiment: {created}")

    experiment = dict(created["experiment"])
    return {
        "campaign_dir": str(root.resolve()),
        "campaign_id": campaign_id,
        "control_creative_id": control["creative_id"],
        "treatment_creative_id": treatment["creative_id"],
        "experiment_id": experiment["id"],
        "window": {
            "since": START.isoformat(),
            "until": END.isoformat(),
            "action_report_time": ACTION_REPORT_TIME,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default="./adclip_performance_demo",
        help="Demo campaign directory (default: ./adclip_performance_demo)",
    )
    args = parser.parse_args()
    result = build(Path(args.output_dir))
    print(json.dumps(result, indent=2))
    print("\nNext commands:")
    print(
        "adclip performance report {dir} --since {since} --until {until} "
        "--action-report-time conversion".format(
            dir=result["campaign_dir"],
            since=START.isoformat(),
            until=END.isoformat(),
        )
    )
    print(
        "adclip performance experiment-evaluate {dir} --experiment-id {exp} "
        "--since {since} --until {until}".format(
            dir=result["campaign_dir"],
            exp=result["experiment_id"],
            since=START.isoformat(),
            until=END.isoformat(),
        )
    )
    print(
        "adclip performance next-test {dir} --experiment-id {exp} "
        "--since {since} --until {until}".format(
            dir=result["campaign_dir"],
            exp=result["experiment_id"],
            since=START.isoformat(),
            until=END.isoformat(),
        )
    )


if __name__ == "__main__":
    main()
