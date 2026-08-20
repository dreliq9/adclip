"""Standalone CLI for persistent BrandKit and SourceLibrary state."""

from __future__ import annotations

import json

import click

from adclip.application.brand_services import BrandApplication


def _csv(value: str | None) -> list[str]:
    return [part.strip() for part in (value or "").split(",") if part.strip()]


@click.group("brand")
def brand_group() -> None:
    """Manage persistent brands, products, sources, and claims."""


@brand_group.command("create")
@click.option("--slug", required=True)
@click.option("--name", required=True)
@click.option("--description", default="")
@click.option("--website-url", default=None)
@click.option("--tone", default=None, help="Comma-separated brand tone descriptors.")
@click.option("--colors", default=None, help="Comma-separated brand colors or tokens.")
def create_cmd(slug: str, name: str, description: str, website_url: str | None, tone: str | None, colors: str | None) -> None:
    result = BrandApplication().create(
        slug=slug,
        name=name,
        description=description,
        website_url=website_url,
        tone=_csv(tone),
        colors=_csv(colors),
    )
    click.echo(json.dumps(result, indent=2))


@brand_group.command("list")
def list_cmd() -> None:
    click.echo(json.dumps(BrandApplication().list(), indent=2))


@brand_group.command("show")
@click.argument("brand")
def show_cmd(brand: str) -> None:
    click.echo(json.dumps(BrandApplication().show(brand), indent=2))


@brand_group.command("add-product")
@click.argument("brand")
@click.option("--name", required=True)
@click.option("--description", default="")
@click.option("--value-prop", default="")
@click.option("--audiences", default=None, help="Comma-separated audience descriptions.")
@click.option("--offers", default=None, help="Comma-separated offers.")
def add_product_cmd(brand: str, name: str, description: str, value_prop: str, audiences: str | None, offers: str | None) -> None:
    result = BrandApplication().add_product(
        brand,
        name=name,
        description=description,
        value_prop=value_prop,
        audiences=_csv(audiences),
        offers=_csv(offers),
    )
    click.echo(json.dumps(result, indent=2))


@brand_group.command("add-source")
@click.argument("brand")
@click.option("--title", required=True)
@click.option("--kind", default="other")
@click.option("--rights", default="unknown")
@click.option("--product-id", default=None)
@click.option("--file", "file_path", type=click.Path(exists=True, dir_okay=False), default=None)
@click.option("--uri", default=None)
def add_source_cmd(brand: str, title: str, kind: str, rights: str, product_id: str | None, file_path: str | None, uri: str | None) -> None:
    result = BrandApplication().add_source(
        brand,
        title=title,
        kind=kind,
        rights=rights,
        product_id=product_id,
        file_path=file_path,
        uri=uri,
    )
    click.echo(json.dumps(result, indent=2))


@brand_group.command("add-claim")
@click.argument("brand")
@click.option("--text", required=True)
@click.option("--status", type=click.Choice(["unreviewed", "approved", "restricted", "rejected"]), default="unreviewed")
@click.option("--product-id", default=None)
@click.option("--evidence", default=None, help="Comma-separated source IDs.")
def add_claim_cmd(brand: str, text: str, status: str, product_id: str | None, evidence: str | None) -> None:
    result = BrandApplication().add_claim(
        brand,
        text=text,
        status=status,
        product_id=product_id,
        evidence_source_ids=_csv(evidence),
    )
    click.echo(json.dumps(result, indent=2))
