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

    result = run_pipeline(brief, llm_provider=provider, image_fn=fake_img)

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
