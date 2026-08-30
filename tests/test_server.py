from __future__ import annotations

import asyncio
import json

import pytest

PHASE1_TOOLS = {"create_dataset", "list_datasets", "describe_dataset", "add_rows", "get_row"}
PHASE2_TOOLS = {"add_column", "update_column", "remove_column", "delete_dataset", "update_rows", "delete_rows", "validate_rows"}
PHASE3_TOOLS = {"search_rows", "summarize_dataset", "import_rows", "export_rows"}
ALL_TOOLS = PHASE1_TOOLS | PHASE2_TOOLS | PHASE3_TOOLS


def _fresh_server(tmp_path, monkeypatch):
    monkeypatch.setenv("MDM_DATA_DIR", str(tmp_path / "data"))
    import importlib

    import mdm_mcp.tools.base as base
    import mdm_mcp.tools.datasets as datasets
    import mdm_mcp.tools.files as files
    import mdm_mcp.tools.rows as rows
    import mdm_mcp.server as server_module

    for module in (base, datasets, rows, files, server_module):
        importlib.reload(module)
    return server_module.create_server()


def _call(server, name, args):
    async def run():
        _content, structured = await server.call_tool(name, args)
        return structured

    return asyncio.run(run())


def test_all_16_tools_registered_with_docs():
    from mdm_mcp.server import create_server

    server = create_server()
    tools = asyncio.run(server.list_tools())
    names = {t.name for t in tools}
    assert ALL_TOOLS <= names and len(names) == 16
    for tool in tools:
        assert tool.description and len(tool.description) > 100, tool.name
        assert tool.inputSchema.get("properties"), tool.name


def test_tool_docstring_audit():
    from mdm_mcp.server import create_server

    server = create_server()
    tools = asyncio.run(server.list_tools())
    assert {t.name for t in tools} == ALL_TOOLS
    for tool in tools:
        description = tool.description
        assert "Args:" in description, f"{tool.name}: missing Args section"
        assert "Returns:" in description, f"{tool.name}: missing Returns section"
        assert "Example" in description, f"{tool.name}: missing usage example"
        assert '"ok"' in description, f"{tool.name}: missing ok/error result shape"


def test_create_dataset_column_schema_is_descriptive():
    from mdm_mcp.server import create_server

    server = create_server()
    tools = asyncio.run(server.list_tools())
    create = next(t for t in tools if t.name == "create_dataset")
    columns_schema = create.inputSchema["properties"]["columns"]
    assert columns_schema["type"] == "array"
    column_def = json.dumps(create.inputSchema["$defs"]["ColumnSpec"])
    assert "Column name" in column_def
    assert "enum" in column_def


def test_call_tool_roundtrip(tmp_path, monkeypatch):
    server = _fresh_server(tmp_path, monkeypatch)
    created = _call(server, "create_dataset", {
        "name": "Candidates",
        "columns": [
            {"name": "name", "type": "string", "required": True},
            {"name": "stage", "type": "enum", "options": ["Applied", "Rejected"]},
        ],
    })
    assert created["ok"] is True and created["dataset"] == "Candidates"
    added = _call(server, "add_rows", {
        "dataset": "Candidates",
        "rows": [{"name": "Asha", "stage": "Applied"}, {"name": "Bad", "stage": "Hired"}],
    })
    assert added["added"] == 1 and added["rejected"] == 1
    rejected = next(r for r in added["results"] if r["status"] == "rejected")
    assert any("Applied, Rejected" in e for e in rejected["errors"])
    fetched = _call(server, "get_row", {"dataset": "Candidates", "row_id": "1", "columns": ["stage"]})
    assert fetched["row"]["stage"] == "Applied"


def test_phase2_lifecycle_roundtrip(tmp_path, monkeypatch):
    server = _fresh_server(tmp_path, monkeypatch)
    created = _call(server, "create_dataset", {
        "name": "Employees",
        "columns": [
            {"name": "name", "type": "string", "required": True},
            {"name": "salary", "type": "float"},
        ],
    })
    assert created["ok"] is True
    _call(server, "add_rows", {"dataset": "Employees", "rows": [{"name": "Asha", "salary": 50000}]})

    updated = _call(server, "update_rows", {"dataset": "Employees", "values": {"salary": 60000}, "row_ids": ["1"]})
    assert updated["updated"] == 1
    validated = _call(server, "validate_rows", {"dataset": "Employees", "rows": [{"name": "Bob", "salary": "42000.5"}]})
    assert validated["valid"] == 1 and validated["results"][0]["normalized"]["salary"] == 42000.5

    preview = _call(server, "delete_rows", {"dataset": "Employees", "row_ids": ["1"], "confirm": False})
    assert preview["requires_confirmation"] is True
    deleted = _call(server, "delete_rows", {"dataset": "Employees", "row_ids": ["1"], "confirm": True})
    assert deleted["deleted"] == 1

    col_preview = _call(server, "remove_column", {"dataset": "Employees", "column": "salary", "confirm": False})
    assert col_preview["requires_confirmation"] is True
    removed = _call(server, "remove_column", {"dataset": "Employees", "column": "salary", "confirm": True})
    assert removed["removed"] == "salary"

    renamed = _call(server, "update_column", {"dataset": "Employees", "column": "name", "changes": {"name": "full_name"}})
    assert renamed["renamed_from"] == "name"

    ds_preview = _call(server, "delete_dataset", {"name": "Employees", "confirm": False})
    assert ds_preview["requires_confirmation"] is True
    gone = _call(server, "delete_dataset", {"name": "Employees", "confirm": True})
    assert gone["deleted"] == "Employees"

    missing = _call(server, "describe_dataset", {"name": "Employees"})
    assert missing["ok"] is False and "does not exist" in missing["error"]


def test_phase3_search_and_files_roundtrip(tmp_path, monkeypatch):
    server = _fresh_server(tmp_path, monkeypatch)
    columns = [
        {"name": "name", "type": "string"},
        {"name": "stage", "type": "enum", "options": ["Applied", "Rejected"]},
        {"name": "score", "type": "float"},
    ]
    _call(server, "create_dataset", {"name": "Candidates", "columns": columns})
    _call(server, "add_rows", {"dataset": "Candidates", "rows": [
        {"name": "Asha", "stage": "Applied", "score": 8},
        {"name": "Rahul Sharma", "stage": "Rejected", "score": 3},
        {"name": "Meera", "stage": "Applied", "score": 5},
    ]})

    filtered = _call(server, "search_rows", {
        "dataset": "Candidates",
        "conditions": [{"column": "stage", "op": "eq", "value": "Applied"}],
        "sort_by": "score",
        "sort_order": "desc",
        "columns": ["name", "score"],
    })
    assert filtered["total"] == 2
    assert [r["name"] for r in filtered["rows"]] == ["Asha", "Meera"]

    fuzzy = _call(server, "search_rows", {"dataset": "Candidates", "fuzzy": True, "query": "Rahual", "fuzzy_columns": ["name"]})
    assert fuzzy["total"] == 1 and fuzzy["rows"][0]["name"] == "Rahul Sharma" and "_score" in fuzzy["rows"][0]

    summary = _call(server, "summarize_dataset", {"dataset": "Candidates"})
    assert summary["row_count"] == 3
    assert summary["numeric"]["score"]["sum"] == 16
    assert summary["enums"]["stage"] == {"Applied": 2, "Rejected": 1}

    bulk_preview = _call(server, "update_rows", {
        "dataset": "Candidates",
        "values": {"stage": "Rejected"},
        "conditions": [{"column": "score", "op": "lt", "value": 6}],
        "dry_run": True,
    })
    assert bulk_preview["requires_confirmation"] is True and bulk_preview["preview"]["count"] == 2
    bulk = _call(server, "update_rows", {
        "dataset": "Candidates",
        "values": {"stage": "Rejected"},
        "conditions": [{"column": "score", "op": "lt", "value": 6}],
        "dry_run": False,
    })
    assert bulk["updated"] == 2 and bulk["matched"] == 2

    csv_path = tmp_path / "export" / "candidates.csv"
    exported = _call(server, "export_rows", {"dataset": "Candidates", "file_path": str(csv_path), "format": "csv"})
    assert exported["rows_exported"] == 3

    imported_preview = _call(server, "import_rows", {"dataset": "Candidates", "file_path": str(csv_path), "confirm": False})
    assert imported_preview["requires_confirmation"] is True
    imported = _call(server, "import_rows", {"dataset": "Candidates", "file_path": str(csv_path), "confirm": True})
    assert imported["added"] == 3 and imported["rejected"] == 0

    deleted = _call(server, "delete_rows", {
        "dataset": "Candidates",
        "conditions": [{"column": "stage", "op": "eq", "value": "Rejected"}],
        "confirm": True,
    })
    assert deleted["deleted"] == 4


@pytest.mark.parametrize("tool,args", [
    ("remove_column", {"dataset": "X", "column": "c"}),
    ("delete_dataset", {"name": "X"}),
    ("delete_rows", {"dataset": "X", "row_ids": ["1"]}),
])
def test_destructive_tools_default_to_preview(tmp_path, monkeypatch, tool, args):
    server = _fresh_server(tmp_path, monkeypatch)
    _call(server, "create_dataset", {"name": "X", "columns": [{"name": "c", "type": "string"}]})
    result = _call(server, tool, args)
    assert result["requires_confirmation"] is True


def test_import_rows_defaults_to_preview(tmp_path, monkeypatch):
    server = _fresh_server(tmp_path, monkeypatch)
    _call(server, "create_dataset", {"name": "X", "columns": [{"name": "c", "type": "string"}]})
    csv_file = tmp_path / "rows.csv"
    csv_file.write_text("c\nhello\n", encoding="utf-8")
    result = _call(server, "import_rows", {"dataset": "X", "file_path": str(csv_file)})
    assert result["requires_confirmation"] is True
    assert result["preview"]["row_count"] == 1
