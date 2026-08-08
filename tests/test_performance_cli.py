from click.testing import CliRunner

from adclip.performance.cli import performance_group


def test_performance_cli_exposes_learning_commands():
    result = CliRunner().invoke(performance_group, ["--help"])
    assert result.exit_code == 0
    for command in (
        "link-meta",
        "sync-meta",
        "report",
        "compare",
        "experiment-create",
        "experiments",
        "experiment-evaluate",
        "next-test",
    ):
        assert command in result.output
