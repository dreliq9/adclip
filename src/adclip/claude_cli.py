"""Claude CLI subprocess text provider.

This is a compatibility adapter, not an application-layer dependency. Provider
and model selection are supplied by the neutral registry.
"""

from __future__ import annotations

import asyncio


_SYSTEM_PROMPT = (
    "You are a non-interactive worker. Return JSON only. "
    "Do not use any tools. Do not ask questions."
)


class ClaudeCliProvider:
    """Async text provider that shells out to ``claude -p``."""

    provider_name = "claude-cli"

    def __init__(
        self,
        model: str = "sonnet",
        timeout: float = 90.0,
        claude_path: str = "claude",
    ):
        self._model = model
        self.model_name = model
        self._timeout = timeout
        self._claude = claude_path

    async def generate(self, prompt: str, n: int) -> str:
        del n
        proc = await asyncio.create_subprocess_exec(
            self._claude,
            "-p",
            "--output-format",
            "text",
            "--no-session-persistence",
            "--tools",
            "",
            "--model",
            self._model,
            "--append-system-prompt",
            _SYSTEM_PROMPT,
            prompt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=self._timeout
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"claude CLI failed (rc={proc.returncode}): "
                f"{stderr.decode()[:500]}"
            )
        return stdout.decode()
