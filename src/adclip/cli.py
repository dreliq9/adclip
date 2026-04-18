"""adclip CLI — thin wrapper over the MCP tool implementations.

The CLI can't use MCP sampling (no connected client), so it defaults to
'claude-cli' (subscription auth, no API key). Pass --llm anthropic to opt
into the direct API, or --llm fake in tests.

Live third-party APIs (anthropic, fal.ai) additionally require
ADCLIP_ALLOW_LIVE_APIS=1 to be set — this prevents surprise billing if a
key happens to be in the environment.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import click

from adclip import _env

_env.load()

from adclip.formats import FORMATS
from adclip.mcp.brief_tools import _estimate_cost_impl
from adclip.mcp.copy_tools import _generate_copy_impl
from adclip.mcp.pipeline_tools import _generate_variants_impl


@click.group()
def main() -> None:
    """adclip — ad creative generation."""


@main.command()
def formats() -> None:
    """List supported ad formats and their specs."""
    for name, spec in FORMATS.items():
        click.echo(
            f"{name}  {spec.aspect:7s}  {spec.width}x{spec.height}  "
            f"kind={spec.kind}  headline<={spec.headline_max}  body<={spec.body_max}"
        )


@main.command("estimate")
@click.argument("brief_path", type=click.Path(exists=True))
def estimate_cmd(brief_path: str) -> None:
    """Estimate cost for a brief JSON file."""
    out = _estimate_cost_impl(Path(brief_path).read_text())
    click.echo(json.dumps(out, indent=2))


@main.command("copy")
@click.argument("brief_path", type=click.Path(exists=True))
@click.option(
    "--provider",
    default="claude-cli",
    type=click.Choice(["claude-cli", "anthropic", "fake"]),
    help=(
        "LLM provider. 'claude-cli' (default) shells out to the claude CLI "
        "using subscription auth (no API key). 'anthropic' uses the direct "
        "API and requires ANTHROPIC_API_KEY. 'fake' is for tests."
    ),
)
def copy_cmd(brief_path: str, provider: str) -> None:
    """Generate ad copy (no images/video)."""
    out = asyncio.run(_generate_copy_impl(
        Path(brief_path).read_text(), provider_name=provider
    ))
    click.echo(json.dumps(out, indent=2))


@main.command("run")
@click.argument("brief_path", type=click.Path(exists=True))
@click.option(
    "--llm",
    default="claude-cli",
    type=click.Choice(["claude-cli", "anthropic", "fake"]),
    help=(
        "LLM provider. 'claude-cli' (default) shells out to the claude CLI "
        "using subscription auth. 'anthropic' uses the direct API and "
        "requires ANTHROPIC_API_KEY. 'fake' is for tests."
    ),
)
@click.option("--image", default="default", type=click.Choice(["default", "fake"]))
def run_cmd(brief_path: str, llm: str, image: str) -> None:
    """Run the full pipeline for a brief JSON file."""
    out = asyncio.run(_generate_variants_impl(
        Path(brief_path).read_text(),
        llm_provider=llm,
        image_provider=image,
    ))
    click.echo(json.dumps(out, indent=2))
