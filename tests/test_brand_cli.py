import json

from click.testing import CliRunner

from adclip.entry import main


def test_storage_and_brand_cli_use_isolated_database(tmp_path, monkeypatch):
    monkeypatch.setenv("ADCLIP_DB_PATH", str(tmp_path / "adclip.db"))
    runner = CliRunner()

    migrated = runner.invoke(main, ["storage", "migrate"])
    assert migrated.exit_code == 0, migrated.output
    assert json.loads(migrated.output)["schema_version"] == 1

    created = runner.invoke(
        main,
        [
            "brand",
            "create",
            "--slug",
            "morrow",
            "--name",
            "Morrow",
            "--tone",
            "calm,specific",
        ],
    )
    assert created.exit_code == 0, created.output
    payload = json.loads(created.output)
    assert payload["ok"] is True
    assert payload["brand"]["voice"]["tone"] == ["calm", "specific"]

    listed = runner.invoke(main, ["brand", "list"])
    assert listed.exit_code == 0, listed.output
    brands = json.loads(listed.output)["brands"]
    assert [item["slug"] for item in brands] == ["morrow"]

    shown = runner.invoke(main, ["brand", "show", "morrow"])
    assert shown.exit_code == 0, shown.output
    assert json.loads(shown.output)["brand"]["name"] == "Morrow"
