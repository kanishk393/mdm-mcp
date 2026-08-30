"""30-second recruiter demo, run with:  bash demo/demo.sh

Spawns the MDM MCP server over stdio (inside the same Docker image) and walks
through the hiring-partner story: schema creation, bulk import with validation
rejects, typo-tolerant fuzzy search, filtering + sorting, bulk shortlisting with
dry-run preview, and dataset summaries.
"""

from __future__ import annotations

import asyncio
import json

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import get_default_environment, stdio_client

SERVER = StdioServerParameters(
    command="mdm-mcp",
    env={**get_default_environment(), "MDM_DATA_DIR": "/data"},
)


def show(title: str, payload: dict, keys=None):
    print(f"\n--- {title} ---")
    slim = {k: v for k, v in payload.items() if k not in ("ok",)}
    if keys:
        slim = {k: v for k, v in slim.items() if k in keys}
    print(json.dumps(slim, indent=2, ensure_ascii=False))


async def call(s: ClientSession, tool: str, args: dict) -> dict:
    result = await s.call_tool(tool, args)
    if result.isError:
        raise RuntimeError(f"{tool} failed: {result.content}")
    return result.structuredContent


async def main():
    async with stdio_client(SERVER) as (read, write):
        async with ClientSession(read, write) as s:
            await s.initialize()

            created = await call(s, "create_dataset", {
                "name": "Java JD Candidates",
                "description": "Applicants for the Senior Java role",
                "columns": [
                    {"name": "name", "type": "string", "required": True},
                    {"name": "phone", "type": "phone"},
                    {"name": "experience", "type": "float", "min_value": 0},
                    {"name": "stage", "type": "enum",
                     "options": ["Applied", "Screened", "Interviewed", "Rejected"]},
                    {"name": "applied_on", "type": "date"},
                ],
            })
            show("Create dataset", created)

            preview = await call(s, "import_rows", {
                "dataset": "Java JD Candidates",
                "file_path": "/demo/applicants.csv",
            })
            show("Import preview (mapping + sample)", preview["preview"],
                 keys=("mapping", "unmatched_file_columns", "missing_required_columns", "row_count"))

            imported = await call(s, "import_rows", {
                "dataset": "Java JD Candidates",
                "file_path": "/demo/applicants.csv",
                "confirm": True,
            })
            show("Import commit (per-row validation)", imported)

            fuzzy = await call(s, "search_rows", {
                "dataset": "Java JD Candidates",
                "fuzzy": True,
                "query": "Rahual",
                "fuzzy_columns": ["name"],
            })
            show("Fuzzy search: 'Rahual' (typo)", fuzzy)

            shortlist = await call(s, "search_rows", {
                "dataset": "Java JD Candidates",
                "conditions": [
                    {"column": "stage", "op": "eq", "value": "Applied"},
                    {"column": "experience", "op": "gte", "value": 3},
                ],
                "sort_by": "experience",
                "sort_order": "desc",
                "columns": ["name", "experience", "applied_on"],
            })
            show("Filter: Applied AND experience >= 3, newest skills first", shortlist)

            ids = [r["id"] for r in shortlist["rows"]]
            dry = await call(s, "update_rows", {
                "dataset": "Java JD Candidates",
                "values": {"stage": "Screened"},
                "conditions": [{"column": "experience", "op": "gte", "value": 3}],
            })
            show("Bulk shortlist: dry-run preview", dry["preview"])

            applied = await call(s, "update_rows", {
                "dataset": "Java JD Candidates",
                "values": {"stage": "Screened"},
                "conditions": [{"column": "experience", "op": "gte", "value": 3}],
                "dry_run": False,
            })
            show("Bulk shortlist: applied", applied)

            summary = await call(s, "summarize_dataset", {"dataset": "Java JD Candidates"})
            show("Dataset summary (aggregates, no rows dumped)", summary)

            print("\nDemo complete. Inspect the data files:")
            print("  docker run --rm -v mdm-data:/data alpine find /data -type f")


if __name__ == "__main__":
    asyncio.run(main())
