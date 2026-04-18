"""Claude CLI subprocess LLM provider.

Shells out to `claude -p` in non-interactive mode using the user's
existing Claude Code subscription auth. No API key required.

Cost: each generate() call spawns a fresh subprocess (~5-10s startup).
For latency-sensitive paths use SamplingLLMProvider (in an MCP session)
or AnthropicProvider (with a key).
"""

from __future__ import annotations

import asyncio


_SYSTEM_PROMPT = (
    "You are a non-interactive worker. Return JSON only. "
    "Do not use any tools. Do not ask questions."
)


class ClaudeCliProvider:
    """Async LLMProvider implementation that shells out to `claude -p`."""

    def __init__(
        self,
        model: str = "sonnet",
        timeout: float = 90.0,
        claude_path: str = "claude",
    ):
        self._model = model
        self._timeout = timeout
        self._claude = claude_path

    async def generate(self, prompt: str, n: int) -> str:
        proc = await asyncio.create_subprocess_exec(
            self._claude,
            "-p",
            "--output-format", "text",
            "--no-session-persistence",
            "--tools", "",
            "--model", self._model,
            "--append-system-prompt", _SYSTEM_PROMPT,
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
