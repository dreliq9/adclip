"""Application-service boundary shared by adclip's CLI, MCP, and future UI.

Core workflows live here rather than under any transport adapter. Interfaces
may accept JSON for compatibility, but the application itself operates on
``AdBrief`` domain objects and provider capabilities.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from pydantic import ValidationError

from adclip.copy import generate_copy_pool
from adclip.cost import estimate_cost
from adclip.formats import FORMATS, get_format
from adclip.llm import LLMProvider
from adclip.policy import check_copy
from adclip.providers.media import (
    resolve_image_provider,
    resolve_video_provider,
)
from adclip.providers.registry import LLMProviderRegistry, default_llm_registry
from adclip.runtime import RuntimePolicy
from adclip.schema import AdBrief
from adclip.scoring import rank_pool


class AdclipApplication:
    """Transport-neutral facade for adclip's current workflows."""

    def __init__(
        self,
        *,
        llm_registry: LLMProviderRegistry | None = None,
        runtime_policy: RuntimePolicy | None = None,
    ) -> None:
        self.llm_registry = llm_registry or default_llm_registry()
        self.runtime_policy = runtime_policy or RuntimePolicy.from_env()

    @staticmethod
    def parse_brief_json(brief_json: str) -> AdBrief:
        data = json.loads(brief_json)
        if not isinstance(data, dict):
            raise ValueError("AdBrief JSON must be an object")
        return AdBrief(**data)

    def validate_brief_json(self, brief_json: str) -> dict:
        try:
            data = json.loads(brief_json)
        except json.JSONDecodeError as exc:
            return {"ok": False, "error": f"Invalid JSON: {exc}"}
        try:
            if not isinstance(data, dict):
                raise ValueError("AdBrief JSON must be an object")
            brief = AdBrief(**data)
        except (ValidationError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "brief": brief.model_dump()}

    @staticmethod
    def list_formats() -> dict:
        return {
            "formats": [
                {
                    "name": spec.name,
                    "aspect": spec.aspect,
                    "width": spec.width,
                    "height": spec.height,
                    "kind": spec.kind,
                    "headline_max": spec.headline_max,
                    "body_max": spec.body_max,
                    "rsa_max_headlines": spec.rsa_max_headlines,
                    "rsa_max_descriptions": spec.rsa_max_descriptions,
                }
                for spec in FORMATS.values()
            ]
        }

    def estimate_cost_json(self, brief_json: str) -> dict:
        try:
            brief = self.parse_brief_json(brief_json)
        except json.JSONDecodeError as exc:
            return {"ok": False, "error": f"Invalid JSON: {exc}"}
        except (ValidationError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}
        estimate = estimate_cost(brief)
        return {"ok": True, **asdict(estimate)}

    def resolve_llm_provider(
        self,
        name: str = "default",
        *,
        session: Any | None = None,
    ) -> LLMProvider:
        return self.llm_registry.resolve(
            name,
            session=session,
            policy=self.runtime_policy,
        )

    @staticmethod
    def filter_copy_pool(
        pool: list[dict],
        brief: AdBrief,
    ) -> tuple[list[dict], list[dict]]:
        """Split copy candidates into policy survivors and rejected entries."""

        survivors: list[dict] = []
        rejected: list[dict] = []
        for candidate in pool:
            format_spec = get_format(candidate["format"])
            report = check_copy(
                headline=candidate["headline"],
                body=candidate["body"],
                cta=candidate["cta"],
                format_spec=format_spec,
                profile=brief.policy_profile,
                must_include=brief.must_include,
                must_avoid=brief.must_avoid,
            )
            output = {**candidate, "warnings": report.warnings}
            if report.violations:
                rejected.append({**output, "violations": report.violations})
            else:
                survivors.append(output)
        return survivors, rejected

    async def generate_copy(
        self,
        brief: AdBrief,
        *,
        provider_name: str = "default",
        session: Any | None = None,
    ) -> dict:
        provider = self.resolve_llm_provider(provider_name, session=session)
        pool = await generate_copy_pool(brief, provider=provider)
        survivors, rejected = self.filter_copy_pool(pool, brief)
        winners = rank_pool(survivors, n=brief.variants)
        return {
            "ok": True,
            "winners": winners,
            "rejected": rejected,
            "pool": pool,
        }

    async def generate_copy_json(
        self,
        brief_json: str,
        *,
        provider_name: str = "default",
        session: Any | None = None,
    ) -> dict:
        try:
            brief = self.parse_brief_json(brief_json)
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            return {"ok": False, "error": str(exc)}
        try:
            return await self.generate_copy(
                brief,
                provider_name=provider_name,
                session=session,
            )
        except (RuntimeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    async def generate_variants(
        self,
        brief: AdBrief,
        *,
        llm_provider_name: str = "default",
        image_provider_name: str = "default",
        video_provider_name: str = "default",
        session: Any | None = None,
    ) -> dict:
        from adclip.pipeline import run_pipeline

        llm = self.resolve_llm_provider(llm_provider_name, session=session)
        image_fn = resolve_image_provider(image_provider_name)
        video_fn = resolve_video_provider(video_provider_name)
        return await run_pipeline(
            brief,
            llm_provider=llm,
            image_fn=image_fn,
            video_fn=video_fn,
        )

    async def generate_variants_json(
        self,
        brief_json: str,
        *,
        llm_provider_name: str = "default",
        image_provider_name: str = "default",
        video_provider_name: str = "default",
        session: Any | None = None,
    ) -> dict:
        try:
            brief = self.parse_brief_json(brief_json)
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            return {"ok": False, "error": str(exc)}
        try:
            return await self.generate_variants(
                brief,
                llm_provider_name=llm_provider_name,
                image_provider_name=image_provider_name,
                video_provider_name=video_provider_name,
                session=session,
            )
        except (RuntimeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def status(self) -> dict[str, object]:
        """Return capability metadata for CLI/UI health and diagnostics."""

        return {
            "runtime": self.runtime_policy.as_dict(),
            "llm_providers": self.llm_registry.describe(),
            "format_count": len(FORMATS),
        }
