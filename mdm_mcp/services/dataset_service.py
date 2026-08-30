"""Dataset lifecycle: create, list, describe, add/update/remove column, delete."""

from __future__ import annotations

from pydantic import ValidationError

from mdm_mcp.models.schema import ColumnSpec, ColumnType, ColumnUpdate, DatasetSchema
from mdm_mcp.storage.repository import JsonRepository
from mdm_mcp.validation.engine import RowValidator

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

    def add_column(self, dataset: str, column: dict) -> dict:
        schema = self.repo.load_schema(dataset)
        try:
            spec = ColumnSpec.model_validate(column)
        except ValidationError as exc:
            raise ValueError(f"Invalid column definition: {self._validation_message(exc)}")
        if schema.column(spec.name) is not None:
            raise ValueError(f"Column '{spec.name}' already exists in '{schema.name}'. Use update_column to change it.")
        store = self.repo.load_rows(dataset)
        for row in store["rows"].values():
            row[spec.name] = spec.default
        self.repo.save_schema(schema.model_copy(update={"columns": [*schema.columns, spec]}))
        self.repo.save_rows(dataset, store)
        return {
            "dataset": schema.name,
            "column": spec.name,
            "type": spec.type.value,
            "backfilled_rows": len(store["rows"]),
        }

    def update_column(self, dataset: str, column_name: str, changes: ColumnUpdate | dict) -> dict:
        schema = self.repo.load_schema(dataset)
        if isinstance(changes, dict):
            try:
                changes = ColumnUpdate.model_validate(changes)
            except ValidationError as exc:
                raise ValueError(f"Invalid column update: {self._validation_message(exc)}")
        existing = schema.column(column_name)
        if existing is None:
            raise ValueError(f"Column '{column_name}' does not exist in '{schema.name}'. Available columns: {', '.join(schema.column_names())}.")
        data = existing.model_dump()
        for key in changes.model_fields_set:
            data[key] = getattr(changes, key)
        new_name = str(data.get("name") or "").strip()
        if new_name and new_name.lower() != existing.name.lower() and schema.column(new_name) is not None:
            raise ValueError(f"Column '{new_name}' already exists in '{schema.name}'.")
        try:
            updated = ColumnSpec.model_validate(data)
        except ValidationError as exc:
            raise ValueError(f"Invalid column update: {self._validation_message(exc)}")
        new_columns = [updated if c is existing else c for c in schema.columns]
        new_schema = schema.model_copy(update={"columns": new_columns})
        store = self.repo.load_rows(dataset)
        renamed = updated.name != existing.name
        if renamed:
            for row in store["rows"].values():
                if existing.name in row:
                    row[updated.name] = row.pop(existing.name)
            self.repo.save_rows(dataset, store)
        validator = RowValidator(new_schema)
        invalid: dict[str, list[str]] = {}
        for rid, row in store["rows"].items():
            errors = validator.validate_row(row)
            if errors:
                invalid[rid] = errors
        self.repo.save_schema(new_schema)
        return {
            "dataset": schema.name,
            "column": updated.name,
            "renamed_from": existing.name if renamed else None,
            "rows_checked": len(store["rows"]),
            "invalid_rows": invalid,
        }

    def remove_column(self, dataset: str, column_name: str, confirm: bool) -> dict:
        schema = self.repo.load_schema(dataset)
        existing = schema.column(column_name)
        if existing is None:
            raise ValueError(f"Column '{column_name}' does not exist in '{schema.name}'. Available columns: {', '.join(schema.column_names())}.")
        store = self.repo.load_rows(dataset)
        if not confirm:
            return {
                "requires_confirmation": True,
                "preview": {
                    "dataset": schema.name,
                    "column": existing.name,
                    "affected_rows": len(store["rows"]),
                    "message": f"This permanently drops column '{existing.name}' and its values from {len(store['rows'])} row(s). Re-invoke with confirm=true to proceed.",
                },
            }
        if len(schema.columns) == 1:
            raise ValueError("Cannot remove the last column of a dataset. Delete the dataset instead.")
        remaining = [c for c in schema.columns if c is not existing]
        self.repo.save_schema(schema.model_copy(update={"columns": remaining}))
        for row in store["rows"].values():
            row.pop(existing.name, None)
        self.repo.save_rows(dataset, store)
        return {"dataset": schema.name, "removed": existing.name, "rows_updated": len(store["rows"])}

    def delete_dataset(self, name: str, confirm: bool) -> dict:
        schema = self.repo.load_schema(name)
        row_count = self.repo.row_count(name)
        if not confirm:
            return {
                "requires_confirmation": True,
                "preview": {
                    "dataset": schema.name,
                    "row_count": row_count,
                    "column_count": len(schema.columns),
                    "message": f"This permanently deletes dataset '{schema.name}' and its {row_count} row(s). Re-invoke with confirm=true to proceed.",
                },
            }
        self.repo.delete_dataset(schema.name)
        return {"deleted": schema.name, "rows_removed": row_count}

    def _build_columns(self, columns: list[dict]) -> list[ColumnSpec]:
        specs: list[ColumnSpec] = []
        problems: list[str] = []
        for index, raw in enumerate(columns):
            try:
                specs.append(ColumnSpec.model_validate(raw))
            except ValidationError as exc:
                problems.append(f"columns[{index}]: {self._validation_message(exc)}")
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
        if col.pattern is not None and col.type is not ColumnType.PHONE:
            detail["pattern"] = col.pattern
        if col.options is not None:
            detail["options"] = col.options
        return detail

    @staticmethod
    def _validation_message(exc: ValidationError) -> str:
        first = exc.errors(include_url=False)[0]
        loc = ".".join(str(part) for part in first.get("loc", ()))
        prefix = f"{loc}: " if loc else ""
        return f"{prefix}{first['msg']}"
