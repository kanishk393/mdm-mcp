from __future__ import annotations

from mdm_mcp.validation.engine import RowValidator


def make_validator(candidates_schema):
    return RowValidator(candidates_schema)


def test_valid_row_passes(candidates_schema):
    validator = make_validator(candidates_schema)
    row = {
        "name": "Asha Verma",
        "age": 27,
        "score": 8.5,
        "active": True,
        "stage": "Applied",
        "phone": "9876543210",
        "applied_on": "2026-08-30",
        "notes": "Strong Java background",
    }
    assert validator.validate_row(row) == []
    normalized = validator.normalize_row(row)
    assert normalized["age"] == 27
    assert normalized["score"] == 8.5
    assert normalized["active"] is True


def test_string_coercion(candidates_schema):
    validator = make_validator(candidates_schema)
    assert validator.validate_row({"name": "Asha", "age": "5", "score": "7.5", "active": "true"}) == []
    normalized = validator.normalize_row({"name": "Asha", "age": "5", "score": "7.5", "active": "true"})
    assert normalized["age"] == 5 and isinstance(normalized["age"], int)
    assert normalized["score"] == 7.5
    assert normalized["active"] is True


def test_integer_rejection_message(candidates_schema):
    validator = make_validator(candidates_schema)
    issues = validator.validate_row({"name": "Asha", "age": "abc"})
    assert any("whole number" in i for i in issues)


def test_float_rejection_message(candidates_schema):
    validator = make_validator(candidates_schema)
    issues = validator.validate_row({"name": "Asha", "score": "senior"})
    assert any("must be a number" in i for i in issues)


def test_boolean_rejection_message(candidates_schema):
    validator = make_validator(candidates_schema)
    issues = validator.validate_row({"name": "Asha", "active": "maybe"})
    assert any("true or false" in i for i in issues)


def test_unknown_column_lists_available(candidates_schema):
    validator = make_validator(candidates_schema)
    issues = validator.validate_row({"name": "Asha", "emial": "x"})
    assert any("not defined" in i and "notes" in i for i in issues)


def test_missing_required_column(candidates_schema):
    validator = make_validator(candidates_schema)
    issues = validator.validate_row({"age": 20})
    assert any("name" in i and "required" in i for i in issues)


def test_enum_rejection_lists_options(candidates_schema):
    validator = make_validator(candidates_schema)
    issues = validator.validate_row({"name": "Asha", "stage": "Hired"})
    assert any("Applied, Screened, Rejected" in i for i in issues)


def test_phone_formats(candidates_schema):
    validator = make_validator(candidates_schema)
    assert validator.validate_row({"name": "Asha", "phone": "9876543210"}) == []
    assert validator.validate_row({"name": "Asha", "phone": "+919876543210"}) == []
    assert validator.validate_row({"name": "Asha", "phone": "09876543210"}) == []
    issues = validator.validate_row({"name": "Asha", "phone": "12345"})
    assert any("Indian mobile" in i for i in issues)


def test_date_formats(candidates_schema):
    validator = make_validator(candidates_schema)
    assert validator.validate_row({"name": "Asha", "applied_on": "2026-08-30"}) == []
    issues = validator.validate_row({"name": "Asha", "applied_on": "30-08-2026"})
    assert any("YYYY-MM-DD" in i for i in issues)


def test_numeric_bounds(candidates_schema):
    validator = make_validator(candidates_schema)
    assert any("at most 10" in i for i in validator.validate_row({"name": "Asha", "score": 11}))
    assert any("at least 0" in i for i in validator.validate_row({"name": "Asha", "score": -1}))
    assert validator.validate_row({"name": "Asha", "score": 0}) == []
    assert validator.validate_row({"name": "Asha", "score": 10}) == []


def test_defaults_fill_missing_optional_columns(candidates_schema):
    validator = make_validator(candidates_schema)
    normalized = validator.normalize_row({"name": "Asha"})
    assert set(normalized) == {c.name for c in candidates_schema.columns}
    assert normalized["age"] is None
    assert normalized["stage"] is None
