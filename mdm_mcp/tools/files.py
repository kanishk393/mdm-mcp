"""File tools: import_rows, export_rows."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from mdm_mcp.services.file_service import FileService
from mdm_mcp.tools.base import get_services, ok_result


def register_file_tools(mcp: FastMCP) -> None:
    default_service: FileService | None = None

    def service() -> FileService:
        nonlocal default_service
        if default_service is None:
            default_service = get_services()[2]
        return default_service

    @mcp.tool()
    @ok_result
    def import_rows(dataset: str, file_path: str, format: str = "auto", confirm: bool = False, create_if_missing: bool = False) -> dict[str, Any]:
        """Import rows into a dataset from a CSV or JSON file, in two safe steps.

        Step 1 (confirm=false, default): returns a mapping preview - how each file
        column maps to a dataset column, unmatched file columns, missing required
        dataset columns, and a small sample. Share the mapping with the user and let
        them confirm or adjust the file.

        Step 2 (confirm=true): imports. Every row is validated against the dataset
        schema; valid rows are added and invalid rows are reported with plain-language
        reasons. CSV values are coerced automatically ("5" becomes the number 5,
        "true" becomes a boolean).

        Args:
            dataset: Exact dataset name, e.g. "Candidates".
            file_path: Path to the .csv or .json file on this machine.
            format: "auto" (default, infers from extension), or force "csv"/"json".
            confirm: Must be true to actually import (default false = preview only).
            create_if_missing: When the dataset does not exist, create it first with one
                string column per file header, then import (default false).

        Returns:
            Preview: {"ok": true, "requires_confirmation": true, "preview": {...}}.
            Commit: {"ok": true, "dataset", "added": <int>, "rejected": <int>,
                     "rejected_rows": [{"row": <index>, "errors": ["..."]}]}.

        Example:
            import_rows(dataset="Candidates", file_path="~/Downloads/applicants.csv")
        """
        return service().import_rows(dataset, file_path, format, confirm, create_if_missing)

    @mcp.tool()
    @ok_result
    def export_rows(
        dataset: str,
        file_path: str,
        format: str = "auto",
        conditions: list[dict[str, Any]] | None = None,
        columns: list[str] | None = None,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Export rows (optionally filtered and projected) to a CSV or JSON file.

        Use this when the user wants their data back in a spreadsheet-friendly form.
        Filters use the same conditions syntax as search_rows. The id column is always
        included. Refuses to overwrite an existing file unless overwrite=true.

        Args:
            dataset: Exact dataset name, e.g. "Candidates".
            file_path: Destination path for the .csv or .json file.
            format: "auto" (default, infers from extension), or force "csv"/"json".
            conditions: Optional filter, e.g. [{"column": "stage", "op": "eq", "value": "Applied"}].
            columns: Optional column projection, e.g. ["name", "phone"].
            overwrite: Allow replacing an existing file (default false).

        Returns:
            {"ok": true, "dataset", "file": "<path>", "format", "rows_exported": <int>}.

        Example:
            export_rows(dataset="Candidates", file_path="~/Documents/applied_august.csv",
                        conditions=[{"column": "applied_on", "op": "between", "value": ["2026-08-01", "2026-08-31"]}])
        """
        return service().export_rows(dataset, file_path, format, conditions=conditions, columns=columns, overwrite=overwrite)
