import json

from adclip.llm import FakeLLMProvider, parse_copy_candidates


def test_parse_copy_candidates_from_json():
    raw = json.dumps({
        "candidates": [
            {"headline": "H1", "body": "B1", "cta": "C1"},
            {"headline": "H2", "body": "B2", "cta": "C2"},
        ]
    })
    out = parse_copy_candidates(raw)
    assert len(out) == 2
    assert out[0]["headline"] == "H1"


def test_parse_copy_candidates_tolerates_prose_wrapper():
    raw = "Here are the candidates:\n\n" + json.dumps({
        "candidates": [{"headline": "H", "body": "B", "cta": "C"}]
    }) + "\n\nLet me know if you need more."
    out = parse_copy_candidates(raw)
    assert len(out) == 1


def test_fake_provider_returns_deterministic_candidates():
    p = FakeLLMProvider()
    text = p.generate(prompt="whatever", n=3)
    parsed = parse_copy_candidates(text)
    assert len(parsed) == 3
    assert all("headline" in c for c in parsed)
