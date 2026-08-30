from __future__ import annotations

import pytest

from mdm_mcp.models.schema import DatasetSchema
from mdm_mcp.search.engine import FilterEngine, FilterError

SCHEMA = DatasetSchema.model_validate({
    "name": "Candidates",
    "columns": [
        {"name": "name", "type": "string"},
        {"name": "age", "type": "integer"},
        {"name": "score", "type": "float"},
        {"name": "stage", "type": "enum", "options": ["Applied", "Rejected"]},
        {"name": "applied_on", "type": "date"},
    ],
})

ROW = {"name": "Asha Verma", "age": 27, "score": 7.5, "stage": "Applied", "applied_on": "2026-08-15"}


def engine():
    return FilterEngine(SCHEMA)


def matches(conditions, row=ROW):
    compiled = engine().compile(conditions)
    return engine().matches_all(row, compiled)


def test_unknown_column_lists_available():
    with pytest.raises(FilterError, match="Available columns"):
        engine().compile([{"column": "emial", "op": "eq", "value": "x"}])


def test_unknown_op_lists_supported():
    with pytest.raises(FilterError, match="Supported ops"):
        engine().compile([{"column": "age", "op": "matches", "value": 1}])


def test_malformed_condition():
    with pytest.raises(FilterError, match="must be an object"):
        engine().compile([{"column": "age"}])


def test_empty_conditions_rejected():
    with pytest.raises(FilterError, match="conditions is empty"):
        engine().compile([])


def test_eq_numeric_coercion():
    assert matches([{"column": "age", "op": "eq", "value": "27"}])
    assert matches([{"column": "score", "op": "eq", "value": 7.5}])


def test_ne_on_missing_value_is_true():
    assert matches([{"column": "score", "op": "ne", "value": 99}], {**ROW, "score": None})


def test_range_ops_numeric():
    assert matches([{"column": "age", "op": "gt", "value": 26}])
    assert matches([{"column": "age", "op": "gte", "value": 27}])
    assert not matches([{"column": "age", "op": "lt", "value": 27}])
    assert matches([{"column": "age", "op": "lte", "value": 27}])


def test_between_inclusive():
    cond = [{"column": "age", "op": "between", "value": [27, 30]}]
    assert matches(cond)
    assert not matches([{"column": "age", "op": "between", "value": [28, 30]}])


def test_between_requires_two_values():
    with pytest.raises(FilterError, match="two-value list"):
        engine().compile([{"column": "age", "op": "between", "value": [1]}])


def test_range_on_text_column_rejected():
    with pytest.raises(FilterError, match="numeric or date column"):
        engine().compile([{"column": "name", "op": "gt", "value": "B"}])


def test_numeric_filter_needs_numeric_value():
    with pytest.raises(FilterError, match="numeric value"):
        engine().compile([{"column": "age", "op": "gt", "value": "old"}])


def test_date_range_filters():
    assert matches([{"column": "applied_on", "op": "between", "value": ["2026-08-01", "2026-08-31"]}])
    assert matches([{"column": "applied_on", "op": "gte", "value": "2026-08-15"}])
    assert not matches([{"column": "applied_on", "op": "gt", "value": "2026-08-15"}])


def test_date_filter_needs_iso_date():
    with pytest.raises(FilterError, match="YYYY-MM-DD"):
        engine().compile([{"column": "applied_on", "op": "gt", "value": "15-08-2026"}])


def test_contains_case_insensitive_text_only():
    assert matches([{"column": "name", "op": "contains", "value": "verma"}])
    with pytest.raises(FilterError, match="string/text columns"):
        engine().compile([{"column": "age", "op": "contains", "value": "7"}])


def test_in_operator():
    assert matches([{"column": "stage", "op": "in", "value": ["Rejected", "Applied"]}])
    assert not matches([{"column": "stage", "op": "in", "value": ["Rejected"]}])
    assert matches([{"column": "age", "op": "in", "value": ["20", "27"]}])


def test_in_requires_list():
    with pytest.raises(FilterError, match="non-empty list"):
        engine().compile([{"column": "stage", "op": "in", "value": "Applied"}])


def test_is_empty_and_not_empty():
    assert matches([{"column": "stage", "op": "is_empty"}], {**ROW, "stage": None})
    assert matches([{"column": "stage", "op": "is_empty"}], {**ROW, "stage": "  "})
    assert matches([{"column": "stage", "op": "is_not_empty"}])


def test_multiple_conditions_are_and():
    assert matches([
        {"column": "stage", "op": "eq", "value": "Applied"},
        {"column": "age", "op": "gt", "value": 25},
    ])
    assert not matches([
        {"column": "stage", "op": "eq", "value": "Applied"},
        {"column": "age", "op": "gt", "value": 30},
    ])


def test_fuzzy_columns_validation():
    with pytest.raises(FilterError, match="string/text columns"):
        engine().fuzzy_columns(["age"])
    assert engine().fuzzy_columns(None) == ["name"]
    assert engine().fuzzy_columns(["NAME"]) == ["name"]


def test_fuzzy_scores_typo_tolerance():
    e = engine()
    score = e.fuzzy_scores(ROW, ["name"], "Ashaa Verma")
    assert score >= 80
    assert e.fuzzy_scores(ROW, ["name"], "zzzz") < 50
