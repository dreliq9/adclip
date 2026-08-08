from __future__ import annotations

import importlib.util
from pathlib import Path

from adclip.application.experiment_services import ExperimentApplication
from adclip.application.performance_services import PerformanceApplication


def _load_performance_demo_module():
    path = Path(__file__).parents[1] / "examples" / "build_performance_demo.py"
    spec = importlib.util.spec_from_file_location("adclip_performance_demo", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_performance_demo_builds_and_evaluates_offline(tmp_path):
    module = _load_performance_demo_module()
    result = module.build(tmp_path / "demo")

    assert str(result["campaign_id"]).startswith("cmp_")
    assert str(result["control_creative_id"]).startswith("crv_")
    assert str(result["treatment_creative_id"]).startswith("crv_")
    assert str(result["experiment_id"]).startswith("exp_")

    report = PerformanceApplication().report(
        result["campaign_dir"],
        since="2026-08-01",
        until="2026-08-07",
        action_report_time="conversion",
    )
    assert report["ok"] is True
    assert report["observation_count"] == 2

    evaluation = ExperimentApplication().evaluate(
        result["campaign_dir"],
        experiment_id=result["experiment_id"],
        since="2026-08-01",
        until="2026-08-07",
    )
    assert evaluation["ok"] is True
    assert evaluation["evaluation"]["verdict"] == "supported"
    assert evaluation["evaluation"]["causal_claim"] is False
