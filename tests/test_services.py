from __future__ import annotations

import pytest

from mdm_mcp.services.dataset_service import DatasetService
from mdm_mcp.services.row_service import RowService
from mdm_mcp.storage.repository import DatasetNotFound

CANDIDATE_COLUMNS = [
    {"name": "name", "type": "string", "required": True},
    {"name": "phone", "type": "phone"},
    {"name": "stage", "type": "enum", "options": ["Applied", "Screened", "Rejected"]},
    {"name": "applied_on", "type": "date"},
]


def make_services(repo):
    return DatasetService(repo), RowService(repo)


def test_create_dataset_returns_summaries(repo):
    svc, _ = make_services(repo)
    result = svc.create_dataset("Candidates", "JD pipeline", CANDIDATE_COLUMNS)
    assert result["dataset"] == "Candidates"
    assert {"name": "phone", "type": "phone"} in result["columns"]


def test_create_duplicate_dataset_rejected(repo):
    svc, _ = make_services(repo)
    svc.create_dataset("Candidates", "", CANDIDATE_COLUMNS)
    with pytest.raises(ValueError, match="already exists"):
        svc.create_dataset("candidates", "", CANDIDATE_COLUMNS)


def test_create_duplicate_column_names_rejected(repo):
    svc, _ = make_services(repo)
    with pytest.raises(ValueError, match="Duplicate column names"):
        svc.create_dataset("Bad", "", [{"name": "name", "type": "string"}, {"name": "NAME", "type": "integer"}])


def test_create_empty_name_rejected(repo):
    svc, _ = make_services(repo)
    with pytest.raises(ValueError, match="cannot be empty"):
        svc.create_dataset("   ", "", CANDIDATE_COLUMNS)


def test_create_enum_without_options_rejected(repo):
    svc, _ = make_services(repo)
    with pytest.raises(ValueError, match="needs at least one option"):
        svc.create_dataset("Bad", "", [{"name": "stage", "type": "enum"}])


def test_list_datasets_pagination(repo):
    svc, _ = make_services(repo)
    for i in range(3):
        svc.create_dataset(f"Dataset{i}", "", [{"name": "a", "type": "string"}])
    page1 = svc.list_datasets(2, 0)
    assert page1["total"] == 3 and page1["count"] == 2 and page1["next_offset"] == 2
    page2 = svc.list_datasets(2, 2)
    assert page2["count"] == 1 and page2["next_offset"] is None


def test_list_datasets_clamps_limit(repo):
    svc, _ = make_services(repo)
    assert svc.list_datasets(500, 0)["count"] == 0
    result = svc.list_datasets(0, 0)
    assert "datasets" in result


def test_describe_dataset_samples(repo):
    svc, rows = make_services(repo)
    svc.create_dataset("Candidates", "", CANDIDATE_COLUMNS)
    rows.add_rows("Candidates", [
        {"name": "Asha", "phone": "9876543210"},
        {"name": "Rahul"},
        {"name": "Meera"},
    ])
    described = svc.describe_dataset("Candidates", 2)
    assert described["row_count"] == 3
    assert len(described["samples"]) == 2
    assert described["samples"][0]["id"] == "1"
    assert described["columns"][0] == {"name": "name", "type": "string", "required": True}


def test_describe_dataset_sample_cap(repo):
    svc, rows = make_services(repo)
    svc.create_dataset("Candidates", "", CANDIDATE_COLUMNS)
    rows.add_rows("Candidates", [{"name": f"P{i}"} for i in range(10)])
    assert len(svc.describe_dataset("Candidates", 8)["samples"]) == 5


def test_describe_missing_dataset_lists_available(repo):
    svc, _ = make_services(repo)
    with pytest.raises(DatasetNotFound, match="none yet"):
        svc.describe_dataset("Missing", 0)


def test_add_rows_mixed_batch(repo):
    svc, rows = make_services(repo)
    svc.create_dataset("Candidates", "", CANDIDATE_COLUMNS)
    result = rows.add_rows("Candidates", [
        {"name": "Asha", "phone": "9876543210"},
        {"name": "Bad", "phone": "12345"},
        {"name": "Rahul"},
    ])
    assert result["added"] == 2 and result["rejected"] == 1
    statuses = {r["status"] for r in result["results"]}
    assert statuses == {"added", "rejected"}
    rejected = next(r for r in result["results"] if r["status"] == "rejected")
    assert any("Indian mobile" in e for e in rejected["errors"])


def test_add_rows_ids_are_sequential_strings(repo):
    svc, rows = make_services(repo)
    svc.create_dataset("Candidates", "", CANDIDATE_COLUMNS)
    result = rows.add_rows("Candidates", [{"name": "A"}, {"name": "B"}])
    assert [r["row_id"] for r in result["results"]] == ["1", "2"]
    assert rows.get_row("Candidates", "2", None)["row"]["name"] == "B"


def test_add_rows_batch_cap(repo):
    svc, rows = make_services(repo)
    svc.create_dataset("Candidates", "", CANDIDATE_COLUMNS)
    with pytest.raises(ValueError, match="at most 100"):
        rows.add_rows("Candidates", [{"name": f"P{i}"} for i in range(150)])
    assert svc.describe_dataset("Candidates", 0)["row_count"] == 0


def test_add_rows_non_dict_row_rejected(repo):
    svc, rows = make_services(repo)
    svc.create_dataset("Candidates", "", CANDIDATE_COLUMNS)
    result = rows.add_rows("Candidates", ["not a row", {"name": "Asha"}])
    assert result["added"] == 1 and result["rejected"] == 1
    assert "object" in result["results"][0]["errors"][0]


def test_add_rows_missing_dataset(repo):
    _, rows = make_services(repo)
    with pytest.raises(DatasetNotFound):
        rows.add_rows("Nope", [{"name": "A"}])


def test_get_row_projection(repo):
    svc, rows = make_services(repo)
    svc.create_dataset("Candidates", "", CANDIDATE_COLUMNS)
    rows.add_rows("Candidates", [{"name": "Asha", "stage": "Applied", "phone": "9876543210"}])
    projected = rows.get_row("Candidates", "1", ["stage"])
    assert projected["row"] == {"id": "1", "stage": "Applied"}


def test_get_row_unknown_id(repo):
    svc, rows = make_services(repo)
    svc.create_dataset("Candidates", "", CANDIDATE_COLUMNS)
    with pytest.raises(ValueError, match="does not exist"):
        rows.get_row("Candidates", "99", None)


def test_get_row_unknown_column(repo):
    svc, rows = make_services(repo)
    svc.create_dataset("Candidates", "", CANDIDATE_COLUMNS)
    rows.add_rows("Candidates", [{"name": "Asha"}])
    with pytest.raises(ValueError, match="Unknown column"):
        rows.get_row("Candidates", "1", ["emial"])
