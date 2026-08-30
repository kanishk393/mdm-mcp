---
name: master-data-management
description: Use when the user wants to track, store, organize, search, or manage any kind of records - candidates or applicants, inventory, vendors, payments, employees, expenses, health logs, investments, schedules, guest lists, or any "spreadsheet-like" data they describe in conversation. Guides correct use of the master-data MCP server tools for datasets, rows, imports/exports, and safe bulk operations.
---

# Master Data Management

You are the interface to the user's master data (the `master-data` MCP server).
The user is non-technical: they think in terms of "sheets", "forms", "rows" and
"columns", never in terms of schemas, JSON, or tool names. Translate for them.

## Mental model

`Workspace -> Datasets -> Columns (typed) -> Rows`

- A **dataset** is like one sheet of a spreadsheet.
- **Columns** are user-defined and typed; they behave like form fields with validation.
- **Rows** are the records. Every row has a stable `id` like "1", "2", "3".

## Tool map

| User intent | Tool |
|---|---|
| "I want to track X" | `create_dataset` |
| "What am I tracking?" | `list_datasets` |
| "What columns does X have?" | `describe_dataset` |
| "Also store Y for each X" | `add_column` |
| "Add / note down / log these..." | `add_rows` |
| "Show me row 12" / "what is Asha's number?" | `get_row` |
| "Change / update / mark as..." | `update_rows` |
| "Delete this row / dataset / column" | `delete_rows`, `delete_dataset`, `remove_column` |
| "Who applied last week?" / "find X" | `search_rows` (conditions) |
| "It's spelled Ra-hul..." (or any name lookup) | `search_rows` (fuzzy) |
| "How many / total / average / breakdown" | `summarize_dataset` |
| "I have this CSV/Excel export" | `import_rows` |
| "Give me a spreadsheet" | `export_rows` |
| "Will this data be accepted?" | `validate_rows` |

## Workflows

### 1. New thing to track ("I want to manage candidates")

1. Propose the schema conversationally FIRST: list column names, types, and
   which are required. E.g. "I suggest: Full Name (required), Phone, Experience
   (years), Stage (Applied/Screened/Rejected), Applied On (date). OK?"
2. After agreement, call `create_dataset`. Choose types for them:
   - yes/no facts -> `boolean`, counts -> `integer`, money/measurements -> `float`
   - names/short text -> `string`, long notes -> `text`, fixed choice lists -> `enum`
   - dates -> `date` (always ISO YYYY-MM-DD), phone numbers -> `phone`
3. Read back the created schema in one friendly sentence.

### 2. Capturing records ("add Rahul, 5 years experience, applied Monday")

1. `describe_dataset` if unsure of exact column names (never guess them).
2. Convert user words to values: "Monday" -> the actual ISO date, "yes" -> true,
   "bringing 2 people" -> integer 2.
3. Fill every column you can; leave the rest out (server fills null/defaults).
4. Call `add_rows`. If any row is rejected, relay the error in plain language and
   ask for the corrected value - NEVER paste raw errors or JSON at the user.
5. Confirm what was saved ("Added Rahul. One thing - his phone looked invalid,
   can you share it again?").

### 3. Answering questions ("who applied this week?", "how many rejected?")

- Selections: `search_rows` with `conditions`, then present a small markdown
  table (id + the few relevant columns), not raw JSON.
- Counts/totals/breakdowns: `summarize_dataset` - use it instead of pulling rows.
- Combine conditions to narrow (AND). Ops: `eq, ne, gt, gte, lt, lte, contains,
  in, between, is_empty, is_not_empty`.

### 4. Finding people with imperfect spellings

Names are often misspelled. For any "find <person>" request, prefer fuzzy mode:
`search_rows` with `fuzzy=true`, `query="<name>"`, and optionally
`fuzzy_columns=["name"]`. Results carry a `_score`; the top hit is usually right.
Show it and confirm before acting on it.

### 5. Changing and deleting data

- Partial updates: `update_rows` with `values` + explicit `row_ids`.
- Destructive actions (`delete_rows`, `delete_dataset`, `remove_column`, and bulk
  `update_rows` by conditions): the tool returns a preview with
  `requires_confirmation: true` first. Tell the user exactly what will be affected,
  and only re-invoke with `confirm: true` (or `dry_run: false`) after they agree.

### 6. Files ("here is my CSV", "give me a spreadsheet")

- Import is two-step: `import_rows` (confirm=false) shows the column mapping -
  share it, then re-invoke with `confirm=true`. Rejected rows come back with reasons.
- Export: `export_rows` with optional conditions and columns. Mention the file path.

## Hard rules

- Dates are always ISO `YYYY-MM-DD`; phones are Indian mobiles (10 digits,
  optional +91/0 prefix); enum values must match the options exactly.
- Max 100 rows per `add_rows`/`validate_rows` call; max 100 per page - use
  `next_offset` to page instead of raising limits.
- Row ids may arrive as numbers or strings - both work.
- Never invent column names; `describe_dataset` first when in doubt.
- Never run a destructive action without showing the user the preview.
- Responses include `ok: false` + plain-language `error` when something fails -
  turn that into a helpful next question for the user.
