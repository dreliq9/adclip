import asyncio
import json
import shutil
from pathlib import Path

import pytest

from adclip.pipeline import run_pipeline
from adclip.llm import FakeLLMProvider
from adclip.schema import AdBrief


class FakeImageGen:
    """Stand-in for fal.ai image generation: writes a blank PNG."""

    def __init__(self):
        self.calls = 0

    def __call__(self, prompt, *, format_name, output_dir, seed):
        from PIL import Image
        from adclip.formats import get_format

        self.calls += 1
        fmt = get_format(format_name)
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        path = Path(output_dir) / f"{format_name}_{seed or 'x'}.png"
        Image.new("RGB", (fmt.width, fmt.height), color=(20, 20, 40)).save(path)

        class R:
            pass

        r = R()
        r.local_path = str(path)
        r.url = ""
        r.model = "flux-fake"
        r.cost_usd = 0.025
        return r


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_run_pipeline_static_only(tmp_path):
    brief = AdBrief(
        product="Taichi",
        value_prop="Paper trade first",
        audience="Crypto traders",
        angles=["credibility"],
        tone="dry",
        cta="Start paper trading",
        formats=["meta_feed_4x5"],
        output_dir=str(tmp_path / "camp"),
        variants=2, pool_size=3,
    )
    provider = FakeLLMProvider()
    fake_img = FakeImageGen()

    result = asyncio.run(run_pipeline(brief, llm_provider=provider, image_fn=fake_img))

    # manifest written
    root = Path(brief.output_dir)
    assert (root / "manifest.json").exists()
    m = json.loads((root / "manifest.json").read_text())
    # 2 variants x 1 format
    assert len(m["entries"]) == 2

    # each entry has a file that exists
    for entry in m["entries"]:
        assert Path(root / entry["path"]).exists()

    # image gen was called once per variant
    assert fake_img.calls == 2


def test_run_pipeline_heals_violations(tmp_path):
    """With heal_violations > 0, violating candidates get rewritten."""
    import asyncio
    import json
    from pathlib import Path

    class _ScriptedProvider:
        """First call generates a pool; heal call rewrites the violation."""

        def __init__(self):
            self._calls = 0

        async def generate(self, prompt: str, n: int):
            self._calls += 1
            if "fixing policy violations" in prompt:
                return json.dumps({"candidates": [{
                    "headline": "Try paper trading",
                    "body": "Run our signals on paper for a week. No card required.",
                    "cta": "Start",
                }]})
            return json.dumps({"candidates": [
                {"headline": "Guaranteed returns",
                 "body": "Guaranteed profit every month",
                 "cta": "Sign up"},
                {"headline": "Skeptical? Paper trade our signals",
                 "body": "Run our bot for a week without risking real cash.",
                 "cta": "Start paper trading"},
            ]})

    brief = AdBrief(
        product="Taichi", value_prop="Paper trade first",
        audience="Crypto traders",
        angles=["credibility"], tone="dry", cta="Start",
        formats=["meta_feed_4x5"],
        output_dir=str(tmp_path / "camp"),
        variants=2, pool_size=2,
        policy_profile="crypto",
        heal_violations=2,
    )

    def _fake_img(prompt, *, format_name, output_dir, seed):
        from PIL import Image
        from adclip.formats import get_format
        fmt = get_format(format_name)
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        p = Path(output_dir) / f"{format_name}_{seed}.png"
        Image.new("RGB", (fmt.width, fmt.height), color=(0, 0, 0)).save(p)

        class R:
            local_path = str(p)
            url = ""
            model = "x"
            cost_usd = 0.0
        return R()

    result = asyncio.run(run_pipeline(
        brief,
        llm_provider=_ScriptedProvider(),
        image_fn=_fake_img,
    ))

    assert result["ok"] is True
    assert len(result["entries"]) == 2

    manifest = json.loads((Path(brief.output_dir) / "manifest.json").read_text())
    copy_files = [
        Path(brief.output_dir) / "variants" / e["variant_id"] / "copy.json"
        for e in manifest["entries"]
    ]
    any_healed = False
    for cf in copy_files:
        data = json.loads(cf.read_text())
        if "healed_from" in data:
            any_healed = True
            assert data["heal_attempts"] >= 1
    assert any_healed, "expected at least one healed variant"


def test_run_pipeline_use_judge_attaches_judge_fields(tmp_path):
    import asyncio
    import json
    from pathlib import Path

    class _ScriptedProvider:
        def __init__(self):
            self._pool_done = False
            self._scores = iter([0.9, 0.3])

        async def generate(self, prompt: str, n: int):
            if "senior performance-ad reviewer" in prompt:
                return json.dumps({
                    "score": next(self._scores),
                    "rationale": "x",
                    "flags": [],
                })
            return json.dumps({"candidates": [
                {"headline": "A headline here", "body": "A reasonably fleshed body.",
                 "cta": "Go A"},
                {"headline": "B headline here", "body": "B reasonably fleshed body.",
                 "cta": "Go B"},
            ]})

    brief = AdBrief(
        product="X", value_prop="Y", audience="Z",
        angles=["a"], tone="t", cta="c",
        formats=["meta_feed_4x5"],
        output_dir=str(tmp_path / "camp"),
        variants=1, pool_size=2,
        use_judge=True,
    )

    def _fake_img(prompt, *, format_name, output_dir, seed):
        from PIL import Image
        from adclip.formats import get_format
        fmt = get_format(format_name)
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        p = Path(output_dir) / f"{format_name}_{seed}.png"
        Image.new("RGB", (fmt.width, fmt.height), color=(0, 0, 0)).save(p)

        class R:
            local_path = str(p)
            url = ""
            model = "x"
            cost_usd = 0.0
        return R()

    result = asyncio.run(run_pipeline(
        brief,
        llm_provider=_ScriptedProvider(),
        image_fn=_fake_img,
    ))

    assert result["ok"] is True
    assert len(result["entries"]) == 1
    copy_data = json.loads(
        (Path(brief.output_dir) / "variants" / "v01" / "copy.json").read_text()
    )
    assert copy_data["headline"] == "A headline here"
    assert copy_data["judge_score"] == 0.9
