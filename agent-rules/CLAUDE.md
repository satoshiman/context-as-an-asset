# CLAUDE.md

Condensed rules for the Context as an Asset workflow. The full rulebook lives
in `AGENTS.md`; this file carries the operational core. All repo artifacts
(records, plans, logs, code, comments, commits) are written in English.

## Hierarchy

`CONTEXTS/` holds decision documents in decreasing authority:

1. `01-bdr/` - Business Decision Records (rare, human-owned)
2. `02-adr/` - Architecture Decision Records (rare, human-owned)
3. `03-implement-plan/` - Implementation Plans (per task, agent-drafted,
   human-approved)
4. Codebase - the artifact produced under a plan (agent-writable in scope)
5. `04-logs/` - Agent Logs (append-only, only via `event.py`)

**Precedence:** read all levels; on conflict the higher level wins. Never
silently violate an upper level. If a needed BDR/ADR is missing at any
point, pause, draft the record, and ask the human before adding it; if it
conflicts with an existing record, propose `supersedes` and flip the old
status.

## Workflow

1. Decompose the task; ask about anything the documents cannot resolve.
2. Review in precedence order: BDRs, ADRs, relevant code.
3. Draft a plan in `03-implement-plan/` with frontmatter
   (`review_count`, `patch`) and a Definition of Done checklist.
4. Run at least one verification pass against BDRs/ADRs/codebase
   (`review_count >= 1`). Never implement `review_count: 0` or
   `patch: pending`. Only the human moves `status` to `reviewed` /
   `approved`.
5. Implement within scope, commit, then log via
   `CONTEXTS/04-logs/event.py` (`--no-commit` for non-code work). A task
   is not done until its event exists; on completion tick the DoD and set
   `status: implemented`.

## Rules that bite

- Append-only: changing a decision means a new record with `supersedes`
  pointing back; never edit an old record's content.
- Commit first, then log: events bind to HEAD.
- Proportional documentation: small tasks may produce only log entries.
