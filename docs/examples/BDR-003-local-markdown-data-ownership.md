---
id: BDR-003
status: superseded
date: 2026-11-05
---

# BDR-003: Local data ownership with Markdown as the canonical record

## Status

superseded by BDR-005 (2026-11-05)

## Context

Sessions may contain confidential interview or meeting content. The user wants
full ownership of the data, portability of the output, and the ability to read
transcripts with any tool. Structured query capability is not a requirement at
current volume.

## Decision

- The canonical artifact of every session is a Markdown file stored on the
  local filesystem, readable and editable with any text tool.
- No database is required at MVP. No data leaves the machine except audio and
  text sent to the configured STT and LLM APIs.
- Transcripts are re-viewed inside the app through rendered Markdown, so the
  storage format and the review format are the same document.
- Raw audio is not retained by default; optional retention may be offered but
  must default to off.

## Consequences

- Transcript content is transmitted to third-party STT/LLM providers during
  live sessions; this residual privacy exposure is accepted and must be
  documented for the user.
- Full-text search across many sessions is limited to filesystem tools until
  an index (for example, SQLite) is later justified (see ADR-004).
- Markdown files must carry enough metadata (frontmatter) to identify session
  date, languages, and providers without a database.
