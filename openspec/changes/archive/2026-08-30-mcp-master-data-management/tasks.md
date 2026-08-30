# Tasks: MCP Master Data Management

## 1. Phase 1 — Foundation (`feat: dataset & row foundation`)

- [x] 1.1 Scaffold Python project: pyproject.toml, `mdm_mcp` package, .gitignore, uv venv (Python 3.12) with mcp + pydantic + pytest installed; verify `python -c "import mdm_mcp"` succeeds
- [x] 1.2 Implement core models (ColumnType, ColumnSpec with constraint validation, DatasetSchema); verify model unit tests pass (enum without options rejected, bad pattern rejected, duplicate columns rejected at service level)
- [x] 1.3 Implement JsonRepository (data/<slug>/schema.json + rows.json, atomic temp-file writes, MDM_DATA_DIR override, DatasetNotFound with available names); verify storage roundtrip tests pass
- [x] 1.4 Implement RowValidator with pydantic create_model for all 8 column types (string, text, boolean, integer, float, phone, date, enum) + required/min/max/pattern; verify validation unit tests pass (phone +91 accepted, enum rejection, unknown column, coercion "5"→5)
- [x] 1.5 Implement dataset_service (create/list/describe with pagination + sample cap) and row_service (add_rows with batch cap + per-row report, get_row with projection); verify service tests pass
- [x] 1.6 Register FastMCP tools create_dataset, list_datasets, describe_dataset, add_rows, get_row with full docstrings and structured ok/error results; verify smoke test lists 5 tools each with description and input schema
- [x] 1.7 Run full pytest suite green and commit `feat: dataset & row foundation`

## 2. Phase 2 — Schema lifecycle & row updates (`feat: schema lifecycle & row updates`)

- [x] 2.1 Implement add_column with default backfill for existing rows; verify rows receive default/null
- [x] 2.2 Implement update_column (type/constraints/rename) with per-row revalidation report preserving offending values; verify offending rows are reported, not dropped
- [x] 2.3 Implement remove_column and delete_dataset with stateless preview/confirm pattern; verify nothing changes without confirm
- [x] 2.4 Implement update_rows (partial, by ids, per-row validation) and validate_rows (no save); verify invalid update leaves rows untouched
- [x] 2.5 Implement delete_rows (by ids) with preview/confirm; verify deleted rows become unreachable
- [x] 2.6 Run full pytest suite green and commit `feat: schema lifecycle & row updates`

## 3. Phase 3 — Search, fuzzy & bulk (`feat: search, fuzzy matching & bulk operations`)

- [x] 3.1 Implement FilterEngine (eq, ne, gt, gte, lt, lte, contains, in, between, is_empty, is_not_empty) with plain-language rejection of unknown columns/type mismatches; verify filter unit tests pass
- [x] 3.2 Implement search_rows (filters, one-column sort, limit/offset pagination clamped at 100, column projection, total + next_offset); verify pagination scenarios from specs pass
- [x] 3.3 Add rapidfuzz fuzzy matching on string/text columns with similarity scores; verify typo scenario ("Rahual" finds "Rahul Sharma")
- [x] 3.4 Implement summarize_dataset (row count, numeric min/max/avg/sum, enum breakdowns); verify aggregates match fixture data
- [x] 3.5 Extend update_rows/delete_rows to filter-based bulk with dry_run default and confirm gate; verify dry-run changes nothing and confirmed run reports counts
- [x] 3.6 Implement import_rows (CSV/JSON, two-step mapping preview then confirmed commit with per-row report) and export_rows (filter + projection to CSV/JSON); verify export→import roundtrip preserves rows
- [x] 3.7 Run full pytest suite green and commit `feat: search, fuzzy matching & bulk operations`

## 4. Phase 4 — Polish (`docs: tool docs & persona walkthroughs`)

- [x] 4.1 Docstring/example audit: every tool has purpose, args, returns, ok/error shape, and a usage example; verify an automated test asserts non-trivial docstrings on all tools
- [x] 4.2 Write README with setup, MDM_DATA_DIR, and OpenCode + Claude Code MCP configuration snippets; verify instructions match pyproject entry point
- [x] 4.3 Add persona walkthrough integration tests (recruiter: dataset per JD + fuzzy search + bulk import; business owner: inventory summarize + bulk edit; individual: date-sorted health log); verify all pass
- [x] 4.4 Run `openspec validate` green and commit `docs: tool docs & persona walkthroughs`
