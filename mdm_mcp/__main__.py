"""Entry point: run the MCP server over stdio."""

from __future__ import annotations

from mdm_mcp.server import mcp


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
