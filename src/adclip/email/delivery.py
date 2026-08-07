"""Provider-neutral boundary for future live email delivery adapters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class EmailDeliveryRequest:
    campaign_dir: str
    variant_id: str
    recipients: tuple[str, ...]
    idempotency_key: str
    send_at: str | None = None

    @property
    def eml_path(self) -> Path:
        return Path(self.campaign_dir) / "variants" / self.variant_id / "message.eml"


@dataclass(frozen=True)
class EmailDeliveryResult:
    provider: str
    message_id: str
    status: str
    accepted: int
    rejected: int = 0


@runtime_checkable
class EmailDeliveryProvider(Protocol):
    """Adapter contract; application code must not import an ESP SDK directly."""

    async def send(self, request: EmailDeliveryRequest) -> EmailDeliveryResult: ...
