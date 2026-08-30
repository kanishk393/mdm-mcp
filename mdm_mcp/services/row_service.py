"""Row lifecycle: add, get, update, delete, validate, search, summarize."""

from __future__ import annotations

from mdm_mcp.models.schema import ColumnType
from mdm_mcp.search.engine import FilterEngine, FilterError
from mdm_mcp.services.dataset_service import clamp_limit
from mdm_mcp.storage.repository import JsonRepository
from mdm_mcp.validation.engine import RowValidator

MAX_BATCH_ROWS = 100
NUMERIC_TYPES = {ColumnType.INTEGER, ColumnType.FLOAT}
SORT_ORDER_ASC = "asc"


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
            selected = self._resolve_columns(schema, columns)
            payload = {name: values.get(name) for name in selected}
        else:
            payload = dict(values)
        return {"dataset": schema.name, "row": {"id": rid, **payload}}

    def update_rows(self, dataset: str, values: dict, row_ids: list[str] | None = None, conditions: list[dict] | None = None, dry_run: bool = True) -> dict:
        schema = self.repo.load_schema(dataset)
        if not values:
            raise ValueError("values is empty: provide at least one column to update.")
        unknown = [k for k in values if schema.column(k) is None]
        if unknown:
            raise ValueError(f"Unknown column(s): {', '.join(unknown)}. Available columns: {', '.join(schema.column_names())}.")
        canonical = {schema.column(k).name: v for k, v in values.items()}
        validator = RowValidator(schema)
        store = self.repo.load_rows(dataset)
        if conditions is not None:
            if row_ids:
                raise ValueError("Pass either row_ids or conditions, not both.")
            engine = FilterEngine(schema)
            compiled = engine.compile(conditions)
            matched = [rid for rid in self._ordered_ids(store) if engine.matches_all(store["rows"][rid], compiled)]
            if dry_run:
                return {
                    "requires_confirmation": True,
                    "preview": {
                        "dataset": schema.name,
                        "matched_row_ids": matched,
                        "count": len(matched),
                        "values": values,
                        "message": f"This would update {len(matched)} row(s) with {values}. Re-invoke with dry_run=false to apply.",
                    },
                }
            results: list[dict] = []
            updated = 0
            for rid in matched:
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
                "matched": len(matched),
                "updated": updated,
                "rejected": sum(1 for r in results if r["status"] == "rejected"),
                "results": results,
            }
        if not row_ids:
            raise ValueError("Provide row_ids or conditions to select rows to update.")
        results = []
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

    def delete_rows(self, dataset: str, row_ids: list[str] | None = None, conditions: list[dict] | None = None, confirm: bool = False) -> dict:
        schema = self.repo.load_schema(dataset)
        store = self.repo.load_rows(dataset)
        missing: list[str] = []
        if row_ids and conditions:
            raise ValueError("Pass either row_ids or conditions, not both.")
        if conditions is not None:
            engine = FilterEngine(schema)
            compiled = engine.compile(conditions)
            matched = [rid for rid in self._ordered_ids(store) if engine.matches_all(store["rows"][rid], compiled)]
        else:
            if not row_ids:
                raise ValueError("row_ids is empty: provide row_ids or conditions to select rows to delete.")
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

    def search_rows(
        self,
        dataset: str,
        conditions: list[dict] | None = None,
        fuzzy: bool = False,
        query: str | None = None,
        fuzzy_columns: list[str] | None = None,
        fuzzy_threshold: float = 80,
        sort_by: str | None = None,
        sort_order: str = "asc",
        limit: int = 20,
        offset: int = 0,
        columns: list[str] | None = None,
    ) -> dict:
        schema = self.repo.load_schema(dataset)
        engine = FilterEngine(schema)
        compiled = engine.compile(conditions) if conditions else []
        store = self.repo.load_rows(dataset)
        items = [(rid, store["rows"][rid]) for rid in self._ordered_ids(store)]
        if compiled:
            items = [(rid, row) for rid, row in items if engine.matches_all(row, compiled)]
        if fuzzy:
            if not query or not str(query).strip():
                raise FilterError("Fuzzy search needs a non-empty query.")
            text_columns = engine.fuzzy_columns(fuzzy_columns)
            threshold = min(max(float(fuzzy_threshold or 80), 1.0), 100.0)
            matches = []
            for rid, row in items:
                score = engine.fuzzy_scores(row, text_columns, str(query))
                if score >= threshold:
                    matches.append((rid, row, round(score, 1)))
            matches.sort(key=lambda entry: entry[2], reverse=True)
        else:
            if query:
                raise FilterError("query requires fuzzy=true. For exact filtering use conditions.")
            if sort_by:
                sort_column = schema.column(sort_by)
                if sort_column is None:
                    raise FilterError(f"Cannot sort by '{sort_by}': not a column. Available columns: {', '.join(schema.column_names())}.")
                reverse = str(sort_order).lower() != SORT_ORDER_ASC
                matches = sorted(items, key=lambda entry: self._sort_key(entry[1].get(sort_column.name)), reverse=reverse)
            else:
                matches = items
        total = len(matches)
        limit = clamp_limit(limit)
        offset = max(offset, 0)
        page = matches[offset:offset + limit]
        next_offset = offset + limit if offset + limit < total else None
        selected = self._resolve_columns(schema, columns) if columns else None
        rows = []
        for entry in page:
            rid, row = entry[0], entry[1]
            payload: dict = {"id": rid}
            if selected:
                payload.update({name: row.get(name) for name in selected})
            else:
                payload.update(row)
            if fuzzy:
                payload["_score"] = entry[2]
            rows.append(payload)
        return {
            "dataset": schema.name,
            "rows": rows,
            "total": total,
            "count": len(rows),
            "next_offset": next_offset,
        }

    def summarize_dataset(self, dataset: str) -> dict:
        schema = self.repo.load_schema(dataset)
        store = self.repo.load_rows(dataset)
        rows = list(store["rows"].values())
        numeric: dict[str, dict] = {}
        enums: dict[str, dict] = {}
        for col in schema.columns:
            if col.type in NUMERIC_TYPES:
                values = [float(row[col.name]) for row in rows if row.get(col.name) is not None]
                if values:
                    numeric[col.name] = {
                        "count": len(values),
                        "min": min(values),
                        "max": max(values),
                        "avg": round(sum(values) / len(values), 4),
                        "sum": round(sum(values), 4),
                    }
                else:
                    numeric[col.name] = {"count": 0}
            elif col.type is ColumnType.ENUM:
                counts: dict[str, int] = {}
                for row in rows:
                    raw = row.get(col.name)
                    if raw is not None:
                        counts[str(raw)] = counts.get(str(raw), 0) + 1
                enums[col.name] = counts
        return {
            "dataset": schema.name,
            "row_count": len(rows),
            "numeric": numeric,
            "enums": enums,
        }

    def _ordered_ids(self, store: dict) -> list[str]:
        return sorted(store["rows"], key=lambda rid: int(rid))

    def _sort_key(self, value):
        return (value is None, value)

    def _resolve_columns(self, schema, columns: list[str]) -> list[str]:
        unknown = [c for c in columns if schema.column(c) is None]
        if unknown:
            raise ValueError(f"Unknown column(s): {', '.join(unknown)}. Available columns: {', '.join(schema.column_names())}.")
        return [schema.column(c).name for c in columns]
