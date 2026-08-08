"""adclip CLI — standalone adapter over shared application services."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import click

from adclip import _env

_env.load()

from adclip.application import AdclipApplication
from adclip.model_routing import IMAGE_ROUTES, VIDEO_ROUTES
from adclip.providers.registry import default_text_registry


_TEXT_PROVIDER_TYPE = click.Choice(
    default_text_registry().names(include_aliases=True),
    case_sensitive=True,
)
_MEDIA_PROVIDER_TYPE = click.Choice(["default", "fal", "openai", "fake"])
_IMAGE_ROUTE_TYPE = click.Choice(["default", *sorted(IMAGE_ROUTES)])
_VIDEO_ROUTE_TYPE = click.Choice(["default", *sorted(VIDEO_ROUTES)])


@click.group()
def main() -> None:
    """adclip — model-agnostic ad creative generation."""


@main.command()
def status() -> None:
    """Show runtime mode, configured models, routes, and providers."""
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


@main.command("routes")
@click.option(
    "--modality",
    type=click.Choice(["image", "video"]),
    default=None,
    help="Limit output to one modality.",
)
def routes_cmd(modality: str | None) -> None:
    """List task routes, preferred models, fallbacks, and unmet requirements."""
    click.echo(json.dumps(AdclipApplication.list_media_routes(modality), indent=2))


@main.command("route-recommend")
@click.argument("modality", type=click.Choice(["image", "video"]))
@click.option(
    "--text-heavy",
    is_flag=True,
)
@click.option("--reference-images", default=0, type=int)
@click.option("--reference-media", default=0, type=int)
@click.option(
    "--existing-video",
    is_flag=True,
)
@click.option(
    "--vector-output",
    is_flag=True,
)
@click.option(
    "--premium",
    is_flag=True,
)
@click.option(
    "--high-volume",
    is_flag=True,
)
@click.option(
    "--draft",
    is_flag=True,
)
@click.option(
    "--multi-shot",
    is_flag=True,
)
@click.option(
    "--brand-control",
    is_flag=True,
)
def route_recommend_cmd(modality: str, **requirements: object) -> None:
    """Recommend an inspectable route from explicit creative requirements."""
    click.echo(
        json.dumps(
            AdclipApplication.recommend_media_route(modality, **requirements),
            indent=2,
        )
    )


@main.command("estimate")
@click.argument("brief_path", type=click.Path(exists=True))
@click.option("--image-route", default="default", type=_IMAGE_ROUTE_TYPE)
@click.option("--image-model", default=None)
@click.option("--video-route", default="default", type=_VIDEO_ROUTE_TYPE)
@click.option(
    "--video-model",
    default=None,
)
def estimate_cmd(
    brief_path: str,
    image_route: str,
    image_model: str | None,
    video_route: str,
    video_model: str | None,
) -> None:
    """Estimate cost for the selected media routes without generating."""
    out = AdclipApplication().estimate_cost_json(
        Path(brief_path).read_text(),
        image_route_name=image_route,
        image_model_name=image_model,
        video_route_name=video_route,
        video_model_name=video_model,
    )
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
)
@click.option(
    "--text-model",
    "--llm-model",
    "text_model",
    default=None,
)
@click.option(
    "--image-route",
    default="default",
    type=_IMAGE_ROUTE_TYPE,
    show_default=True,
    help="Task route. Explicit provider/model values override its primary target.",
)
@click.option(
    "--image-provider",
    "--image",
    "image_provider",
    default="default",
    type=_MEDIA_PROVIDER_TYPE,
    show_default=True,
)
@click.option("--image-model", default=None)
@click.option(
    "--video-route",
    default="default",
    type=_VIDEO_ROUTE_TYPE,
    show_default=True,
)
@click.option(
    "--video-provider",
    "--video",
    "video_provider",
    default="default",
    type=click.Choice(["default", "fal", "fake"]),
    show_default=True,
)
@click.option("--video-model", default=None)
def run_cmd(
    brief_path: str,
    text_provider: str,
    text_model: str | None,
    image_route: str,
    image_provider: str,
    image_model: str | None,
    video_route: str,
    video_provider: str,
    video_model: str | None,
) -> None:
    """Run the creative pipeline with task-routed media models."""
    out = asyncio.run(
        AdclipApplication().generate_variants_json(
            Path(brief_path).read_text(),
            text_provider_name=text_provider,
            text_model_name=text_model,
            image_route_name=image_route,
            image_provider_name=image_provider,
            image_model_name=image_model,
            video_route_name=video_route,
            video_provider_name=video_provider,
            video_model_name=video_model,
        )
    )
    click.echo(json.dumps(out, indent=2))


@main.command("bakeoff")
@click.option("--modality", type=click.Choice(["image", "video"]), required=True)
@click.option(
    "--routes",
    "routes_value",
    default=None,
    help="Comma-separated routes. Defaults to the standard comparison set.",
)
@click.option("--repetitions", default=1, type=click.IntRange(min=1, max=10))
@click.option(
    "--output-dir",
    default="adclip_bakeoff",
    type=click.Path(file_okay=False),
    show_default=True,
)
@click.option(
    "--execute",
    is_flag=True,
    help="Actually call providers. Without this flag only a JSON plan is written.",
)
def bakeoff_cmd(
    modality: str,
    routes_value: str | None,
    repetitions: int,
    output_dir: str,
    execute: bool,
) -> None:
    """Build or execute the recurring media-model bake-off suite."""
    from adclip.evals.media_bakeoff import build_bakeoff_plan, run_bakeoff

    selected_routes = (
        [part.strip() for part in routes_value.split(",") if part.strip()]
        if routes_value
        else None
    )
    try:
        jobs = build_bakeoff_plan(
            modality,  # type: ignore[arg-type]
            routes=selected_routes,
            repetitions=repetitions,
        )
        result = run_bakeoff(jobs, output_dir=output_dir, execute=execute)
    except (RuntimeError, ValueError) as exc:
        result = {"ok": False, "error": str(exc)}
    click.echo(json.dumps(result, indent=2))


from adclip.email.cli import email_group
from adclip.performance.cli import performance_group

main.add_command(email_group)
main.add_command(performance_group)
