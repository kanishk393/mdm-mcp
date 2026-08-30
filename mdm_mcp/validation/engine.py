"""RowValidator: coerces and validates rows against a dataset schema.

Each column is checked independently so a row with several problems reports all
of them: type coercion runs per column via a cached pydantic TypeAdapter, then
constraint checks (required, min/max, pattern, enum, phone, date) produce
plain-language messages the agent can relay directly to a naive user.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError, create_model

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

TYPE_MESSAGES: dict[ColumnType, str] = {
    ColumnType.INTEGER: "must be a whole number (integer)",
    ColumnType.FLOAT: "must be a number",
    ColumnType.BOOLEAN: "must be true or false",
}

_TYPE_ADAPTERS: dict[ColumnType, TypeAdapter] = {}

_INVALID_BOOL = object()


def _type_adapter(column_type: ColumnType) -> TypeAdapter:
    if column_type not in _TYPE_ADAPTERS:
        _TYPE_ADAPTERS[column_type] = TypeAdapter(PYDANTIC_TYPE_MAP[column_type] | None)
    return _TYPE_ADAPTERS[column_type]


class _RowBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RowValidator:
    def __init__(self, schema: DatasetSchema):
        self.schema = schema
        self._model = self._build_model()
        self._available = ", ".join(schema.column_names())

    def _build_model(self) -> type[BaseModel]:
        fields: dict[str, tuple[type, Any]] = {}
        for col in self.schema.columns:
            fields[col.name] = (PYDANTIC_TYPE_MAP[col.type] | None, col.default)
        return create_model("RowModel", __base__=_RowBase, **fields)

    def validate_row(self, row: dict) -> list[str]:
        issues: list[str] = []
        for key in row:
            if self.schema.column(key) is None:
                issues.append(f"Column '{key}' is not defined in this dataset. Available columns: {self._available}.")
        for col in self.schema.columns:
            raw = row[col.name] if col.name in row else col.default
            if col.type is ColumnType.BOOLEAN:
                value = self._coerce_bool(raw)
                if value is _INVALID_BOOL:
                    issues.append(f"Column '{col.name}' must be true or false.")
                    continue
            else:
                try:
                    value = _type_adapter(col.type).validate_python(raw)
                except ValidationError:
                    issues.append(f"Column '{col.name}' {TYPE_MESSAGES.get(col.type, 'must be text')}.")
                    continue
            if col.required and (value is None or (isinstance(value, str) and not value.strip())):
                issues.append(f"Column '{col.name}' is required.")
                continue
            issues.extend(self._constraint_issues(col, value))
        return issues

    @staticmethod
    def _coerce_bool(raw):
        if raw is None:
            return None
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, int) and raw in (0, 1):
            return bool(raw)
        if isinstance(raw, str):
            lowered = raw.strip().lower()
            if lowered in {"true", "1"}:
                return True
            if lowered in {"false", "0"}:
                return False
        return _INVALID_BOOL

    def normalize_row(self, row: dict) -> dict:
        coerced = self._model.model_validate(row)
        return {col.name: getattr(coerced, col.name) for col in self.schema.columns}

    def _constraint_issues(self, col: ColumnSpec, value: Any) -> list[str]:
        if value is None:
            return []
        if col.type is ColumnType.ENUM:
            if str(value) not in [str(option) for option in (col.options or [])]:
                return [f"Column '{col.name}' must be one of: {', '.join(col.options or [])}."]
        if col.type is ColumnType.PHONE:
            digits = re.sub(r"[\s\-\(\)]", "", str(value))
            if not re.fullmatch(col.pattern, digits):
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
                return [f"Column '{col.name}' must be at least {self._fmt_number(col.min_value)}."]
            if col.max_value is not None and value > col.max_value:
                return [f"Column '{col.name}' must be at most {self._fmt_number(col.max_value)}."]
        return []

    @staticmethod
    def _fmt_number(value: float) -> str:
        if float(value).is_integer():
            return f"{int(value):,}"
        return f"{value:.6f}".rstrip("0").rstrip(".")
