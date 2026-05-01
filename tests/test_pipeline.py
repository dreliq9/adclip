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


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_run_pipeline_video_format(tmp_path):
    from adclip.mcp.pipeline_tools import _fake_video_fn
    from adclip.render import has_drawtext

    if not has_drawtext():
        pytest.skip("ffmpeg lacks drawtext filter (rebuild with freetype)")

    brief = AdBrief(
        product="Taichi",
        value_prop="Paper trade first",
        audience="Crypto traders",
        angles=["credibility"],
        tone="dry",
        cta="Start paper trading",
        formats=["tiktok_9x16"],
        output_dir=str(tmp_path / "camp"),
        variants=1, pool_size=1,
    )
    fake_img = FakeImageGen()

    result = asyncio.run(run_pipeline(
        brief, llm_provider=FakeLLMProvider(),
        image_fn=fake_img, video_fn=_fake_video_fn,
    ))

    root = Path(brief.output_dir)
    assert (root / "manifest.json").exists()
    m = json.loads((root / "manifest.json").read_text())
    assert len(m["entries"]) == 1
    entry = m["entries"][0]
    assert entry["path"].endswith("tiktok_9x16.mp4")
    assert (root / entry["path"]).exists()
    # raw clip persists alongside the rendered ad
    assert any(Path(root / "variants" / "v01").glob("tiktok_9x16_*_raw.mp4"))


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


def test_manifest_entry_carries_judge_fields_when_use_judge(tmp_path):
    import asyncio
    import json
    from pathlib import Path

    class _ScriptedProvider:
        def __init__(self):
            self._scores = iter([0.9, 0.3])

        async def generate(self, prompt: str, n: int):
            if "senior performance-ad reviewer" in prompt:
                return json.dumps({
                    "score": next(self._scores),
                    "rationale": "crisp hook",
                    "flags": ["weak_hook"],
                })
            return json.dumps({"candidates": [
                {"headline": "A headline here", "body": "A reasonably fleshed body.", "cta": "Go A"},
                {"headline": "B headline here", "body": "B reasonably fleshed body.", "cta": "Go B"},
            ]})

    brief = AdBrief(
        product="X", value_prop="Y", audience="Z",
        angles=["a"], tone="t", cta="c",
        formats=["meta_feed_4x5"],
        output_dir=str(tmp_path / "camp"),
        variants=1, pool_size=2, use_judge=True,
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
            url = ""; model = "x"; cost_usd = 0.0
        return R()

    asyncio.run(run_pipeline(brief, llm_provider=_ScriptedProvider(), image_fn=_fake_img))
    manifest = json.loads((Path(brief.output_dir) / "manifest.json").read_text())
    entry = manifest["entries"][0]
    assert entry["judge_score"] == 0.9
    assert entry["judge_rationale"] == "crisp hook"
    assert entry["judge_flags"] == ["weak_hook"]


def test_manifest_entry_carries_heal_metadata_when_healed(tmp_path):
    import asyncio
    import json
    from pathlib import Path

    class _ScriptedProvider:
        async def generate(self, prompt: str, n: int):
            if "fixing policy violations" in prompt:
                return json.dumps({"candidates": [{
                    "headline": "Paper trade first",
                    "body": "Run our signals on paper for a week. No card required.",
                    "cta": "Start",
                }]})
            return json.dumps({"candidates": [
                {"headline": "Guaranteed returns",
                 "body": "Guaranteed profit every month",
                 "cta": "Sign up"},
            ]})

    brief = AdBrief(
        product="Taichi", value_prop="Paper trade first",
        audience="Crypto traders",
        angles=["credibility"], tone="dry", cta="Start",
        formats=["meta_feed_4x5"],
        output_dir=str(tmp_path / "camp"),
        variants=1, pool_size=1,
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
            url = ""; model = "x"; cost_usd = 0.0
        return R()

    asyncio.run(run_pipeline(brief, llm_provider=_ScriptedProvider(), image_fn=_fake_img))
    manifest = json.loads((Path(brief.output_dir) / "manifest.json").read_text())
    entry = manifest["entries"][0]
    assert entry["heal_attempts"] == 1
    assert entry["healed_from"]["headline"] == "Guaranteed returns"


def test_pipeline_covers_all_formats_when_multiple(tmp_path):
    """With 2 formats and variants=2, each format must get one winner
    even when one format's candidates are lower scored globally."""
    import asyncio
    import json
    from pathlib import Path

    class _ScriptedProvider:
        def __init__(self):
            # 2 formats x 1 angle x 2 candidates each = 4 candidates
            # feed judge scores: fmt_a gets [0.95, 0.9], fmt_b gets [0.4, 0.3]
            self._judge_scores = iter([0.95, 0.9, 0.4, 0.3])

        async def generate(self, prompt: str, n: int):
            if "senior performance-ad reviewer" in prompt:
                return json.dumps({
                    "score": next(self._judge_scores),
                    "rationale": "x", "flags": [],
                })
            # copy prompt — emit 2 candidates
            return json.dumps({"candidates": [
                {"headline": "Headline one here", "body": "Reasonably fleshed body text.", "cta": "Go"},
                {"headline": "Headline two here", "body": "Another reasonably fleshed body.", "cta": "Go"},
            ]})

    brief = AdBrief(
        product="X", value_prop="Y", audience="Z",
        angles=["a"], tone="t", cta="c",
        formats=["meta_feed_4x5", "google_rsa"],
        output_dir=str(tmp_path / "camp"),
        variants=2, pool_size=2, use_judge=True,
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
            url = ""; model = "x"; cost_usd = 0.0
        return R()

    asyncio.run(run_pipeline(brief, llm_provider=_ScriptedProvider(), image_fn=_fake_img))
    manifest = json.loads((Path(brief.output_dir) / "manifest.json").read_text())
    formats_in_winners = {e["format"] for e in manifest["entries"]}
    assert formats_in_winners == {"meta_feed_4x5", "google_rsa"}


def test_manifest_entry_carries_heuristic_score(tmp_path):
    import asyncio
    import json
    from pathlib import Path

    brief = AdBrief(
        product="X", value_prop="Y", audience="Z",
        angles=["a"], tone="t", cta="c",
        formats=["meta_feed_4x5"],
        output_dir=str(tmp_path / "camp"),
        variants=1, pool_size=2,
    )
    provider = FakeLLMProvider()

    def _fake_img(prompt, *, format_name, output_dir, seed):
        from PIL import Image
        from adclip.formats import get_format
        fmt = get_format(format_name)
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        p = Path(output_dir) / f"{format_name}_{seed}.png"
        Image.new("RGB", (fmt.width, fmt.height), color=(0, 0, 0)).save(p)

        class R:
            local_path = str(p)
            url = ""; model = "x"; cost_usd = 0.0
        return R()

    asyncio.run(run_pipeline(brief, llm_provider=provider, image_fn=_fake_img))
    manifest = json.loads((Path(brief.output_dir) / "manifest.json").read_text())
    entry = manifest["entries"][0]
    assert "heuristic_score" in entry
    assert 0.0 <= entry["heuristic_score"] <= 1.0


def test_pipeline_semantic_policy_triggers_heal_on_paraphrase(tmp_path):
    import asyncio
    import json
    from pathlib import Path

    class _Scripted:
        def __init__(self):
            self._sem_calls = 0

        async def generate(self, prompt, n):
            if "compliance reviewer" in prompt.lower():
                self._sem_calls += 1
                if self._sem_calls == 1:
                    return json.dumps({"violations": ["implies risk elimination"]})
                return json.dumps({"violations": []})
            if "fixing policy violations" in prompt:
                return json.dumps({"candidates": [{
                    "headline": "Paper trade first",
                    "body": "Audit signals before you commit real cash.",
                    "cta": "Start",
                }]})
            return json.dumps({"candidates": [
                {"headline": "Zero risk trading ahead",
                 "body": "A safe bet for skeptical folks.",
                 "cta": "Sign up"},
            ]})

    brief = AdBrief(
        product="Taichi", value_prop="Paper trade",
        audience="Crypto traders",
        angles=["credibility"], tone="dry", cta="Start",
        formats=["meta_feed_4x5"],
        output_dir=str(tmp_path / "camp"),
        variants=1, pool_size=1,
        policy_profile="crypto",
        heal_violations=2,
        use_semantic_policy=True,
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
            url = ""; model = "x"; cost_usd = 0.0
        return R()

    result = asyncio.run(run_pipeline(brief, llm_provider=_Scripted(), image_fn=_fake_img))
    assert result["ok"] is True
    assert len(result["entries"]) == 1
    entry = result["entries"][0]
    assert entry.get("heal_attempts", 0) >= 1
    assert entry["healed_from"]["headline"] == "Zero risk trading ahead"


def test_pipeline_deduplicates_near_duplicate_winners(tmp_path):
    import asyncio
    import json
    from pathlib import Path

    class _Scripted:
        def __init__(self):
            # 3 judged candidates: two identical (0.95, 0.93) and one different (0.5).
            # Without dedup, top-2 would be the two dups.
            self._scores = iter([0.95, 0.93, 0.5])

        async def generate(self, prompt, n):
            if "senior performance-ad reviewer" in prompt:
                return json.dumps({
                    "score": next(self._scores),
                    "rationale": "x", "flags": [],
                })
            return json.dumps({"candidates": [
                {"headline": "Skeptical paper trade first",
                 "body": "Run the bot on paper first.",
                 "cta": "Go"},
                {"headline": "Skeptical paper trade first",
                 "body": "Run the bot on paper first.",
                 "cta": "Go"},
                {"headline": "What if you just tested",
                 "body": "Wildly different body language entirely.",
                 "cta": "Go"},
            ]})

    brief = AdBrief(
        product="X", value_prop="Y", audience="Z",
        angles=["a"], tone="t", cta="c",
        formats=["meta_feed_4x5"],
        output_dir=str(tmp_path / "camp"),
        variants=2, pool_size=3, use_judge=True,
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
            url = ""; model = "x"; cost_usd = 0.0
        return R()

    asyncio.run(run_pipeline(brief, llm_provider=_Scripted(), image_fn=_fake_img))
    copy_0 = json.loads(
        (Path(brief.output_dir) / "variants" / "v01" / "copy.json").read_text()
    )
    copy_1 = json.loads(
        (Path(brief.output_dir) / "variants" / "v02" / "copy.json").read_text()
    )
    assert copy_0["headline"] != copy_1["headline"], (
        f"winners are duplicates: {copy_0['headline']} == {copy_1['headline']}"
    )
