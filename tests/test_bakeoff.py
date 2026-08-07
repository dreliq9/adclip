import json
from pathlib import Path

from adclip.evals.media_bakeoff import build_bakeoff_plan, run_bakeoff


def test_bakeoff_is_dry_run_by_default(tmp_path):
    jobs = build_bakeoff_plan("image", routes=["general", "bulk"], repetitions=1)
    result = run_bakeoff(jobs, output_dir=tmp_path)
    assert result["ok"] is True
    assert result["executed"] is False
    plan = json.loads(Path(result["plan_path"]).read_text())
    assert len(plan) == 8
    assert {row["route"]["name"] for row in plan} == {"general", "bulk"}
