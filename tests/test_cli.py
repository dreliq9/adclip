import inspect

from click.testing import CliRunner

import adclip.cli
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


def test_cli_status_reports_runtime_and_providers():
    runner = CliRunner()
    result = runner.invoke(main, ["status"])
    assert result.exit_code == 0
    assert '"runtime"' in result.output
    assert '"llm_providers"' in result.output


def test_cli_is_not_coupled_to_mcp_implementations():
    assert "adclip.mcp" not in inspect.getsource(adclip.cli)


def test_cli_copy_accepts_claude_cli_provider():
    """Invalid provider names should fail at Click validation."""
    runner = CliRunner()
    bad = runner.invoke(
        main,
        ["copy", "examples/taichi_brief.json", "--provider", "bogus"],
    )
    assert bad.exit_code != 0
    assert "bogus" in bad.output or "Invalid value" in bad.output


def test_cli_run_accepts_claude_cli_llm():
    runner = CliRunner()
    bad = runner.invoke(
        main,
        ["run", "examples/taichi_brief.json", "--llm", "bogus"],
    )
    assert bad.exit_code != 0
