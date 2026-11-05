---
id: BDR-006
status: accepted
date: 2026-11-05
supersedes: BDR-005
---

# BDR-006: Local data ownership; transcript stored as standard SRT

## Status

accepted - supersedes BDR-005.

## Context

BDR-005 made the Markdown file the canonical session artifact and made the
storage format and the review render format the same document. In practice
this coupling has two costs:

- The review UI renders the stored Markdown through `marked` + `DOMPurify`
  into `dangerouslySetInnerHTML`, then queries the generated DOM back out
  (`<li>`/`<code>`/`<strong>`) to rebuild segments for seek and highlight.
  Presentation improvements require DOM surgery on rendered markup.
- The `.md` transcript is not usable outside the app: the session WAV
  (retained by default since BDR-005) cannot be replayed with subtitles in
  any standard player, editor, or sharing workflow.

SRT is the universal subtitle format: plain text, human-readable and
editable with any tool, and directly loadable by VLC, mpv, YouTube, and
video editors alongside the retained WAV.

## Decision

- Sessions remain plain local files; no database. Every artifact stays
  readable and editable with any text tool. (restated)
- Session audio is retained as a sibling WAV by default; the Record audio
  switch defaults to ON and remains a per-session opt-out. (restated,
  unchanged from BDR-005)
- The canonical session record becomes a file bundle sharing one stem:
  - `<stem>.md` - YAML frontmatter (session metadata) plus a human-readable
    `## Assist` section for answer-assist notes.
  - `<stem>.srt` - the transcript, as one bilingual cue per segment:
    numbered, `HH:MM:SS,mmm --> HH:MM:SS,mmm`, source line (with optional
    `Speaker: ` prefix), translation line.
  - `<stem>.wav` - session audio when recording was on. (unchanged)
- The storage format and the review format are decoupled: the review view
  parses the `.srt` into structured cues and renders components; the
  single-document coupling from BDR-003/BDR-005 is abandoned.
- A single bilingual `.srt` is chosen over per-language files so the file
  is directly playable; the cost (in-place cue insertion when a
  translation lands) is accepted and handled atomically at the storage
  layer (see ADR-007).
- Existing session files in the legacy Markdown-line format are not
  migrated; the owner has chosen to discard them.

## Consequences

- Transcripts are usable outside the app with zero export step: drop the
  `.srt` next to the `.wav` in any player.
- Transcript content is still transmitted to third-party STT/LLM providers
  during live sessions; this residual privacy exposure is accepted and
  must be documented for the user. (restated)
- Full-text search remains a filesystem concern (grep over `.srt`+`.md`)
  until an index is justified. (restated)
- Frontmatter still carries enough metadata to identify session date,
  languages, providers, and speaker names without a database. (restated)
- Speaker identity in SRT uses the `Name: ` text-prefix convention; there
  is no speaker channel in the format itself.
- Assist notes have no place in SRT and live in the `.md` body; the two
  artifacts must be read together for a complete session picture.
