from click.testing import CliRunner

from adclip.cli import main


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "adclip" in result.output.lower()


def test_cli_formats_lists_formats():
    runner = CliRunner()
    result = runner.invoke(main, ["formats"])
    assert result.exit_code == 0
    assert "meta_feed_4x5" in result.output
