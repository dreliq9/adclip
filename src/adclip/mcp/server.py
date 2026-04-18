"""adclip MCP server — ad creative generation tools for Claude."""

import logging
import sys

from mcp.server.fastmcp import FastMCP

# All logging to stderr (MCP uses stdio for transport)
logging.basicConfig(stream=sys.stderr, level=logging.WARNING)

mcp = FastMCP("adclip")


def _register_all():
    from adclip.mcp import brief_tools, copy_tools

    brief_tools.register(mcp)
    copy_tools.register(mcp)


_register_all()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
