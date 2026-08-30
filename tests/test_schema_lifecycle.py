from __future__ import annotations

import pytest

from mdm_mcp.services.dataset_service import DatasetService
from mdm_mcp.services.row_service import RowService
from mdm_mcp.storage.repository import DatasetNotFound

CANDIDATE_COLUMNS = [
    {"name": "name", "type": "string", "required": True},
    {"name": "stage", "type": "enum", "options": ["Applied", "Screened", "Rejected"]},
    {"name": "score", "type": "float"},
]


def make_services(repo):
    return DatasetService(repo), RowService(repo)


def seed_candidates(svc, rows):
    svc.create_dataset("Candidates", "", CANDIDATE_COLUMNS)
    rows.add_rows("Candidates", [
        {"name": "Asha", "stage": "Applied", "score": 7},
        {"name": "Rahul", "stage": "Screened", "score": 9},
    ])


def test_add_column_backfills_default(repo):
    svc, rows = make_services(repo)
    seed_candidates(svc, rows)
    result = svc.add_column("Candidates", {"name": "city", "type": "string", "default": "Delhi"})
    assert result["backfilled_rows"] == 2
    stored = rows.get_row("Candidates", "1", ["city"])["row"]["city"]
    assert stored == "Delhi"


def test_add_column_without_default_fills_null(repo):
    svc, rows = make_services(repo)
    seed_candidates(svc, rows)
    svc.add_column("Candidates", {"name": "city", "type": "string"})
    assert rows.get_row("Candidates", "1", ["city"])["row"]["city"] is None


def test_add_column_duplicate_rejected(repo):
    svc, rows = make_services(repo)
    seed_candidates(svc, rows)
    with pytest.raises(ValueError, match="already exists"):
        svc.add_column("Candidates", {"name": "NAME", "type": "string"})


def test_add_column_enum_without_options_rejected(repo):
    svc, rows = make_services(repo)
    seed_candidates(svc, rows)
    with pytest.raises(ValueError, match="needs at least one option"):
        svc.add_column("Candidates", {"name": "tier", "type": "enum"})


def test_update_column_bounds_reports_offending_rows(repo):
    svc, rows = make_services(repo)
    seed_candidates(svc, rows)
    result = svc.update_column("Candidates", "score", {"min_value": 8})
    assert result["invalid_rows"] == {"1": ["Column 'score' must be at least 8."]}
    assert rows.get_row("Candidates", "1", ["score"])["row"]["score"] == 7


def test_update_column_rename_remaps_rows(repo):
    svc, rows = make_services(repo)
    seed_candidates(svc, rows)
    result = svc.update_column("Candidates", "stage", {"name": "status"})
    assert result["renamed_from"] == "stage"
    assert rows.get_row("Candidates", "1", ["status"])["row"]["status"] == "Applied"
    with pytest.raises(ValueError, match="Unknown column"):
        rows.get_row("Candidates", "1", ["stage"])


def test_update_column_unknown_rejected(repo):
    svc, rows = make_services(repo)
    seed_candidates(svc, rows)
    with pytest.raises(ValueError, match="does not exist"):
        svc.update_column("Candidates", "bogus", {"required": True})


def test_update_column_invalid_definition_rejected(repo):
    svc, rows = make_services(repo)
    seed_candidates(svc, rows)
    with pytest.raises(ValueError, match="needs at least one option"):
        svc.update_column("Candidates", "stage", {"type": "enum", "options": []})


def test_remove_column_requires_confirmation(repo):
    svc, rows = make_services(repo)
    seed_candidates(svc, rows)
    preview = svc.remove_column("Candidates", "score", False)
    assert preview["requires_confirmation"] is True
    assert preview["preview"]["affected_rows"] == 2
    assert svc.describe_dataset("Candidates", 0)["row_count"] == 2
    assert any(c["name"] == "score" for c in svc.describe_dataset("Candidates", 0)["columns"])


def test_remove_column_confirmed(repo):
    svc, rows = make_services(repo)
    seed_candidates(svc, rows)
    result = svc.remove_column("Candidates", "score", True)
    assert result["removed"] == "score"
    described = svc.describe_dataset("Candidates", 2)
    assert all(c["name"] != "score" for c in described["columns"])
    assert "score" not in described["samples"][0]


def test_remove_last_column_rejected(repo):
    svc, rows = make_services(repo)
    svc.create_dataset("Tiny", "", [{"name": "only", "type": "string"}])
    with pytest.raises(ValueError, match="last column"):
        svc.remove_column("Tiny", "only", True)


def test_delete_dataset_flow(repo):
    svc, rows = make_services(repo)
    seed_candidates(svc, rows)
    preview = svc.delete_dataset("Candidates", False)
    assert preview["requires_confirmation"] is True
    assert preview["preview"]["row_count"] == 2
    assert svc.describe_dataset("Candidates", 0)["row_count"] == 2
    result = svc.delete_dataset("Candidates", True)
    assert result == {"deleted": "Candidates", "rows_removed": 2}
    with pytest.raises(DatasetNotFound):
        svc.describe_dataset("Candidates", 0)
