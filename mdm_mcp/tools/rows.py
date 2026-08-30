"""Row tools: add_rows, get_row."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from mdm_mcp.services.row_service import RowService
from mdm_mcp.tools.base import get_services, ok_result


def register_row_tools(mcp: FastMCP) -> None:
    default_service: RowService | None = None

    def service() -> RowService:
        nonlocal default_service
        if default_service is None:
            default_service = get_services()[1]
        return default_service

    @mcp.tool()
    @ok_result
    def add_rows(dataset: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        """Add one or more rows to a dataset with per-row validation.

        Use this to capture records the user dictates in conversation. Each row is an
        object mapping column names to values; every row is validated against the
        dataset schema and valid rows are saved while invalid rows are reported back
        with plain-language reasons. At most 100 rows per call - split larger batches.

        Check describe_dataset first so column names, types, and constraints match exactly.

        Args:
            dataset: Exact dataset name, e.g. "Candidates".
            rows: List of row objects, e.g. [{"name": "Asha", "phone": "9876543210"}].

        Returns:
            {"ok": true, "dataset", "added": <int>, "rejected": <int>,
             "results": [{"row": <index>, "status": "added", "row_id": "<id>"} |
                         {"row": <index>, "status": "rejected", "errors": ["..."]}]}
            Relay every rejected row's errors to the user in plain language.

        Example:
            add_rows(dataset="Candidates", rows=[
                {"name": "Asha Verma", "phone": "9876543210", "stage": "Applied", "applied_on": "2026-08-30"}
            ])
        """
        return service().add_rows(dataset, rows)

    @mcp.tool()
    @ok_result
    def get_row(dataset: str, row_id: str, columns: list[str] | None = None) -> dict[str, Any]:
        """Fetch a single row by id, optionally limited to specific columns.

        Use this when the user asks about one record ("show me row 12", "what is
        Asha's phone number?"). Ask for only the columns you need to keep the
        response small.

        Args:
            dataset: Exact dataset name, e.g. "Candidates".
            row_id: The row id, e.g. "12".
            columns: Optional list of column names to project, e.g. ["name", "stage"].

        Returns:
            {"ok": true, "dataset", "row": {"id", ...requested columns}} on success,
            {"ok": false, "error": "<reason>"} for unknown ids or columns.
        """
        return service().get_row(dataset, row_id, columns)
