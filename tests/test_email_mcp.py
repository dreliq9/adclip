import inspect

from adclip.mcp.email_tools import register


class CaptureMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(function):
            self.tools[function.__name__] = function
            return function

        return decorator


def test_email_mcp_surface():
    mcp = CaptureMCP()
    register(mcp)
    assert {
        "adclip_email_generate_campaign",
        "adclip_email_render",
        "adclip_email_lint",
        "adclip_email_patch_html",
        "adclip_email_patch_message",
    } <= set(mcp.tools)

    signature = inspect.signature(mcp.tools["adclip_email_generate_campaign"])
    assert {"brief_json", "ctx", "provider", "model"} <= set(signature.parameters)
