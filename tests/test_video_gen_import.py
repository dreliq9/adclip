def test_video_gen_imports():
    from adclip import video_gen
    assert hasattr(video_gen, "MODELS")
    assert "kling-2.6" in video_gen.MODELS


def test_check_key_raises_without_env(monkeypatch):
    """With the live-APIs gate open but FAL_KEY missing, the key-specific
    error fires. (The gate itself is covered in test_live_apis.py.)"""
    import pytest

    from adclip import video_gen

    monkeypatch.setenv("ADCLIP_ALLOW_LIVE_APIS", "1")
    monkeypatch.delenv("FAL_KEY", raising=False)
    with pytest.raises(RuntimeError, match="FAL_KEY"):
        video_gen._check_key()
