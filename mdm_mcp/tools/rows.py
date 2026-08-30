"""Row tools: add_rows, get_row, update_rows, delete_rows, validate_rows, search_rows, summarize_dataset."""

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
    def get_row(dataset: str, row_id: str | int, columns: list[str] | None = None) -> dict[str, Any]:
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

        Example:
            get_row(dataset="Candidates", row_id="12", columns=["name", "phone"])
        """
        return service().get_row(dataset, row_id, columns)

    @mcp.tool()
    @ok_result
    def update_rows(
        dataset: str,
        values: dict[str, Any],
        row_ids: list[str | int] | None = None,
        conditions: list[dict[str, Any]] | None = None,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Update rows by explicit ids, or in bulk for every row matching a filter.

        Only the provided columns change; everything else stays as-is. New values are
        validated together with the rest of each row, so an invalid change leaves that
        row untouched and is reported with plain-language errors.

        Bulk mode (conditions): defaults to a dry-run preview. Review the preview with
        the user, then re-invoke with dry_run=false to apply. Never set dry_run=false
        on the first call when a filter may match many rows.

        Args:
            dataset: Exact dataset name, e.g. "Candidates".
            values: Column values to set, e.g. {"stage": "Rejected"}.
            row_ids: Explicit row ids to update, e.g. ["3", "7"]. Mutually exclusive with conditions.
            conditions: Filter selecting rows to update, e.g. [{"column": "stage", "op": "eq", "value": "Screened"}].
            dry_run: Bulk mode only - true (default) previews; false applies the update.

        Returns:
            Id mode: {"ok": true, "dataset", "updated", "rejected", "not_found", "results": [...]}.
            Bulk mode dry-run: {"ok": true, "requires_confirmation": true, "preview": {...}}.
            Bulk mode applied: {"ok": true, "dataset", "matched", "updated", "rejected", "results": [...]}.

        Example:
            update_rows(dataset="Candidates", values={"stage": "Rejected"},
                        conditions=[{"column": "score", "op": "lt", "value": 3}], dry_run=true)
        """
        return service().update_rows(dataset, values, row_ids=row_ids, conditions=conditions, dry_run=dry_run)

    @mcp.tool()
    @ok_result
    def delete_rows(
        dataset: str,
        row_ids: list[str | int] | None = None,
        conditions: list[dict[str, Any]] | None = None,
        confirm: bool = False,
    ) -> dict[str, Any]:
        """Delete rows by explicit ids, or in bulk for every row matching a filter.

        Destructive: without confirm=true the tool only returns a preview listing the
        rows that would be deleted. Call it with confirm=false first, tell the user
        what will be lost, and only re-invoke with confirm=true after they agree.

        Args:
            dataset: Exact dataset name, e.g. "Candidates".
            row_ids: Explicit row ids to delete, e.g. ["4"]. Mutually exclusive with conditions.
            conditions: Filter selecting rows to delete, e.g. [{"column": "experience", "op": "lt", "value": 2}].
            confirm: Must be true to actually delete (default false = preview only).

        Returns:
            {"ok": true, "dataset", "deleted": <int>, "row_ids": [...], "not_found": [...]}
            after confirmation, {"ok": true, "requires_confirmation": true, "preview": {...}}
            without.

        Example:
            delete_rows(dataset="Candidates", conditions=[{"column": "stage", "op": "eq", "value": "Rejected"}])
        """
        return service().delete_rows(dataset, row_ids=row_ids, conditions=conditions, confirm=confirm)

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

        Example:
            validate_rows(dataset="Candidates", rows=[{"name": "Asha", "phone": "9876543210"}])
        """
        return service().validate_rows(dataset, rows)

    @mcp.tool()
    @ok_result
    def search_rows(
        dataset: str,
        conditions: list[dict[str, Any]] | None = None,
        fuzzy: bool = False,
        query: str | None = None,
        fuzzy_columns: list[str] | None = None,
        fuzzy_threshold: float = 80,
        sort_by: str | None = None,
        sort_order: str = "asc",
        limit: int = 20,
        offset: int = 0,
        columns: list[str] | None = None,
    ) -> dict[str, Any]:
        """Search rows with exact filters, or typo-tolerant fuzzy matching, with sorting and pagination.

        Two search modes:
        - Exact: pass conditions built from {column, op, value}. Ops: eq, ne, gt, gte,
          lt, lte, contains, in, between, is_empty, is_not_empty. Combine conditions to
          narrow further (AND).
        - Fuzzy: pass fuzzy=true plus a query string to match string/text columns
          tolerantly against typos and misspellings ("Rahual" finds "Rahul Sharma").
          Results are ordered by similarity and carry an _score. Narrow with
          fuzzy_columns to search only specific text columns.

        Results are always paginated: page with next_offset instead of raising the
        limit, and request only the columns you need via columns.

        Args:
            dataset: Exact dataset name, e.g. "Candidates".
            conditions: Exact-mode filters, e.g. [{"column": "stage", "op": "eq", "value": "Applied"}].
            fuzzy: Set true for typo-tolerant matching (requires query).
            query: Text to fuzzy-match, e.g. "Rahual".
            fuzzy_columns: Optional text columns to fuzzy-match against (default: all text columns).
            fuzzy_threshold: Minimum similarity score 1-100 (default 80).
            sort_by: Column to sort by (exact mode).
            sort_order: "asc" (default) or "desc".
            limit: Page size 1-100 (default 20).
            offset: Rows to skip for pagination (default 0).
            columns: Column projection, e.g. ["name", "stage"]; id is always included.

        Returns:
            {"ok": true, "dataset", "rows": [{"id", ...columns, "_score"?}],
             "total": <int>, "count": <int>, "next_offset": <int or null>}.

        Example:
            search_rows(dataset="Candidates", conditions=[
                {"column": "applied_on", "op": "between", "value": ["2026-08-01", "2026-08-31"]},
                {"column": "stage", "op": "ne", "value": "Rejected"}
            ], sort_by="applied_on", sort_order="desc", columns=["name", "stage"])
            search_rows(dataset="Candidates", fuzzy=true, query="Rahual", fuzzy_columns=["name"])
        """
        return service().search_rows(
            dataset,
            conditions=conditions,
            fuzzy=fuzzy,
            query=query,
            fuzzy_columns=fuzzy_columns,
            fuzzy_threshold=fuzzy_threshold,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset,
            columns=columns,
        )

    @mcp.tool()
    @ok_result
    def summarize_dataset(dataset: str) -> dict[str, Any]:
        """Summarize a dataset with aggregates instead of raw rows.

        Use this when the user asks for totals or breakdowns ("how many candidates
        per stage?", "total inventory value?") - it returns row count, count/min/max/
        avg/sum for every numeric column, and value breakdowns for every enum column,
        without ever dumping rows into the conversation.

        Args:
            dataset: Exact dataset name, e.g. "Inventory".

        Returns:
            {"ok": true, "dataset", "row_count": <int>,
             "numeric": {"<column>": {"count", "min", "max", "avg", "sum"} or {"count": 0}},
             "enums": {"<column>": {"<value>": <count>}}}.

        Example:
            summarize_dataset(dataset="Inventory")
        """
        return service().summarize_dataset(dataset)
