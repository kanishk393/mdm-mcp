"""Row lifecycle: add, get, update, delete, validate."""

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

    def update_rows(self, dataset: str, row_ids: list[str], values: dict) -> dict:
        schema = self.repo.load_schema(dataset)
        if not values:
            raise ValueError("values is empty: provide at least one column to update.")
        unknown = [k for k in values if schema.column(k) is None]
        if unknown:
            raise ValueError(f"Unknown column(s): {', '.join(unknown)}. Available columns: {', '.join(schema.column_names())}.")
        canonical = {schema.column(k).name: v for k, v in values.items()}
        validator = RowValidator(schema)
        store = self.repo.load_rows(dataset)
        results: list[dict] = []
        updated = 0
        for raw_id in row_ids:
            rid = str(raw_id)
            if rid not in store["rows"]:
                results.append({"row_id": rid, "status": "not_found"})
                continue
            merged = {**store["rows"][rid], **canonical}
            errors = validator.validate_row(merged)
            if errors:
                results.append({"row_id": rid, "status": "rejected", "errors": errors})
                continue
            store["rows"][rid] = validator.normalize_row(merged)
            results.append({"row_id": rid, "status": "updated"})
            updated += 1
        if updated:
            self.repo.save_rows(dataset, store)
        return {
            "dataset": schema.name,
            "updated": updated,
            "rejected": sum(1 for r in results if r["status"] == "rejected"),
            "not_found": sum(1 for r in results if r["status"] == "not_found"),
            "results": results,
        }

    def delete_rows(self, dataset: str, row_ids: list[str], confirm: bool) -> dict:
        schema = self.repo.load_schema(dataset)
        if not row_ids:
            raise ValueError("row_ids is empty: provide at least one row id to delete.")
        store = self.repo.load_rows(dataset)
        wanted = [str(rid) for rid in row_ids]
        matched = [rid for rid in wanted if rid in store["rows"]]
        missing = [rid for rid in wanted if rid not in store["rows"]]
        if not confirm:
            return {
                "requires_confirmation": True,
                "preview": {
                    "dataset": schema.name,
                    "row_ids": matched,
                    "count": len(matched),
                    "not_found": missing,
                    "message": f"This permanently deletes {len(matched)} row(s). Re-invoke with confirm=true to proceed.",
                },
            }
        for rid in matched:
            store["rows"].pop(rid)
        self.repo.save_rows(dataset, store)
        return {"dataset": schema.name, "deleted": len(matched), "row_ids": matched, "not_found": missing}

    def validate_rows(self, dataset: str, rows: list[dict]) -> dict:
        if len(rows) > MAX_BATCH_ROWS:
            raise ValueError(f"validate_rows accepts at most {MAX_BATCH_ROWS} rows per call; got {len(rows)}.")
        schema = self.repo.load_schema(dataset)
        validator = RowValidator(schema)
        results: list[dict] = []
        valid = 0
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                results.append({"row": index, "status": "invalid", "errors": ["Each row must be an object mapping column names to values."]})
                continue
            errors = validator.validate_row(row)
            if errors:
                results.append({"row": index, "status": "invalid", "errors": errors})
                continue
            results.append({"row": index, "status": "valid", "normalized": validator.normalize_row(row)})
            valid += 1
        return {
            "dataset": schema.name,
            "total": len(rows),
            "valid": valid,
            "invalid": len(rows) - valid,
            "results": results,
        }
