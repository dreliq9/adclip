from adclip.application.brand_services import BrandApplication
from adclip.storage.database import Database


def test_brand_product_source_claim_round_trip(tmp_path):
    database = Database(tmp_path / "adclip.db")
    app = BrandApplication(database=database)

    created = app.create(
        slug="morrow",
        name="Morrow",
        description="Simple skincare",
        website_url="https://example.com",
        tone=["calm", "specific"],
        colors=["#F6F1E8", "#1F2937"],
    )
    assert created["ok"] is True
    brand_id = created["brand"]["id"]

    product_result = app.add_product(
        "morrow",
        name="Daily Barrier Moisturizer",
        value_prop="Lightweight daily moisture",
        audiences=["Adults with dry or sensitive skin"],
        offers=["20% off first order"],
    )
    assert product_result["ok"] is True
    product_id = product_result["product"]["id"]

    source_file = tmp_path / "product-notes.txt"
    source_file.write_text("Ceramides and squalane. Fragrance free.", encoding="utf-8")
    source_result = app.add_source(
        "morrow",
        title="Product notes",
        kind="reference",
        rights="owned",
        product_id=product_id,
        file_path=str(source_file),
    )
    assert source_result["ok"] is True
    assert source_result["source"]["uri"].startswith("artifact://sha256/")
    assert len(source_result["source"]["sha256"]) == 64
    source_id = source_result["source"]["id"]

    claim_result = app.add_claim(
        "morrow",
        text="Fragrance free",
        status="approved",
        product_id=product_id,
        evidence_source_ids=[source_id],
    )
    assert claim_result["ok"] is True

    snapshot = app.show(brand_id)
    assert snapshot["ok"] is True
    assert snapshot["brand"]["slug"] == "morrow"
    assert snapshot["products"][0]["id"] == product_id
    assert snapshot["sources"][0]["id"] == source_id
    assert snapshot["claims"][0]["evidence_source_ids"] == [source_id]


def test_claim_rejects_foreign_evidence_source(tmp_path):
    app = BrandApplication(database=Database(tmp_path / "adclip.db"))
    app.create(slug="one", name="One")
    app.create(slug="two", name="Two")
    source = app.add_source("one", title="Source", uri="https://example.com/source")
    result = app.add_claim(
        "two",
        text="Unsupported foreign evidence",
        evidence_source_ids=[source["source"]["id"]],
    )
    assert result["ok"] is False
    assert "do not belong" in result["error"]
