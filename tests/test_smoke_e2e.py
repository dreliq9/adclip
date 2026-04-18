import asyncio
import json
import shutil
from pathlib import Path

import pytest

from adclip.mcp.pipeline_tools import _generate_variants_impl


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_e2e_with_fakes(tmp_path):
    brief_path = Path(__file__).parent.parent / "examples" / "taichi_brief.json"
    brief = json.loads(brief_path.read_text())
    brief["output_dir"] = str(tmp_path / "camp")
    result = asyncio.run(_generate_variants_impl(
        json.dumps(brief),
        llm_provider="fake",
        image_provider="fake",
    ))
    assert result["ok"] is True
    assert len(result["entries"]) >= 2
    camp = Path(brief["output_dir"])
    assert (camp / "manifest.json").exists()
    assert (camp / "brief.json").exists()
