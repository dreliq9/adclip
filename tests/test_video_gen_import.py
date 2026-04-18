def test_video_gen_imports():
    from adclip import video_gen
    assert hasattr(video_gen, "MODELS")
    assert "kling-2.6" in video_gen.MODELS


def test_check_key_raises_without_env(monkeypatch):
    import pytest

    from adclip import video_gen

    monkeypatch.delenv("FAL_KEY", raising=False)
    with pytest.raises(RuntimeError, match="FAL_KEY"):
        video_gen._check_key()
