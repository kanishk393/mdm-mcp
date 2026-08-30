"""Local JSON storage: one directory per dataset with schema.json and rows.json.

Writes are atomic (temp file + replace) so a failed write never corrupts data.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from mdm_mcp.models.schema import DatasetSchema


class StorageError(Exception):
    """Raised when a storage-level operation fails."""


class DatasetNotFound(StorageError):
    def __init__(self, name: str, available: list[str]):
        names = ", ".join(available) if available else "none yet"
        super().__init__(f"Dataset '{name}' does not exist. Available datasets: {names}.")


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "dataset"


class JsonRepository:
    """Repository interface implementation backed by JSON files."""

    def __init__(self, root: str | Path | None = None):
        root_path = Path(root) if root is not None else Path(os.environ.get("MDM_DATA_DIR", "data"))
        self.root = root_path
        self.root.mkdir(parents=True, exist_ok=True)

    def dataset_dir(self, name: str) -> Path:
        return self.root / slugify(name)

    def dataset_exists(self, name: str) -> bool:
        return (self.dataset_dir(name) / "schema.json").exists()

    def dataset_names(self) -> list[str]:
        if not self.root.exists():
            return []
        names = []
        for entry in sorted(self.root.iterdir()):
            schema_path = entry / "schema.json"
            if entry.is_dir() and schema_path.exists():
                payload = json.loads(schema_path.read_text(encoding="utf-8"))
                names.append(payload["name"])
        return names

    def load_schema(self, name: str) -> DatasetSchema:
        path = self.dataset_dir(name) / "schema.json"
        if not path.exists():
            raise DatasetNotFound(name, self.dataset_names())
        return DatasetSchema.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def save_schema(self, schema: DatasetSchema) -> None:
        path = self.dataset_dir(schema.name) / "schema.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write(path, schema.model_dump(mode="json"))

    def delete_dataset(self, name: str) -> None:
        if not self.dataset_exists(name):
            raise DatasetNotFound(name, self.dataset_names())
        shutil.rmtree(self.dataset_dir(name))

    def load_rows(self, name: str) -> dict:
        path = self.dataset_dir(name) / "rows.json"
        if not path.exists():
            return {"rows": {}, "next_id": 1}
        return json.loads(path.read_text(encoding="utf-8"))

    def save_rows(self, name: str, store: dict) -> None:
        path = self.dataset_dir(name) / "rows.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write(path, store)

    def row_count(self, name: str) -> int:
        return len(self.load_rows(name)["rows"])

    def _atomic_write(self, path: Path, payload: dict) -> None:
        handle, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2)
            os.replace(tmp_name, path)
        finally:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)
