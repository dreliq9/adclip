"""Generic local command adapter for text generation.

The configured executable receives the prompt on stdin and writes the raw
model response to stdout. No shell is used. This makes any local model CLI
usable without adding a vendor-specific dependency to adclip.

Individual argv tokens may contain ``{model}`` and ``{n}`` placeholders. The
same values are also exposed as ``ADCLIP_MODEL`` and
``ADCLIP_CANDIDATE_COUNT`` environment variables.
"""

from __future__ import annotations

import asyncio
import os
import shlex
from collections.abc import Sequence


class CommandTextProvider:
    """Run a local text model command behind the neutral provider contract."""

    provider_name = "command"

    def __init__(
        self,
        command: str | Sequence[str],
        *,
        model: str | None = None,
        timeout: float = 90.0,
    ) -> None:
        argv = shlex.split(command) if isinstance(command, str) else list(command)
        if not argv:
            raise RuntimeError(
                "command provider requires ADCLIP_COMMAND_TEXT_COMMAND"
            )
        self._argv = tuple(str(part) for part in argv)
        self.model_name = model
        self.timeout = float(timeout)

    async def generate(self, prompt: str, n: int) -> str:
        model = self.model_name or ""
        argv = [
            token.replace("{model}", model).replace("{n}", str(n))
            for token in self._argv
        ]
        env = os.environ.copy()
        env["ADCLIP_MODEL"] = model
        env["ADCLIP_CANDIDATE_COUNT"] = str(n)

        process = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(prompt.encode("utf-8")),
                timeout=self.timeout,
            )
        except TimeoutError:
            process.kill()
            await process.communicate()
            raise RuntimeError(
                f"command provider timed out after {self.timeout:g}s"
            ) from None

        if process.returncode != 0:
            detail = stderr.decode("utf-8", errors="replace")[:1000]
            raise RuntimeError(
                f"command provider failed (rc={process.returncode}): {detail}"
            )
        return stdout.decode("utf-8", errors="replace")
