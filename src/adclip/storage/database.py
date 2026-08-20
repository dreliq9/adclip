"""SQLite database bootstrap and forward-only migrations."""

from __future__ import annotations

import os
import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


MIGRATIONS: tuple[tuple[int, str], ...] = (
    (
        1,
        """
        CREATE TABLE IF NOT EXISTS brands (
            id TEXT PRIMARY KEY,
            slug TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            website_url TEXT,
            voice_json TEXT NOT NULL DEFAULT '{}',
            visual_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS products (
            id TEXT PRIMARY KEY,
            brand_id TEXT NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            value_prop TEXT NOT NULL DEFAULT '',
            audience_json TEXT NOT NULL DEFAULT '[]',
            offers_json TEXT NOT NULL DEFAULT '[]',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_products_brand_id ON products(brand_id);

        CREATE TABLE IF NOT EXISTS sources (
            id TEXT PRIMARY KEY,
            brand_id TEXT NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
            product_id TEXT REFERENCES products(id) ON DELETE SET NULL,
            kind TEXT NOT NULL,
            title TEXT NOT NULL,
            uri TEXT NOT NULL,
            rights TEXT NOT NULL DEFAULT 'unknown',
            sha256 TEXT,
            provenance_json TEXT NOT NULL DEFAULT '{}',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_sources_brand_id ON sources(brand_id);
        CREATE INDEX IF NOT EXISTS idx_sources_product_id ON sources(product_id);
        CREATE INDEX IF NOT EXISTS idx_sources_sha256 ON sources(sha256);

        CREATE TABLE IF NOT EXISTS claims (
            id TEXT PRIMARY KEY,
            brand_id TEXT NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
            product_id TEXT REFERENCES products(id) ON DELETE SET NULL,
            text TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'unreviewed',
            evidence_source_ids_json TEXT NOT NULL DEFAULT '[]',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_claims_brand_id ON claims(brand_id);
        CREATE INDEX IF NOT EXISTS idx_claims_product_id ON claims(product_id);

        CREATE TABLE IF NOT EXISTS artifacts (
            sha256 TEXT PRIMARY KEY,
            size_bytes INTEGER NOT NULL,
            media_type TEXT,
            original_name TEXT,
            created_at TEXT NOT NULL
        );
        """,
    ),
)


def default_data_dir() -> Path:
    override = os.environ.get("ADCLIP_DATA_DIR")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "adclip"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "adclip"
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "adclip"
    return Path.home() / ".local" / "share" / "adclip"


def default_database_path() -> Path:
    override = os.environ.get("ADCLIP_DB_PATH")
    if override:
        return Path(override).expanduser()
    return default_data_dir() / "adclip.db"


class Database:
    """Small SQLite wrapper with explicit migrations and transactional access."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_database_path()

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        return connection

    def migrate(self) -> int:
        with self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.commit()
            applied = {
                int(row["version"])
                for row in connection.execute("SELECT version FROM schema_migrations")
            }
            for version, sql in MIGRATIONS:
                if version in applied:
                    continue
                try:
                    connection.executescript(
                        "BEGIN IMMEDIATE;\n"
                        + sql
                        + f"\nINSERT INTO schema_migrations(version) VALUES ({version});\n"
                        + "COMMIT;"
                    )
                except Exception:
                    connection.rollback()
                    raise
        return self.schema_version()

    def schema_version(self) -> int:
        if not self.path.exists():
            return 0
        with self.connect() as connection:
            row = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
            ).fetchone()
            if row is None:
                return 0
            value = connection.execute(
                "SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations"
            ).fetchone()
            return int(value["version"])

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        self.migrate()
        connection = self.connect()
        try:
            connection.execute("BEGIN")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
