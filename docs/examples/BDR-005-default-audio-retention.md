---
id: BDR-005
status: superseded
date: 2026-11-05
supersedes: BDR-003
---

# BDR-005: Local data ownership; session audio retained by default

## Status

superseded by BDR-006.

## Context

BDR-003 established local Markdown ownership and made raw audio retention
strictly opt-in ("must default to off"). After the opt-in recording switch
shipped (PLAN-010), actual use showed the default was wrong for this tool:
the user expects session audio to exist in Review, and discovering after a
session that audio was not kept is worse than the disk it saves. Disk is
local and cheap (~115 MB/hour of uncompressed WAV); the privacy motivation
for default-off weighs less at single-user scale because the file never
leaves the machine.

## Decision

- The canonical artifact of every session is a Markdown file stored on the
  local filesystem, readable and editable with any text tool. (restated)
- No database is required at MVP. No data leaves the machine except audio
  and text sent to the configured STT and LLM APIs. (restated)
- Transcripts are re-viewed inside the app through rendered Markdown, so
  the storage format and the review format are the same document.
  (restated)
- Session audio is retained as a sibling WAV **by default**. The start
  form's Record audio switch defaults to ON and remains a per-session
  opt-out. (changed from BDR-003, which required default-off)

## Consequences

- Transcript content is transmitted to third-party STT/LLM providers
  during live sessions; this residual privacy exposure is accepted and
  must be documented for the user. (restated)
- Full-text search across many sessions is limited to filesystem tools
  until an index (for example, SQLite) is later justified (see ADR-004).
  (restated)
- Markdown files must carry enough metadata (frontmatter) to identify
  session date, languages, and providers without a database. (restated)
- Local disk now grows ~115 MB per recorded hour by default; deletion is
  manual (a .wav lives and dies with its .md). If growth becomes a
  problem, a cleanup/compaction policy is a follow-up decision, not an
  implementation detail.
