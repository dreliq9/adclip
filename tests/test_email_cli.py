from click.testing import CliRunner

from adclip.email.cli import email_group


def test_email_cli_exposes_authoring_commands():
    result = CliRunner().invoke(email_group, ["--help"])
    assert result.exit_code == 0
    for command in (
        "generate",
        "render",
        "lint",
        "patch-html",
        "patch-message",
    ):
        assert command in result.output
