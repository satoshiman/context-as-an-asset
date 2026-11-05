---
id: BDR-EX2
status: accepted
date: YYYY-MM-DD
note: Sanitized reproduction of a client record. Names, dates, and domain
  details are changed; the structure and decision logic are preserved.
---

# BDR-EX2: Operations team size and infrastructure budget

## Status

accepted (sanitized example)

## Context

The client operates an ERP system. The operations team has five staff and
is not expected to exceed ten within five years; the client will not fund
infrastructure built for larger scale. This single sentence of business
context is invisible in any codebase, yet it determines the entire
technical posture.

## Decision

- Capacity planning targets ten concurrent business users, not thousands.
- No budget for server-managed database infrastructure; operational
  simplicity outranks scalability headroom.

## Consequences

- The derived ADR selects SQLite (single-file, zero-operations) over a
  client-server database, with file-copy backups.
- Without this record, an agent inspecting the repository sees SQLite and
  reasonably suggests "upgrading" to PostgreSQL: the codebase alone
  cannot distinguish a deliberate constraint from an unaddressed
  weakness. With the record, SQLite is a decision, not a debt.
- If a future BDR supersedes the staffing assumption, the BDR-to-ADR link
  identifies exactly which decisions must be revisited.
