"""Runtime policy for standalone, connected, and air-gapped operation.

Provider adapters declare their operational requirements. The application
checks those requirements before construction or invocation so CLI, MCP, and
future HTTP/UI interfaces enforce the same connectivity and billing policy.
"""

from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlparse


_TRUTHY = {"1", "true", "yes", "on"}


class RuntimeMode(str, Enum):
    """How much external connectivity adclip may use."""

    ONLINE = "online"
    RESTRICTED_NETWORK = "restricted_network"
    OFFLINE = "offline"
    AIR_GAPPED = "air_gapped"

    @classmethod
    def coerce(cls, value: RuntimeMode | str | None) -> RuntimeMode:
        if isinstance(value, cls):
            return value
        raw = value or os.environ.get("ADCLIP_RUNTIME_MODE", cls.ONLINE.value)
        try:
            return cls(raw.strip().lower())
        except ValueError as exc:
            known = ", ".join(mode.value for mode in cls)
            raise ValueError(
                f"Unknown ADCLIP_RUNTIME_MODE {raw!r}. Known modes: {known}"
            ) from exc


@dataclass(frozen=True)
class ProviderRequirements:
    """Runtime properties declared by a provider adapter.

    ``loopback_only`` distinguishes a local inference server from external
    network access. Localhost inference remains usable in offline and
    air-gapped modes; adapters must re-check dynamically if their endpoint can
    be configured to a non-loopback host.
    """

    network: bool = False
    loopback_only: bool = False
    paid_api: bool = False
    host_session: bool = False

    def __post_init__(self) -> None:
        if self.loopback_only and not self.network:
            object.__setattr__(self, "network", True)


def endpoint_is_loopback(url: str) -> bool:
    """Return whether an HTTP(S) endpoint resolves syntactically to loopback."""

    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@dataclass(frozen=True)
class RuntimePolicy:
    """Enforce provider use consistently across every adclip interface."""

    mode: RuntimeMode = RuntimeMode.ONLINE
    allowed_network_providers: frozenset[str] = field(default_factory=frozenset)
    allow_paid_apis: bool = False
    allow_host_sessions: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "mode", RuntimeMode.coerce(self.mode))
        object.__setattr__(
            self,
            "allowed_network_providers",
            frozenset(self.allowed_network_providers),
        )

    @classmethod
    def from_env(cls) -> RuntimePolicy:
        mode = RuntimeMode.coerce(None)
        allowlist = frozenset(
            name.strip()
            for name in os.environ.get(
                "ADCLIP_ALLOWED_NETWORK_PROVIDERS", ""
            ).split(",")
            if name.strip()
        )
        paid = os.environ.get("ADCLIP_ALLOW_LIVE_APIS", "").lower() in _TRUTHY
        host_default = mode not in {RuntimeMode.OFFLINE, RuntimeMode.AIR_GAPPED}
        host_raw = os.environ.get("ADCLIP_ALLOW_HOST_SESSIONS")
        allow_host = (
            host_default
            if host_raw is None
            else host_raw.strip().lower() in _TRUTHY
        )
        return cls(
            mode=mode,
            allowed_network_providers=allowlist,
            allow_paid_apis=paid,
            allow_host_sessions=allow_host,
        )

    def check_provider(
        self,
        provider_name: str,
        requirements: ProviderRequirements,
    ) -> None:
        """Raise ``RuntimeError`` when a provider violates this policy."""

        if requirements.host_session and (
            self.mode is RuntimeMode.AIR_GAPPED or not self.allow_host_sessions
        ):
            raise RuntimeError(
                f"Provider {provider_name!r} requires a host session, but host "
                f"sessions are disabled in runtime mode {self.mode.value!r}."
            )

        if requirements.network and not requirements.loopback_only:
            if self.mode in {RuntimeMode.OFFLINE, RuntimeMode.AIR_GAPPED}:
                raise RuntimeError(
                    f"Provider {provider_name!r} requires network access outside "
                    f"loopback, but adclip is running in {self.mode.value!r} mode."
                )
            if (
                self.mode is RuntimeMode.RESTRICTED_NETWORK
                and provider_name not in self.allowed_network_providers
            ):
                allowed = ", ".join(sorted(self.allowed_network_providers)) or "(none)"
                raise RuntimeError(
                    f"Provider {provider_name!r} is not in the restricted-network "
                    f"allowlist. Allowed providers: {allowed}. Set "
                    "ADCLIP_ALLOWED_NETWORK_PROVIDERS to change it."
                )

        if requirements.paid_api and not self.allow_paid_apis:
            raise RuntimeError(
                f"Provider {provider_name!r} may incur paid API charges. Set "
                "ADCLIP_ALLOW_LIVE_APIS=1 to authorize paid providers."
            )

    def as_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode.value,
            "allowed_network_providers": sorted(self.allowed_network_providers),
            "allow_paid_apis": self.allow_paid_apis,
            "allow_host_sessions": self.allow_host_sessions,
        }
