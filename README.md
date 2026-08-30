# MDM MCP — Master Data Management for Conversational Agents

A backend-only master data management system exposed as a **Model Context Protocol (MCP)
server**. Non-technical users describe what they want to track in plain language; an AI
agent (OpenCode, Claude Code, or any MCP client) creates the schema, captures records,
and answers questions through **16 well-documented tools** — no GUI, no spreadsheet
skills, no SQL. The agent is the interface; the data lives in clean local JSON.

```
User ("track my job applicants")  →  Agent  →  MCP tools  →  JSON storage
                                     ↑ you are here (server + skill)
```

---

## 1. Quickstart (60 seconds, Docker only)

```bash
bash setup.sh          # builds image, smoke-tests the MCP handshake, writes client configs
bash demo/demo.sh      # optional: 30-second scripted walkthrough of the product
opencode               # OpenCode: server already registered via opencode.json
#   or
claude                 # Claude Code: approve the "master-data" project server when prompted
```

Then simply talk:

> "I want to track candidates for the Java developer role — name, phone, experience,
> and which stage they're in."
> "Add Rahul Sharma, 9876543210, 5 years, applied yesterday."
> "Who applied in the last week with more than 3 years experience?"
> "How many candidates are in each stage?"

**Requirements**: Docker + (OpenCode *or* Claude Code). Nothing else — no Python, no
venv, no database server, no ports. Data persists in the Docker volume `mdm-data`
(reset anytime: `docker volume rm mdm-data`).

<details>
<summary>Local (non-Docker) setup</summary>

```bash
uv venv --python 3.12 .venv
uv pip install -e . --python .venv/bin/python
.venv/bin/mdm-mcp     # stdio MCP server; data in ./data (override with MDM_DATA_DIR)
```
Point `opencode.json` / `.mcp.json` at `.venv/bin/mdm-mcp` instead of `docker run`.
</details>

---

## 2. The problem

People without spreadsheet experience waste significant time maintaining records in
Excel/Google Sheets: column discipline, filters, formulas, and data types all demand
training. Existing tools assume the user drives a GUI; AI agents remove that assumption.

**Solution**: expose a *form-like* data backend to an agent. The agent acts as a
data clerk — proposes a schema (like building a Google Form), captures records from
conversation, validates them instantly, and answers questions — while the server
enforces types, safety gates, and context limits.

**Three personas anchor the design** (used as acceptance scenarios, not features):

| Persona | What they exercise |
|---|---|
| **Hiring partner** | Dataset per JD, enum stages, 100s of applicants, typo-tolerant fuzzy name search, bulk CSV import |
| **Business owner** | Inventory/vendors/payments/employees, numeric + date validation, combined filters, bulk edits, totals |
| **Individual** | Health logs, investments, schedules — date-heavy, low volume, high frequency |

**User mental model**: `Workspace → Datasets → Columns (typed) → Rows`.

---

## 3. Tool catalog (16 tools)

**Datasets & columns** — `create_dataset`, `list_datasets`, `describe_dataset`,
`add_column`, `update_column`, `remove_column`, `delete_dataset`

**Rows** — `add_rows`, `get_row`, `update_rows`, `delete_rows`, `validate_rows`,
`search_rows`, `summarize_dataset`

**Files** — `import_rows`, `export_rows`

Column types: `string, text, boolean, integer, float, phone, date, enum` with
Google-Forms-style constraints: `required`, `default`, `min_value/max_value`,
`pattern`, enum `options`.

---

## 4. Engineering for user-friendliness

This section is the heart of the assessment: the server is designed so that *whatever
the user says, the agent can fulfil safely*.

1. **Agent-coaching server instructions + skill file** — the server ships `instructions`
   and a skill (`.opencode/skills/master-data-management/`, `.claude/skills/...`)
   teaching the agent to: propose schemas before creating, convert "yesterday" to an
   ISO date, null-fill unmentioned fields, answer with tables, and confirm before
   destructive actions.
2. **Plain-language validation** — every failure is a sentence a human can act on:
   ```
   Column 'phone' must be a valid Indian mobile number (10 digits, optional +91 or 0 prefix).
   Column 'stage' must be one of: Applied, Screened, Rejected.
   ```
   Per-column checks report *all* problems in a row, not just the first.
3. **Lenient inputs** — `"5"` becomes the number 5, `"true"` becomes a boolean,
   numeric row ids (`2` vs `"2"`) both work; empty CSV cells become nulls.
4. **Typo-tolerant search** — `search_rows(fuzzy=true, query="Rahual")` finds
   "Rahul Sharma" (rapidfuzz, similarity-scored).
5. **Safety gates, no undo needed** — delete/bulk-edit/schema-changing tools return a
   preview + `requires_confirmation: true`; execution needs explicit `confirm`/`dry_run=false`.
6. **Agent-context protection** — server-enforced: `limit` default 20 / max 100 with
   `total` + `next_offset` on every list, column projection, batch cap 100 rows,
   sample caps, aggregate-only summaries. The conversation never drowns in rows.
7. **Structured results** — `{"ok": true, ...}` / `{"ok": false, "error": "<reason>"}`
   so the agent converses about failures instead of crashing.

---

## 5. Architecture

```
mdm_mcp/
├── models/        Pydantic: ColumnSpec, DatasetSchema, ColumnUpdate, FilterCondition
├── storage/       JsonRepository (interface): dir-per-dataset, schema.json + rows.json,
│                  atomic temp-file writes, MDM_DATA_DIR override
├── validation/    RowValidator: pydantic TypeAdapter coercion per column + constraint
│                  checks → plain-language issues; ONE engine reused by 4 tools
├── search/        FilterEngine: {column, op, value} DSL (11 ops) + rapidfuzz fuzzy
│                  scoring; reused by search, bulk update/delete, export
├── services/      dataset_service, row_service, file_service (all business logic)
├── tools/         Thin FastMCP registrations: docstrings + Pydantic-typed args ARE
│                  the generated tool documentation (JSON schema)
└── server.py      FastMCP server (stdio) + agent instructions
```

**Key decisions** (full rationale in `openspec/changes/archive/2026-08-30-mcp-master-data-management/design.md`):

- **Local JSON over a database** — zero infrastructure, human-inspectable files,
  single-user localhost scope; storage sits behind a repository interface so MongoDB
  can slot in without touching tools.
- **Pydantic dynamic validation** — one validator instance per dataset reused by
  add/update/import/validate; pydantic gives type coercion and error localization for free.
- **One FilterEngine, four consumers** — search, bulk update, bulk delete, export share
  identical filter semantics.
- **Official `mcp` SDK (FastMCP)** — tool JSON schemas derive automatically from typed
  signatures + docstrings, so documentation debt is structurally impossible.

---

## 6. Spec-driven development (OpenSpec)

The project was built with an artifact-driven workflow (`openspec/`), where code starts
only after behavior contracts exist. All artifacts are preserved in
`openspec/changes/archive/2026-08-30-mcp-master-data-management/`:

| Artifact | Contents |
|---|---|
| `proposal.md` | Problem, personas, mental model, tool surface, deferred scope |
| `specs/*/spec.md` | **4 capability specs** — `dataset-management`, `row-management`, `row-search`, `bulk-operations` — 23 requirements, each with WHEN/THEN scenarios that double as test cases |
| `design.md` | Decisions with rejected alternatives, risks/trade-offs (JSON rewrite cost, no locking, coercion surprises) |
| `tasks.md` | 24 phase-ordered tasks, each with its own verification step |

Rules followed throughout: no implementation without a spec covering it;
`openspec validate` green before any commit; implementation verified against the
spec scenarios (e.g. the "Rahual finds Rahul" and "100-row batch cap" scenarios are
literal pytest cases).

---

## 7. Phase-wise delivery (one commit per phase)

| Phase | Commit | Delivered |
|---|---|---|
| Planning | `d018b0a`-era `03d0089` | All OpenSpec artifacts, validated |
| 1 — Foundation | `79fbf0d` | Models, atomic JSON storage, validator, create/list/describe/add/get, 47 tests |
| 2 — Schema & updates | `7803df7` | Column lifecycle, preview→confirm deletions, partial updates, dry-run validation |
| 3 — Search & bulk | `0db2554` | Filter DSL, fuzzy search, summaries, bulk-by-filter, CSV/JSON import/export |
| 4 — Polish | `4fa709d` | Docstring audit (automated), README, 3 persona walkthrough suites |
| Hardening | `7440227` | Console-script cwd fix, numeric ids, richer agent instructions |
| Packaging | `a9ca732`, `6123890` | Docker one-command setup + 30-second demo |

---

## 8. Testing strategy (127 tests)

| Layer | What it proves |
|---|---|
| **Unit** (`test_models`, `test_validation`, `test_storage`, `test_filter_engine`) | Every column type, constraint, rejection message, filter op, atomic-write behavior |
| **Service integration** (`test_services`, `test_row_updates`, `test_schema_lifecycle`, `test_search`, `test_bulk`, `test_files`) | Full workflows incl. pagination, confirm gates, import/export roundtrips |
| **Persona walkthroughs** (`test_personas`) | The 3 personas as end-to-end scenarios: recruiter funnel, business-owner restock + totals, individual health log |
| **MCP wire tests** (`test_server`) | Tool registration (16), schema descriptiveness, docstring audit, structured results, destructive tools default to preview |
| **Manual/automated E2E** | MCP Inspector over real stdio; scripted Docker client session (create → validate → persist across two container runs); live OpenCode agent conversations incl. a bad-phone recovery flow |

---

## 9. Example interaction

```
User:   add my friend Aman Gupta to the invitees, his phone is 123
Agent:  ⚙ master-data_add_rows {..., "phone": "123"}
Server: {"ok": true, "added": 0, "rejected": 1,
         "results": [{"row": 0, "status": "rejected",
                      "errors": ["Column 'phone' must be a valid Indian mobile number
                                 (10 digits, optional +91 or 0 prefix)."]}]}
Agent:  Aman wasn't added yet — the phone column requires a valid Indian mobile
        number, so "123" was rejected. Do you have his full number?
```

---

## 10. Project layout

```
├── Dockerfile, setup.sh, .dockerignore   one-command Docker packaging
├── demo/                                  30-second scripted demo (inside Docker)
├── mdm_mcp/                               the server (see Architecture)
├── tests/                                 127 tests, 4 layers
├── .opencode/skills/, .claude/skills/     agent skill for effective tool use
├── opencode.json, .mcp.json               client configs (generated by setup.sh)
├── openspec/                              spec-driven development artifacts (archive)
└── README.md                              this file
```

**Stack**: Python 3.12, official MCP SDK (FastMCP, stdio), Pydantic v2, rapidfuzz,
stdlib `csv`/`json`. Dependencies kept deliberately minimal.

---

## 11. Evaluation checklist

1. `bash setup.sh` → handshake smoke test passes
2. `bash demo/demo.sh` → import with rejects, fuzzy match, dry-run bulk edit, summary
3. Start `opencode` (or `claude`) in this folder and hold a natural conversation
4. Try a mistake on purpose (bad phone, unknown person) — observe recovery UX
5. Inspect `data/` (or `docker run --rm -v mdm-data:/data alpine cat /data/<dataset>/rows.json`)
   — the storage is readable JSON
6. `.venv/bin/python -m pytest` (local setup) — 127 tests green
