"""Read-only Meta Marketing API performance connector.

Only GET requests are implemented. The connector intentionally operates on
explicitly linked ad IDs rather than discovering or mutating an ad account.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from adclip.performance.identity import observation_id_for
from adclip.performance.schema import (
    DeploymentRecord,
    PerformanceMetrics,
    PerformanceObservation,
)
from adclip.runtime import ProviderRequirements, RuntimePolicy


DEFAULT_META_API_VERSION = "v24.0"
DEFAULT_META_BASE_URL = "https://graph.facebook.com"
META_PERFORMANCE_PROVIDER = "meta-performance"

INSIGHT_FIELDS: tuple[str, ...] = (
    "ad_id",
    "account_currency",
    "clicks",
    "impressions",
    "reach",
    "spend",
    "outbound_clicks",
    "actions",
    "action_values",
    "video_thruplay_watched_actions",
    "video_p25_watched_actions",
    "video_p50_watched_actions",
    "video_p75_watched_actions",
    "video_p95_watched_actions",
    "video_p100_watched_actions",
)


def _number(value: object, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _integer(value: object, default: int = 0) -> int:
    try:
        return int(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _action_map(value: object) -> dict[str, float]:
    output: dict[str, float] = {}
    if isinstance(value, dict):
        for key, raw in value.items():
            output[str(key)] = output.get(str(key), 0.0) + _number(raw)
        return output
    if not isinstance(value, list):
        return output
    for row in value:
        if not isinstance(row, dict):
            continue
        action_type = row.get("action_type")
        if not isinstance(action_type, str) or not action_type:
            continue
        output[action_type] = output.get(action_type, 0.0) + _number(row.get("value"))
    return output


def _action_total(value: object) -> float:
    return sum(_action_map(value).values())


def _date_value(value: object, fallback: date) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    return fallback


class MetaPerformanceClient:
    """Minimal bearer-authenticated read client for Meta ads and insights."""

    def __init__(
        self,
        *,
        access_token: str,
        api_version: str = DEFAULT_META_API_VERSION,
        base_url: str = DEFAULT_META_BASE_URL,
        timeout: float = 30.0,
    ) -> None:
        if not access_token.strip():
            raise ValueError("Meta access token must not be empty")
        version = api_version.strip()
        if not version.startswith("v"):
            version = f"v{version}"
        self.access_token = access_token.strip()
        self.api_version = version
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @classmethod
    def from_env(
        cls,
        policy: RuntimePolicy | None = None,
    ) -> MetaPerformanceClient:
        active_policy = policy or RuntimePolicy.from_env()
        active_policy.check_provider(
            META_PERFORMANCE_PROVIDER,
            ProviderRequirements(network=True),
        )
        token = (
            os.environ.get("ADCLIP_META_ACCESS_TOKEN")
            or os.environ.get("META_ACCESS_TOKEN")
        )
        if not token:
            raise RuntimeError(
                "Meta performance sync requires ADCLIP_META_ACCESS_TOKEN "
                "(or META_ACCESS_TOKEN). The token is used only for read calls."
            )
        return cls(
            access_token=token,
            api_version=os.environ.get(
                "ADCLIP_META_API_VERSION",
                DEFAULT_META_API_VERSION,
            ),
            base_url=os.environ.get("ADCLIP_META_BASE_URL", DEFAULT_META_BASE_URL),
            timeout=float(os.environ.get("ADCLIP_META_TIMEOUT", "30")),
        )

    def _url(self, path: str, params: dict[str, object] | None = None) -> str:
        clean_path = path.lstrip("/")
        url = f"{self.base_url}/{self.api_version}/{clean_path}"
        query = urlencode(
            {key: value for key, value in (params or {}).items() if value is not None}
        )
        return f"{url}?{query}" if query else url

    def _get_json(
        self,
        path: str,
        params: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        request = Request(
            self._url(path, params),
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Accept": "application/json",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise RuntimeError(
                f"Meta Marketing API returned HTTP {exc.code}: {detail}"
            ) from exc
        except URLError as exc:
            raise RuntimeError(
                f"Meta Marketing API request failed: {exc.reason}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("Meta Marketing API returned invalid JSON") from exc

        if not isinstance(payload, dict):
            raise RuntimeError("Meta Marketing API returned a non-object response")
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message") or "unknown Meta API error"
            code = error.get("code")
            raise RuntimeError(f"Meta Marketing API error {code}: {message}")
        return payload

    def _get_collection(
        self,
        path: str,
        params: dict[str, object],
        *,
        max_pages: int = 100,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        current = dict(params)
        seen_after: set[str] = set()
        for _ in range(max_pages):
            payload = self._get_json(path, current)
            data = payload.get("data", [])
            if not isinstance(data, list):
                raise RuntimeError("Meta collection response did not contain data[]")
            rows.extend(row for row in data if isinstance(row, dict))

            paging = payload.get("paging", {})
            cursors = paging.get("cursors", {}) if isinstance(paging, dict) else {}
            after = cursors.get("after") if isinstance(cursors, dict) else None
            next_url = paging.get("next") if isinstance(paging, dict) else None
            if not next_url or not isinstance(after, str) or after in seen_after:
                break
            seen_after.add(after)
            current["after"] = after
        return rows

    def get_ad(self, ad_id: str) -> dict[str, Any]:
        return self._get_json(
            ad_id,
            {
                "fields": (
                    "id,name,account_id,campaign_id,adset_id,effective_status,"
                    "creative{id,name}"
                )
            },
        )

    def get_ad_insights(
        self,
        ad_id: str,
        *,
        since: date,
        until: date,
        action_report_time: str = "conversion",
    ) -> list[dict[str, Any]]:
        return self._get_collection(
            f"{ad_id}/insights",
            {
                "fields": ",".join(INSIGHT_FIELDS),
                "time_range": json.dumps(
                    {"since": since.isoformat(), "until": until.isoformat()},
                    separators=(",", ":"),
                ),
                "action_report_time": action_report_time,
                "limit": 500,
            },
        )


def normalize_meta_insight(
    row: dict[str, Any],
    deployment: DeploymentRecord,
    *,
    requested_start: date,
    requested_end: date,
    api_version: str,
    action_report_time: str = "conversion",
    fetched_at: datetime | None = None,
) -> PerformanceObservation:
    start = _date_value(row.get("date_start"), requested_start)
    end = _date_value(row.get("date_stop"), requested_end)
    actions = _action_map(row.get("actions"))
    action_values = _action_map(row.get("action_values"))
    video = {
        "thruplay": _action_total(row.get("video_thruplay_watched_actions")),
        "p25": _action_total(row.get("video_p25_watched_actions")),
        "p50": _action_total(row.get("video_p50_watched_actions")),
        "p75": _action_total(row.get("video_p75_watched_actions")),
        "p95": _action_total(row.get("video_p95_watched_actions")),
        "p100": _action_total(row.get("video_p100_watched_actions")),
    }
    observation_id = observation_id_for(
        deployment.id,
        start,
        end,
        action_report_time=action_report_time,
    )
    return PerformanceObservation(
        id=observation_id,
        deployment_id=deployment.id,
        campaign_id=deployment.campaign_id,
        creative_id=deployment.creative_id,
        variant_id=deployment.variant_id,
        platform="meta",
        account_id=deployment.account_id,
        external_ad_id=deployment.external_ad_id,
        period_start=start,
        period_end=end,
        currency=(str(row["account_currency"]) if row.get("account_currency") else None),
        action_report_time=action_report_time,
        metrics=PerformanceMetrics(
            impressions=_integer(row.get("impressions")),
            reach=(
                _integer(row.get("reach"))
                if row.get("reach") not in {None, ""}
                else None
            ),
            clicks=_integer(row.get("clicks")),
            outbound_clicks=_action_total(row.get("outbound_clicks")),
            spend=_number(row.get("spend")),
            actions=actions,
            action_values=action_values,
            video=video,
        ),
        source_api_version=api_version,
        fetched_at=fetched_at or datetime.now(timezone.utc),
        raw=dict(row),
    )
