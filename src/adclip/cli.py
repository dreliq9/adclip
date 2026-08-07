"""adclip CLI — standalone adapter over shared application services.

Provider and model are independent selections. The default provider remains
configurable and compatibility flags such as ``--llm`` and ``--image`` are
retained while neutral names are introduced.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import click

from adclip import _env

_env.load()

from adclip.application import AdclipApplication
from adclip.providers.registry import default_text_registry


_TEXT_PROVIDER_TYPE = click.Choice(
    default_text_registry().names(include_aliases=True),
    case_sensitive=True,
)
_MEDIA_PROVIDER_TYPE = click.Choice(["default", "fal", "fake"])


@click.group()
def main() -> None:
    """adclip — model-agnostic ad creative generation."""


@main.command()
def status() -> None:
    """Show runtime mode, configured models, and provider capabilities."""
    click.echo(json.dumps(AdclipApplication().status(), indent=2))


@main.command()
def formats() -> None:
    """List supported ad formats and their specs."""
    for spec in AdclipApplication.list_formats()["formats"]:
        click.echo(
            f"{spec['name']}  {spec['aspect']:7s}  "
            f"{spec['width']}x{spec['height']}  kind={spec['kind']}  "
            f"headline<={spec['headline_max']}  body<={spec['body_max']}"
        )


@main.command("estimate")
@click.argument("brief_path", type=click.Path(exists=True))
def estimate_cmd(brief_path: str) -> None:
    """Estimate cost for a brief JSON file."""
    out = AdclipApplication().estimate_cost_json(Path(brief_path).read_text())
    click.echo(json.dumps(out, indent=2))


@main.command("copy")
@click.argument("brief_path", type=click.Path(exists=True))
@click.option(
    "--provider",
    default="default",
    type=_TEXT_PROVIDER_TYPE,
    show_default=True,
    help="Text-generation provider registered with adclip.",
)
@click.option(
    "--model",
    default=None,
    help="Provider-specific model ID; overrides configured defaults.",
)
def copy_cmd(brief_path: str, provider: str, model: str | None) -> None:
    """Generate ad copy without images or video."""
    out = asyncio.run(
        AdclipApplication().generate_copy_json(
            Path(brief_path).read_text(),
            provider_name=provider,
            model_name=model,
        )
    )
    click.echo(json.dumps(out, indent=2))


@main.command("run")
@click.argument("brief_path", type=click.Path(exists=True))
@click.option(
    "--text-provider",
    "--llm",
    "text_provider",
    default="default",
    type=_TEXT_PROVIDER_TYPE,
    show_default=True,
    help="Text-generation provider. --llm is retained for compatibility.",
)
@click.option(
    "--text-model",
    "--llm-model",
    "text_model",
    default=None,
    help="Text model ID independent of provider selection.",
)
@click.option(
    "--image-provider",
    "--image",
    "image_provider",
    default="default",
    type=_MEDIA_PROVIDER_TYPE,
    show_default=True,
)
@click.option("--image-model", default=None, help="Image model ID.")
@click.option(
    "--video-provider",
    "--video",
    "video_provider",
    default="default",
    type=_MEDIA_PROVIDER_TYPE,
    show_default=True,
)
@click.option("--video-model", default=None, help="Video model ID.")
def run_cmd(
    brief_path: str,
    text_provider: str,
    text_model: str | None,
    image_provider: str,
    image_model: str | None,
    video_provider: str,
    video_model: str | None,
) -> None:
    """Run the full creative pipeline for a brief JSON file."""
    out = asyncio.run(
        AdclipApplication().generate_variants_json(
            Path(brief_path).read_text(),
            text_provider_name=text_provider,
            text_model_name=text_model,
            image_provider_name=image_provider,
            image_model_name=image_model,
            video_provider_name=video_provider,
            video_model_name=video_model,
        )
    )
    click.echo(json.dumps(out, indent=2))
