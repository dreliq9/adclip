"""adclip CLI — thin wrapper over the MCP tool implementations."""

from __future__ import annotations

import json
from pathlib import Path

import click

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
@click.option("--provider", default="default", type=click.Choice(["default", "fake"]))
def copy_cmd(brief_path: str, provider: str) -> None:
    """Generate ad copy (no images/video)."""
    out = _generate_copy_impl(Path(brief_path).read_text(), provider_name=provider)
    click.echo(json.dumps(out, indent=2))


@main.command("run")
@click.argument("brief_path", type=click.Path(exists=True))
@click.option("--llm", default="default", type=click.Choice(["default", "fake"]))
@click.option("--image", default="default", type=click.Choice(["default", "fake"]))
def run_cmd(brief_path: str, llm: str, image: str) -> None:
    """Run the full pipeline for a brief JSON file."""
    out = _generate_variants_impl(
        Path(brief_path).read_text(),
        llm_provider=llm,
        image_provider=image,
    )
    click.echo(json.dumps(out, indent=2))
