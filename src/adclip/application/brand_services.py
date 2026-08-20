"""Transport-neutral BrandKit and SourceLibrary application service."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from adclip.domain.brand import BrandKit, BrandVisual, BrandVoice, ClaimRecord, ProductProfile
from adclip.domain.source import SourceRecord
from adclip.storage.artifacts import ArtifactStore
from adclip.storage.database import Database
from adclip.storage.repositories import BrandRepository


class BrandApplication:
    """Create and inspect persistent brand, product, source, and claim context."""

    def __init__(self, *, database: Database | None = None) -> None:
        self.database = database or Database()
        self.repository = BrandRepository(self.database)
        self.artifacts = ArtifactStore(
            self.database.path.parent / "artifacts" / "sha256",
            database=self.database,
        )

    def create(
        self,
        *,
        slug: str,
        name: str,
        description: str = "",
        website_url: str | None = None,
        tone: list[str] | None = None,
        colors: list[str] | None = None,
    ) -> dict[str, object]:
        try:
            brand = BrandKit(
                slug=slug,
                name=name,
                description=description,
                website_url=website_url,
                voice=BrandVoice(tone=tone or []),
                visual=BrandVisual(colors=colors or []),
            )
            self.repository.save_brand(brand)
        except sqlite3.IntegrityError as exc:
            return {"ok": False, "error": f"Brand slug or ID already exists: {exc}"}
        except (ValueError, OSError) as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "brand": brand.model_dump(mode="json")}

    def list(self) -> dict[str, object]:
        try:
            brands = self.repository.list_brands()
        except (ValueError, OSError, sqlite3.DatabaseError) as exc:
            return {"ok": False, "error": str(exc)}
        return {
            "ok": True,
            "brands": [brand.model_dump(mode="json") for brand in brands],
        }

    def show(self, slug_or_id: str) -> dict[str, object]:
        try:
            snapshot = self.repository.snapshot(slug_or_id)
        except (ValueError, OSError, sqlite3.DatabaseError) as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, **snapshot}

    def add_product(
        self,
        slug_or_id: str,
        *,
        name: str,
        description: str = "",
        value_prop: str = "",
        audiences: list[str] | None = None,
        offers: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, object]:
        try:
            brand = self.repository.get_brand(slug_or_id)
            product = ProductProfile(
                brand_id=brand.id,
                name=name,
                description=description,
                value_prop=value_prop,
                audiences=audiences or [],
                offers=offers or [],
                metadata=metadata or {},
            )
            self.repository.save_product(product)
        except (ValueError, OSError, sqlite3.DatabaseError) as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "product": product.model_dump(mode="json")}

    def add_source(
        self,
        slug_or_id: str,
        *,
        title: str,
        kind: str = "other",
        rights: str = "unknown",
        product_id: str | None = None,
        file_path: str | None = None,
        uri: str | None = None,
        provenance: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, object]:
        if bool(file_path) == bool(uri):
            return {"ok": False, "error": "provide exactly one of file_path or uri"}
        try:
            brand = self.repository.get_brand(slug_or_id)
            if product_id is not None:
                valid_products = {item.id for item in self.repository.list_products(brand.id)}
                if product_id not in valid_products:
                    raise ValueError(f"Product {product_id} does not belong to brand {brand.slug}")
            sha256 = None
            resolved_uri = str(uri) if uri else ""
            source_kind = kind
            source_provenance = dict(provenance or {})
            source_metadata = dict(metadata or {})
            if file_path:
                artifact = self.artifacts.put_file(Path(file_path))
                resolved_uri = artifact.uri
                sha256 = artifact.sha256
                source_kind = "file" if kind == "other" else kind
                source_provenance.setdefault("original_path", str(Path(file_path).resolve()))
                source_metadata.setdefault("original_name", artifact.original_name)
                source_metadata.setdefault("media_type", artifact.media_type)
            source = SourceRecord(
                brand_id=brand.id,
                product_id=product_id,
                kind=source_kind,  # type: ignore[arg-type]
                title=title,
                uri=resolved_uri,
                rights=rights,  # type: ignore[arg-type]
                sha256=sha256,
                provenance=source_provenance,
                metadata=source_metadata,
            )
            self.repository.save_source(source)
        except (FileNotFoundError, ValueError, OSError, sqlite3.DatabaseError) as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "source": source.model_dump(mode="json")}

    def add_claim(
        self,
        slug_or_id: str,
        *,
        text: str,
        status: str = "unreviewed",
        product_id: str | None = None,
        evidence_source_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, object]:
        try:
            brand = self.repository.get_brand(slug_or_id)
            valid_products = {item.id for item in self.repository.list_products(brand.id)}
            if product_id is not None and product_id not in valid_products:
                raise ValueError(f"Product {product_id} does not belong to brand {brand.slug}")
            evidence = evidence_source_ids or []
            valid_sources = {item.id for item in self.repository.list_sources(brand.id)}
            unknown = sorted(set(evidence) - valid_sources)
            if unknown:
                raise ValueError(f"Evidence sources do not belong to brand {brand.slug}: {unknown}")
            claim = ClaimRecord(
                brand_id=brand.id,
                product_id=product_id,
                text=text,
                status=status,  # type: ignore[arg-type]
                evidence_source_ids=evidence,
                metadata=metadata or {},
            )
            self.repository.save_claim(claim)
        except (ValueError, OSError, sqlite3.DatabaseError) as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "claim": claim.model_dump(mode="json")}
