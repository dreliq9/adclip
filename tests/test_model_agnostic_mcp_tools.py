import inspect

from adclip.mcp.regenerate_tools import register as register_regenerate
from adclip.mcp.score_tools import register as register_score
from adclip.mcp.visual_tools import register as register_visuals


class CaptureMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(function):
            self.tools[function.__name__] = function
            return function

        return decorator


def _signature(register, tool_name):
    mcp = CaptureMCP()
    register(mcp)
    return inspect.signature(mcp.tools[tool_name])


def test_visual_only_tool_has_image_and_video_model_selection():
    signature = _signature(register_visuals, "adclip_generate_visuals")
    assert "image_model" in signature.parameters
    assert "video_model" in signature.parameters


def test_regenerate_tool_has_text_and_image_model_selection():
    signature = _signature(register_regenerate, "adclip_regenerate")
    assert "ctx" in signature.parameters
    assert "llm_model" in signature.parameters
    assert "image_model" in signature.parameters


def test_judge_tool_has_text_model_selection():
    signature = _signature(register_score, "adclip_score_variants")
    assert "ctx" in signature.parameters
    assert "llm_model" in signature.parameters
