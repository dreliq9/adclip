"""Descriptive creative-performance summaries without causal overclaiming."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from adclip.performance.schema import PerformanceObservation


def _ratio(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def _merge_metric_map(target: dict[str, float], source: dict[str, float]) -> None:
    for key, value in source.items():
        target[key] = target.get(key, 0.0) + float(value)


def available_windows(
    observations: list[PerformanceObservation],
) -> list[tuple[date, date]]:
    return sorted(
        {(item.period_start, item.period_end) for item in observations},
        key=lambda window: (window[1], window[0]),
    )


def select_window(
    observations: list[PerformanceObservation],
    *,
    since: date | None = None,
    until: date | None = None,
) -> tuple[list[PerformanceObservation], tuple[date, date] | None]:
    if bool(since) != bool(until):
        raise ValueError("since and until must be provided together")
    if since is not None and until is not None:
        selected = [
            item
            for item in observations
            if item.period_start == since and item.period_end == until
        ]
        return selected, (since, until)
    windows = available_windows(observations)
    if not windows:
        return [], None
    latest = windows[-1]
    return [
        item
        for item in observations
        if (item.period_start, item.period_end) == latest
    ], latest


def summarize_observations(
    observations: list[PerformanceObservation],
) -> list[dict[str, object]]:
    grouped: dict[str, list[PerformanceObservation]] = defaultdict(list)
    for observation in observations:
        grouped[observation.creative_id].append(observation)

    summaries: list[dict[str, object]] = []
    for creative_id, rows in sorted(grouped.items()):
        impressions = sum(item.metrics.impressions for item in rows)
        clicks = sum(item.metrics.clicks for item in rows)
        outbound_clicks = sum(item.metrics.outbound_clicks for item in rows)
        spend = sum(item.metrics.spend for item in rows)
        actions: dict[str, float] = {}
        action_values: dict[str, float] = {}
        video: dict[str, float] = {}
        reach_values = [
            item.metrics.reach
            for item in rows
            if item.metrics.reach is not None
        ]
        for item in rows:
            _merge_metric_map(actions, item.metrics.actions)
            _merge_metric_map(action_values, item.metrics.action_values)
            _merge_metric_map(video, item.metrics.video)

        action_rates = {
            key: _ratio(value, float(impressions))
            for key, value in sorted(actions.items())
        }
        cost_per_action = {
            key: _ratio(spend, value)
            for key, value in sorted(actions.items())
        }
        roas = {
            key: _ratio(value, spend)
            for key, value in sorted(action_values.items())
        }
        summaries.append(
            {
                "creative_id": creative_id,
                "variant_id": rows[0].variant_id,
                "platform": rows[0].platform,
                "deployment_count": len({item.deployment_id for item in rows}),
                "observation_count": len(rows),
                "impressions": impressions,
                "clicks": clicks,
                "outbound_clicks": round(outbound_clicks, 6),
                "spend": round(spend, 6),
                "reported_reach_sum": (
                    sum(reach_values) if reach_values else None
                ),
                "reach_is_additive": False,
                "actions": actions,
                "action_values": action_values,
                "video": video,
                "derived": {
                    "ctr": _ratio(float(clicks), float(impressions)),
                    "outbound_ctr": _ratio(outbound_clicks, float(impressions)),
                    "cpc": _ratio(spend, float(clicks)),
                    "cpm": (
                        _ratio(spend * 1000.0, float(impressions))
                        if impressions
                        else None
                    ),
                    "action_rates": action_rates,
                    "cost_per_action": cost_per_action,
                    "roas": roas,
                },
            }
        )
    return summaries


def compare_observations(
    observations: list[PerformanceObservation],
    *,
    metric: str,
    action_type: str | None = None,
) -> dict[str, object]:
    supported = {
        "ctr",
        "outbound_ctr",
        "cpc",
        "cpm",
        "impressions",
        "clicks",
        "action_rate",
        "cost_per_action",
        "roas",
    }
    if metric not in supported:
        raise ValueError(f"Unsupported comparison metric {metric!r}")
    if metric in {"action_rate", "cost_per_action", "roas"} and not action_type:
        raise ValueError(f"metric {metric!r} requires action_type")

    summaries = summarize_observations(observations)
    rows: list[dict[str, object]] = []
    for summary in summaries:
        derived = summary["derived"]
        assert isinstance(derived, dict)
        if metric in {"impressions", "clicks"}:
            value = summary[metric]
        elif metric in {"ctr", "outbound_ctr", "cpc", "cpm"}:
            value = derived.get(metric)
        elif metric == "action_rate":
            value = dict(derived.get("action_rates", {})).get(action_type)
        elif metric == "cost_per_action":
            value = dict(derived.get("cost_per_action", {})).get(action_type)
        else:
            value = dict(derived.get("roas", {})).get(action_type)
        rows.append(
            {
                "creative_id": summary["creative_id"],
                "variant_id": summary["variant_id"],
                "value": value,
                "impressions": summary["impressions"],
                "clicks": summary["clicks"],
                "spend": summary["spend"],
            }
        )

    lower_is_better = metric in {"cpc", "cpm", "cost_per_action"}
    comparable = [row for row in rows if row["value"] is not None]
    incomparable = [row for row in rows if row["value"] is None]
    comparable.sort(
        key=lambda row: float(row["value"]),
        reverse=not lower_is_better,
    )
    ranked = comparable + incomparable
    for index, row in enumerate(ranked, start=1):
        row["rank"] = index if row["value"] is not None else None

    return {
        "metric": metric,
        "action_type": action_type,
        "direction": "lower_is_better" if lower_is_better else "higher_is_better",
        "descriptive_only": True,
        "causal_claim": False,
        "rows": ranked,
    }
