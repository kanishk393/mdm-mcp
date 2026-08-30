"""Dataset and column schema models."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ColumnType(str, Enum):
    STRING = "string"
    TEXT = "text"
    BOOLEAN = "boolean"
    INTEGER = "integer"
    FLOAT = "float"
    PHONE = "phone"
    DATE = "date"
    ENUM = "enum"


INDIA_PHONE_PATTERN = r"(?:\+91[\s-]?|0)?[6-9]\d{9}"

NUMERIC_TYPES = {ColumnType.INTEGER, ColumnType.FLOAT}
TEXTUAL_TYPES = {ColumnType.STRING, ColumnType.TEXT}


class ColumnSpec(BaseModel):
    """A single user-defined column of a dataset."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Column name, e.g. 'full_name' or 'applied_on'.", min_length=1)
    type: ColumnType = Field(description="Value type: string, text, boolean, integer, float, phone, date, enum.")
    required: bool = Field(default=False, description="Whether every row must provide a non-empty value.")
    default: Any = Field(default=None, description="Value used when a row omits this column.")
    min_value: float | None = Field(default=None, description="Minimum allowed value for numeric columns.")
    max_value: float | None = Field(default=None, description="Maximum allowed value for numeric columns.")
    pattern: str | None = Field(default=None, description="Regex the value must fully match (string/text columns). Defaults to Indian mobile format for phone columns.")
    options: list[str] | None = Field(default=None, description="Allowed values for enum columns.")

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def _check_constraints(self) -> "ColumnSpec":
        if self.type is ColumnType.ENUM and not self.options:
            raise ValueError(f"enum column '{self.name}' needs at least one option")
        if self.options is not None and len(self.options) != len({o.strip() for o in self.options}):
            raise ValueError(f"enum column '{self.name}' has duplicate options")
        if self.pattern is not None:
            try:
                re.compile(self.pattern)
            except re.error as exc:
                raise ValueError(f"column '{self.name}' has an invalid pattern: {exc}") from exc
        elif self.type is ColumnType.PHONE:
            self.pattern = INDIA_PHONE_PATTERN
        if self.min_value is not None and self.max_value is not None and self.min_value > self.max_value:
            raise ValueError(f"column '{self.name}' has min_value greater than max_value")
        return self


class DatasetSchema(BaseModel):
    """The user-defined schema of one dataset."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Dataset display name, e.g. 'Candidates'.")
    description: str = ""
    columns: list[ColumnSpec] = Field(min_length=1)

    def column(self, name: str) -> ColumnSpec | None:
        lowered = name.strip().lower()
        return next((c for c in self.columns if c.name.lower() == lowered), None)

    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]
