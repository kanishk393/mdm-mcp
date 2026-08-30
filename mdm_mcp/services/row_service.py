"""Row lifecycle: add, get (update, delete, validate arrive in Phase 2)."""

from __future__ import annotations

from mdm_mcp.storage.repository import JsonRepository
from mdm_mcp.validation.engine import RowValidator

MAX_BATCH_ROWS = 100


class RowService:
    def __init__(self, repo: JsonRepository):
        self.repo = repo

    def add_rows(self, dataset: str, rows: list[dict]) -> dict:
        if len(rows) > MAX_BATCH_ROWS:
            raise ValueError(f"add_rows accepts at most {MAX_BATCH_ROWS} rows per call; got {len(rows)}. Split the batch and try again.")
        schema = self.repo.load_schema(dataset)
        validator = RowValidator(schema)
        store = self.repo.load_rows(dataset)
        results: list[dict] = []
        added = 0
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                results.append({"row": index, "status": "rejected", "errors": ["Each row must be an object mapping column names to values."]})
                continue
            errors = validator.validate_row(row)
            if errors:
                results.append({"row": index, "status": "rejected", "errors": errors})
                continue
            row_id = str(store["next_id"])
            store["next_id"] += 1
            store["rows"][row_id] = validator.normalize_row(row)
            results.append({"row": index, "status": "added", "row_id": row_id})
            added += 1
        if added:
            self.repo.save_rows(dataset, store)
        return {
            "dataset": schema.name,
            "added": added,
            "rejected": len(rows) - added,
            "results": results,
        }

    def get_row(self, dataset: str, row_id: str, columns: list[str] | None) -> dict:
        schema = self.repo.load_schema(dataset)
        store = self.repo.load_rows(dataset)
        rid = str(row_id)
        if rid not in store["rows"]:
            raise ValueError(f"Row '{row_id}' does not exist in dataset '{schema.name}'.")
        values = store["rows"][rid]
        if columns:
            unknown = [c for c in columns if schema.column(c) is None]
            if unknown:
                raise ValueError(f"Unknown column(s): {', '.join(unknown)}. Available columns: {', '.join(schema.column_names())}.")
            payload = {schema.column(c).name: values.get(schema.column(c).name) for c in columns}
        else:
            payload = dict(values)
        return {"dataset": schema.name, "row": {"id": rid, **payload}}
