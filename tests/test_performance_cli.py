from click.testing import CliRunner

from adclip.performance.cli import performance_group


def test_performance_cli_exposes_learning_commands():
    result = CliRunner().invoke(performance_group, ["--help"])
    assert result.exit_code == 0
    assert "link-meta" in result.output
    assert "sync-meta" in result.output
    assert "report" in result.output
    assert "compare" in result.output
