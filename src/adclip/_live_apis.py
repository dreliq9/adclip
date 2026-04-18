"""Opt-in gate for live third-party APIs (Anthropic, fal.ai).

adclip's defaults are keyless and free: claude-cli for LLM, ``--image fake``
for static backgrounds. To avoid surprise billing when a credential happens
to be present in the environment, every provider that calls a paid third
party must also check ``ADCLIP_ALLOW_LIVE_APIS``. Unset (or ``0``/``false``)
means "do not bill the user even if a key is in env".
"""

from __future__ import annotations

import os


_TRUTHY = {"1", "true", "yes", "on"}


def allow_live_apis() -> bool:
    return os.environ.get("ADCLIP_ALLOW_LIVE_APIS", "").strip().lower() in _TRUTHY


def require_live_apis(provider_name: str) -> None:
    if allow_live_apis():
        return
    raise RuntimeError(
        f"{provider_name} would make a billed API call, but "
        "ADCLIP_ALLOW_LIVE_APIS is not set. Either (a) set "
        "ADCLIP_ALLOW_LIVE_APIS=1 to authorize live calls, or "
        "(b) use a keyless/free path instead (e.g. --llm claude-cli, "
        "--image fake, llm_provider='fake' in tests)."
    )
