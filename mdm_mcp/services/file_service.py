"""File operations: CSV/JSON import and export."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from mdm_mcp.models.schema import DatasetSchema
from mdm_mcp.search.engine import FilterEngine
from mdm_mcp.storage.repository import DatasetNotFound, JsonRepository
from mdm_mcp.validation.engine import RowValidator

MAX_REPORTED_REJECTIONS = 100


class FileService:
    def __init__(self, repo: JsonRepository):
        self.repo = repo

    def import_rows(self, dataset: str, file_path: str, format: str, confirm: bool, create_if_missing: bool = False) -> dict:
        path = Path(file_path).expanduser()
        if not path.exists():
            raise ValueError(f"File not found: {file_path}")
        fmt = self._resolve_format(path, format)
        rows, file_columns = self._read_rows(path, fmt)
        try:
            schema = self.repo.load_schema(dataset)
        except DatasetNotFound:
            if not create_if_missing:
                raise
            schema = self._create_from_headers(dataset, file_columns)
        mapping, unmatched = self._build_mapping(schema, file_columns)
        mapped = [{mapping[key]: value for key, value in row.items() if key in mapping} for row in rows]
        missing_required = [col.name for col in schema.columns if col.required and col.name not in mapping.values()]
        if not confirm:
            return {
                "requires_confirmation": True,
                "preview": {
                    "dataset": schema.name,
                    "file": str(path),
                    "format": fmt,
                    "row_count": len(mapped),
                    "file_columns": file_columns,
                    "mapping": mapping,
                    "unmatched_file_columns": unmatched,
                    "missing_required_columns": missing_required,
                    "sample_rows": mapped[:3],
                    "message": "Re-invoke with confirm=true to import. Unmatched file columns are ignored; rows missing required columns will be rejected.",
                },
            }
        validator = RowValidator(schema)
        store = self.repo.load_rows(dataset)
        added = 0
        rejected: list[dict] = []
        for index, row in enumerate(mapped):
            errors = validator.validate_row(row)
            if errors:
                rejected.append({"row": index, "errors": errors})
                continue
            row_id = str(store["next_id"])
            store["next_id"] += 1
            store["rows"][row_id] = validator.normalize_row(row)
            added += 1
        if added:
            self.repo.save_rows(dataset, store)
        return {
            "dataset": schema.name,
            "added": added,
            "rejected": len(rejected),
            "rejected_rows": rejected[:MAX_REPORTED_REJECTIONS],
            "rejected_truncated": len(rejected) > MAX_REPORTED_REJECTIONS,
        }

    def export_rows(self, dataset: str, file_path: str, format: str, conditions: list[dict] | None = None, columns: list[str] | None = None, overwrite: bool = False) -> dict:
        schema = self.repo.load_schema(dataset)
        path = Path(file_path).expanduser()
        fmt = self._resolve_format(path, format)
        if path.exists() and not overwrite:
            raise ValueError(f"File already exists: {path}. Pass overwrite=true to replace it.")
        engine = FilterEngine(schema)
        compiled = engine.compile(conditions) if conditions else []
        store = self.repo.load_rows(dataset)
        items = sorted(store["rows"].items(), key=lambda entry: int(entry[0]))
        matched = [(rid, row) for rid, row in items if engine.matches_all(row, compiled)]
        selected = self._resolve_columns(schema, columns) if columns else schema.column_names()
        path.parent.mkdir(parents=True, exist_ok=True)
        if fmt == "csv":
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(["id", *selected])
                for rid, row in matched:
                    writer.writerow([rid] + [self._csv_cell(row.get(name)) for name in selected])
        else:
            payload = [{"id": rid, **{name: row.get(name) for name in selected}} for rid, row in matched]
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "dataset": schema.name,
            "file": str(path),
            "format": fmt,
            "rows_exported": len(matched),
        }

    def _create_from_headers(self, dataset: str, file_columns: list[str]) -> DatasetSchema:
        if not file_columns:
            raise ValueError("Cannot auto-create a dataset from an empty file.")
        schema = DatasetSchema(name=dataset.strip(), columns=[
            {"name": col, "type": "string"} for col in file_columns
        ])
        self.repo.save_schema(schema)
        self.repo.save_rows(schema.name, {"rows": {}, "next_id": 1})
        return schema

    def _resolve_format(self, path: Path, format: str) -> str:
        fmt = (format or "auto").strip().lower()
        if fmt in {"csv", "json"}:
            return fmt
        suffix = path.suffix.lower()
        if suffix == ".csv":
            return "csv"
        if suffix == ".json":
            return "json"
        raise ValueError(f"Cannot infer file format from '{path.name}'. Pass format='csv' or format='json'.")

    def _read_rows(self, path: Path, fmt: str) -> tuple[list[dict], list[str]]:
        if fmt == "csv":
            with path.open(newline="", encoding="utf-8-sig") as stream:
                reader = csv.DictReader(stream)
                if not reader.fieldnames:
                    return [], []
                rows = [
                    {key: (None if value is None or value == "" else value) for key, value in row.items() if key is not None}
                    for row in reader
                ]
                return rows, list(reader.fieldnames)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
            payload = payload["rows"]
        if not isinstance(payload, list):
            raise ValueError("JSON import file must contain a list of row objects, or an object with a 'rows' list.")
        file_columns: list[str] = []
        for row in payload:
            if not isinstance(row, dict):
                raise ValueError("Every JSON row must be an object mapping column names to values.")
            for key in row:
                if key not in file_columns:
                    file_columns.append(key)
        return payload, file_columns

    def _build_mapping(self, schema: DatasetSchema, file_columns: list[str]) -> tuple[dict, list[str]]:
        mapping: dict[str, str] = {}
        unmatched: list[str] = []
        for file_column in file_columns:
            col = schema.column(file_column)
            if col is None or col.name in mapping.values():
                unmatched.append(file_column)
            else:
                mapping[file_column] = col.name
        return mapping, unmatched

    def _resolve_columns(self, schema: DatasetSchema, columns: list[str]) -> list[str]:
        unknown = [c for c in columns if schema.column(c) is None]
        if unknown:
            raise ValueError(f"Unknown column(s): {', '.join(unknown)}. Available columns: {', '.join(schema.column_names())}.")
        return [schema.column(c).name for c in columns]

    @staticmethod
    def _csv_cell(value):
        if value is None:
            return ""
        if value is True:
            return "true"
        if value is False:
            return "false"
        return value
