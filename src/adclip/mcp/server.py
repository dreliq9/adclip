"""adclip MCP server — marketing creative, email, routing, and learning tools."""

import logging
import sys

from adclip import _env

_env.load()

from mcp.server.fastmcp import FastMCP

logging.basicConfig(stream=sys.stderr, level=logging.WARNING)

mcp = FastMCP("adclip")


def _register_all():
    from adclip.mcp import (
        brief_tools,
        campaign_tools,
        copy_tools,
        dco_tools,
        email_tools,
        performance_tools,
        pipeline_tools,
        regenerate_tools,
        render_tools,
        routing_tools,
        score_tools,
        visual_tools,
    )

    brief_tools.register(mcp)
    copy_tools.register(mcp)
    pipeline_tools.register(mcp)
    campaign_tools.register(mcp)
    render_tools.register(mcp)
    score_tools.register(mcp)
    regenerate_tools.register(mcp)
    visual_tools.register(mcp)
    dco_tools.register(mcp)
    routing_tools.register(mcp)
    email_tools.register(mcp)
    performance_tools.register(mcp)


_register_all()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
