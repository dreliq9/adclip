import json
from datetime import date
from pathlib import Path

from adclip.campaign import (
    CAMPAIGN_STATE_FILENAME,
    ensure_campaign_state,
    ensure_manifest_identity,
    init_campaign_dir,
    write_manifest,
)
from adclip.performance.identity import deployment_id_for, observation_id_for
from adclip.performance.schema import (
    DeploymentRecord,
    PerformanceMetrics,
    PerformanceObservation,
)
from adclip.performance.store import (
    find_creative_entry,
    load_deployments,
    load_observations,
    upsert_deployment,
    upsert_observations,
)
from adclip.schema import AdBrief


def _brief(tmp_path):
    return AdBrief(
        product="X",
        value_prop="Y",
        audience="Z",
        angles=["a"],
        tone="t",
        cta="c",
        formats=["meta_feed_4x5"],
        output_dir=str(tmp_path / "campaign"),
    )


def _artifact(brief, content=b"creative-a"):
    path = Path(brief.output_dir) / "variants" / "v01" / "meta_feed_4x5.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_campaign_and_creative_identity_are_stable(tmp_path):
    brief = _brief(tmp_path)
    init_campaign_dir(brief)
    _artifact(brief)
    first = ensure_campaign_state(brief.output_dir)
    second = ensure_campaign_state(brief.output_dir)
    assert first["campaign_id"] == second["campaign_id"]

    write_manifest(
        brief,
        entries=[{
            "variant_id": "v01",
            "format": "meta_feed_4x5",
            "path": "variants/v01/meta_feed_4x5.png",
        }],
        cost_usd=0.0,
    )
    manifest = ensure_manifest_identity(brief.output_dir)
    assert manifest["campaign_id"] == first["campaign_id"]
    assert manifest["entries"][0]["creative_id"].startswith("crv_")
    assert len(manifest["entries"][0]["artifact_sha256"]) == 64
    assert ensure_manifest_identity(brief.output_dir) == manifest


def test_creative_identity_changes_when_rendered_artifact_changes(tmp_path):
    brief = _brief(tmp_path)
    init_campaign_dir(brief)
    artifact = _artifact(brief, b"creative-a")
    write_manifest(
        brief,
        entries=[{
            "variant_id": "v01",
            "format": "meta_feed_4x5",
            "path": "variants/v01/meta_feed_4x5.png",
        }],
        cost_usd=0.0,
    )
    before = ensure_manifest_identity(brief.output_dir)
    before_entry = dict(before["entries"][0])

    artifact.write_bytes(b"creative-b")
    after = ensure_manifest_identity(brief.output_dir)
    after_entry = after["entries"][0]
    assert after_entry["artifact_sha256"] != before_entry["artifact_sha256"]
    assert after_entry["creative_id"] != before_entry["creative_id"]


def test_portable_manifest_restores_missing_local_state(tmp_path):
    brief = _brief(tmp_path)
    init_campaign_dir(brief)
    _artifact(brief)
    write_manifest(
        brief,
        entries=[{
            "variant_id": "v01",
            "format": "meta_feed_4x5",
            "path": "variants/v01/meta_feed_4x5.png",
        }],
        cost_usd=0.0,
    )
    original = ensure_manifest_identity(brief.output_dir)
    root = Path(brief.output_dir)
    (root / CAMPAIGN_STATE_FILENAME).unlink()

    restored = ensure_manifest_identity(root)
    state = ensure_campaign_state(root)
    assert restored["campaign_id"] == original["campaign_id"]
    assert state["campaign_id"] == original["campaign_id"]
    assert restored["entries"][0]["creative_id"] == original["entries"][0]["creative_id"]


def test_deployment_and_observation_upsert(tmp_path):
    brief = _brief(tmp_path)
    init_campaign_dir(brief)
    _artifact(brief)
    write_manifest(
        brief,
        entries=[{
            "variant_id": "v01",
            "format": "meta_feed_4x5",
            "path": "variants/v01/meta_feed_4x5.png",
        }],
        cost_usd=0.0,
    )
    manifest = ensure_manifest_identity(brief.output_dir)
    creative = find_creative_entry(brief.output_dir, variant_id="v01")
    deployment_id = deployment_id_for("meta", "act_123", "ad_456")
    deployment = DeploymentRecord(
        id=deployment_id,
        campaign_id=manifest["campaign_id"],
        creative_id=creative["creative_id"],
        variant_id="v01",
        format=creative["format"],
        platform="meta",
        account_id="act_123",
        external_ad_id="ad_456",
    )
    upsert_deployment(brief.output_dir, deployment)
    assert load_deployments(brief.output_dir) == [deployment]

    obs_id = observation_id_for(
        deployment_id,
        date(2026, 8, 1),
        date(2026, 8, 7),
        action_report_time="conversion",
    )
    observation = PerformanceObservation(
        id=obs_id,
        deployment_id=deployment_id,
        campaign_id=manifest["campaign_id"],
        creative_id=creative["creative_id"],
        variant_id="v01",
        platform="meta",
        account_id="act_123",
        external_ad_id="ad_456",
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 7),
        metrics=PerformanceMetrics(impressions=1000, clicks=25, spend=50.0),
    )
    upsert_observations(brief.output_dir, [observation])
    updated = observation.model_copy(
        update={"metrics": PerformanceMetrics(impressions=1100, clicks=30, spend=55.0)}
    )
    upsert_observations(brief.output_dir, [updated])
    loaded = load_observations(brief.output_dir)
    assert len(loaded) == 1
    assert loaded[0].metrics.impressions == 1100

    payload = json.loads(
        (Path(brief.output_dir) / "performance" / "observations.json").read_text()
    )
    assert payload["campaign_id"] == manifest["campaign_id"]
