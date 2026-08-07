"""adclip CLI — standalone adapter over the shared application services.

The CLI does not depend on the MCP implementation. It defaults to the Claude
CLI provider (subscription auth, no API key); direct paid APIs remain opt-in
through ``ADCLIP_ALLOW_LIVE_APIS=1``.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import click

from adclip import _env

_env.load()

from adclip.application import AdclipApplication


@click.group()
def main() -> None:
    """adclip — ad creative generation."""


@main.command()
def status() -> None:
    """Show runtime mode and registered provider capabilities."""
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
    default="claude-cli",
    type=click.Choice(["claude-cli", "anthropic", "fake"]),
    help=(
        "LLM provider. 'claude-cli' (default) uses subscription auth; "
        "'anthropic' uses the paid direct API; 'fake' is for tests."
    ),
)
def copy_cmd(brief_path: str, provider: str) -> None:
    """Generate ad copy (no images/video)."""
    out = asyncio.run(
        AdclipApplication().generate_copy_json(
            Path(brief_path).read_text(),
            provider_name=provider,
        )
    )
    click.echo(json.dumps(out, indent=2))


@main.command("run")
@click.argument("brief_path", type=click.Path(exists=True))
@click.option(
    "--llm",
    default="claude-cli",
    type=click.Choice(["claude-cli", "anthropic", "fake"]),
    help=(
        "LLM provider. 'claude-cli' (default) uses subscription auth; "
        "'anthropic' uses the paid direct API; 'fake' is for tests."
    ),
)
@click.option("--image", default="default", type=click.Choice(["default", "fake"]))
@click.option("--video", default="default", type=click.Choice(["default", "fake"]))
def run_cmd(brief_path: str, llm: str, image: str, video: str) -> None:
    """Run the full pipeline for a brief JSON file."""
    out = asyncio.run(
        AdclipApplication().generate_variants_json(
            Path(brief_path).read_text(),
            llm_provider_name=llm,
            image_provider_name=image,
            video_provider_name=video,
        )
    )
    click.echo(json.dumps(out, indent=2))
