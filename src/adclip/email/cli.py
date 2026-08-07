"""CLI group for email campaign generation and HTML editing."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import click

from adclip.application.email_services import EmailApplication
from adclip.providers.registry import default_text_registry


_TEXT_PROVIDER_TYPE = click.Choice(
    default_text_registry().names(include_aliases=True),
    case_sensitive=True,
)


@click.group("email")
def email_group() -> None:
    """Generate, render, lint, and edit responsive email campaigns."""


@email_group.command("generate")
@click.argument("brief_path", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--provider",
    default="default",
    type=_TEXT_PROVIDER_TYPE,
    show_default=True,
)
@click.option("--model", default=None)
def generate_cmd(
    brief_path: str,
    provider: str,
    model: str | None,
) -> None:
    """Generate and export a complete email sequence from a JSON brief."""

    result = asyncio.run(
        EmailApplication().generate_campaign_json(
            Path(brief_path).read_text(encoding="utf-8"),
            provider_name=provider,
            model_name=model,
        )
    )
    click.echo(json.dumps(result, indent=2))


@email_group.command("render")
@click.argument("brief_path", type=click.Path(exists=True, dir_okay=False))
@click.argument("message_path", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--output-dir",
    required=True,
    type=click.Path(file_okay=False),
)
def render_cmd(
    brief_path: str,
    message_path: str,
    output_dir: str,
) -> None:
    """Render one structured message to HTML, text, headers, and lint JSON."""

    result = EmailApplication().render_json(
        Path(brief_path).read_text(encoding="utf-8"),
        Path(message_path).read_text(encoding="utf-8"),
    )
    if "html" in result:
        root = Path(output_dir)
        root.mkdir(parents=True, exist_ok=True)
        (root / "email.html").write_text(str(result["html"]), encoding="utf-8")
        (root / "email.txt").write_text(str(result["text"]), encoding="utf-8")
        (root / "headers.json").write_text(
            json.dumps(result["headers"], indent=2),
            encoding="utf-8",
        )
        (root / "lint.json").write_text(
            json.dumps(result["lint"], indent=2),
            encoding="utf-8",
        )
        result = {
            "ok": result["ok"],
            "output_dir": str(root.resolve()),
            "lint": result["lint"],
        }
    click.echo(json.dumps(result, indent=2))


@email_group.command("lint")
@click.argument("html_path", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--context",
    "context_path",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Optional EmailLintContext JSON file.",
)
@click.option(
    "--plain-text",
    "plain_text_path",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
)
def lint_cmd(
    html_path: str,
    context_path: str | None,
    plain_text_path: str | None,
) -> None:
    """Lint rendered or imported email HTML without executing it."""

    context_json = (
        Path(context_path).read_text(encoding="utf-8")
        if context_path
        else "{}"
    )
    plain_text = (
        Path(plain_text_path).read_text(encoding="utf-8")
        if plain_text_path
        else None
    )
    result = EmailApplication().lint_html_json(
        Path(html_path).read_text(encoding="utf-8"),
        context_json,
        plain_text,
    )
    click.echo(json.dumps(result, indent=2))


@email_group.command("patch-html")
@click.argument("html_path", type=click.Path(exists=True, dir_okay=False))
@click.argument("patches_path", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--context",
    "context_path",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
)
@click.option("--output", required=True, type=click.Path(dir_okay=False))
def patch_html_cmd(
    html_path: str,
    patches_path: str,
    context_path: str | None,
    output: str,
) -> None:
    """Apply marker-targeted edits to rendered email HTML."""

    context_json = (
        Path(context_path).read_text(encoding="utf-8")
        if context_path
        else "{}"
    )
    result = EmailApplication().patch_html_json(
        Path(html_path).read_text(encoding="utf-8"),
        Path(patches_path).read_text(encoding="utf-8"),
        context_json,
    )
    if "html" in result:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(str(result["html"]), encoding="utf-8")
        result = {
            "ok": result["ok"],
            "output": str(output_path.resolve()),
            "lint": result["lint"],
        }
    click.echo(json.dumps(result, indent=2))


@email_group.command("patch-message")
@click.argument("message_path", type=click.Path(exists=True, dir_okay=False))
@click.argument("patches_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--output", required=True, type=click.Path(dir_okay=False))
def patch_message_cmd(
    message_path: str,
    patches_path: str,
    output: str,
) -> None:
    """Edit the structured message document before rendering HTML."""

    result = EmailApplication().patch_message_json(
        Path(message_path).read_text(encoding="utf-8"),
        Path(patches_path).read_text(encoding="utf-8"),
    )
    if "message" in result:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(result["message"], indent=2),
            encoding="utf-8",
        )
        result = {"ok": True, "output": str(output_path.resolve())}
    click.echo(json.dumps(result, indent=2))
