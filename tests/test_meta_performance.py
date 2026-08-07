import json
from datetime import date

import pytest

from adclip.connectors.meta_performance import (
    MetaPerformanceClient,
    normalize_meta_insight,
)
from adclip.performance.schema import DeploymentRecord
from adclip.runtime import RuntimeMode, RuntimePolicy


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def _deployment():
    return DeploymentRecord(
        id="dep_1",
        campaign_id="cmp_1",
        creative_id="crv_1",
        variant_id="v01",
        platform="meta",
        account_id="act_123",
        external_ad_id="456",
    )


def test_meta_client_uses_get_and_bearer_auth(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["method"] = request.get_method()
        captured["auth"] = request.get_header("Authorization")
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return _Response({"data": [{"ad_id": "456", "impressions": "100"}]})

    monkeypatch.setattr("adclip.connectors.meta_performance.urlopen", fake_urlopen)
    client = MetaPerformanceClient(
        access_token="secret",
        api_version="v24.0",
        timeout=9,
    )
    rows = client.get_ad_insights(
        "456",
        since=date(2026, 8, 1),
        until=date(2026, 8, 7),
    )
    assert rows[0]["impressions"] == "100"
    assert captured["method"] == "GET"
    assert captured["auth"] == "Bearer secret"
    assert "/v24.0/456/insights?" in captured["url"]
    assert "time_range=" in captured["url"]
    assert captured["timeout"] == 9


def test_normalize_meta_actions_and_video():
    observation = normalize_meta_insight(
        {
            "date_start": "2026-08-01",
            "date_stop": "2026-08-07",
            "account_currency": "USD",
            "impressions": "1000",
            "reach": "800",
            "clicks": "40",
            "spend": "80.50",
            "outbound_clicks": [{"action_type": "outbound_click", "value": "31"}],
            "actions": [
                {"action_type": "link_click", "value": "40"},
                {"action_type": "purchase", "value": "4"},
            ],
            "action_values": [{"action_type": "purchase", "value": "220"}],
            "video_thruplay_watched_actions": [
                {"action_type": "video_view", "value": "90"}
            ],
        },
        _deployment(),
        requested_start=date(2026, 8, 1),
        requested_end=date(2026, 8, 7),
        api_version="v24.0",
    )
    assert observation.metrics.impressions == 1000
    assert observation.metrics.outbound_clicks == 31
    assert observation.metrics.actions["purchase"] == 4
    assert observation.metrics.action_values["purchase"] == 220
    assert observation.metrics.video["thruplay"] == 90
    assert observation.currency == "USD"


def test_meta_connector_is_blocked_offline(monkeypatch):
    monkeypatch.setenv("ADCLIP_META_ACCESS_TOKEN", "secret")
    with pytest.raises(RuntimeError, match="requires network access"):
        MetaPerformanceClient.from_env(
            RuntimePolicy(mode=RuntimeMode.OFFLINE)
        )
