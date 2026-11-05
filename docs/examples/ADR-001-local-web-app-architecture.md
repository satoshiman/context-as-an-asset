---
id: ADR-001
status: accepted
date: 2026-11-05
---

# ADR-001: Local web application: Node.js backend + browser frontend on localhost

## Status

accepted

## Context

Constrained by BDR-001 (single user, single machine) and BDR-002 (zero fixed
infrastructure). A local web app gives a real browser UI (microphone capture
via `getUserMedia`, rendered Markdown review) without desktop-packaging
overhead. Node.js + TypeScript is chosen per owner direction: one language
across backend and frontend, and all candidate providers (AssemblyAI,
Deepgram, OpenAI) ship official Node SDKs with streaming WebSocket support.

## Decision

- Backend: Node.js + TypeScript on Fastify, serving (a) the built frontend
  assets, (b) a WebSocket endpoint that relays mic audio to the STT provider
  and pushes transcript/translation events back, and (c) a small REST surface
  for session lifecycle (start/stop/list/read).
- Frontend: a single-page React + TypeScript app built with Vite (Tailwind +
  shadcn/ui). Audio capture via `getUserMedia` + `AudioWorklet`, sent as PCM
  chunks over WebSocket. In development the Vite dev server proxies API and
  WebSocket traffic to Fastify; in production Fastify serves the built
  `dist/` directly. Full library list lives in ADR-006.
- The server binds to `127.0.0.1` only. There is no auth layer; loopback
  binding is the entire security boundary.
- Single process, single user, single active session at a time.

## Consequences

- No CORS, auth, or tenancy code anywhere; exposing the server beyond loopback
  (for example, binding `0.0.0.0`) is an architecture violation. The Vite dev
  proxy is configured for `127.0.0.1` only.
- The frontend has a real build step; UI complexity (dual-column live
  transcript, speaker renaming, session list, rendered review) justifies React
  + shadcn over a no-build page.
- Browser-based capture inherits browser mic-permission behavior and cannot
  see system audio directly (consistent with the limitation recorded in
  BDR-001).
- A desktop wrapper (for example, Tauri) can be added later without changing
  the backend; the WebSocket boundary makes the frontend replaceable.
