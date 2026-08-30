from __future__ import annotations

import pytest

from mdm_mcp.services.dataset_service import DatasetService
from mdm_mcp.services.row_service import RowService

CANDIDATE_COLUMNS = [
    {"name": "name", "type": "string", "required": True},
    {"name": "age", "type": "integer"},
    {"name": "stage", "type": "enum", "options": ["Applied", "Screened", "Rejected"]},
]


def make_services(repo):
    return DatasetService(repo), RowService(repo)


def seed(svc, rows):
    svc.create_dataset("Candidates", "", CANDIDATE_COLUMNS)
    rows.add_rows("Candidates", [
        {"name": "Asha", "age": 27, "stage": "Applied"},
        {"name": "Rahul", "age": 31, "stage": "Screened"},
        {"name": "Meera", "age": 25, "stage": "Applied"},
    ])


def test_partial_update_changes_only_given_columns(repo):
    svc, rows = make_services(repo)
    seed(svc, rows)
    result = rows.update_rows("Candidates", {"stage": "Rejected"}, row_ids=["1"])
    assert result["updated"] == 1 and result["rejected"] == 0
    row = rows.get_row("Candidates", "1", None)["row"]
    assert row["stage"] == "Rejected" and row["age"] == 27


def test_invalid_update_leaves_row_untouched(repo):
    svc, rows = make_services(repo)
    seed(svc, rows)
    result = rows.update_rows("Candidates", {"age": "not a number"}, row_ids=["1"])
    assert result["updated"] == 0 and result["rejected"] == 1
    rejected = result["results"][0]
    assert any("whole number" in e for e in rejected["errors"])
    assert rows.get_row("Candidates", "1", ["age"])["row"]["age"] == 27


def test_update_multiple_ids_with_counts(repo):
    svc, rows = make_services(repo)
    seed(svc, rows)
    result = rows.update_rows("Candidates", {"stage": "Rejected"}, row_ids=["1", "2", "99"])
    assert result["updated"] == 2 and result["not_found"] == 1
    assert [r["status"] for r in result["results"]] == ["updated", "updated", "not_found"]


def test_update_unknown_column_rejected(repo):
    svc, rows = make_services(repo)
    seed(svc, rows)
    with pytest.raises(ValueError, match="Unknown column"):
        rows.update_rows("Candidates", {"emial": "x"}, row_ids=["1"])


def test_update_empty_values_rejected(repo):
    svc, rows = make_services(repo)
    seed(svc, rows)
    with pytest.raises(ValueError, match="values is empty"):
        rows.update_rows("Candidates", {}, row_ids=["1"])


def test_update_coerces_values(repo):
    svc, rows = make_services(repo)
    seed(svc, rows)
    rows.update_rows("Candidates", {"age": "33"}, row_ids=["1"])
    assert rows.get_row("Candidates", "1", ["age"])["row"]["age"] == 33


def test_validate_rows_reports_without_saving(repo):
    svc, rows = make_services(repo)
    seed(svc, rows)
    result = rows.validate_rows("Candidates", [
        {"name": "New", "age": "20"},
        {"name": "Bad", "stage": "Hired"},
    ])
    assert result["valid"] == 1 and result["invalid"] == 1
    valid = result["results"][0]
    assert valid["normalized"]["age"] == 20
    invalid = result["results"][1]
    assert any("Applied, Screened, Rejected" in e for e in invalid["errors"])
    assert svc.describe_dataset("Candidates", 0)["row_count"] == 3


def test_validate_rows_batch_cap(repo):
    svc, rows = make_services(repo)
    seed(svc, rows)
    with pytest.raises(ValueError, match="at most 100"):
        rows.validate_rows("Candidates", [{"name": f"P{i}"} for i in range(150)])


def test_delete_rows_flow(repo):
    svc, rows = make_services(repo)
    seed(svc, rows)
    preview = rows.delete_rows("Candidates", ["2", "99"], confirm=False)
    assert preview["requires_confirmation"] is True
    assert preview["preview"]["row_ids"] == ["2"]
    assert preview["preview"]["not_found"] == ["99"]
    assert svc.describe_dataset("Candidates", 0)["row_count"] == 3
    result = rows.delete_rows("Candidates", ["2", "99"], confirm=True)
    assert result["deleted"] == 1 and result["not_found"] == ["99"]
    assert svc.describe_dataset("Candidates", 0)["row_count"] == 2
    with pytest.raises(ValueError, match="does not exist"):
        rows.get_row("Candidates", "2", None)


def test_delete_rows_empty_ids_rejected(repo):
    svc, rows = make_services(repo)
    seed(svc, rows)
    with pytest.raises(ValueError, match="row_ids is empty"):
        rows.delete_rows("Candidates", [], confirm=True)
