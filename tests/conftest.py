"""Shared fixtures for the MDM test suite."""

from __future__ import annotations

import pytest

from mdm_mcp.storage.repository import JsonRepository


@pytest.fixture
def repo(tmp_path):
    return JsonRepository(root=tmp_path / "data")


@pytest.fixture
def candidates_schema():
    from mdm_mcp.models.schema import DatasetSchema

    return DatasetSchema.model_validate({
        "name": "Candidates",
        "columns": [
            {"name": "name", "type": "string", "required": True},
            {"name": "age", "type": "integer"},
            {"name": "score", "type": "float", "min_value": 0, "max_value": 10},
            {"name": "active", "type": "boolean"},
            {"name": "stage", "type": "enum", "options": ["Applied", "Screened", "Rejected"]},
            {"name": "phone", "type": "phone"},
            {"name": "applied_on", "type": "date"},
            {"name": "notes", "type": "text"},
        ],
    })
