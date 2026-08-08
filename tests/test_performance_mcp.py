from adclip.mcp.performance_tools import register


class CaptureMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(function):
            self.tools[function.__name__] = function
            return function

        return decorator


def test_performance_mcp_registers_learning_tools():
    mcp = CaptureMCP()
    register(mcp)
    assert {
        "adclip_performance_link_meta",
        "adclip_performance_deployments",
        "adclip_performance_sync_meta",
        "adclip_performance_report",
        "adclip_performance_compare",
        "adclip_experiment_create",
        "adclip_experiments",
        "adclip_experiment_evaluate",
        "adclip_experiment_next_test",
    } <= set(mcp.tools)
