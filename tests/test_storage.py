from __future__ import annotations

import json

import pytest

from mdm_mcp.models.schema import DatasetSchema
from mdm_mcp.storage.repository import DatasetNotFound, JsonRepository, slugify


def test_slugify():
    assert slugify("Candidates 2026!") == "candidates-2026"


def test_schema_roundtrip(repo):
    schema = DatasetSchema.model_validate({
        "name": "Candidates",
        "columns": [{"name": "name", "type": "string", "required": True}],
    })
    repo.save_schema(schema)
    loaded = repo.load_schema("CANDIDATES")
    assert loaded.name == "Candidates"
    assert loaded.columns[0].name == "name"


def test_dataset_names_sorted(repo):
    for name in ["Zebra", "alpha", "Beta"]:
        repo.save_schema(DatasetSchema.model_validate({"name": name, "columns": [{"name": "a", "type": "string"}]}))
    assert repo.dataset_names() == ["alpha", "Beta", "Zebra"]


def test_load_missing_dataset_lists_available(repo):
    repo.save_schema(DatasetSchema.model_validate({"name": "Exists", "columns": [{"name": "a", "type": "string"}]}))
    with pytest.raises(DatasetNotFound) as excinfo:
        repo.load_schema("Missing")
    assert "Exists" in str(excinfo.value)


def test_rows_default_shape(repo):
    assert repo.load_rows("Anything") == {"rows": {}, "next_id": 1}


def test_repeated_row_writes_stay_valid(repo):
    for next_id in (1, 2, 3):
        repo.save_rows("Candidates", {"rows": {str(next_id): {"name": f"row{next_id}"}}, "next_id": next_id + 1})
        path = repo.dataset_dir("Candidates") / "rows.json"
        assert json.loads(path.read_text())["next_id"] == next_id + 1


def test_delete_dataset(repo):
    repo.save_schema(DatasetSchema.model_validate({"name": "Gone", "columns": [{"name": "a", "type": "string"}]}))
    repo.delete_dataset("Gone")
    assert not repo.dataset_exists("Gone")
    with pytest.raises(DatasetNotFound):
        repo.delete_dataset("Gone")
