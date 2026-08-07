"""Application-service boundary shared by CLI, MCP, and future UI.

Workflows operate on provider-neutral capabilities and explicit provider/model
selections. Interface adapters may retain legacy ``llm_*`` parameter names,
but vendor SDKs and model IDs do not belong in this layer.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from pydantic import ValidationError

from adclip.copy import generate_copy_pool
from adclip.cost import estimate_cost
from adclip.formats import FORMATS, get_format
from adclip.policy import check_copy
from adclip.providers.contracts import (
    ModelSelection,
    TextGenerationProvider,
)
from adclip.providers.media import (
    describe_media_configuration,
    resolve_image_provider,
    resolve_video_provider,
)
from adclip.providers.registry import (
    LLMProviderRegistry,
    TextProviderRegistry,
    default_text_registry,
)
from adclip.runtime import RuntimePolicy
from adclip.schema import AdBrief
from adclip.scoring import rank_pool


class AdclipApplication:
    """Transport-neutral facade for adclip's current workflows."""

    def __init__(
        self,
        *,
        text_registry: TextProviderRegistry | None = None,
        llm_registry: LLMProviderRegistry | None = None,
        runtime_policy: RuntimePolicy | None = None,
    ) -> None:
        if text_registry is not None and llm_registry is not None:
            raise ValueError("Pass text_registry or llm_registry, not both")
        self.text_registry = text_registry or llm_registry or default_text_registry()
        self.llm_registry = self.text_registry
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

    def resolve_text_provider_with_selection(
        self,
        name: str = "default",
        *,
        model: str | None = None,
        session: Any | None = None,
    ) -> tuple[TextGenerationProvider, ModelSelection]:
        return self.text_registry.resolve_with_selection(
            name,
            model=model,
            session=session,
            policy=self.runtime_policy,
        )

    def resolve_text_provider(
        self,
        name: str = "default",
        *,
        model: str | None = None,
        session: Any | None = None,
    ) -> TextGenerationProvider:
        provider, _selection = self.resolve_text_provider_with_selection(
            name,
            model=model,
            session=session,
        )
        return provider

    def resolve_llm_provider(
        self,
        name: str = "default",
        *,
        model: str | None = None,
        session: Any | None = None,
    ) -> TextGenerationProvider:
        """Backward-compatible alias for :meth:`resolve_text_provider`."""

        return self.resolve_text_provider(
            name,
            model=model,
            session=session,
        )

    @staticmethod
    def filter_copy_pool(
        pool: list[dict],
        brief: AdBrief,
    ) -> tuple[list[dict], list[dict]]:
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
        model_name: str | None = None,
        session: Any | None = None,
    ) -> dict:
        provider, selection = self.resolve_text_provider_with_selection(
            provider_name,
            model=model_name,
            session=session,
        )
        pool = await generate_copy_pool(brief, provider=provider)
        survivors, rejected = self.filter_copy_pool(pool, brief)
        winners = rank_pool(survivors, n=brief.variants)
        return {
            "ok": True,
            "winners": winners,
            "rejected": rejected,
            "pool": pool,
            "models": {"text": selection.as_dict()},
        }

    async def generate_copy_json(
        self,
        brief_json: str,
        *,
        provider_name: str = "default",
        model_name: str | None = None,
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
                model_name=model_name,
                session=session,
            )
        except (RuntimeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    async def generate_variants(
        self,
        brief: AdBrief,
        *,
        text_provider_name: str | None = None,
        text_model_name: str | None = None,
        llm_provider_name: str | None = None,
        llm_model_name: str | None = None,
        image_provider_name: str = "default",
        image_model_name: str | None = None,
        video_provider_name: str = "default",
        video_model_name: str | None = None,
        session: Any | None = None,
    ) -> dict:
        from adclip.pipeline import run_pipeline

        requested_text_provider = (
            text_provider_name or llm_provider_name or "default"
        )
        requested_text_model = text_model_name or llm_model_name
        text_provider, text_selection = self.resolve_text_provider_with_selection(
            requested_text_provider,
            model=requested_text_model,
            session=session,
        )

        format_kinds = {get_format(name).kind for name in brief.formats}
        image_binding = None
        video_binding = None
        if "static" in format_kinds:
            image_binding = resolve_image_provider(
                image_provider_name,
                model=image_model_name,
                policy=self.runtime_policy,
            )
        if "video" in format_kinds:
            video_binding = resolve_video_provider(
                video_provider_name,
                model=video_model_name,
                policy=self.runtime_policy,
            )

        models: dict[str, object] = {
            "text": text_selection.as_dict(),
        }
        if image_binding is not None:
            models["image"] = image_binding.as_dict()
        if video_binding is not None:
            models["video"] = video_binding.as_dict()

        return await run_pipeline(
            brief,
            llm_provider=text_provider,
            image_fn=image_binding,
            video_fn=video_binding,
            models=models,
        )

    async def generate_variants_json(
        self,
        brief_json: str,
        *,
        text_provider_name: str | None = None,
        text_model_name: str | None = None,
        llm_provider_name: str | None = None,
        llm_model_name: str | None = None,
        image_provider_name: str = "default",
        image_model_name: str | None = None,
        video_provider_name: str = "default",
        video_model_name: str | None = None,
        session: Any | None = None,
    ) -> dict:
        try:
            brief = self.parse_brief_json(brief_json)
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            return {"ok": False, "error": str(exc)}
        try:
            return await self.generate_variants(
                brief,
                text_provider_name=text_provider_name,
                text_model_name=text_model_name,
                llm_provider_name=llm_provider_name,
                llm_model_name=llm_model_name,
                image_provider_name=image_provider_name,
                image_model_name=image_model_name,
                video_provider_name=video_provider_name,
                video_model_name=video_model_name,
                session=session,
            )
        except (RuntimeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def status(self) -> dict[str, object]:
        text_providers = self.text_registry.describe()
        media = describe_media_configuration()
        return {
            "runtime": self.runtime_policy.as_dict(),
            "configured_models": {
                "text": self.text_registry.configured_default(),
                **{
                    key: value["configured_default"]
                    for key, value in media.items()
                },
            },
            "text_providers": text_providers,
            "llm_providers": text_providers,
            "media_providers": media,
            "format_count": len(FORMATS),
        }
