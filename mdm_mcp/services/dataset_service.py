"""Dataset lifecycle: create, list, describe."""

from __future__ import annotations

from pydantic import ValidationError

from mdm_mcp.models.schema import ColumnSpec, ColumnType, DatasetSchema
from mdm_mcp.storage.repository import JsonRepository

DEFAULT_PAGE_LIMIT = 20
MAX_PAGE_LIMIT = 100
MAX_SAMPLE_ROWS = 5


def clamp_limit(limit: int, default: int = DEFAULT_PAGE_LIMIT) -> int:
    if limit is None or limit <= 0:
        return default
    return min(limit, MAX_PAGE_LIMIT)


class DatasetService:
    def __init__(self, repo: JsonRepository):
        self.repo = repo

    def create_dataset(self, name: str, description: str, columns: list[dict]) -> dict:
        stripped = name.strip()
        if not stripped:
            raise ValueError("Dataset name cannot be empty.")
        if self.repo.dataset_exists(stripped):
            raise ValueError(f"A dataset named '{stripped}' already exists. Choose a different name or use describe_dataset to inspect the existing one.")
        specs = self._build_columns(columns)
        self._ensure_unique_column_names(specs)
        schema = DatasetSchema(name=stripped, description=description.strip(), columns=specs)
        self.repo.save_schema(schema)
        self.repo.save_rows(stripped, {"rows": {}, "next_id": 1})
        return {"dataset": schema.name, "columns": self._column_summaries(schema)}

    def list_datasets(self, limit: int, offset: int) -> dict:
        limit = clamp_limit(limit)
        offset = max(offset, 0)
        names = self.repo.dataset_names()
        total = len(names)
        items = []
        for name in names[offset:offset + limit]:
            schema = self.repo.load_schema(name)
            items.append({
                "name": schema.name,
                "description": schema.description,
                "row_count": self.repo.row_count(name),
                "columns": self._column_summaries(schema),
            })
        next_offset = offset + limit if offset + limit < total else None
        return {"datasets": items, "total": total, "count": len(items), "next_offset": next_offset}

    def describe_dataset(self, name: str, sample_rows: int) -> dict:
        schema = self.repo.load_schema(name)
        sample_rows = max(0, min(sample_rows, MAX_SAMPLE_ROWS))
        samples: list[dict] = []
        if sample_rows:
            store = self.repo.load_rows(name)
            row_ids = sorted(store["rows"], key=lambda rid: int(rid))[:sample_rows]
            samples = [{"id": rid, **store["rows"][rid]} for rid in row_ids]
        return {
            "dataset": schema.name,
            "description": schema.description,
            "row_count": self.repo.row_count(name),
            "columns": [self._column_detail(col) for col in schema.columns],
            "samples": samples,
        }

    def _build_columns(self, columns: list[dict]) -> list[ColumnSpec]:
        specs: list[ColumnSpec] = []
        problems: list[str] = []
        for index, raw in enumerate(columns):
            try:
                specs.append(ColumnSpec.model_validate(raw))
            except ValidationError as exc:
                problems.append(f"columns[{index}]: {exc.errors(include_url=False)[0]['msg']}")
        if problems:
            raise ValueError("Invalid column definition(s):\n" + "\n".join(problems))
        if not specs:
            raise ValueError("A dataset needs at least one column.")
        return specs

    def _ensure_unique_column_names(self, specs: list[ColumnSpec]) -> None:
        lowered = [c.name.lower() for c in specs]
        duplicates = sorted({n for n in lowered if lowered.count(n) > 1})
        if duplicates:
            raise ValueError(f"Duplicate column names are not allowed: {', '.join(duplicates)}.")

    def _column_summaries(self, schema: DatasetSchema) -> list[dict]:
        return [{"name": c.name, "type": c.type.value} for c in schema.columns]

    def _column_detail(self, col: ColumnSpec) -> dict:
        detail: dict = {
            "name": col.name,
            "type": col.type.value,
            "required": col.required,
        }
        if col.default is not None:
            detail["default"] = col.default
        if col.min_value is not None:
            detail["min_value"] = col.min_value
        if col.max_value is not None:
            detail["max_value"] = col.max_value
        if col.pattern is not None and col.type not in {ColumnType.PHONE}:
            detail["pattern"] = col.pattern
        if col.options is not None:
            detail["options"] = col.options
        return detail
