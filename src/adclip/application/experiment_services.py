"""Application services for explicit creative experiments and next-test evidence."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from adclip.performance.experiment import (
    EvidenceThresholds,
    ExperimentRecord,
    arm_from_variant,
    default_thresholds,
    evaluate_experiment,
    experiment_id_for,
    get_experiment,
    load_experiments,
    recommend_next_test,
    upsert_experiment,
)
from adclip.performance.store import campaign_manifest, load_observations


def _date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Expected YYYY-MM-DD date, got {value!r}") from exc


class ExperimentApplication:
    """Create, inspect, evaluate, and continue creative hypotheses."""

    def create(
        self,
        campaign_dir: str,
        *,
        name: str,
        hypothesis: str,
        changed_factor: str,
        control_variant_id: str,
        treatment_variant_id: str,
        control_value: str,
        treatment_value: str,
        primary_metric: str = "ctr",
        action_type: str | None = None,
        expected_direction: str = "higher",
        design: str = "controlled_single_factor",
        min_denominator_per_arm: int | None = None,
        min_events_per_arm: int | None = None,
        confidence_level: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, object]:
        root = Path(campaign_dir)
        if not root.is_dir():
            return {"ok": False, "error": f"Campaign dir not found: {campaign_dir}"}
        try:
            manifest = campaign_manifest(root)
            control = arm_from_variant(
                root,
                variant_id=control_variant_id,
                role="control",
                factor_value=control_value,
            )
            treatment = arm_from_variant(
                root,
                variant_id=treatment_variant_id,
                role="treatment",
                factor_value=treatment_value,
            )
            if design == "controlled_single_factor" and control.format != treatment.format:
                raise ValueError(
                    "controlled_single_factor experiments require matching formats"
                )
            defaults = default_thresholds(primary_metric)  # type: ignore[arg-type]
            thresholds = EvidenceThresholds(
                min_denominator_per_arm=(
                    min_denominator_per_arm
                    if min_denominator_per_arm is not None
                    else defaults.min_denominator_per_arm
                ),
                min_events_per_arm=(
                    min_events_per_arm
                    if min_events_per_arm is not None
                    else defaults.min_events_per_arm
                ),
                confidence_level=(
                    confidence_level
                    if confidence_level is not None
                    else defaults.confidence_level
                ),
            )
            experiment = ExperimentRecord(
                id=experiment_id_for(
                    str(manifest["campaign_id"]),
                    control_creative_id=control.creative_id,
                    treatment_creative_id=treatment.creative_id,
                    changed_factor=changed_factor,
                    primary_metric=primary_metric,
                    action_type=action_type,
                ),
                campaign_id=str(manifest["campaign_id"]),
                name=name,
                hypothesis=hypothesis,
                changed_factor=changed_factor,
                control=control,
                treatment=treatment,
                primary_metric=primary_metric,  # type: ignore[arg-type]
                action_type=action_type,
                expected_direction=expected_direction,  # type: ignore[arg-type]
                design=design,  # type: ignore[arg-type]
                thresholds=thresholds,
                metadata=metadata or {},
            )
            upsert_experiment(root, experiment)
        except (FileNotFoundError, KeyError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "experiment": experiment.model_dump(mode="json")}

    def list(self, campaign_dir: str) -> dict[str, object]:
        try:
            experiments = load_experiments(campaign_dir)
        except (FileNotFoundError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}
        return {
            "ok": True,
            "experiments": [item.model_dump(mode="json") for item in experiments],
        }

    def evaluate(
        self,
        campaign_dir: str,
        *,
        experiment_id: str,
        since: str | date,
        until: str | date,
    ) -> dict[str, object]:
        try:
            start = _date(since)
            end = _date(until)
            if end < start:
                raise ValueError("until must be on or after since")
            experiment = get_experiment(campaign_dir, experiment_id)
            observations = load_observations(campaign_dir)
            result = evaluate_experiment(
                experiment,
                observations,
                since=start,
                until=end,
            )
        except (FileNotFoundError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "evaluation": result}

    def next_test(
        self,
        campaign_dir: str,
        *,
        experiment_id: str,
        since: str | date,
        until: str | date,
    ) -> dict[str, object]:
        evaluated = self.evaluate(
            campaign_dir,
            experiment_id=experiment_id,
            since=since,
            until=until,
        )
        if not evaluated.get("ok"):
            return evaluated
        evaluation = dict(evaluated["evaluation"])  # type: ignore[arg-type]
        return {
            "ok": True,
            "evaluation": evaluation,
            "next_test": recommend_next_test(evaluation),
        }
