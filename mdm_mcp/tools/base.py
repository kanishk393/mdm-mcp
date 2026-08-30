"""Shared service instances and the structured ok/error result wrapper."""

from __future__ import annotations

import functools
from typing import Callable

from mdm_mcp.services.dataset_service import DatasetService
from mdm_mcp.services.file_service import FileService
from mdm_mcp.services.row_service import RowService
from mdm_mcp.storage.repository import JsonRepository, StorageError

EXPECTED_ERRORS = (ValueError, StorageError)

_services: tuple[DatasetService, RowService, FileService] | None = None


def get_services() -> tuple[DatasetService, RowService, FileService]:
    global _services
    if _services is None:
        repo = JsonRepository()
        _services = (DatasetService(repo), RowService(repo), FileService(repo))
    return _services


def ok_result(func: Callable) -> Callable:
    """Convert expected service errors into {"ok": false, "error": ...} results."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            payload = func(*args, **kwargs)
        except EXPECTED_ERRORS as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, **payload}

    return wrapper
