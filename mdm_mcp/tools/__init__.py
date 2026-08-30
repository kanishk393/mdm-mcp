"""Thin FastMCP tool registrations backed by services."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def register_all_tools(mcp: FastMCP) -> None:
    from mdm_mcp.tools.datasets import register_dataset_tools
    from mdm_mcp.tools.rows import register_row_tools

    register_dataset_tools(mcp)
    register_row_tools(mcp)

