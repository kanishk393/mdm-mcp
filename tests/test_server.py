from __future__ import annotations

import asyncio
import json

from mdm_mcp.server import create_server

PHASE1_TOOLS = {"create_dataset", "list_datasets", "describe_dataset", "add_rows", "get_row"}


def test_phase1_tools_registered_with_docs():
    server = create_server()
    tools = asyncio.run(server.list_tools())
    names = {t.name for t in tools}
    assert PHASE1_TOOLS <= names
    for tool in tools:
        if tool.name in PHASE1_TOOLS:
            assert tool.description and len(tool.description) > 100, tool.name
            assert tool.inputSchema.get("properties"), tool.name


def test_create_dataset_column_schema_is_descriptive():
    server = create_server()
    tools = asyncio.run(server.list_tools())
    create = next(t for t in tools if t.name == "create_dataset")
    columns_schema = create.inputSchema["properties"]["columns"]
    assert columns_schema["type"] == "array"
    column_def = json.dumps(create.inputSchema["$defs"]["ColumnSpec"])
    assert "Column name" in column_def
    assert "enum" in column_def


def test_call_tool_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("MDM_DATA_DIR", str(tmp_path / "data"))
    import importlib

    import mdm_mcp.tools.base as base

    importlib.reload(base)
    import mdm_mcp.tools.datasets as datasets
    import mdm_mcp.tools.rows as rows

    importlib.reload(datasets)
    importlib.reload(rows)
    import mdm_mcp.server as server_module

    importlib.reload(server_module)
    server = server_module.create_server()

    async def run():
        created = await server.call_tool("create_dataset", {
            "name": "Candidates",
            "columns": [
                {"name": "name", "type": "string", "required": True},
                {"name": "stage", "type": "enum", "options": ["Applied", "Rejected"]},
            ],
        })
        added = await server.call_tool("add_rows", {
            "dataset": "Candidates",
            "rows": [{"name": "Asha", "stage": "Applied"}, {"name": "Bad", "stage": "Hired"}],
        })
        fetched = await server.call_tool("get_row", {"dataset": "Candidates", "row_id": "1", "columns": ["stage"]})
        return created, added, fetched

    created, added, fetched = asyncio.run(run())
    assert created[1]["ok"] is True
    assert created[1]["dataset"] == "Candidates"
    assert added[1]["added"] == 1 and added[1]["rejected"] == 1
    rejected = next(r for r in added[1]["results"] if r["status"] == "rejected")
    assert any("Applied, Rejected" in e for e in rejected["errors"])
    assert fetched[1]["row"]["stage"] == "Applied"
