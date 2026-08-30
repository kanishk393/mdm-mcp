"""FastMCP server assembly."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mdm_mcp.tools import register_all_tools


def create_server() -> FastMCP:
    mcp = FastMCP(
        "master-data-management",
        instructions=(
            "Conversational master data management: create datasets with typed columns, then "
            "add, inspect, update, and search rows. All list results are paginated - keep the "
            "limit small and page with next_offset. Confirm with the user before destructive "
            "actions, and relay validation errors in plain language."
        ),
    )
    register_all_tools(mcp)
    return mcp


mcp = create_server()
