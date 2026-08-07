import asyncio
import inspect
import json
from pathlib import Path

from PIL import Image

from adclip.application import AdclipApplication
from adclip.formats import get_format
from adclip.mcp import regenerate_tools, score_tools, visual_tools
from adclip.runtime import RuntimeMode, RuntimePolicy


def _brief(tmp_path: Path, *, formats: list[str]) -> str:
    return json.dumps({
        "product": "X",
        "value_prop": "Y",
        "audience": "Z",
        "angles": ["credibility"],
        "tone": "dry",
        "cta": "Start",
        "formats": formats,
        "output_dir": str(tmp_path / "campaign"),
        "variants": 1,
        "pool_size": 2,
    })


def _copy(format_name: str) -> dict:
    return {
        "headline": "Headline",
        "body": "A sufficiently complete body for the fixture.",
        "cta": "Start",
        "angle": "credibility",
        "format": format_name,
    }


def _fake_image(prompt, *, format_name, output_dir, seed):
    del prompt
    spec = get_format(format_name)
    path = Path(output_dir) / f"{format_name}_{seed}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (spec.width, spec.height), color=(20, 20, 40)).save(path)

    class Result:
        local_path = str(path)
        url = ""
        model = "image-fixture-v2"
        cost_usd = 0.0

    return Result()


def test_text_only_run_ignores_unused_media_configuration_and_persists_models(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("ADCLIP_IMAGE_PROVIDER", "not-a-provider")
    monkeypatch.setenv("ADCLIP_VIDEO_PROVIDER", "also-not-a-provider")
    app = AdclipApplication(
        runtime_policy=RuntimePolicy(mode=RuntimeMode.OFFLINE)
    )
    result = asyncio.run(
        app.generate_variants_json(
            _brief(tmp_path, formats=["google_rsa"]),
            text_provider_name="fake",
            text_model_name="copy-model-v3",
        )
    )
    assert result["ok"] is True
    assert result["models"] == {
        "text": {"provider": "fake", "model": "copy-model-v3"}
    }

    manifest = json.loads(
        (tmp_path / "campaign" / "manifest.json").read_text()
    )
    assert manifest["models"] == result["models"]


def test_visual_only_manifest_records_selected_media_model(tmp_path):
    models = {
        "image": {"provider": "fake", "model": "image-fixture-v2"}
    }
    result = visual_tools._generate_visuals_impl(
        _brief(tmp_path, formats=["meta_feed_4x5"]),
        json.dumps([_copy("meta_feed_4x5")]),
        image_fn=_fake_image,
        models=models,
    )
    assert result["ok"] is True
    assert result["models"] == models

    manifest = json.loads(
        (tmp_path / "campaign" / "manifest.json").read_text()
    )
    assert manifest["models"] == models


class _CapturingMCP:
    def __init__(self):
        self.functions = {}

    def tool(self):
        def decorator(function):
            self.functions[function.__name__] = function
            return function
        return decorator


def test_iteration_tools_expose_model_selection_and_mcp_context():
    capture = _CapturingMCP()
    visual_tools.register(capture)
    regenerate_tools.register(capture)
    score_tools.register(capture)

    visual = inspect.signature(capture.functions["adclip_generate_visuals"])
    regenerate = inspect.signature(capture.functions["adclip_regenerate"])
    score = inspect.signature(capture.functions["adclip_score_variants"])

    assert {"image_provider", "image_model", "video_provider", "video_model"} <= set(
        visual.parameters
    )
    assert {"ctx", "llm_provider", "llm_model", "image_provider", "image_model"} <= set(
        regenerate.parameters
    )
    assert {"ctx", "llm_provider", "llm_model"} <= set(score.parameters)
