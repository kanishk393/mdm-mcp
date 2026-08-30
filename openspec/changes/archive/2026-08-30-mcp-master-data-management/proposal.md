# Proposal: MCP Master Data Management

## Why

Non-technical users lose significant time maintaining records in spreadsheets because Excel demands spreadsheet skills (column discipline, formulas, filters) that naive users don't have. We will build a backend-only master data management tool exposed as an MCP server: the user converses with an agent (OpenCode today, Claude Code also supported), and the agent creates datasets, defines schemas, and performs all data operations through well-documented tools. No GUI, no spreadsheet skills required — the agent is the interface.

Three personas anchor the design (used as acceptance scenarios, not separate features):

- **Hiring partner** — one dataset per JD, hundreds of candidates per role, enum stages (Applied → Rejected), typo-tolerant fuzzy name search, bulk import of applicants.
- **Business owner** — many datasets (Inventory, Vendors, Payments, Payroll, Employees) with numeric/date/phone fields, combined filters ("unpaid vendors in August"), bulk edits ("mark all paid").
- **Individual** — many small personal datasets (health log, investments, schedule), date-heavy, low volume / high frequency.

**User mental model**: `Workspace → Datasets → Columns (typed) → Rows`. The agent acts as a form-filler: propose a schema → user confirms → rows are captured conversationally with instant validation feedback → search/filter/update → bulk operations with preview. Naive-user rules: confirm before destructive actions, summarize every action in plain language, never silently invent fields.

## What Changes

- New Python MCP server (FastMCP, stdio transport) — the entire product; talks directly to local JSON storage.
- **User-defined schemas**: each dataset's columns are defined by the user through conversation (like building a Google Form). Column types: string, text, boolean, integer, float, phone (India default, per-column regex override), date (ISO 8601), enum. Constraints: required, min/max, pattern, enum options, defaults.
- **Row lifecycle**: add (1..n with per-row plain-language validation reports), get (by id, with column projection), update, delete, with JSON storage (directory per dataset: `schema.json` + `rows.json`, atomic writes).
- **Search**: filter DSL (eq/ne/contains/in/gt/lt/between/is_empty), sort, pagination, fuzzy matching on text columns.
- **Bulk operations**: import from CSV/JSON (with file-column→dataset-column mapping preview), export to CSV/JSON, bulk edit by filter (dry-run default).
- **Safety pattern for destructive ops** (no versioning/undo exists): delete/bulk-edit/schema-changing operations return a preview first and require explicit confirmation.
- **Summarization**: `summarize_dataset` (count, sum/avg/min/max for numeric columns, per-enum breakdowns).
- **Tool documentation is a first-class requirement**: every tool gets a precise docstring, parameter descriptions, and usage examples — vague tools confuse naive users and degrade agent behavior.
- Deferred to a later phase (out of scope for v1): unique-field constraints, versioning/undo, auth/multi-tenancy, MongoDB backend (storage stays behind a repository interface so a swap is possible without touching tools).

## Capabilities

### New Capabilities

- `dataset-management`: Creating, listing, describing, schema-updating, and deleting user-defined datasets. Covers user-defined column definitions (types + constraints), schema change handling for existing rows (backfill/nullable), and confirmation-gated dataset deletion.
- `row-management`: Adding, reading, updating, and deleting rows against a dataset's schema. Covers Google-Forms-style validation (types, required, ranges, enums, phone/date formats) with per-row, plain-language error reports; JSON storage with atomic writes; confirmation-gated row deletion.
- `row-search`: Filtering, sorting, paginating, fuzzy-matching, and summarizing rows. Covers the filter DSL, fuzzy name matching (typo tolerance), date/numeric range filters, and `summarize_dataset` aggregates.
- `bulk-operations`: Importing rows from CSV/JSON files, exporting datasets to CSV/JSON, and bulk-editing rows by filter. Covers file-column→dataset-column mapping preview on import, per-row import reports (accepted/rejected with reasons), dry-run previews, and confirmation-gated bulk edits.

### Modified Capabilities

(none — greenfield)

## Impact

- **New code**: Python MCP server package (`server/` — FastMCP tools, validation engine, JSON storage repository), developed phase-wise with one git commit per phase.
- **New data**: local `data/` directory holding per-dataset JSON files; localhost only, single user, no auth.
- **Clients**: OpenCode (primary) and Claude Code — both consume the server via stdio MCP; no client-side code is built.
- **Dependencies**: `mcp` / `fastmcp` SDK; fuzzy matching via `rapidfuzz`; CSV handling via stdlib `csv`.
- **No frontend, no REST API, no database server** — the MCP server is the only interface to the data.
