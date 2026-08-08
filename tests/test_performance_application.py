from datetime import date
from pathlib import Path

from adclip.application.performance_services import PerformanceApplication
from adclip.campaign import init_campaign_dir, write_manifest
from adclip.connectors.meta_performance import MetaPerformanceClient
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
    init_campaign_dir(brief)
    entries = []
    for variant_id, payload in (("v01", b"exact creative bytes"), ("v02", b"other creative bytes")):
        artifact = (
            Path(brief.output_dir)
            / "variants"
            / variant_id
            / "meta_feed_4x5.png"
        )
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_bytes(payload)
        entries.append({
            "variant_id": variant_id,
            "format": "meta_feed_4x5",
            "path": f"variants/{variant_id}/meta_feed_4x5.png",
        })
    write_manifest(brief, entries=entries, cost_usd=0.0)
    return brief.output_dir


class _FakeMeta:
    api_version = "v24.0"

    def get_ad(self, ad_id):
        return {
            "id": ad_id,
            "name": "Test ad",
            "account_id": "123",
            "campaign_id": "camp_1",
            "adset_id": "set_1",
            "effective_status": "ACTIVE",
            "creative": {"id": "meta_creative_1"},
        }

    def get_ad_insights(self, ad_id, *, since, until, action_report_time):
        assert ad_id == "456"
        assert since == date(2026, 8, 1)
        assert until == date(2026, 8, 7)
        return [{
            "date_start": "2026-08-01",
            "date_stop": "2026-08-07",
            "account_currency": "USD",
            "impressions": "2000",
            "clicks": "100",
            "spend": "150",
            "outbound_clicks": [{"action_type": "outbound_click", "value": "80"}],
            "actions": [{"action_type": "purchase", "value": "10"}],
            "action_values": [{"action_type": "purchase", "value": "600"}],
        }]


class _WrongAdMeta(_FakeMeta):
    def get_ad(self, ad_id):
        payload = super().get_ad(ad_id)
        payload["id"] = "different-ad"
        return payload


def test_link_sync_report_and_compare(tmp_path, monkeypatch):
    campaign_dir = _campaign(tmp_path)
    app = PerformanceApplication()
    linked = app.link_meta(
        campaign_dir,
        variant_id="v01",
        account_id="123",
        ad_id="456",
    )
    assert linked["ok"] is True
    assert linked["deployment"]["account_id"] == "act_123"
    assert linked["deployment"]["creative_id"].startswith("crv_")
    assert len(linked["deployment"]["metadata"]["artifact_sha256"]) == 64

    monkeypatch.setattr(
        MetaPerformanceClient,
        "from_env",
        classmethod(lambda cls, policy=None: _FakeMeta()),
    )
    synced = app.sync_meta(
        campaign_dir,
        since="2026-08-01",
        until="2026-08-07",
    )
    assert synced["ok"] is True
    assert synced["read_only"] is True
    assert synced["observation_count"] == 1
    assert synced["window"]["action_report_time"] == "conversion"
    assert synced["summary"][0]["derived"]["ctr"] == 0.05
    assert synced["summary"][0]["derived"]["roas"]["purchase"] == 4.0

    report = app.report(campaign_dir)
    assert report["ok"] is True
    assert report["selected_window"] == {
        "since": "2026-08-01",
        "until": "2026-08-07",
        "action_report_time": "conversion",
    }

    comparison = app.compare(
        campaign_dir,
        since="2026-08-01",
        until="2026-08-07",
        metric="roas",
        action_type="purchase",
    )
    assert comparison["ok"] is True
    assert comparison["causal_claim"] is False
    assert comparison["action_report_time"] == "conversion"
    assert comparison["rows"][0]["value"] == 4.0


def test_sync_requires_explicit_lineage(tmp_path):
    campaign_dir = _campaign(tmp_path)
    result = PerformanceApplication().sync_meta(
        campaign_dir,
        since="2026-08-01",
        until="2026-08-07",
    )
    assert result["ok"] is False
    assert "No linked Meta deployments" in result["error"]


def test_same_meta_ad_cannot_be_silently_relinked_to_another_creative(tmp_path):
    campaign_dir = _campaign(tmp_path)
    app = PerformanceApplication()
    first = app.link_meta(
        campaign_dir,
        variant_id="v01",
        account_id="123",
        ad_id="456",
    )
    assert first["ok"] is True
    second = app.link_meta(
        campaign_dir,
        variant_id="v02",
        account_id="act_123",
        ad_id="456",
    )
    assert second["ok"] is False
    assert "already linked to creative" in second["error"]


def test_sync_rejects_meta_response_for_different_ad_id(tmp_path, monkeypatch):
    campaign_dir = _campaign(tmp_path)
    app = PerformanceApplication()
    assert app.link_meta(
        campaign_dir,
        variant_id="v01",
        account_id="123",
        ad_id="456",
    )["ok"] is True
    monkeypatch.setattr(
        MetaPerformanceClient,
        "from_env",
        classmethod(lambda cls, policy=None: _WrongAdMeta()),
    )
    result = app.sync_meta(
        campaign_dir,
        since="2026-08-01",
        until="2026-08-07",
    )
    assert result["ok"] is False
    assert result["observation_count"] == 0
    assert "returned ad id" in result["errors"][0]["error"]
