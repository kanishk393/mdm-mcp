# MDM MCP — Master Data Management for conversational agents

A backend-only master data management tool exposed as an MCP server. Naive users describe
what they want to track in plain language; the agent creates datasets, defines typed
columns (like building a Google Form), and performs every data operation through
well-documented tools. No GUI, no spreadsheet skills required — the agent is the interface.

Mental model: `Workspace → Datasets → Columns (typed) → Rows`.

## Quickstart

```bash
uv venv --python 3.12 .venv
uv pip install -e . --python .venv/bin/python
.venv/bin/mdm-mcp          # runs the MCP server over stdio
```

Requires Python 3.10+ (the venv above provisions 3.12 via uv). `pip install -e .` works too.

Data lives in local JSON files — one directory per dataset (`data/<dataset>/schema.json`
plus `rows.json`), written atomically. Set `MDM_DATA_DIR` to change the storage location
(default `./data`). No database server, single user, localhost, no auth.

## Registering the server

### OpenCode

Add to `opencode.json` (project root or `~/.config/opencode/opencode.json`):

```json
{
  "mcp": {
    "master-data": {
      "type": "local",
      "command": ["/absolute/path/to/this/repo/.venv/bin/mdm-mcp"],
      "enabled": true
    }
  }
}
```

### Claude Code

```bash
claude mcp add master-data -- /absolute/path/to/this/repo/.venv/bin/mdm-mcp
```

## Tool catalog (16 tools)

**Datasets & columns**

| Tool | Purpose |
|---|---|
| `create_dataset` | New dataset with typed columns (string, text, boolean, integer, float, phone, date, enum) |
| `list_datasets` | Paginated list with row counts and column summaries |
| `describe_dataset` | Full column definitions + optional sample rows (capped at 5) |
| `add_column` | Add a typed column, backfilling existing rows with its default |
| `update_column` | Rename / retype / re-constrain with per-row revalidation report |
| `remove_column` | Preview → confirm removal |
| `delete_dataset` | Preview → confirm deletion |

**Rows**

| Tool | Purpose |
|---|---|
| `add_rows` | Add up to 100 rows per call, per-row plain-language validation reports |
| `get_row` | One row by id, optional column projection |
| `update_rows` | Partial updates by ids, or in bulk by filter (dry-run default) |
| `delete_rows` | Delete by ids or filter (preview → confirm) |
| `validate_rows` | Dry-run validation with normalized output, nothing saved |
| `search_rows` | Filter DSL, typo-tolerant fuzzy matching, sorting, pagination |
| `summarize_dataset` | Row counts, numeric min/max/avg/sum, enum breakdowns |

**Files**

| Tool | Purpose |
|---|---|
| `import_rows` | Two-step CSV/JSON import: mapping preview → confirmed commit with per-row reports |
| `export_rows` | Filtered + projected CSV/JSON export with overwrite guard |

## Built-in conventions

- **Context protection**: every list response is paginated (`limit` default 20, clamped
  at 100) and carries `total` + `next_offset`; column projection keeps rows small.
- **Safety**: destructive operations return `requires_confirmation: true` plus a preview;
  re-invoke with `confirm: true` (or `dry_run: false` for bulk updates) to execute.
- **Agent-friendly results**: tools return `{"ok": true, ...}` or
  `{"ok": false, "error": "<plain-language reason>"}` so the agent can converse about
  failures instead of crashing.
- **Validation**: Google-Forms-style — required, min/max, pattern, enum options, Indian
  mobile numbers (10 digits, optional +91/0 prefix), ISO dates. "5" coerces to the
  number 5; every problem in a row is reported, not just the first.

## Development

```bash
uv pip install -e . pytest --python .venv/bin/python
.venv/bin/python -m pytest
```

Planning artifacts live in `openspec/` (proposal, specs, design, tasks). Development is
phase-wise with one commit per phase; persona walkthroughs (recruiter, business owner,
individual) run as integration tests in `tests/test_personas.py`.
