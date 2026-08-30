# Design: MCP Master Data Management

## Context

Greenfield repo — no code exists yet. Motivation and personas live in proposal.md. Constraints fixed during grooming: Python + MCP server (stdio) consumed by OpenCode first and Claude Code second; local JSON storage with no database server; single user, localhost, no auth; no versioning/undo, so destructive operations must be confirmation-gated; tool documentation quality is a first-class requirement; agent context must be protected from large payloads; delivery is phase-wise with one git commit per phase.

## Goals / Non-Goals

**Goals:**
- One Python package `mdm_mcp` exposing the full 16-tool catalog through a FastMCP server.
- One validation engine and one filter engine reused by every tool (add/update/import/validate share validation; search/update/delete/export share filtering).
- Agent-friendly behavior: structured `ok`/`error` results, plain-language validation messages, server-enforced pagination/projection/batch caps so context never explodes.
- Storage behind a repository interface so JSON can later be swapped for MongoDB without touching tools.

**Non-Goals:**
- Frontend, REST API, auth, multi-tenancy, versioning/undo, unique-field constraints (deferred), MongoDB implementation (interface only), performance tuning.

## Decisions

1. **Official `mcp` SDK (FastMCP) over standalone `fastmcp` or the TypeScript SDK.** User chose Python; the official SDK keeps dependencies minimal, speaks stdio natively, and auto-derives tool JSON schemas from type hints plus docstrings — which directly serves the "proper docstrings" requirement. Alternatives rejected: standalone `fastmcp` (extra features we do not need, extra dependency churn) and TypeScript (no user preference, splits tooling).

2. **JSON storage, one directory per dataset (`data/<slug>/schema.json` + `rows.json`), atomic writes via temp file + `os.replace`.** Zero infrastructure, human-inspectable files, matches the "JSON over relational" requirement. Alternatives rejected: MongoDB (needs a server; deferred), SQLite (opaque file, relational pressure). Row ids are sequential strings ("1", "2", …) with a `next_id` counter — conversation-friendly ("delete row 12"). Dataset directories are slugified names; uniqueness is enforced case-insensitively.

3. **Pydantic v2 dynamic validation.** For each dataset schema, a `RowValidator` builds a Pydantic model with `create_model` (lax coercion so "5" becomes 5) and one model-level validator that enforces required, min/max, pattern, enum options, India phone format, and ISO dates, translating every failure into plain-language strings. One validator instance is reused across tools. Alternatives rejected: hand-rolled checks (duplicates Pydantic coercion/localization), marshmallow (no benefit over Pydantic which the SDK already uses).

4. **Filter DSL as a list of `{column, op, value}` conditions evaluated in memory.** Simple for agents to construct and for tests to pin: eq, ne, gt, gte, lt, lte, contains, in, between, is_empty, is_not_empty. Fuzzy matching uses rapidfuzz similarity on string/text columns with a threshold, returning ordered matches with scores. Alternatives rejected: query strings (harder for agents to get right), SQL (no SQL engine present).

5. **Context protection is enforced server-side, not left to the agent.** Every list-returning tool: `limit` default 20 clamped to max 100, responses carry `total` and `next_offset`. `columns` projection wherever rows are returned. `add_rows` batch cap 100. `describe_dataset` samples capped at 5. `summarize_dataset` returns aggregates only.

6. **Confirmation pattern is stateless:** destructive tools called with `confirm: false` return a preview plus `requires_confirmation: true`; the caller re-invokes with identical arguments plus `confirm: true`. Alternative (server-issued confirmation tokens) rejected as needless state.

7. **Structured tool results instead of raised errors:** tools return `{"ok": true, ...}` or `{"ok": false, "error": "<plain language>"}` so the agent can converse about failures; unexpected exceptions still surface as MCP tool errors. Docstrings document the shape.

8. **Package layout:** `models/` (Pydantic schemas), `storage/` (JsonRepository), `validation/` (RowValidator), `search/` (FilterEngine, Phase 3), `services/` (dataset_service, row_service, file_service), `tools/` (thin FastMCP registrations), `server.py`, `__main__.py`. Services receive the repository via constructor; the data root resolves from `MDM_DATA_DIR` (tests) or `./data`.

9. **Phase → commit mapping:** Phase 1 foundation (`feat: dataset & row foundation`), Phase 2 schema lifecycle and row updates (`feat: schema lifecycle & row updates`), Phase 3 search/fuzzy/bulk (`feat: search, fuzzy matching & bulk operations`), Phase 4 docs and persona walkthroughs (`docs: tool docs & persona walkthroughs`).

## Risks / Trade-offs

- [Whole-file JSON rewrite per mutation] → acceptable at single-user scale; repository interface isolates the swap to SQLite/Mongo if data grows.
- [No file locking; concurrent tool calls could race] → single-user localhost assumption; revisit with a lock file if concurrent clients appear.
- [Pydantic lax coercion may surprise, e.g. "1.5" rejected for integer] → tests pin coercion behavior; error messages state the expected type.
- [Structured error dicts hide failures from clients expecting raised errors] → docstrings document the `ok`/`error` shape; consistent across all tools.
- [Dynamic create_model per validator] → negligible cost at this scale; one instance per service call.

## Open Questions

None blocking — remaining unknowns (exact fuzzy threshold, CSV quoting edge cases) are resolved by tests inside Phase 3.
