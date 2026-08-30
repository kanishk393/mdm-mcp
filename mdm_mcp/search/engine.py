"""FilterEngine: compiles and evaluates the {column, op, value} filter DSL.

Also hosts fuzzy matching over string/text columns via rapidfuzz.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from rapidfuzz import fuzz

from mdm_mcp.models.schema import ColumnSpec, ColumnType, DatasetSchema

SUPPORTED_OPS = {"eq", "ne", "gt", "gte", "lt", "lte", "contains", "in", "between", "is_empty", "is_not_empty"}
RANGE_OPS = {"gt", "gte", "lt", "lte", "between"}
NO_VALUE_OPS = {"is_empty", "is_not_empty"}
TEXTUAL = {ColumnType.STRING, ColumnType.TEXT}
ORDERED = {ColumnType.INTEGER, ColumnType.FLOAT, ColumnType.DATE}


class FilterError(ValueError):
    """Raised when a filter or fuzzy search request is invalid."""


class FilterEngine:
    def __init__(self, schema: DatasetSchema):
        self.schema = schema

    def compile(self, conditions: list[dict]) -> list[tuple[ColumnSpec, str, Any]]:
        if not conditions:
            raise FilterError("conditions is empty: provide at least one {column, op, value} filter.")
        return [self._compile_one(index, cond) for index, cond in enumerate(conditions)]

    def _compile_one(self, index: int, cond: Any) -> tuple[ColumnSpec, str, Any]:
        if not isinstance(cond, dict) or "column" not in cond or "op" not in cond:
            raise FilterError(f"conditions[{index}] must be an object with 'column' and 'op' keys.")
        col = self.schema.column(cond["column"])
        if col is None:
            raise FilterError(f"Column '{cond['column']}' is not defined in this dataset. Available columns: {', '.join(self.schema.column_names())}.")
        op = str(cond["op"]).lower()
        if op not in SUPPORTED_OPS:
            raise FilterError(f"Filter op '{cond['op']}' is not supported. Supported ops: {', '.join(sorted(SUPPORTED_OPS))}.")
        value = cond.get("value")
        if op in NO_VALUE_OPS:
            return (col, op, None)
        if op in RANGE_OPS:
            self._require_ordered(col, op)
            if op == "between":
                if not isinstance(value, (list, tuple)) or len(value) != 2:
                    raise FilterError(f"Filter on '{col.name}' with op 'between' needs a two-value list [low, high].")
                value = [self._coerce_bound(col, value[0], op), self._coerce_bound(col, value[1], op)]
            else:
                value = self._coerce_bound(col, value, op)
        elif op == "in":
            if not isinstance(value, (list, tuple)) or not value:
                raise FilterError(f"Filter on '{col.name}' with op 'in' needs a non-empty list of values.")
            value = [self._coerce_bound(col, item, op) for item in value]
        elif op in {"eq", "ne"} and col.type in ORDERED:
            value = self._coerce_bound(col, value, op)
        elif op == "contains":
            if col.type not in TEXTUAL:
                raise FilterError(f"op 'contains' works on string/text columns; '{col.name}' is {col.type.value}. Use eq or in instead.")
            if not isinstance(value, str):
                raise FilterError(f"Filter on '{col.name}' with op 'contains' needs a text value.")
        return (col, op, value)

    def fuzzy_columns(self, names: list[str] | None) -> list[str]:
        available = [c.name for c in self.schema.columns if c.type in TEXTUAL]
        if not available:
            raise FilterError(f"Dataset '{self.schema.name}' has no string/text columns to fuzzy search.")
        if names is None:
            return available
        resolved: list[str] = []
        for name in names:
            col = self.schema.column(name)
            if col is None or col.type not in TEXTUAL:
                raise FilterError(f"Fuzzy search columns must be string/text columns; '{name}' is not. Text columns: {', '.join(available)}.")
            if col.name not in resolved:
                resolved.append(col.name)
        return resolved

    def fuzzy_scores(self, row: dict, columns: list[str], query: str) -> float:
        best = 0.0
        needle = query.strip().lower()
        for name in columns:
            raw = row.get(name)
            if raw is None or not str(raw).strip():
                continue
            target = str(raw).lower()
            best = max(best, fuzz.ratio(needle, target), fuzz.partial_ratio(needle, target))
        return best

    def matches_all(self, row: dict, compiled: list[tuple[ColumnSpec, str, Any]]) -> bool:
        return all(self._test(row, col, op, value) for col, op, value in compiled)

    def _require_ordered(self, col: ColumnSpec, op: str) -> None:
        if col.type not in ORDERED:
            raise FilterError(f"op '{op}' needs a numeric or date column; '{col.name}' is {col.type.value}.")

    def _coerce_bound(self, col: ColumnSpec, value: Any, op: str) -> Any:
        if col.type in {ColumnType.INTEGER, ColumnType.FLOAT}:
            try:
                return float(value)
            except (TypeError, ValueError):
                raise FilterError(f"Filter on '{col.name}' with op '{op}' needs a numeric value, got {value!r}.")
        if col.type is ColumnType.DATE:
            try:
                date.fromisoformat(str(value))
            except ValueError:
                raise FilterError(f"Filter on '{col.name}' with op '{op}' needs a YYYY-MM-DD date, got {value!r}.")
            return str(value)
        return value

    def _test(self, row: dict, col: ColumnSpec, op: str, value: Any) -> bool:
        raw = row.get(col.name)
        if op == "is_empty":
            return raw is None or (isinstance(raw, str) and not raw.strip())
        if op == "is_not_empty":
            return not (raw is None or (isinstance(raw, str) and not raw.strip()))
        if raw is None:
            return op == "ne"
        if col.type in {ColumnType.INTEGER, ColumnType.FLOAT}:
            try:
                left = float(raw)
            except (TypeError, ValueError):
                return False
            return self._compare(left, op, value)
        if col.type is ColumnType.DATE:
            return self._compare(str(raw), op, value)
        if op == "eq":
            return str(raw) == str(value)
        if op == "ne":
            return str(raw) != str(value)
        if op == "in":
            return str(raw) in [str(item) for item in value]
        if op == "contains":
            return str(value).lower() in str(raw).lower()
        return False

    def _compare(self, left: Any, op: str, value: Any) -> bool:
        if op == "eq":
            return left == value
        if op == "ne":
            return left != value
        if op == "gt":
            return left > value
        if op == "gte":
            return left >= value
        if op == "lt":
            return left < value
        if op == "lte":
            return left <= value
        if op == "between":
            return value[0] <= left <= value[1]
        if op == "in":
            return left in value
        return False
