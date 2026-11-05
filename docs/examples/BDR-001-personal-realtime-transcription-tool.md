---
id: BDR-001
status: accepted
date: 2026-11-05
---

# BDR-001: Personal real-time transcription and translation tool for meetings and interviews

## Status

accepted

## Context

The user needs a tool that produces a live English transcript during meetings
and interviews and translates it into another language in real time. The tool
is a personal productivity aid, not a commercial product: one user, one
machine, no collaboration or sharing features required.

## Decision

- Product scope: real-time (live) transcription of spoken English with
  concurrent translation into a user-selected target language, aimed at
  meetings and interviews.
- Single-user, single-machine deployment. No multi-tenancy, no accounts, no
  sharing, no sync.
- Target translation language is configurable per session; no fixed default is
  mandated.
- Speaker labeling (diarization) is a required capability: sessions must
  attribute text to distinct speakers (for example, interviewer vs.
  interviewee).
- Explicitly out of scope for MVP: uploading pre-recorded files, collaborative
  editing, integrations with meeting platforms (Zoom/Meet bots), mobile apps.

## Consequences

- All architecture decisions assume exactly one concurrent user and session;
  no concurrency or isolation design is needed.
- Live capture depends on the machine's microphone. Remote meeting audio (for
  example, Zoom playing on speakers) is captured through the mic; a virtual
  audio device for cleaner capture is a documented user-side workaround, not a
  feature.
- Requiring diarization constrains STT provider choice and raises the cost
  floor; the $/hr ceiling is adjusted accordingly (see ADR-002, BDR-002).
- Re-processing of recordings is deferred; if needed later it is an additive
  feature, not an architectural change.
