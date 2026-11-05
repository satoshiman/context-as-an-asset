---
id: ADR-002
status: accepted
date: 2026-11-05
---

# ADR-002: Streaming cloud STT behind a provider interface; default Deepgram Nova-3 with diarization

## Status

accepted

## Context

BDR-001 requires real-time output and mandatory speaker labeling (diarization);
BDR-002 keeps dollars-per-audio-hour as the primary selection criterion within
that constraint. Market check as of 2026-11-05, streaming English rates:

| Provider / model | Streaming price | Diarization | Notes |
| --- | --- | --- | --- |
| Deepgram Nova-3 Monolingual | $0.46/hr | +$0.12/hr (total ~$0.58/hr) | Cheapest streaming option with real speaker labels; $200 free credit |
| Deepgram Nova-3 Multilingual | $0.55/hr | +$0.12/hr (total ~$0.67/hr) | For mixed-language meetings |
| AssemblyAI Universal-Streaming | $0.15/hr (session duration) | Not supported on streaming | ~300 ms immutable finals, built-in endpointing |
| OpenAI gpt-4o-mini-transcribe (Realtime transcription) | ~$0.18/hr | Not supported on streaming | Token-billed estimate; older whisper/gpt-4o transcribe models are deprecated, shutdown 2027-02-26 |

## Decision

- STT is consumed only through a provider interface (`start_stream`,
  `send_audio`, events: `partial`, `final`, `error`; `final` carries a
  `speaker` field when diarization is on). Providers are selectable by config;
  no provider SDK types leak into application code.
- MVP default: Deepgram Nova-3 Monolingual streaming with the diarization
  add-on, roughly $0.58 per audio hour, the cheapest streaming STT with real
  speaker attribution. Nova-3 Multilingual is the per-session alternative for
  mixed-language meetings.
- Diarization is a per-session toggle. When it is off (solo dictation, notes),
  the designated low-cost path is AssemblyAI Universal-Streaming at ~$0.15
  per session-hour.
- Billing hygiene: Deepgram bills per second of streamed audio; AssemblyAI
  bills on socket-open duration. The backend must close streams immediately on
  stop or browser disconnect and enforce an idle-timeout auto-close.

## Consequences

- All-in session cost with diarization lands near $0.60-0.70 per hour
  (STT ~$0.58 plus translation), well under the revised BDR-002 ceiling of
  $2.00/hr. The headroom allows optional accuracy add-ons such as Deepgram
  Keyterm Prompting (~$0.08/hr) for names and domain vocabulary when needed.
- Diarization on a single mixed mic channel is voice-based and approximate:
  it separates speakers but cannot reliably map labels to named people, and
  overlapping speech degrades accuracy. The UI labels speakers generically
  (`Speaker 1`, `Speaker 2`) and lets the user rename them per session.
- Provider pricing and deprecations change (OpenAI's 2027-02-26 shutdown is
  already announced); re-validating the rate card is part of any future
  provider change.
