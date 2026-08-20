from pathlib import Path

from adclip.storage.artifacts import ArtifactStore
from adclip.storage.database import Database


def test_database_migrates_idempotently(tmp_path):
    database = Database(tmp_path / "adclip.db")
    assert database.schema_version() == 0
    assert database.migrate() == 1
    assert database.migrate() == 1

    with database.connect() as connection:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert {"brands", "products", "sources", "claims", "artifacts"} <= tables


def test_artifact_store_is_content_addressed_and_deduplicated(tmp_path):
    database = Database(tmp_path / "adclip.db")
    store = ArtifactStore(tmp_path / "artifacts" / "sha256", database=database)

    first = store.put_bytes(b"same payload", original_name="first.txt")
    second = store.put_bytes(b"same payload", original_name="second.txt")

    assert first.sha256 == second.sha256
    assert first.path == second.path
    assert first.path.read_bytes() == b"same payload"
    assert store.resolve(first.uri) == first.path

    with database.connect() as connection:
        count = connection.execute("SELECT COUNT(*) AS count FROM artifacts").fetchone()["count"]
    assert count == 1


def test_artifact_store_imports_files(tmp_path):
    source = tmp_path / "logo.svg"
    source.write_text("<svg></svg>", encoding="utf-8")
    database = Database(tmp_path / "state" / "adclip.db")
    store = ArtifactStore(tmp_path / "state" / "artifacts" / "sha256", database=database)

    artifact = store.put_file(source)

    assert artifact.original_name == "logo.svg"
    assert artifact.media_type == "image/svg+xml"
    assert Path(artifact.path).is_file()
