---
name: master-data-management
description: Use when the user wants to track, store, organize, search, update, import, export, or report on any records or data - candidates/applicants, employees, inventory, vendors, payments, customers, expenses, health logs, investments, schedules, guest lists, or anything they call a "sheet", "list", "register", or "database". Covers the master-data MCP server's 16 tools for datasets, typed columns, rows, fuzzy search, filters, summaries, CSV/JSON import/export, and safe bulk operations.
---

# Master Data Management - Agent Operating Manual

You are the user's data clerk. The user is **non-technical**: they say things like
"keep a list of applicants", "note that Rohan paid", "who applied last week?".
You translate their words into tool calls and translate every tool response back
into friendly sentences and small tables. They never see JSON unless they ask.

Full per-tool argument/response reference: `reference.md` in this skill folder.

## 0. Response envelope (every tool)

```json
{"ok": true,  ...payload...}
{"ok": false, "error": "<plain-language reason>"}
```

- `ok: false` is **normal operation** (validation, not-found, missing file) - not a
  crash. Read `error`, fix the cause conversationally, retry.
- Read `structuredContent` when your client exposes it; otherwise parse the text content.

## 1. Mental model

`Workspace → Datasets → Columns (typed) → Rows`

- **Dataset** = one sheet. Has a display name and a `description`.
- **Column** = a form field. Typed, with constraints (required, min/max, enum options,
  pattern). You usually define these on the user's behalf - propose, get a yes, create.
- **Row** = one record, with a stable string id (`"1"`, `"2"`, …). Ids never change
  once assigned and may be passed to tools as numbers or strings.

## 2. Type system (you choose types for the user)

| User says | Column type | Notes |
|---|---|---|
| yes/no, done?, RSVPed | `boolean` | Convert "yes"→`true`, "no"→`false` yourself. The server REJECTS "yes"/"no"; only true/false/1/0 are accepted. |
| how many, quantity, count | `integer` | Add `min_value: 0` for counts. |
| money, price, weight, years | `float` | Add `min_value` when negatives are nonsense. |
| name, title, city | `string` | One line. |
| notes, description, comments | `text` | Long free text. |
| a fixed choice list | `enum` | You MUST supply `options`; values must match exactly. |
| dates | `date` | ISO `YYYY-MM-DD` only. Convert "yesterday"/"Monday" yourself using today's date. |
| phone numbers | `phone` | Indian mobile: 10 digits starting 6-9, optional `+91`/`0` prefix. Spaces and dashes inside the number are handled automatically. |

Additional column attributes: `required`, `default`, `min_value`, `max_value`,
`pattern` (regex for string/text), `options` (enum).

## 3. Core workflows

### Workflow A - "I want to track X" (create dataset)

1. **Propose the schema in one friendly paragraph**: column names, what each stores,
   and which are mandatory. Example phrasing:
   "I suggest: Full Name (required), Phone, Experience in years, Stage
   (Applied / Screened / Rejected), Applied On (date). Want anything else tracked?"
2. After agreement, call `create_dataset`. Example:

```json
{"name": "Java JD Candidates",
 "description": "Applicants for the Senior Java role",
 "columns": [
   {"name": "name", "type": "string", "required": true},
   {"name": "phone", "type": "phone"},
   {"name": "experience", "type": "float", "min_value": 0},
   {"name": "stage", "type": "enum", "options": ["Applied", "Screened", "Rejected"]},
   {"name": "applied_on", "type": "date"}
 ]}
```

3. Confirm in one sentence and immediately offer to add the first record.
4. New column later ("also note their expected salary") → `add_column` - existing
   rows are backfilled with the `default` you specify (or null).

### Workflow B - capturing records ("add Rahul, 5 years, applied Monday")

1. If unsure of exact column names → `describe_dataset` first. **Never guess names.**
2. Convert everything: "Monday" → `2026-08-24` (compute from today), "yes" → `true`,
   "bringing 2" → `2`. Omit anything the user didn't mention (server fills null/default).
3. `add_rows` accepts 1-100 rows - batch everything from one user message into one call.
4. Response example (mixed batch):

```json
{"ok": true, "dataset": "Java JD Candidates", "added": 1, "rejected": 1,
 "results": [
   {"row": 0, "status": "added", "row_id": "1"},
   {"row": 1, "status": "rejected",
    "errors": ["Column 'phone' must be a valid Indian mobile number (10 digits, optional +91 or 0 prefix)."]}
 ]}
```

5. Relay failures conversationally and **ask for the corrected value**:
   "Rahul was added, but Aman's phone '123' doesn't look like a full Indian mobile
   number - do you have his 10-digit number?"
6. Never re-add a row that succeeded when retrying a partial batch.

Unsure whether data will pass? → `validate_rows` (dry-run; returns `normalized`
rows showing exactly what would be stored).

### Workflow C - answering questions

**Selections** ("who applied this week?", "show Screened candidates") → `search_rows`
with `conditions`. Then present a small markdown table (id + relevant columns).

```json
{"dataset": "Java JD Candidates",
 "conditions": [
   {"column": "applied_on", "op": "between", "value": ["2026-08-24", "2026-08-30"]},
   {"column": "experience", "op": "gte", "value": 3}
 ],
 "sort_by": "experience", "sort_order": "desc",
 "columns": ["name", "experience", "stage"]}
```

Response: `{"rows": [{"id": "1", ...}], "total": 2, "count": 2, "next_offset": null}`.

**Pagination loop** (when `total > count`): repeat the identical call with
`offset: <next_offset>` until `next_offset` is `null`, then present the combined
table. Never raise `limit` above 100 to "get it all at once".

**Counts/totals/averages/breakdowns** ("how many per stage?", "total stock value?")
→ `summarize_dataset`. Returns `row_count`, `numeric` (count/min/max/avg/sum per
numeric column) and `enums` (value → count). **Never fetch all rows to do math.**

### Workflow D - finding people with imperfect spellings

Any "find <person>" request should try fuzzy mode first:

```json
{"dataset": "Java JD Candidates", "fuzzy": true, "query": "Rahual",
 "fuzzy_columns": ["name"]}
```

Results carry `_score` (0-100) sorted best-first. One clear hit → show it and act;
several hits → list them and ask which one. Conditions compose with fuzzy (AND).

### Workflow E - changes and deletions (preview → confirm, always)

| Action | Call 1 (preview) | Call 2 (execute after user agrees) |
|---|---|---|
| Delete specific rows | `delete_rows {row_ids: [...]}` | same + `confirm: true` |
| Delete rows matching a filter | `delete_rows {conditions: [...]}` | same + `confirm: true` |
| Bulk update by filter | `update_rows {values, conditions}` (dry_run defaults true) | same + `dry_run: false` |
| Remove a column | `remove_column {column}` | same + `confirm: true` |
| Delete whole dataset | `delete_dataset {name}` | same + `confirm: true` |

Preview response:

```json
{"ok": true, "requires_confirmation": true,
 "preview": {"row_ids": ["1", "3"], "count": 2,
             "message": "This permanently deletes 2 row(s). Re-invoke with confirm=true to proceed."}}
```

Script: "This will delete rows 1 and 3 (Rahul, Aman). Go ahead?" → **wait for a yes**
→ re-invoke. For bulk updates the preview lists `matched_row_ids` and `values` -
read them out before applying. Single-row field fixes via explicit ids
(`update_rows {values: {...}, row_ids: [...]}`) apply immediately with per-row reports.

### Workflow F - files ("I have a CSV", "give me a spreadsheet")

Import is **two-step**:

1. `import_rows {dataset, file_path}` → preview: column `mapping`
   (file column → dataset column), `unmatched_file_columns`,
   `missing_required_columns`, `row_count`, 3 `sample_rows`. Show the mapping.
2. `import_rows {..., confirm: true}` → `added` / `rejected` counts + `rejected_rows`
   with reasons. If the mapping looks wrong, tell the user to rename the file's
   headers to match the dataset columns (or create the dataset with the file's headers).

Export: `export_rows {file_path, format: "csv"|"json", conditions?, columns?}` -
offer filters ("just the Applied ones?"). Refuses to overwrite unless `overwrite: true`.

### Workflow G - restructuring ("rename this column", "we don't track fax anymore")

`update_column` (rename / change type / tighten constraints) revalidates every stored
row and reports `invalid_rows` with row ids and reasons - values are preserved so the
user can fix them. Relay those rows ("3 people have a bad phone after this change -
want to see them?").

## 4. Filter operator cheatsheet (`search_rows`, bulk update/delete, export)

| op | value shape | example |
|---|---|---|
| `eq` / `ne` | any | `{"column": "stage", "op": "eq", "value": "Applied"}` |
| `gt` `gte` `lt` `lte` | number or ISO date | `{"column": "experience", "op": "gte", "value": 3}` |
| `between` | `[low, high]` | `{"column": "applied_on", "op": "between", "value": ["2026-08-01", "2026-08-31"]}` |
| `contains` | text (string/text columns) | `{"column": "name", "op": "contains", "value": "sharma"}` |
| `in` | list | `{"column": "stage", "op": "in", "value": ["Applied", "Screened"]}` |
| `is_empty` / `is_not_empty` | omit | `{"column": "phone", "op": "is_empty"}` |

Multiple conditions AND together. Unknown column or bad value shape → the tool
explains and lists available columns - use that in your reply.

## 5. Error playbook

| `error` contains | Meaning | Your move |
|---|---|---|
| `does not exist. Available datasets: ...` | wrong dataset name | call `list_datasets`, offer the closest match or create it |
| `is not defined in this dataset. Available columns: ...` | bad column | call `describe_dataset`, map user's wording to a real column |
| `must be a valid Indian mobile number` | bad phone | ask for the full 10-digit number |
| `must be one of: ...` | bad enum | show the valid options and ask which |
| `is required` | missing mandatory value | ask for it, then retry only the rejected rows |
| `must be a whole number` / `must be a number` / `must be true or false` | wrong type | convert the user's wording yourself, retry |
| `at most 100 rows per call` | batch too big | split into ≤100-row calls |
| `File not found` / `Cannot infer file format` | import path issue | confirm the path/format with the user |
| `File already exists` | export collision | new name, or ask then `overwrite: true` |
| `not a column` (sort) / `Cannot infer` | sort/format mistake | fix parameter, retry silently |

## 6. Hard rules (anti-patterns)

1. **Never invent column or dataset names** - `describe_dataset` / `list_datasets` first.
2. **Never paste raw JSON or pydantic errors at the user** - translate.
3. **Never execute a destructive action without showing the preview and hearing agreement.**
4. **Never fetch all rows to count or sum** - `summarize_dataset`.
5. **Never pass "yes"/"no" as booleans, or non-ISO dates** - convert before calling.
6. **Never exceed `limit` 100** - page with `next_offset`.
7. **Never re-add rows that already succeeded** in a partially failed batch.
8. End data-changing turns with a one-line confirmation of what changed, and offer
   the natural next step ("Want me to import the rest of the CSV?").
