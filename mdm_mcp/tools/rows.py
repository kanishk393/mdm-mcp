"""Row tools: add_rows, get_row, update_rows, delete_rows, validate_rows."""

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

    @mcp.tool()
    @ok_result
    def update_rows(dataset: str, row_ids: list[str], values: dict[str, Any]) -> dict[str, Any]:
        """Update one or more rows by id with a partial set of column values.

        Only the provided columns change; everything else stays as-is. New values are
        validated together with the rest of each row, so an invalid change leaves that
        row untouched and is reported with plain-language errors. Ids that do not exist
        are reported as not_found rather than failing the whole call.

        Args:
            dataset: Exact dataset name, e.g. "Candidates".
            row_ids: Row ids to update, e.g. ["3", "7"].
            values: Column values to set, e.g. {"stage": "Rejected"}.

        Returns:
            {"ok": true, "dataset", "updated": <int>, "rejected": <int>, "not_found": <int>,
             "results": [{"row_id", "status": "updated"|"rejected"|"not_found", "errors"?}]}.

        Example:
            update_rows(dataset="Candidates", row_ids=["3", "7"], values={"stage": "Rejected"})
        """
        return service().update_rows(dataset, row_ids, values)

    @mcp.tool()
    @ok_result
    def delete_rows(dataset: str, row_ids: list[str], confirm: bool = False) -> dict[str, Any]:
        """Delete specific rows by id after explicit confirmation.

        Destructive: without confirm=true the tool only returns a preview listing the
        rows that would be deleted. Call it with confirm=false first, tell the user
        what will be lost, and only re-invoke with confirm=true after they agree.

        Args:
            dataset: Exact dataset name, e.g. "Candidates".
            row_ids: Row ids to delete, e.g. ["4"].
            confirm: Must be true to actually delete (default false = preview only).

        Returns:
            {"ok": true, "dataset", "deleted": <int>, "row_ids": [...], "not_found": [...]}
            after confirmation, {"ok": true, "requires_confirmation": true, "preview": {...}}
            without.
        """
        return service().delete_rows(dataset, row_ids, confirm)

    @mcp.tool()
    @ok_result
    def validate_rows(dataset: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        """Validate rows against a dataset's schema without saving anything.

        Use this to pre-check data before committing it - e.g. when the user pastes a
        list of records and wants to know what would be rejected and why. Valid rows
        come back normalized (types coerced, defaults filled) so you can show the
        user exactly what would be stored.

        Args:
            dataset: Exact dataset name, e.g. "Candidates".
            rows: List of row objects to check (max 100 per call).

        Returns:
            {"ok": true, "dataset", "total": <int>, "valid": <int>, "invalid": <int>,
             "results": [{"row": <index>, "status": "valid", "normalized": {...}} |
                         {"row": <index>, "status": "invalid", "errors": ["..."]}]}.
        """
        return service().validate_rows(dataset, rows)
