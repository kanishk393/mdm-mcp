from __future__ import annotations

import json

import pytest

from mdm_mcp.services.dataset_service import DatasetService
from mdm_mcp.services.file_service import FileService
from mdm_mcp.services.row_service import RowService

COLUMNS = [
    {"name": "name", "type": "string", "required": True},
    {"name": "phone", "type": "phone"},
    {"name": "age", "type": "integer"},
    {"name": "stage", "type": "enum", "options": ["Applied", "Rejected"]},
]


def make_services(repo):
    return DatasetService(repo), RowService(repo), FileService(repo)


CSV_CONTENT = """name,phone,age,stage,extra_column
Asha,9876543210,27,Applied,noise
Bad,12345,abc,Applied,noise
Rahul,+919876543210,31,,noise
"""


def write_csv(tmp_path, content=CSV_CONTENT):
    file = tmp_path / "applicants.csv"
    file.write_text(content, encoding="utf-8")
    return str(file)


def seed(svc):
    svc.create_dataset("Candidates", "", COLUMNS)


def test_import_preview_maps_columns(repo, tmp_path):
    svc, _, files = make_services(repo)
    seed(svc)
    preview = files.import_rows("Candidates", write_csv(tmp_path), "auto", confirm=False)
    assert preview["requires_confirmation"] is True
    body = preview["preview"]
    assert body["row_count"] == 3
    assert body["mapping"] == {"name": "name", "phone": "phone", "age": "age", "stage": "stage"}
    assert body["unmatched_file_columns"] == ["extra_column"]
    assert body["sample_rows"][0]["name"] == "Asha"
    assert svc.describe_dataset("Candidates", 0)["row_count"] == 0


def test_import_commit_with_rejects(repo, tmp_path):
    svc, _, files = make_services(repo)
    seed(svc)
    result = files.import_rows("Candidates", write_csv(tmp_path), "auto", confirm=True)
    assert result["added"] == 2 and result["rejected"] == 1
    rejected = result["rejected_rows"][0]
    assert rejected["row"] == 1
    assert any("Indian mobile" in e for e in rejected["errors"])
    assert svc.describe_dataset("Candidates", 0)["row_count"] == 2
    first = repo.load_rows("Candidates")["rows"]["1"]
    assert first["age"] == 27 and isinstance(first["age"], int)


def test_import_missing_required_column_rejects_rows(repo, tmp_path):
    svc, _, files = make_services(repo)
    seed(svc)
    file = tmp_path / "partial.csv"
    file.write_text("phone,age\n9876543210,30\n", encoding="utf-8")
    result = files.import_rows("Candidates", str(file), "auto", confirm=True)
    assert result["added"] == 0 and result["rejected"] == 1
    assert any("required" in e for e in result["rejected_rows"][0]["errors"])


def test_import_missing_file_named(repo, tmp_path):
    svc, _, files = make_services(repo)
    seed(svc)
    with pytest.raises(ValueError, match="File not found"):
        files.import_rows("Candidates", str(tmp_path / "nope.csv"), "auto", confirm=False)


def test_import_unknown_format_rejected(repo, tmp_path):
    svc, _, files = make_services(repo)
    seed(svc)
    file = tmp_path / "data.txt"
    file.write_text("name\nA\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Cannot infer"):
        files.import_rows("Candidates", str(file), "auto", confirm=False)


def test_import_json_list_and_rows_wrapper(repo, tmp_path):
    svc, _, files = make_services(repo)
    seed(svc)
    file = tmp_path / "people.json"
    file.write_text(json.dumps({"rows": [{"name": "Asha", "age": "27"}, {"name": "Rahul", "age": "31"}]}), encoding="utf-8")
    result = files.import_rows("Candidates", str(file), "auto", confirm=True)
    assert result["added"] == 2 and result["rejected"] == 0
    assert repo.load_rows("Candidates")["rows"]["1"]["age"] == 27


def test_import_json_invalid_shape_rejected(repo, tmp_path):
    svc, _, files = make_services(repo)
    seed(svc)
    file = tmp_path / "bad.json"
    file.write_text(json.dumps({"name": "Asha"}), encoding="utf-8")
    with pytest.raises(ValueError, match="list of row objects"):
        files.import_rows("Candidates", str(file), "auto", confirm=True)


def test_export_csv_filtered_and_projected(repo, tmp_path):
    svc, rows, files = make_services(repo)
    seed(svc)
    rows.add_rows("Candidates", [
        {"name": "Asha", "stage": "Applied", "age": 27},
        {"name": "Rahul", "stage": "Rejected", "age": 31},
    ])
    target = tmp_path / "out" / "applied.csv"
    result = files.export_rows(
        "Candidates", str(target), "csv",
        conditions=[{"column": "stage", "op": "eq", "value": "Applied"}],
        columns=["name", "stage"],
    )
    assert result["rows_exported"] == 1
    lines = target.read_text().strip().splitlines()
    assert lines[0] == "id,name,stage"
    assert lines[1] == "1,Asha,Applied"


def test_export_csv_bool_and_null_cells(repo, tmp_path):
    svc, rows, files = make_services(repo)
    svc.create_dataset("Tasks", "", [{"name": "title", "type": "string"}, {"name": "done", "type": "boolean"}])
    rows.add_rows("Tasks", [{"title": "one", "done": True}, {"title": "two"}])
    target = tmp_path / "tasks.csv"
    files.export_rows("Tasks", str(target), "csv")
    lines = target.read_text().strip().splitlines()
    assert lines[1] == "1,one,true"
    assert lines[2] == "2,two,"


def test_export_json_roundtrip(repo, tmp_path):
    svc, rows, files = make_services(repo)
    seed(svc)
    rows.add_rows("Candidates", [{"name": "Asha", "age": 27, "stage": "Applied"}])
    target = tmp_path / "out.json"
    files.export_rows("Candidates", str(target), "json")
    payload = json.loads(target.read_text())
    assert payload[0]["id"] == "1" and payload[0]["age"] == 27


def test_export_refuses_overwrite(repo, tmp_path):
    svc, rows, files = make_services(repo)
    seed(svc)
    rows.add_rows("Candidates", [{"name": "Asha"}])
    target = tmp_path / "out.csv"
    files.export_rows("Candidates", str(target), "csv")
    with pytest.raises(ValueError, match="already exists"):
        files.export_rows("Candidates", str(target), "csv")
    result = files.export_rows("Candidates", str(target), "csv", overwrite=True)
    assert result["rows_exported"] == 1


def test_export_unknown_column_rejected(repo, tmp_path):
    svc, rows, files = make_services(repo)
    seed(svc)
    with pytest.raises(ValueError, match="Unknown column"):
        files.export_rows("Candidates", str(tmp_path / "o.csv"), "csv", columns=["emial"])
