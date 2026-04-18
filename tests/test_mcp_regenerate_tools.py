import asyncio
import json
from pathlib import Path

from PIL import Image

from adclip.llm import FakeLLMProvider
from adclip.mcp.pipeline_tools import _fake_image_fn
from adclip.mcp.regenerate_tools import _regenerate_impl


def _brief_payload(**o):
    p = dict(
        product="X", value_prop="Y", audience="Z",
        angles=["credibility"], tone="dry", cta="Start",
        formats=["meta_feed_4x5"],
        output_dir="/tmp/x",
    )
    p.update(o)
    return p


def _seed(tmp_path: Path, *, format_name: str = "meta_feed_4x5", with_bg: bool = True) -> Path:
    (tmp_path / "variants").mkdir()
    (tmp_path / "brief.json").write_text(json.dumps(_brief_payload(formats=[format_name])))
    vdir = tmp_path / "variants" / "v01"
    vdir.mkdir()
    (vdir / "copy.json").write_text(json.dumps({
        "headline": "Old headline",
        "body": "Old body text with enough length to pass.",
        "cta": "Old CTA",
        "angle": "credibility",
        "format": format_name,
    }))
    if with_bg:
        Image.new("RGB", (1080, 1350), color=(40, 40, 80)).save(
            vdir / f"{format_name}_1.png"
        )
    return tmp_path


def test_missing_campaign():
    r = asyncio.run(_regenerate_impl("/tmp/does-not-exist-adclip", "v01"))
    assert r["ok"] is False


def test_missing_variant(tmp_path):
    _seed(tmp_path)
    r = asyncio.run(_regenerate_impl(str(tmp_path), "v99"))
    assert r["ok"] is False
    assert "Variant not found" in r["error"]


def test_invalid_what_rejected_in_impl(tmp_path):
    # impl doesn't validate what directly; the MCP-facing wrapper does.
    # Verify copy path errors without provider:
    _seed(tmp_path)
    r = asyncio.run(_regenerate_impl(str(tmp_path), "v01", what="copy"))
    assert r["ok"] is False
    assert "llm_provider" in r["error"]


def test_copy_only_regen_updates_copy_json_and_recomposites(tmp_path):
    _seed(tmp_path)
    llm = FakeLLMProvider()
    r = asyncio.run(_regenerate_impl(
        str(tmp_path), "v01", what="copy", llm_provider=llm,
    ))
    assert r["ok"] is True
    new_copy = json.loads((tmp_path / "variants" / "v01" / "copy.json").read_text())
    assert new_copy["headline"] != "Old headline"
    # FakeLLMProvider emits "Headline N"; rank_pool picks the top of N survivors
    assert new_copy["headline"].startswith("Headline")
    # Final composite should exist
    assert (tmp_path / "variants" / "v01" / "meta_feed_4x5.png").exists()


def test_visual_only_regen_writes_new_background(tmp_path):
    _seed(tmp_path, with_bg=False)
    r = asyncio.run(_regenerate_impl(
        str(tmp_path), "v01", what="visual", image_fn=_fake_image_fn, seed=42,
    ))
    assert r["ok"] is True
    # _fake_image_fn writes {format}_{seed}.png
    assert (tmp_path / "variants" / "v01" / "meta_feed_4x5_42.png").exists()
    assert (tmp_path / "variants" / "v01" / "meta_feed_4x5.png").exists()


def test_both_regenerates_copy_and_visual(tmp_path):
    _seed(tmp_path)
    llm = FakeLLMProvider()
    r = asyncio.run(_regenerate_impl(
        str(tmp_path), "v01", what="both",
        llm_provider=llm, image_fn=_fake_image_fn, seed=7,
    ))
    assert r["ok"] is True
    assert "copy" in r
    assert "image_path" in r
    assert (tmp_path / "variants" / "v01" / "meta_feed_4x5_7.png").exists()


def test_visual_regen_fails_on_text_format(tmp_path):
    _seed(tmp_path, format_name="google_rsa", with_bg=False)
    r = asyncio.run(_regenerate_impl(
        str(tmp_path), "v01", what="visual", image_fn=_fake_image_fn,
    ))
    assert r["ok"] is False
    assert "static" in r["error"].lower()


def test_copy_regen_text_format_works(tmp_path):
    _seed(tmp_path, format_name="google_rsa", with_bg=False)
    llm = FakeLLMProvider()
    r = asyncio.run(_regenerate_impl(
        str(tmp_path), "v01", what="copy", llm_provider=llm,
    ))
    assert r["ok"] is True
    # Text formats recomposite by writing {format}.json
    assert (tmp_path / "variants" / "v01" / "google_rsa.json").exists()


def test_recomposite_requires_background_for_static(tmp_path):
    _seed(tmp_path, with_bg=False)
    llm = FakeLLMProvider()
    r = asyncio.run(_regenerate_impl(
        str(tmp_path), "v01", what="copy", llm_provider=llm,
    ))
    assert r["ok"] is False
    assert "No raw background" in r["error"]


class AllViolatingProvider(FakeLLMProvider):
    async def generate(self, prompt: str, n: int) -> str:
        cands = [
            {
                "headline": "GUARANTEED RETURNS " * 3,
                "body": "GUARANTEED RETURNS AND ZERO RISK FOR EVERYONE",
                "cta": "buy now",
            }
            for _ in range(n)
        ]
        return json.dumps({"candidates": cands})


def test_all_violators_returns_policy_error(tmp_path):
    # Use crypto profile so 'guaranteed returns' is flagged
    (tmp_path / "variants").mkdir()
    (tmp_path / "brief.json").write_text(json.dumps(
        _brief_payload(policy_profile="crypto")
    ))
    vdir = tmp_path / "variants" / "v01"
    vdir.mkdir()
    (vdir / "copy.json").write_text(json.dumps({
        "headline": "ok", "body": "ok body over 30 chars no issues here.",
        "cta": "Start", "angle": "credibility", "format": "meta_feed_4x5",
    }))
    Image.new("RGB", (1080, 1350), color=(40, 40, 80)).save(vdir / "meta_feed_4x5_1.png")

    r = asyncio.run(_regenerate_impl(
        str(tmp_path), "v01", what="copy", llm_provider=AllViolatingProvider(),
    ))
    assert r["ok"] is False
    assert "policy" in r["error"].lower()
