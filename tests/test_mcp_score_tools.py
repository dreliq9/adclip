import asyncio
import json
from pathlib import Path

from adclip.llm import FakeLLMProvider
from adclip.mcp.score_tools import _score_variants_impl


class ScriptedJudge(FakeLLMProvider):
    def __init__(self, scores: list[float]):
        self._scores = scores
        self._i = 0

    async def generate(self, prompt: str, n: int) -> str:
        s = self._scores[self._i % len(self._scores)]
        self._i += 1
        return json.dumps({"score": s, "rationale": "s", "flags": []})


def _brief_payload(**overrides) -> dict:
    p = dict(
        product="Taichi", value_prop="Paper trade first",
        audience="Crypto traders",
        angles=["credibility"], tone="dry", cta="Start",
        formats=["meta_feed_4x5"],
        output_dir="/tmp/x",
    )
    p.update(overrides)
    return p


def _seed(tmp_path: Path, *, variants: list[dict], brief: dict | None = None) -> Path:
    (tmp_path / "variants").mkdir()
    (tmp_path / "brief.json").write_text(json.dumps(brief or _brief_payload()))
    for v in variants:
        vid = v["variant_id"]
        vdir = tmp_path / "variants" / vid
        vdir.mkdir()
        (vdir / "copy.json").write_text(json.dumps(v["copy"]))
    return tmp_path


def test_missing_campaign():
    out = asyncio.run(_score_variants_impl("/tmp/does-not-exist-adclip"))
    assert out["ok"] is False


def test_missing_brief(tmp_path):
    (tmp_path / "variants").mkdir()
    out = asyncio.run(_score_variants_impl(str(tmp_path)))
    assert out["ok"] is False
    assert "brief.json" in out["error"]


def test_no_variants(tmp_path):
    _seed(tmp_path, variants=[])
    out = asyncio.run(_score_variants_impl(str(tmp_path)))
    assert out["ok"] is False
    assert "No variants" in out["error"]


def test_heuristic_ranks_longer_body_higher(tmp_path):
    _seed(tmp_path, variants=[
        {"variant_id": "v01", "copy": {
            "headline": "Short", "body": "x", "cta": "Go",
            "angle": "credibility", "format": "meta_feed_4x5",
        }},
        {"variant_id": "v02", "copy": {
            "headline": "Substantive headline here",
            "body": "A much longer body with more than 60 characters to hit the length bonus cleanly",
            "cta": "Start trading",
            "angle": "credibility", "format": "meta_feed_4x5",
        }},
    ])
    out = asyncio.run(_score_variants_impl(str(tmp_path)))
    assert out["ok"] is True
    assert out["use_judge"] is False
    assert out["ranked"][0]["variant_id"] == "v02"
    assert out["ranked"][0]["heuristic_score"] > out["ranked"][1]["heuristic_score"]


def test_use_judge_without_provider_errors(tmp_path):
    _seed(tmp_path, variants=[
        {"variant_id": "v01", "copy": {
            "headline": "H", "body": "B", "cta": "C",
            "angle": "credibility", "format": "meta_feed_4x5",
        }},
    ])
    out = asyncio.run(_score_variants_impl(str(tmp_path), use_judge=True))
    assert out["ok"] is False
    assert "llm_provider" in out["error"].lower()


def test_judge_ranks_by_scripted_scores(tmp_path):
    _seed(tmp_path, variants=[
        {"variant_id": "v01", "copy": {
            "headline": "A", "body": "b", "cta": "c",
            "angle": "credibility", "format": "meta_feed_4x5",
        }},
        {"variant_id": "v02", "copy": {
            "headline": "A", "body": "b", "cta": "c",
            "angle": "credibility", "format": "meta_feed_4x5",
        }},
    ])
    # v01 scripted to 0.2, v02 to 0.9 (order matches sorted glob)
    judge = ScriptedJudge([0.2, 0.9])
    out = asyncio.run(_score_variants_impl(
        str(tmp_path), use_judge=True, llm_provider=judge,
    ))
    assert out["ok"] is True
    assert out["ranked"][0]["variant_id"] == "v02"
    assert out["ranked"][0]["judge_score"] == 0.9


def test_write_updates_manifest(tmp_path):
    _seed(tmp_path, variants=[
        {"variant_id": "v01", "copy": {
            "headline": "Short", "body": "x", "cta": "Go",
            "angle": "credibility", "format": "meta_feed_4x5",
        }},
        {"variant_id": "v02", "copy": {
            "headline": "Meaty headline here", "body": "A longer substantive body text over 60 chars for the bonus.",
            "cta": "Go", "angle": "credibility", "format": "meta_feed_4x5",
        }},
    ])
    # Pre-existing manifest in reverse order of what the score should produce
    (tmp_path / "manifest.json").write_text(json.dumps({
        "entries": [
            {"variant_id": "v01", "format": "meta_feed_4x5", "path": "variants/v01/meta_feed_4x5.png"},
            {"variant_id": "v02", "format": "meta_feed_4x5", "path": "variants/v02/meta_feed_4x5.png"},
        ],
    }))

    out = asyncio.run(_score_variants_impl(str(tmp_path), write=True))
    assert out["ok"] is True
    assert out["manifest_updated"] is True

    m = json.loads((tmp_path / "manifest.json").read_text())
    assert m["entries"][0]["variant_id"] == "v02"
    assert m["entries"][0]["path"] == "variants/v02/meta_feed_4x5.png"
    assert "heuristic_score" in m["entries"][0]
    assert "score" in m["entries"][0]


def test_write_clears_stale_judge_score_on_heuristic_rerun(tmp_path):
    # Prior judge run stamped judge_score=0.99. Current heuristic-only rerun
    # must drop the stale judge_score and refresh 'score' from the heuristic.
    _seed(tmp_path, variants=[
        {"variant_id": "v01", "copy": {
            "headline": "H", "body": "x", "cta": "C",
            "angle": "credibility", "format": "meta_feed_4x5",
        }},
    ])
    (tmp_path / "manifest.json").write_text(json.dumps({
        "entries": [
            {"variant_id": "v01", "format": "meta_feed_4x5",
             "score": 0.99, "judge_score": 0.99},
        ],
    }))

    out = asyncio.run(_score_variants_impl(str(tmp_path), write=True))
    assert out["ok"] is True

    m = json.loads((tmp_path / "manifest.json").read_text())
    entry = m["entries"][0]
    assert "judge_score" not in entry
    assert entry["score"] == entry["heuristic_score"]
    assert entry["score"] != 0.99


def test_write_clears_stale_heuristic_on_judge_rerun(tmp_path):
    # Prior heuristic run stamped heuristic_score. Current judge rerun must
    # drop the stale heuristic_score and set score=judge_score.
    _seed(tmp_path, variants=[
        {"variant_id": "v01", "copy": {
            "headline": "H", "body": "x", "cta": "C",
            "angle": "credibility", "format": "meta_feed_4x5",
        }},
    ])
    (tmp_path / "manifest.json").write_text(json.dumps({
        "entries": [
            {"variant_id": "v01", "format": "meta_feed_4x5",
             "score": 0.42, "heuristic_score": 0.42},
        ],
    }))

    judge = ScriptedJudge([0.77])
    out = asyncio.run(_score_variants_impl(
        str(tmp_path), use_judge=True, llm_provider=judge, write=True,
    ))
    assert out["ok"] is True

    m = json.loads((tmp_path / "manifest.json").read_text())
    entry = m["entries"][0]
    # Judge path computes both scores; current values replace the stale 0.42
    assert entry["judge_score"] == 0.77
    assert entry["score"] == 0.77
    assert entry["heuristic_score"] != 0.42


def test_unreadable_copy_json_skipped(tmp_path):
    _seed(tmp_path, variants=[
        {"variant_id": "v01", "copy": {
            "headline": "H", "body": "B", "cta": "C",
            "angle": "credibility", "format": "meta_feed_4x5",
        }},
    ])
    bad = tmp_path / "variants" / "v02"
    bad.mkdir()
    (bad / "copy.json").write_text("{not-json")
    out = asyncio.run(_score_variants_impl(str(tmp_path)))
    assert out["ok"] is True
    assert len(out["ranked"]) == 1
    assert out["ranked"][0]["variant_id"] == "v01"
