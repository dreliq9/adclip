import base64
import json

from adclip.providers.openai_image import generate_image, image_size_for_format


class Response:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps({
            "data": [{"b64_json": base64.b64encode(b"png").decode()}]
        }).encode()


def test_direct_openai_request(monkeypatch, tmp_path):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data.decode())
        captured["url"] = request.full_url
        return Response()

    monkeypatch.setenv("ADCLIP_ALLOW_LIVE_APIS", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setattr("adclip.providers.openai_image.urlopen", fake_urlopen)
    result = generate_image(
        "hello",
        format_name="meta_feed_4x5",
        output_dir=str(tmp_path),
        options={"quality": "medium"},
    )
    assert captured["body"]["model"] == "gpt-image-2"
    assert captured["body"]["quality"] == "medium"
    assert captured["url"].endswith("/v1/images/generations")
    assert open(result.local_path, "rb").read() == b"png"


def test_size_is_api_compatible():
    width, height = map(int, image_size_for_format("meta_feed_4x5").split("x"))
    assert width % 16 == 0 and height % 16 == 0
