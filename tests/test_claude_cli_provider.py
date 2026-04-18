import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adclip.claude_cli import ClaudeCliProvider


def _mock_proc(stdout: bytes = b"", stderr: bytes = b"", returncode: int = 0):
    """Build a MagicMock that looks like an asyncio.subprocess.Process."""
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    return proc


def test_argv_shape():
    provider = ClaudeCliProvider()
    captured_argv: list = []

    async def _fake_exec(*args, **kwargs):
        captured_argv.extend(args)
        return _mock_proc(stdout=b'{"candidates": []}')

    with patch(
        "adclip.claude_cli.asyncio.create_subprocess_exec",
        side_effect=_fake_exec,
    ):
        asyncio.run(provider.generate("some prompt", n=1))

    assert captured_argv[0] == "claude"
    assert "-p" in captured_argv
    assert "--output-format" in captured_argv
    i = captured_argv.index("--output-format")
    assert captured_argv[i + 1] == "text"
    assert "--no-session-persistence" in captured_argv
    assert "--tools" in captured_argv
    i = captured_argv.index("--tools")
    assert captured_argv[i + 1] == ""
    assert "--model" in captured_argv
    i = captured_argv.index("--model")
    assert captured_argv[i + 1] == "sonnet"
    assert "--append-system-prompt" in captured_argv
    i = captured_argv.index("--append-system-prompt")
    system_prompt = captured_argv[i + 1]
    assert "JSON only" in system_prompt
    assert captured_argv[-1] == "some prompt"


def test_happy_path_returns_stdout_verbatim():
    provider = ClaudeCliProvider()

    async def _fake_exec(*args, **kwargs):
        return _mock_proc(stdout=b'{"candidates": [{"headline": "H"}]}')

    with patch(
        "adclip.claude_cli.asyncio.create_subprocess_exec",
        side_effect=_fake_exec,
    ):
        out = asyncio.run(provider.generate("prompt", n=1))

    assert out == '{"candidates": [{"headline": "H"}]}'


def test_nonzero_returncode_raises_with_stderr_prefix():
    provider = ClaudeCliProvider()

    async def _fake_exec(*args, **kwargs):
        return _mock_proc(
            stdout=b"",
            stderr=b"claude: some error happened",
            returncode=2,
        )

    with patch(
        "adclip.claude_cli.asyncio.create_subprocess_exec",
        side_effect=_fake_exec,
    ):
        with pytest.raises(RuntimeError, match="some error happened"):
            asyncio.run(provider.generate("prompt", n=1))


def test_timeout_raises():
    provider = ClaudeCliProvider(timeout=0.01)

    async def _fake_exec(*args, **kwargs):
        proc = MagicMock()
        proc.returncode = 0

        async def _never():
            await asyncio.sleep(10)
            return (b"", b"")

        proc.communicate = _never
        return proc

    with patch(
        "adclip.claude_cli.asyncio.create_subprocess_exec",
        side_effect=_fake_exec,
    ):
        with pytest.raises((asyncio.TimeoutError, TimeoutError)):
            asyncio.run(provider.generate("prompt", n=1))


def test_custom_model_flows_through():
    provider = ClaudeCliProvider(model="opus")
    captured_argv: list = []

    async def _fake_exec(*args, **kwargs):
        captured_argv.extend(args)
        return _mock_proc(stdout=b"ok")

    with patch(
        "adclip.claude_cli.asyncio.create_subprocess_exec",
        side_effect=_fake_exec,
    ):
        asyncio.run(provider.generate("p", n=1))

    i = captured_argv.index("--model")
    assert captured_argv[i + 1] == "opus"


def test_custom_claude_path():
    provider = ClaudeCliProvider(claude_path="/custom/claude")
    captured_argv: list = []

    async def _fake_exec(*args, **kwargs):
        captured_argv.extend(args)
        return _mock_proc(stdout=b"ok")

    with patch(
        "adclip.claude_cli.asyncio.create_subprocess_exec",
        side_effect=_fake_exec,
    ):
        asyncio.run(provider.generate("p", n=1))

    assert captured_argv[0] == "/custom/claude"
