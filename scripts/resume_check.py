"""Resume verification: write data in session 1, read it from a brand-new session 2.

Run fully inside Docker (no host Python needed):
    bash scripts/resume_check.sh
"""

import asyncio
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import get_default_environment, stdio_client

PARAMS = StdioServerParameters(
    command="mdm-mcp",
    env={**get_default_environment(), "MDM_DATA_DIR": os.environ.get("MDM_DATA_DIR", "/data")},
)


async def session1():
    async with stdio_client(PARAMS) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            await s.call_tool("create_dataset", {
                "name": "ResumeCheck",
                "columns": [{"name": "note", "type": "string", "required": True}],
            })
            await s.call_tool("add_rows", {
                "dataset": "ResumeCheck",
                "rows": [{"note": "written before shutdown"}],
            })
    print("session 1: data written, client + container session fully closed")


async def session2():
    async with stdio_client(PARAMS) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            res = await s.call_tool("search_rows", {
                "dataset": "ResumeCheck",
                "conditions": [{"column": "note", "op": "contains", "value": "shutdown"}],
            })
            rows = res.structuredContent["rows"]
            assert rows and rows[0]["note"] == "written before shutdown", rows
            print(f"session 2: resumed -> found {rows[0]['note']!r} (row {rows[0]['id']}) in a brand-new session")


asyncio.run(session1())
asyncio.run(session2())
print("RESUME TEST PASSED")
