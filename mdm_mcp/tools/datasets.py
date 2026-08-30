"""Dataset and column tools: create_dataset, list_datasets, describe_dataset."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from mdm_mcp.models.schema import ColumnSpec
from mdm_mcp.services.dataset_service import DatasetService
from mdm_mcp.tools.base import get_services, ok_result


def register_dataset_tools(mcp: FastMCP) -> None:
    default_service: DatasetService | None = None

    def service() -> DatasetService:
        nonlocal default_service
        if default_service is None:
            default_service = get_services()[0]
        return default_service

    @mcp.tool()
    @ok_result
    def create_dataset(name: str, columns: list[ColumnSpec], description: str = "") -> dict[str, Any]:
        """Create a new dataset (a table) with user-defined typed columns.

        Use this whenever the user wants to start tracking something new - candidates,
        inventory, payments, a health log. Columns behave like spreadsheet headers with
        Google-Forms-style validation. Always propose the column list to the user and
        get their confirmation before calling this tool.

        Args:
            name: Unique dataset name, e.g. "Candidates" (case-insensitive uniqueness).
            columns: One or more column definitions.
            description: Optional short description of what this dataset tracks.

        Column types: string, text, boolean, integer, float, phone, date, enum.
        Column attributes: required, default, min_value/max_value (numeric columns),
        pattern (string/text columns), options (enum columns, at least one value).

        Returns:
            {"ok": true, "dataset": "<name>", "columns": [{"name", "type"}]} on success,
            {"ok": false, "error": "<plain-language reason>"} on failure.

        Example:
            create_dataset(name="Candidates", description="Applicants for the Java JD", columns=[
                {"name": "name", "type": "string", "required": true},
                {"name": "phone", "type": "phone"},
                {"name": "experience", "type": "float", "min_value": 0},
                {"name": "stage", "type": "enum", "options": ["Applied", "Screened", "Rejected"]},
                {"name": "applied_on", "type": "date"}
            ])
        """
        return service().create_dataset(name, description, [c.model_dump() for c in columns])

    @mcp.tool()
    @ok_result
    def list_datasets(limit: int = 20, offset: int = 0) -> dict[str, Any]:
        """List all datasets with row counts and a name:type column summary.

        Use this to discover what the user is already tracking before creating or
        querying a dataset. Results are paginated: use next_offset from the response
        to fetch the next page instead of raising the limit.

        Args:
            limit: Page size (1-100, default 20).
            offset: Number of datasets to skip (default 0).

        Returns:
            {"ok": true, "datasets": [{"name", "description", "row_count", "columns"}],
             "total": <int>, "count": <int>, "next_offset": <int or null>}.
        """
        return service().list_datasets(limit, offset)

    @mcp.tool()
    @ok_result
    def describe_dataset(name: str, sample_rows: int = 0) -> dict[str, Any]:
        """Show a dataset's full column definitions (types and constraints) and row count.

        Use this before adding or searching rows so you know the exact column names,
        types, and constraints. Optionally include a few sample rows (capped at 5) to
        see what the data looks like.

        Args:
            name: Exact dataset name, e.g. "Candidates".
            sample_rows: Optional number of first rows to include, 0-5 (default 0).

        Returns:
            {"ok": true, "dataset", "description", "row_count",
             "columns": [{"name", "type", "required", "default?", "options?", ...}],
             "samples": [{"id", ...}]} on success,
            {"ok": false, "error": "<reason>"} when the dataset does not exist.
        """
        return service().describe_dataset(name, sample_rows)
