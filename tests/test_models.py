from __future__ import annotations

import pytest
from pydantic import ValidationError

from mdm_mcp.models.schema import ColumnSpec, ColumnType


def test_valid_column_spec_defaults():
    spec = ColumnSpec.model_validate({"name": " name ", "type": "string"})
    assert spec.name == "name"
    assert spec.required is False
    assert spec.default is None


def test_phone_gets_india_pattern_by_default():
    spec = ColumnSpec.model_validate({"name": "phone", "type": "phone"})
    assert spec.pattern is not None
    assert ColumnType.PHONE in str(spec.pattern) or "+" in spec.pattern


def test_enum_without_options_rejected():
    with pytest.raises(ValidationError, match="needs at least one option"):
        ColumnSpec.model_validate({"name": "stage", "type": "enum"})


def test_enum_duplicate_options_rejected():
    with pytest.raises(ValidationError, match="duplicate options"):
        ColumnSpec.model_validate({"name": "stage", "type": "enum", "options": ["A", "A"]})


def test_invalid_pattern_rejected():
    with pytest.raises(ValidationError, match="invalid pattern"):
        ColumnSpec.model_validate({"name": "code", "type": "string", "pattern": "("})


def test_min_greater_than_max_rejected():
    with pytest.raises(ValidationError, match="min_value greater than max_value"):
        ColumnSpec.model_validate({"name": "score", "type": "float", "min_value": 10, "max_value": 0})


def test_unknown_attribute_rejected():
    with pytest.raises(ValidationError):
        ColumnSpec.model_validate({"name": "x", "type": "string", "bogus": 1})
