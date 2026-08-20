"""SQLite repositories for BrandKit and SourceLibrary state."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from adclip.domain.brand import BrandKit, ClaimRecord, ProductProfile
from adclip.domain.source import SourceRecord
from adclip.storage.database import Database


def _dump(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _load(value: str) -> object:
    return json.loads(value)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BrandRepository:
    """Authoritative persistence for brands and their source/claim context."""

    def __init__(self, database: Database | None = None) -> None:
        self.database = database or Database()
        self.database.migrate()

    def save_brand(self, brand: BrandKit) -> BrandKit:
        brand.updated_at = datetime.now(timezone.utc)
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO brands(id, slug, name, description, website_url, voice_json, visual_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    slug=excluded.slug, name=excluded.name, description=excluded.description,
                    website_url=excluded.website_url, voice_json=excluded.voice_json,
                    visual_json=excluded.visual_json, updated_at=excluded.updated_at
                """,
                (
                    brand.id, brand.slug, brand.name, brand.description, brand.website_url,
                    brand.voice.model_dump_json(), brand.visual.model_dump_json(),
                    brand.created_at.isoformat(), brand.updated_at.isoformat(),
                ),
            )
            connection.commit()
        return brand

    def get_brand(self, slug_or_id: str) -> BrandKit:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM brands WHERE slug = ? OR id = ?", (slug_or_id, slug_or_id)
            ).fetchone()
        if row is None:
            raise ValueError(f"Brand not found: {slug_or_id}")
        return BrandKit.model_validate({
            "id": row["id"], "slug": row["slug"], "name": row["name"],
            "description": row["description"], "website_url": row["website_url"],
            "voice": _load(row["voice_json"]), "visual": _load(row["visual_json"]),
            "created_at": row["created_at"], "updated_at": row["updated_at"],
        })

    def list_brands(self) -> list[BrandKit]:
        with self.database.connect() as connection:
            rows = connection.execute("SELECT slug FROM brands ORDER BY name, slug").fetchall()
        return [self.get_brand(str(row["slug"])) for row in rows]

    def save_product(self, product: ProductProfile) -> ProductProfile:
        product.updated_at = datetime.now(timezone.utc)
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO products(id, brand_id, name, description, value_prop, audience_json, offers_json, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name, description=excluded.description, value_prop=excluded.value_prop,
                    audience_json=excluded.audience_json, offers_json=excluded.offers_json,
                    metadata_json=excluded.metadata_json, updated_at=excluded.updated_at
                """,
                (
                    product.id, product.brand_id, product.name, product.description,
                    product.value_prop, _dump(product.audiences), _dump(product.offers),
                    _dump(product.metadata), product.created_at.isoformat(), product.updated_at.isoformat(),
                ),
            )
            connection.commit()
        return product

    def list_products(self, brand_id: str) -> list[ProductProfile]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM products WHERE brand_id = ? ORDER BY name, id", (brand_id,)
            ).fetchall()
        return [ProductProfile.model_validate({
            "id": row["id"], "brand_id": row["brand_id"], "name": row["name"],
            "description": row["description"], "value_prop": row["value_prop"],
            "audiences": _load(row["audience_json"]), "offers": _load(row["offers_json"]),
            "metadata": _load(row["metadata_json"]), "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }) for row in rows]

    def save_source(self, source: SourceRecord) -> SourceRecord:
        source.updated_at = datetime.now(timezone.utc)
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO sources(id, brand_id, product_id, kind, title, uri, rights, sha256, provenance_json, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    product_id=excluded.product_id, kind=excluded.kind, title=excluded.title,
                    uri=excluded.uri, rights=excluded.rights, sha256=excluded.sha256,
                    provenance_json=excluded.provenance_json, metadata_json=excluded.metadata_json,
                    updated_at=excluded.updated_at
                """,
                (
                    source.id, source.brand_id, source.product_id, source.kind, source.title,
                    source.uri, source.rights, source.sha256, _dump(source.provenance),
                    _dump(source.metadata), source.created_at.isoformat(), source.updated_at.isoformat(),
                ),
            )
            connection.commit()
        return source

    def list_sources(self, brand_id: str) -> list[SourceRecord]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM sources WHERE brand_id = ? ORDER BY created_at, id", (brand_id,)
            ).fetchall()
        return [SourceRecord.model_validate({
            "id": row["id"], "brand_id": row["brand_id"], "product_id": row["product_id"],
            "kind": row["kind"], "title": row["title"], "uri": row["uri"],
            "rights": row["rights"], "sha256": row["sha256"],
            "provenance": _load(row["provenance_json"]), "metadata": _load(row["metadata_json"]),
            "created_at": row["created_at"], "updated_at": row["updated_at"],
        }) for row in rows]

    def save_claim(self, claim: ClaimRecord) -> ClaimRecord:
        claim.updated_at = datetime.now(timezone.utc)
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO claims(id, brand_id, product_id, text, status, evidence_source_ids_json, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    product_id=excluded.product_id, text=excluded.text, status=excluded.status,
                    evidence_source_ids_json=excluded.evidence_source_ids_json,
                    metadata_json=excluded.metadata_json, updated_at=excluded.updated_at
                """,
                (
                    claim.id, claim.brand_id, claim.product_id, claim.text, claim.status,
                    _dump(claim.evidence_source_ids), _dump(claim.metadata),
                    claim.created_at.isoformat(), claim.updated_at.isoformat(),
                ),
            )
            connection.commit()
        return claim

    def list_claims(self, brand_id: str) -> list[ClaimRecord]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM claims WHERE brand_id = ? ORDER BY created_at, id", (brand_id,)
            ).fetchall()
        return [ClaimRecord.model_validate({
            "id": row["id"], "brand_id": row["brand_id"], "product_id": row["product_id"],
            "text": row["text"], "status": row["status"],
            "evidence_source_ids": _load(row["evidence_source_ids_json"]),
            "metadata": _load(row["metadata_json"]), "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }) for row in rows]

    def snapshot(self, slug_or_id: str) -> dict[str, object]:
        brand = self.get_brand(slug_or_id)
        return {
            "brand": brand.model_dump(mode="json"),
            "products": [item.model_dump(mode="json") for item in self.list_products(brand.id)],
            "sources": [item.model_dump(mode="json") for item in self.list_sources(brand.id)],
            "claims": [item.model_dump(mode="json") for item in self.list_claims(brand.id)],
        }
