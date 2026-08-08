from click.testing import CliRunner

from adclip.cli import main


def test_main_cli_exposes_performance_group():
    result = CliRunner().invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "performance" in result.output
