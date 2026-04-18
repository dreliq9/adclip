import json
import shutil

import pytest

from adclip.mcp.pipeline_tools import _generate_variants_impl


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_generate_variants_with_fakes(tmp_path):
    brief = dict(
        product="X", value_prop="Y", audience="Z",
        angles=["a"], tone="t", cta="c",
        formats=["meta_feed_4x5"],
        output_dir=str(tmp_path / "camp"),
        variants=1, pool_size=2,
    )
    result = _generate_variants_impl(
        json.dumps(brief), llm_provider="fake", image_provider="fake",
    )
    assert result["ok"] is True
    assert result["entries"]
