"""Explicit creative experiments, evidence thresholds, and next-test guidance.

This layer separates declared hypotheses from observed platform performance.
Rate metrics can receive confidence intervals when their aggregate
numerators/denominators are suitable. Value metrics such as ROAS and CPA stay
descriptive until richer variance or event-level evidence exists.
"""

from __future__ import annotations

import json
import math
import uuid
from datetime import date, datetime
from pathlib import Path
from statistics import NormalDist
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from adclip.performance.schema import PerformanceObservation, utc_now
from adclip.performance.store import (
    campaign_manifest,
    find_creative_entry,
    performance_dir,
)


ExperimentMetric = Literal[
    "ctr",
    "outbound_ctr",
    "action_rate",
    "cost_per_action",
    "roas",
]
ExpectedDirection = Literal["higher", "lower"]
ExperimentDesign = Literal["controlled_single_factor", "observational_comparison"]
ExperimentStatus = Literal["draft", "running", "completed", "archived"]
ExperimentVerdict = Literal["supported", "contradicted", "inconclusive"]

EXPERIMENT_SCHEMA_VERSION = "experiments-v1"
INFERENTIAL_RATE_METRICS = {"ctr", "outbound_ctr", "action_rate"}


class EvidenceThresholds(BaseModel):
    """Minimum evidence before an inferential rate verdict is allowed."""

    min_denominator_per_arm: int = Field(default=1000, ge=1)
    min_events_per_arm: int = Field(default=20, ge=1)
    confidence_level: float = Field(default=0.95, gt=0.5, lt=0.999)


class ExperimentArm(BaseModel):
    role: Literal["control", "treatment"]
    creative_id: str = Field(min_length=1)
    variant_id: str = Field(min_length=1)
    format: str | None = None
    artifact_path: str | None = None
    artifact_sha256: str | None = None
    factor_value: str = Field(min_length=1)


class ExperimentRecord(BaseModel):
    """A declared single-factor or observational creative comparison."""

    id: str = Field(min_length=1, pattern=r"^exp_[a-f0-9]{32}$")
    campaign_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    hypothesis: str = Field(min_length=1)
    changed_factor: str = Field(min_length=1)
    control: ExperimentArm
    treatment: ExperimentArm
    primary_metric: ExperimentMetric = "ctr"
    action_type: str | None = None
    expected_direction: ExpectedDirection = "higher"
    design: ExperimentDesign = "controlled_single_factor"
    thresholds: EvidenceThresholds = Field(default_factory=EvidenceThresholds)
    status: ExperimentStatus = "running"
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_experiment(self) -> "ExperimentRecord":
        if self.control.role != "control" or self.treatment.role != "treatment":
            raise ValueError("experiment arms must preserve control/treatment roles")
        if self.control.creative_id == self.treatment.creative_id:
            raise ValueError("control and treatment must reference different creatives")
        if self.primary_metric in {"action_rate", "cost_per_action", "roas"}:
            if not self.action_type:
                raise ValueError(
                    f"primary_metric {self.primary_metric!r} requires action_type"
                )
        return self


def default_thresholds(metric: ExperimentMetric) -> EvidenceThresholds:
    if metric == "action_rate":
        return EvidenceThresholds(
            min_denominator_per_arm=100,
            min_events_per_arm=10,
        )
    if metric in {"cost_per_action", "roas"}:
        return EvidenceThresholds(
            min_denominator_per_arm=1,
            min_events_per_arm=10,
        )
    return EvidenceThresholds()


def experiment_id_for(
    campaign_id: str,
    *,
    control_creative_id: str,
    treatment_creative_id: str,
    changed_factor: str,
    primary_metric: str,
    action_type: str | None,
    control_factor_value: str | None = None,
    treatment_factor_value: str | None = None,
) -> str:
    """Create a deterministic experiment ID including declared factor values."""

    identity = uuid.uuid5(
        uuid.NAMESPACE_URL,
        ":".join(
            [
                "adclip",
                campaign_id,
                "experiment",
                control_creative_id,
                treatment_creative_id,
                changed_factor,
                control_factor_value or "",
                treatment_factor_value or "",
                primary_metric,
                action_type or "",
            ]
        ),
    )
    return f"exp_{identity.hex}"


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


def experiment_path(campaign_dir: str | Path) -> Path:
    return performance_dir(campaign_dir) / "experiments.json"


def load_experiments(campaign_dir: str | Path) -> list[ExperimentRecord]:
    path = experiment_path(campaign_dir)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(
        payload.get("experiments", []), list
    ):
        raise ValueError(f"{path} must contain an 'experiments' array")
    return [
        ExperimentRecord.model_validate(item) for item in payload["experiments"]
    ]


def write_experiments(
    campaign_dir: str | Path,
    experiments: list[ExperimentRecord],
) -> Path:
    manifest = campaign_manifest(campaign_dir)
    path = experiment_path(campaign_dir)
    _atomic_write_json(
        path,
        {
            "schema_version": EXPERIMENT_SCHEMA_VERSION,
            "campaign_id": manifest["campaign_id"],
            "experiments": [
                experiment.model_dump(mode="json")
                for experiment in sorted(experiments, key=lambda item: item.id)
            ],
        },
    )
    return path


def upsert_experiment(
    campaign_dir: str | Path,
    experiment: ExperimentRecord,
) -> ExperimentRecord:
    current = {item.id: item for item in load_experiments(campaign_dir)}
    prior = current.get(experiment.id)
    if prior is not None:
        prior_factor_values = (
            prior.control.factor_value,
            prior.treatment.factor_value,
        )
        new_factor_values = (
            experiment.control.factor_value,
            experiment.treatment.factor_value,
        )
        if prior_factor_values != new_factor_values:
            raise ValueError(
                "experiment identity collision with different factor values; "
                "refusing to overwrite the earlier experiment"
            )
    current[experiment.id] = experiment
    write_experiments(campaign_dir, list(current.values()))
    return experiment


def get_experiment(campaign_dir: str | Path, experiment_id: str) -> ExperimentRecord:
    matches = [
        item for item in load_experiments(campaign_dir) if item.id == experiment_id
    ]
    if not matches:
        raise ValueError(f"Experiment not found: {experiment_id}")
    return matches[0]


def arm_from_variant(
    campaign_dir: str | Path,
    *,
    variant_id: str,
    role: Literal["control", "treatment"],
    factor_value: str,
) -> ExperimentArm:
    entry = find_creative_entry(campaign_dir, variant_id=variant_id)
    return ExperimentArm(
        role=role,
        creative_id=str(entry["creative_id"]),
        variant_id=variant_id,
        format=(str(entry["format"]) if entry.get("format") else None),
        artifact_path=(str(entry["path"]) if entry.get("path") else None),
        artifact_sha256=(
            str(entry["artifact_sha256"])
            if entry.get("artifact_sha256")
            else None
        ),
        factor_value=factor_value,
    )


def _arm_totals(
    observations: list[PerformanceObservation],
    creative_id: str,
) -> dict[str, object]:
    rows = [item for item in observations if item.creative_id == creative_id]
    actions: dict[str, float] = {}
    values: dict[str, float] = {}
    for item in rows:
        for key, value in item.metrics.actions.items():
            actions[key] = actions.get(key, 0.0) + float(value)
        for key, value in item.metrics.action_values.items():
            values[key] = values.get(key, 0.0) + float(value)
    return {
        "rows": rows,
        "impressions": sum(item.metrics.impressions for item in rows),
        "clicks": sum(item.metrics.clicks for item in rows),
        "outbound_clicks": sum(item.metrics.outbound_clicks for item in rows),
        "spend": sum(item.metrics.spend for item in rows),
        "actions": actions,
        "action_values": values,
        "platforms": sorted({item.platform for item in rows}),
        "action_report_times": sorted({item.action_report_time for item in rows}),
        "currencies": sorted({item.currency for item in rows if item.currency}),
    }


def _rate_inputs(
    totals: dict[str, object],
    metric: ExperimentMetric,
    action_type: str | None,
) -> tuple[float, float]:
    impressions = float(totals["impressions"])
    clicks = float(totals["clicks"])
    if metric == "ctr":
        return clicks, impressions
    if metric == "outbound_ctr":
        return float(totals["outbound_clicks"]), impressions
    if metric == "action_rate":
        actions = dict(totals["actions"])
        return float(actions.get(action_type or "", 0.0)), clicks
    raise ValueError(f"{metric!r} is not an inferential rate metric")


def _point_value(
    totals: dict[str, object],
    metric: ExperimentMetric,
    action_type: str | None,
) -> float | None:
    if metric in INFERENTIAL_RATE_METRICS:
        numerator, denominator = _rate_inputs(totals, metric, action_type)
        return numerator / denominator if denominator > 0 else None
    actions = dict(totals["actions"])
    count = float(actions.get(action_type or "", 0.0))
    spend = float(totals["spend"])
    if metric == "cost_per_action":
        return spend / count if count > 0 else None
    values = dict(totals["action_values"])
    value = float(values.get(action_type or "", 0.0))
    if metric == "roas":
        return value / spend if spend > 0 else None
    return None


def _wilson_interval(
    events: float,
    denominator: float,
    confidence_level: float,
) -> tuple[float, float] | None:
    if denominator <= 0 or events < 0 or events > denominator:
        return None
    proportion = events / denominator
    z = NormalDist().inv_cdf(0.5 + confidence_level / 2.0)
    z2 = z * z
    base = 1.0 + z2 / denominator
    center = (proportion + z2 / (2.0 * denominator)) / base
    radius = (
        z
        * math.sqrt(
            proportion * (1.0 - proportion) / denominator
            + z2 / (4.0 * denominator * denominator)
        )
        / base
    )
    return max(0.0, center - radius), min(1.0, center + radius)


def _minimum_evidence(
    *,
    control_events: float,
    control_denominator: float,
    treatment_events: float,
    treatment_denominator: float,
    thresholds: EvidenceThresholds,
) -> dict[str, object]:
    shortfalls: list[str] = []
    for label, events, denominator in (
        ("control", control_events, control_denominator),
        ("treatment", treatment_events, treatment_denominator),
    ):
        if denominator < thresholds.min_denominator_per_arm:
            shortfalls.append(
                f"{label} denominator {denominator:g} < "
                f"{thresholds.min_denominator_per_arm}"
            )
        if events < thresholds.min_events_per_arm:
            shortfalls.append(
                f"{label} events {events:g} < {thresholds.min_events_per_arm}"
            )
        if events > denominator:
            shortfalls.append(
                f"{label} events {events:g} exceed denominator {denominator:g}; "
                "binomial rate inference is not valid"
            )
    return {"met": not shortfalls, "shortfalls": shortfalls}


def _same_measurement_context(
    control: dict[str, object],
    treatment: dict[str, object],
) -> tuple[bool, list[str]]:
    problems: list[str] = []
    for key in ("platforms", "action_report_times"):
        left = list(control[key])
        right = list(treatment[key])
        if len(left) != 1 or len(right) != 1 or left != right:
            problems.append(f"arms have incompatible {key}: {left} vs {right}")
    return not problems, problems


def _rate_evidence(
    experiment: ExperimentRecord,
    control: dict[str, object],
    treatment: dict[str, object],
) -> tuple[dict[str, object], tuple[float, float] | None]:
    control_events, control_denominator = _rate_inputs(
        control, experiment.primary_metric, experiment.action_type
    )
    treatment_events, treatment_denominator = _rate_inputs(
        treatment, experiment.primary_metric, experiment.action_type
    )
    evidence = _minimum_evidence(
        control_events=control_events,
        control_denominator=control_denominator,
        treatment_events=treatment_events,
        treatment_denominator=treatment_denominator,
        thresholds=experiment.thresholds,
    )
    control_interval = _wilson_interval(
        control_events,
        control_denominator,
        experiment.thresholds.confidence_level,
    )
    treatment_interval = _wilson_interval(
        treatment_events,
        treatment_denominator,
        experiment.thresholds.confidence_level,
    )
    difference_interval = None
    if control_interval and treatment_interval:
        difference_interval = (
            treatment_interval[0] - control_interval[1],
            treatment_interval[1] - control_interval[0],
        )
    evidence.update(
        {
            "control_events": control_events,
            "control_denominator": control_denominator,
            "control_confidence_interval": control_interval,
            "treatment_events": treatment_events,
            "treatment_denominator": treatment_denominator,
            "treatment_confidence_interval": treatment_interval,
        }
    )
    return evidence, difference_interval


def evaluate_experiment(
    experiment: ExperimentRecord,
    observations: list[PerformanceObservation],
    *,
    since: date,
    until: date,
) -> dict[str, object]:
    selected = [
        item
        for item in observations
        if item.period_start == since
        and item.period_end == until
        and item.creative_id
        in {
            experiment.control.creative_id,
            experiment.treatment.creative_id,
        }
    ]
    control = _arm_totals(selected, experiment.control.creative_id)
    treatment = _arm_totals(selected, experiment.treatment.creative_id)
    context_ok, context_problems = _same_measurement_context(control, treatment)

    control_value = _point_value(
        control, experiment.primary_metric, experiment.action_type
    )
    treatment_value = _point_value(
        treatment, experiment.primary_metric, experiment.action_type
    )
    base: dict[str, object] = {
        "experiment_id": experiment.id,
        "campaign_id": experiment.campaign_id,
        "hypothesis": experiment.hypothesis,
        "changed_factor": experiment.changed_factor,
        "design": experiment.design,
        "metric": experiment.primary_metric,
        "action_type": experiment.action_type,
        "expected_direction": experiment.expected_direction,
        "window": {"since": since.isoformat(), "until": until.isoformat()},
        "descriptive_only": experiment.design == "observational_comparison",
        "causal_claim": False,
        "control": {
            "creative_id": experiment.control.creative_id,
            "variant_id": experiment.control.variant_id,
            "factor_value": experiment.control.factor_value,
            "observation_count": len(control["rows"]),
            "value": control_value,
        },
        "treatment": {
            "creative_id": experiment.treatment.creative_id,
            "variant_id": experiment.treatment.variant_id,
            "factor_value": experiment.treatment.factor_value,
            "observation_count": len(treatment["rows"]),
            "value": treatment_value,
        },
    }

    if not control["rows"] or not treatment["rows"]:
        return {
            **base,
            "inferential": False,
            "verdict": "inconclusive",
            "reason": "missing_exact_window_observations_for_one_or_both_arms",
            "minimum_evidence": {"met": False, "shortfalls": ["missing arm data"]},
        }
    if not context_ok:
        return {
            **base,
            "inferential": False,
            "verdict": "inconclusive",
            "reason": "incompatible_measurement_context",
            "context_problems": context_problems,
            "minimum_evidence": {"met": False, "shortfalls": context_problems},
        }

    difference = (
        treatment_value - control_value
        if control_value is not None and treatment_value is not None
        else None
    )
    relative_lift = (
        difference / control_value
        if difference is not None and control_value not in {None, 0.0}
        else None
    )
    base["difference"] = difference
    base["relative_lift"] = relative_lift

    if experiment.primary_metric not in INFERENTIAL_RATE_METRICS:
        actions_control = float(
            dict(control["actions"]).get(experiment.action_type or "", 0.0)
        )
        actions_treatment = float(
            dict(treatment["actions"]).get(experiment.action_type or "", 0.0)
        )
        shortfalls: list[str] = []
        if actions_control < experiment.thresholds.min_events_per_arm:
            shortfalls.append("control action count below minimum")
        if actions_treatment < experiment.thresholds.min_events_per_arm:
            shortfalls.append("treatment action count below minimum")
        return {
            **base,
            "inferential": False,
            "verdict": "inconclusive",
            "reason": "value_metric_requires_variance_or_event_level_evidence",
            "minimum_evidence": {"met": not shortfalls, "shortfalls": shortfalls},
        }

    evidence, difference_interval = _rate_evidence(
        experiment, control, treatment
    )
    base["control"].update(  # type: ignore[union-attr]
        {
            "events": evidence["control_events"],
            "denominator": evidence["control_denominator"],
            "confidence_interval": evidence["control_confidence_interval"],
        }
    )
    base["treatment"].update(  # type: ignore[union-attr]
        {
            "events": evidence["treatment_events"],
            "denominator": evidence["treatment_denominator"],
            "confidence_interval": evidence["treatment_confidence_interval"],
        }
    )
    public_evidence = {
        "met": evidence["met"],
        "shortfalls": evidence["shortfalls"],
    }
    confidence = {
        "level": experiment.thresholds.confidence_level,
        "method": "newcombe_wilson_difference",
        "difference_interval": difference_interval,
    }

    if experiment.design == "observational_comparison":
        return {
            **base,
            "descriptive_only": True,
            "inferential": False,
            "verdict": "inconclusive",
            "reason": "observational_comparison_is_descriptive_only",
            "minimum_evidence": public_evidence,
            "confidence": confidence,
        }

    if not bool(evidence["met"]):
        verdict: ExperimentVerdict = "inconclusive"
        reason = "minimum_evidence_not_met"
    elif difference_interval is None:
        verdict = "inconclusive"
        reason = "rate_confidence_interval_unavailable"
    else:
        lower, upper = difference_interval
        if experiment.expected_direction == "higher":
            if lower > 0:
                verdict, reason = (
                    "supported",
                    "confidence_interval_excludes_zero_in_expected_direction",
                )
            elif upper < 0:
                verdict, reason = (
                    "contradicted",
                    "confidence_interval_excludes_zero_against_expected_direction",
                )
            else:
                verdict, reason = "inconclusive", "confidence_interval_includes_zero"
        else:
            if upper < 0:
                verdict, reason = (
                    "supported",
                    "confidence_interval_excludes_zero_in_expected_direction",
                )
            elif lower > 0:
                verdict, reason = (
                    "contradicted",
                    "confidence_interval_excludes_zero_against_expected_direction",
                )
            else:
                verdict, reason = "inconclusive", "confidence_interval_includes_zero"

    return {
        **base,
        "inferential": True,
        "verdict": verdict,
        "reason": reason,
        "minimum_evidence": public_evidence,
        "confidence": confidence,
    }


def recommend_next_test(evaluation: dict[str, object]) -> dict[str, object]:
    """Return a deterministic recommendation grounded in recorded evidence."""

    verdict = str(evaluation.get("verdict", "inconclusive"))
    experiment_id = str(evaluation.get("experiment_id", ""))
    changed_factor = str(evaluation.get("changed_factor", "creative factor"))
    control = dict(evaluation.get("control", {}))
    treatment = dict(evaluation.get("treatment", {}))
    evidence = dict(evaluation.get("minimum_evidence", {}))
    inferential = bool(evaluation.get("inferential"))

    if verdict == "supported":
        return {
            "experiment_id": experiment_id,
            "action": "replicate_supported_factor",
            "evidence_status": "supported",
            "keep": treatment.get("creative_id"),
            "recommendation": (
                f"Replicate the {changed_factor!r} treatment in a fresh, "
                "non-overlapping window or audience before generalizing it. "
                "Keep all other declared factors fixed."
            ),
            "causal_claim": False,
        }
    if verdict == "contradicted":
        return {
            "experiment_id": experiment_id,
            "action": "revise_changed_factor",
            "evidence_status": "contradicted",
            "keep": control.get("creative_id"),
            "recommendation": (
                f"Retain the control and test a materially different value of "
                f"{changed_factor!r}; do not combine additional creative changes."
            ),
            "causal_claim": False,
        }
    if not inferential:
        return {
            "experiment_id": experiment_id,
            "action": "improve_measurement_design",
            "evidence_status": "inconclusive",
            "recommendation": (
                "Treat the current direction as descriptive only. Use a controlled "
                "rate-based comparison or ingest event-level/variance evidence "
                "before an inferential verdict."
            ),
            "causal_claim": False,
        }
    if not evidence.get("met", False):
        return {
            "experiment_id": experiment_id,
            "action": "collect_more_evidence",
            "evidence_status": "inconclusive",
            "shortfalls": list(evidence.get("shortfalls", [])),
            "recommendation": (
                "Continue the same single-factor test until both arms meet the "
                "declared minimum evidence thresholds; avoid changing creative "
                "mid-window."
            ),
            "causal_claim": False,
        }
    return {
        "experiment_id": experiment_id,
        "action": "replicate_or_extend",
        "evidence_status": "inconclusive",
        "recommendation": (
            "The confidence interval still crosses zero. Replicate the same "
            "single-factor comparison in a fresh non-overlapping window rather "
            "than declaring a winner."
        ),
        "causal_claim": False,
    }
