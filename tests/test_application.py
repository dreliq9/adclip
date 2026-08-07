import asyncio
import json

from adclip.application import AdclipApplication
from adclip.runtime import RuntimeMode, RuntimePolicy


BRIEF = {
    "product": "X",
    "value_prop": "Y",
    "audience": "Z",
    "angles": ["credibility"],
    "tone": "dry",
    "cta": "Start",
    "formats": ["google_rsa"],
    "output_dir": "/tmp/adclip-application-test",
    "variants": 1,
    "pool_size": 2,
}


def test_application_validates_and_estimates_without_mcp():
    app = AdclipApplication()
    validated = app.validate_brief_json(json.dumps(BRIEF))
    estimated = app.estimate_cost_json(json.dumps(BRIEF))
    assert validated["ok"] is True
    assert estimated["ok"] is True
    assert estimated["total_usd"] >= 0


def test_application_generates_copy_with_offline_fake_provider():
    app = AdclipApplication(
        runtime_policy=RuntimePolicy(mode=RuntimeMode.OFFLINE)
    )
    result = asyncio.run(
        app.generate_copy_json(json.dumps(BRIEF), provider_name="fake")
    )
    assert result["ok"] is True
    assert len(result["winners"]) == 1


def test_application_enforces_runtime_policy():
    app = AdclipApplication(
        runtime_policy=RuntimePolicy(mode=RuntimeMode.OFFLINE)
    )
    result = asyncio.run(
        app.generate_copy_json(json.dumps(BRIEF), provider_name="claude-cli")
    )
    assert result["ok"] is False
    assert "requires network access" in result["error"]


def test_application_status_is_interface_neutral():
    status = AdclipApplication(
        runtime_policy=RuntimePolicy(mode=RuntimeMode.OFFLINE)
    ).status()
    assert status["runtime"]["mode"] == "offline"
    assert status["format_count"] >= 10
    assert any(p["name"] == "fake" for p in status["llm_providers"])
