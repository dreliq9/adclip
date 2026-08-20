"""CLI diagnostics for adclip local persistence."""

from __future__ import annotations

import json

import click

from adclip.storage.database import Database, default_data_dir


@click.group("storage")
def storage_group() -> None:
    """Inspect and migrate authoritative local storage."""


@storage_group.command("status")
def status_cmd() -> None:
    database = Database()
    click.echo(json.dumps({
        "ok": True,
        "data_dir": str(default_data_dir()),
        "database": str(database.path),
        "schema_version": database.schema_version(),
        "database_exists": database.path.exists(),
        "artifact_root": str(database.path.parent / "artifacts" / "sha256"),
    }, indent=2))


@storage_group.command("migrate")
def migrate_cmd() -> None:
    database = Database()
    version = database.migrate()
    click.echo(json.dumps({
        "ok": True,
        "database": str(database.path),
        "schema_version": version,
    }, indent=2))
