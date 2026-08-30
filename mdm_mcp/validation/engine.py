"""RowValidator: coerces and validates rows against a dataset schema.

Type coercion is delegated to a pydantic model built per dataset schema, so
"5" becomes 5 for integer columns and "true" becomes True for boolean columns.
Constraint checks (required, min/max, pattern, enum, phone, date) produce
plain-language messages the agent can relay directly to a naive user.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError, create_model

from mdm_mcp.models.schema import ColumnSpec, ColumnType, DatasetSchema

PYDANTIC_TYPE_MAP: dict[ColumnType, type] = {
    ColumnType.STRING: str,
    ColumnType.TEXT: str,
    ColumnType.BOOLEAN: bool,
    ColumnType.INTEGER: int,
    ColumnType.FLOAT: float,
    ColumnType.PHONE: str,
    ColumnType.DATE: str,
    ColumnType.ENUM: str,
}


class _RowBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RowValidator:
    def __init__(self, schema: DatasetSchema):
        self.schema = schema
        self._model = self._build_model()

    def _build_model(self) -> type[BaseModel]:
        fields: dict[str, tuple[type, Any]] = {}
        for col in self.schema.columns:
            fields[col.name] = (PYDANTIC_TYPE_MAP[col.type], col.default)
        return create_model("RowModel", __base__=_RowBase, **fields)

    def validate_row(self, row: dict) -> list[str]:
        try:
            coerced = self._model.model_validate(row)
        except ValidationError as exc:
            return self._coercion_messages(exc)
        issues: list[str] = []
        for col in self.schema.columns:
            issues.extend(self._constraint_issues(col, getattr(coerced, col.name)))
        return issues

    def normalize_row(self, row: dict) -> dict:
        coerced = self._model.model_validate(row)
        return {col.name: getattr(coerced, col.name) for col in self.schema.columns}

    def _coercion_messages(self, exc: ValidationError) -> list[str]:
        available = ", ".join(self.schema.column_names())
        messages = []
        for error in exc.errors(include_url=False):
            loc = error.get("loc", ())
            column = str(loc[0]) if loc else "row"
            etype = error.get("type", "")
            if etype == "extra_forbidden":
                messages.append(f"Column '{column}' is not defined in this dataset. Available columns: {available}.")
            elif etype in {"int_parsing", "int_from_float"}:
                messages.append(f"Column '{column}' must be a whole number (integer).")
            elif etype == "float_parsing":
                messages.append(f"Column '{column}' must be a number.")
            elif etype in {"bool_parsing", "bool_type"}:
                messages.append(f"Column '{column}' must be true or false.")
            elif etype == "string_type":
                messages.append(f"Column '{column}' must be text.")
            else:
                messages.append(f"Column '{column}' has an invalid value: {error.get('msg', '')}.")
        return messages

    def _constraint_issues(self, col: ColumnSpec, value: Any) -> list[str]:
        if col.required and (value is None or (isinstance(value, str) and not value.strip())):
            return [f"Column '{col.name}' is required."]
        if value is None:
            return []
        if col.type is ColumnType.ENUM:
            if str(value) not in [str(o) for o in (col.options or [])]:
                return [f"Column '{col.name}' must be one of: {', '.join(col.options or [])}."]
        if col.type is ColumnType.PHONE:
            if not re.fullmatch(col.pattern, str(value).strip()):
                return [f"Column '{col.name}' must be a valid Indian mobile number (10 digits, optional +91 or 0 prefix)."]
        if col.type is ColumnType.DATE:
            try:
                date.fromisoformat(str(value))
            except ValueError:
                return [f"Column '{col.name}' must be a date in YYYY-MM-DD format."]
        if col.pattern is not None and col.type in {ColumnType.STRING, ColumnType.TEXT}:
            if not re.fullmatch(col.pattern, str(value)):
                return [f"Column '{col.name}' does not match the required pattern."]
        if col.type is ColumnType.INTEGER or col.type is ColumnType.FLOAT:
            if col.min_value is not None and value < col.min_value:
                return [f"Column '{col.name}' must be at least {col.min_value:g}."]
            if col.max_value is not None and value > col.max_value:
                return [f"Column '{col.name}' must be at most {col.max_value:g}."]
        return []
