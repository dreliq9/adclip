from datetime import date
from pathlib import Path

from adclip.application.experiment_services import ExperimentApplication
from adclip.campaign import init_campaign_dir, write_manifest
from adclip.performance.schema import PerformanceMetrics, PerformanceObservation
from adclip.performance.store import upsert_observations
from adclip.schema import AdBrief


def _campaign(tmp_path):
    brief = AdBrief(
        product="X",
        value_prop="Y",
        audience="Z",
        angles=["a"],
        tone="t",
        cta="c",
        formats=["meta_feed_4x5"],
        output_dir=str(tmp_path / "campaign"),
    )
    root = init_campaign_dir(brief)
    for variant, payload in (("v01", b"control"), ("v02", b"treatment")):
        directory = root / "variants" / variant
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "meta_feed_4x5.png").write_bytes(payload)
    write_manifest(
        brief,
        entries=[
            {
                "variant_id": "v01",
                "format": "meta_feed_4x5",
                "path": "variants/v01/meta_feed_4x5.png",
            },
            {
                "variant_id": "v02",
                "format": "meta_feed_4x5",
                "path": "variants/v02/meta_feed_4x5.png",
            },
        ],
        cost_usd=0.0,
    )
    return root


def test_create_evaluate_and_recommend(tmp_path):
    root = _campaign(tmp_path)
    app = ExperimentApplication()
    created = app.create(
        str(root),
        name="Hook test",
        hypothesis="Contrarian hook improves CTR",
        changed_factor="hook",
        control_variant_id="v01",
        treatment_variant_id="v02",
        control_value="plain",
        treatment_value="contrarian",
        primary_metric="ctr",
        min_denominator_per_arm=1000,
        min_events_per_arm=20,
    )
    assert created["ok"] is True
    experiment = created["experiment"]
    assert experiment["control"]["artifact_sha256"]
    assert experiment["control"]["creative_id"] != experiment["treatment"]["creative_id"]

    observations = []
    for arm, impressions, clicks in (
        (experiment["control"], 2000, 100),
        (experiment["treatment"], 2000, 180),
    ):
        observations.append(
            PerformanceObservation(
                id="obs_" + arm["creative_id"],
                deployment_id="dep_" + arm["creative_id"],
                campaign_id=experiment["campaign_id"],
                creative_id=arm["creative_id"],
                variant_id=arm["variant_id"],
                platform="meta",
                account_id="act_1",
                external_ad_id="ad_" + arm["variant_id"],
                period_start=date(2026, 8, 1),
                period_end=date(2026, 8, 7),
                metrics=PerformanceMetrics(
                    impressions=impressions,
                    clicks=clicks,
                    spend=100,
                ),
            )
        )
    upsert_observations(root, observations)

    evaluated = app.evaluate(
        str(root),
        experiment_id=experiment["id"],
        since="2026-08-01",
        until="2026-08-07",
    )
    assert evaluated["ok"] is True
    assert evaluated["evaluation"]["verdict"] == "supported"

    next_test = app.next_test(
        str(root),
        experiment_id=experiment["id"],
        since="2026-08-01",
        until="2026-08-07",
    )
    assert next_test["next_test"]["action"] == "replicate_supported_factor"


def test_controlled_experiment_rejects_format_mismatch(tmp_path):
    root = _campaign(tmp_path)
    manifest_path = root / "manifest.json"
    import json
    manifest = json.loads(manifest_path.read_text())
    manifest["entries"][1]["format"] = "google_display_square"
    manifest_path.write_text(json.dumps(manifest))
    result = ExperimentApplication().create(
        str(root),
        name="Bad test",
        hypothesis="Different formats",
        changed_factor="hook",
        control_variant_id="v01",
        treatment_variant_id="v02",
        control_value="a",
        treatment_value="b",
    )
    assert result["ok"] is False
    assert "matching formats" in result["error"]
