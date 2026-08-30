# Master Data MCP Server - Complete Tool Reference

Companion to `SKILL.md`. Exact arguments, defaults, and response shapes for all
16 tools. All tools return the envelope `{"ok": true, ...}` or
`{"ok": false, "error": "<plain-language reason>"}`. Numeric row ids are accepted
wherever string ids are shown.

Global conventions: pagination (`limit` default 20, hard max 100, responses carry
`total` + `count` + `next_offset`), column projection (`columns` param wherever rows
are returned - `id` is always included), batch caps (100 rows), destructive tools
default to a preview.

---

## Datasets & columns

### `create_dataset`
Create a dataset with typed columns.

| arg | type | default | notes |
|---|---|---|---|
| `name` | string | required | unique case-insensitive |
| `columns` | list | required | ≥1; see Column spec below |
| `description` | string | `""` | what this dataset tracks |

Column spec: `{"name", "type": string|text|boolean|integer|float|phone|date|enum,
"required": bool, "default": any, "min_value": num, "max_value": num,
"pattern": "regex", "options": ["A","B"]}` - enum requires non-empty `options`;
`pattern` applies to string/text; `min_value`/`max_value` to numeric.

Example → `{"ok": true, "dataset": "Candidates", "columns": [{"name": "name", "type": "string"}, ...]}`
Errors: name taken; duplicate column names; enum without options; invalid pattern.

### `list_datasets`
| arg | type | default |
|---|---|---|
| `limit` | int 1-100 | 20 |
| `offset` | int | 0 |

→ `{"ok": true, "datasets": [{"name", "description", "row_count", "columns": [{"name","type"}]}], "total", "count", "next_offset"}`

### `describe_dataset`
| arg | type | default |
|---|---|---|
| `name` | string | required |
| `sample_rows` | int 0-5 | 0 |

→ `{"ok": true, "dataset", "description", "row_count",
"columns": [{"name", "type", "required", "default?", "min_value?", "max_value?", "pattern?", "options?"}],
"samples": [{"id", ...}]}` (samples: first rows by id).
Errors: `Dataset 'X' does not exist. Available datasets: ...`

### `add_column`
| arg | type | default |
|---|---|---|
| `dataset` | string | required |
| `column` | Column spec | required |

Existing rows are backfilled with `default` (or null).
→ `{"ok": true, "dataset", "column", "type", "backfilled_rows": <int>}`
Errors: column already exists; invalid definition.

### `update_column`
| arg | type | default |
|---|---|---|
| `dataset` | string | required |
| `column` | string | required - current column name |
| `changes` | object | required - only provided keys apply: `name` (rename), `type`, `required`, `default`, `min_value`, `max_value`, `pattern`, `options` |

Revalidates every stored row; offending rows are **reported, not modified**.
→ `{"ok": true, "dataset", "column", "renamed_from": <old|null>, "rows_checked": <int>,
"invalid_rows": {"<row_id>": ["<error>", ...]}}`
Rename also remaps the key inside every stored row.

### `remove_column`
| arg | type | default |
|---|---|---|
| `dataset` | string | required |
| `column` | string | required |
| `confirm` | bool | false - true executes |

No confirm → `{"ok": true, "requires_confirmation": true, "preview": {"dataset", "column", "affected_rows", "message"}}`.
Confirmed → `{"ok": true, "dataset", "removed", "rows_updated"}`.
Error: cannot remove the last column of a dataset.

### `delete_dataset`
| arg | type | default |
|---|---|---|
| `name` | string | required |
| `confirm` | bool | false |

No confirm → preview `{dataset, row_count, column_count, message}`.
Confirmed → `{"ok": true, "deleted": "<name>", "rows_removed": <int>}`.

---

## Rows

### `add_rows`
| arg | type | default |
|---|---|---|
| `dataset` | string | required |
| `rows` | list of objects (≤100) | required - one object per row, column→value |

→ `{"ok": true, "dataset", "added": <int>, "rejected": <int>,
"results": [{"row": <index>, "status": "added", "row_id": "<id>"} |
            {"row": <index>, "status": "rejected", "errors": ["..."]}]}`
Valid rows are stored even when others in the batch fail. Omitted optional columns
become null/default. Coercions: `"5"`→5 (int), `"7.5"`→7.5, `"true"`→true. "yes"/"no"/
"on"/"off" are REJECTED with a clear error - convert them to true/false yourself.

### `get_row`
| arg | type | default |
|---|---|---|
| `dataset` | string | required |
| `row_id` | string \| int | required |
| `columns` | list of names | null = all |

→ `{"ok": true, "dataset", "row": {"id": "2", ...}}`
Errors: unknown id; unknown column(s) with available list.

### `update_rows` (two modes)
| arg | type | default |
|---|---|---|
| `dataset` | string | required |
| `values` | object column→new value | required - partial update |
| `row_ids` | list \| null | id mode |
| `conditions` | list of filters \| null | bulk mode (mutually exclusive with row_ids) |
| `dry_run` | bool | true - bulk mode only |

Id mode → `{"ok": true, "dataset", "updated", "rejected", "not_found",
"results": [{"row_id", "status": "updated"|"rejected"|"not_found", "errors"?}]}`.
Bulk + dry_run → `{"ok": true, "requires_confirmation": true,
"preview": {"matched_row_ids", "count", "values", "message"}}`.
Bulk + `dry_run: false` → `{"ok": true, "dataset", "matched", "updated", "rejected", "results"}`.
Changed values are revalidated together with the whole row; a rejected row is untouched.

### `delete_rows` (two modes)
| arg | type | default |
|---|---|---|
| `dataset` | string | required |
| `row_ids` | list \| null | id mode |
| `conditions` | list of filters \| null | bulk mode |
| `confirm` | bool | false - true executes either mode |

No confirm → `{"ok": true, "requires_confirmation": true,
"preview": {"dataset", "row_ids": [...matched...], "count", "not_found": [...], "message"}}`.
Confirmed → `{"ok": true, "dataset", "deleted": <int>, "row_ids": [...], "not_found": [...]}`.

### `validate_rows`
Dry-run validation, nothing stored.

| arg | type | default |
|---|---|---|
| `dataset` | string | required |
| `rows` | list (≤100) | required |

→ `{"ok": true, "dataset", "total", "valid", "invalid",
"results": [{"row", "status": "valid", "normalized": {...}} |
            {"row", "status": "invalid", "errors": ["..."]}]}`

### `search_rows`
| arg | type | default | notes |
|---|---|---|---|
| `dataset` | string | required | |
| `conditions` | list of filters \| null | null = all rows | ops: eq, ne, gt, gte, lt, lte, contains, in, between, is_empty, is_not_empty; AND-combined |
| `fuzzy` | bool | false | requires `query` |
| `query` | string | null | fuzzy text |
| `fuzzy_columns` | list \| null | all string/text columns | typo-tolerant match |
| `fuzzy_threshold` | number 1-100 | 80 | similarity cutoff |
| `sort_by` | column \| null | null | exact mode |
| `sort_order` | "asc"\|"desc" | "asc" | nulls last (asc) |
| `limit` | int 1-100 | 20 | clamped |
| `offset` | int | 0 | |
| `columns` | list \| null | null | projection; id always included |

→ `{"ok": true, "dataset", "rows": [{"id", ...}], "total", "count", "next_offset"}`
(`rows[]."_score"` present in fuzzy mode, sorted best-first).
Errors: unknown column (lists available), unsupported op, `contains` on non-text,
`between` without 2-value list, `query` without `fuzzy: true`, non-text `fuzzy_columns`.

### `summarize_dataset`
| arg | type |
|---|---|
| `dataset` | string |

→ `{"ok": true, "dataset", "row_count",
"numeric": {"<col>": {"count", "min", "max", "avg", "sum"}} (or {"count": 0} when empty),
"enums": {"<col>": {"<value>": <count>}}}`
Only numeric and enum columns appear. Never returns row payloads.

---

## Files

### `import_rows`
| arg | type | default | notes |
|---|---|---|---|
| `dataset` | string | required | |
| `file_path` | string | required | .csv or .json on the server's machine |
| `create_if_missing` | bool | false | when the dataset does not exist, create it first with one string column per file header |
| `format` | "auto"\|"csv"\|"json" | "auto" | infers from extension |
| `confirm` | bool | false | two-step import |

Step 1 (no confirm) → `{"ok": true, "requires_confirmation": true,
"preview": {"dataset", "file", "format", "row_count", "file_columns",
"mapping": {file_col: dataset_col}, "unmatched_file_columns", "missing_required_columns",
"sample_rows": [...3 rows...], "message"}}` - nothing imported.
Step 2 (confirm) → `{"ok": true, "dataset", "added", "rejected",
"rejected_rows": [{"row": <index>, "errors": [...]}] (max 100 shown),
"rejected_truncated": bool}`.
CSV cells are strings → auto-coerced (`"27"`→27, `"true"`→true, empty cell→null).
JSON: a list of objects, or `{"rows": [...]}`.
Errors: `File not found: <path>`; `Cannot infer file format`.

### `export_rows`
| arg | type | default | notes |
|---|---|---|---|
| `dataset` | string | required | |
| `file_path` | string | required | destination .csv/.json |
| `format` | "auto"\|"csv"\|"json" | "auto" | |
| `conditions` | list of filters \| null | null = all rows | |
| `columns` | list \| null | all | projection; id always included |
| `overwrite` | bool | false | refuses existing files otherwise |

→ `{"ok": true, "dataset", "file": "<path>", "format", "rows_exported": <int>}`
CSV header: `id,<columns...>`; booleans as `true`/`false`, nulls as empty cells.

---

## Filter condition shape (shared by search_rows / bulk update / bulk delete / export)

```json
{"column": "<dataset column>", "op": "<op>", "value": <any, per op>}
```

Compile-time validation with plain-language errors: unknown column (lists available
columns), unknown op (lists supported ops), non-numeric value for numeric range ops,
non-ISO value for date range ops, `between` without a 2-value list, `in` without a
non-empty list, `contains` on non-text columns.
