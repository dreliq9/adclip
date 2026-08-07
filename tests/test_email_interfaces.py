import inspect

from click.testing import CliRunner

from adclip.cli import main
from adclip.mcp.email_tools import register


class _CaptureMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(function):
            self.tools[function.__name__] = function
            return function

        return decorator


def test_email_cli_group_exposes_authoring_commands():
    result = CliRunner().invoke(main, ["email", "--help"])
    assert result.exit_code == 0
    for command in (
        "brief-validate",
        "scaffold",
        "generate",
        "edit",
        "validate",
        "validate-html",
        "status",
    ):
        assert command in result.output


def test_email_mcp_surface_has_model_and_edit_contracts():
    mcp = _CaptureMCP()
    register(mcp)
    assert {
        "adclip_email_brief_validate",
        "adclip_email_scaffold",
        "adclip_email_generate",
        "adclip_email_edit",
        "adclip_email_validate",
        "adclip_email_validate_html",
        "adclip_email_campaign_status",
    } <= set(mcp.tools)
    generate_signature = inspect.signature(mcp.tools["adclip_email_generate"])
    assert {"ctx", "provider", "model"} <= set(generate_signature.parameters)
    edit_signature = inspect.signature(mcp.tools["adclip_email_edit"])
    assert {"campaign_dir", "variant_id", "patch_json"} <= set(
        edit_signature.parameters
    )
