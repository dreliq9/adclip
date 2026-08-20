import pytest

from adclip.domain.brand import BrandKit, ClaimRecord, ProductProfile
from adclip.domain.source import SourceRecord
from adclip.storage.database import Database
from adclip.storage.repositories import BrandRepository


def test_repository_refuses_cross_brand_reassignment(tmp_path):
    repository = BrandRepository(Database(tmp_path / "adclip.db"))
    one = repository.save_brand(BrandKit(slug="one", name="One"))
    two = repository.save_brand(BrandKit(slug="two", name="Two"))

    product = repository.save_product(ProductProfile(brand_id=one.id, name="Product"))
    moved = product.model_copy(update={"brand_id": two.id})

    with pytest.raises(ValueError, match="another brand"):
        repository.save_product(moved)


def test_claim_evidence_is_relational_and_brand_scoped(tmp_path):
    database = Database(tmp_path / "adclip.db")
    repository = BrandRepository(database)
    one = repository.save_brand(BrandKit(slug="one", name="One"))
    two = repository.save_brand(BrandKit(slug="two", name="Two"))

    source = repository.save_source(
        SourceRecord(
            brand_id=one.id,
            title="Evidence",
            uri="https://example.com/evidence",
        )
    )
    claim = repository.save_claim(
        ClaimRecord(
            brand_id=one.id,
            text="Supported claim",
            evidence_source_ids=[source.id],
        )
    )

    with database.connect() as connection:
        row = connection.execute(
            "SELECT source_id FROM claim_evidence WHERE claim_id = ?",
            (claim.id,),
        ).fetchone()
    assert row["source_id"] == source.id

    foreign_claim = ClaimRecord(
        brand_id=two.id,
        text="Wrong evidence owner",
        evidence_source_ids=[source.id],
    )
    with pytest.raises(ValueError, match="another brand"):
        repository.save_claim(foreign_claim)
