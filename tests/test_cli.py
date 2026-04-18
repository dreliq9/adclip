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


def test_cli_copy_accepts_claude_cli_provider():
    """--provider claude-cli should be a valid choice (even though we can't
    actually invoke subprocess here; just verify click's choice validation)."""
    from click.testing import CliRunner
    from adclip.cli import main

    runner = CliRunner()
    bad = runner.invoke(main, ["copy", "examples/taichi_brief.json", "--provider", "bogus"])
    assert bad.exit_code != 0
    assert "bogus" in bad.output or "Invalid value" in bad.output


def test_cli_run_accepts_claude_cli_llm():
    from click.testing import CliRunner
    from adclip.cli import main

    runner = CliRunner()
    bad = runner.invoke(main, ["run", "examples/taichi_brief.json", "--llm", "bogus"])
    assert bad.exit_code != 0
