---
id: PLAN-006-replaceable-draft
status: implemented
date: 2026-11-05
review_count: 1
patch: applied
---

# PLAN-006: Replaceable draft - each interim renders verbatim, clears on final

## Status

implemented - code, tests, and gates done. The live manual check
(speaking into the app) is left for the developer; the no-duplication
invariant is structural and covered by the capture-replay test.

## Context

Developer decision (this session): the draft strip must show the whole
interim exactly as received and delete the previous one, instead of the
append-only overlap-matched accumulation introduced by PLAN-005.

Why: the append-only + `shownOverlap` design still produces visible
duplication. Duplicates appear whenever alignment fails and the whole
interim is appended, which happens when a revision rewrites the tail
words AND fewer than `MIN_DROPPED_MATCH = 3` stable words remain as
anchor (common at utterance start, when the shown tail is still short).
Additionally, the reducer never removes draft entries on `final`, so a
just-committed sentence stays visible in the draft strip while also
appearing in the committed feed above it.

Replace-verbatim removes duplication by construction: the draft strip
holds at most one interim, so nothing can repeat; and clearing on
`final` removes the committed words immediately.

Accepted trade-off (developer decision): text under the reader's eyes
can now be rewritten or vanish when Deepgram re-decodes a window, which
is exactly what PLAN-005's append-only design was built to avoid. This
is deliberate: stable, correct text beats stable-but-duplicated text.

## Governing records

- BDR-001: the live transcript must be followable in real time -
  duplicated draft text is a readability defect this plan removes.
- BDR-002: zero new cost - the change deletes code, adds no dependency.
- ADR-001/ADR-006: all changes stay in `web/`; no server, wire, or
  Markdown changes.
- ADR-002/ADR-004: Deepgram interim semantics are consumed as-is
  (cumulative re-decode); the Markdown artifact still stores only
  finals and is untouched.
- PLAN-005 (implemented): this plan reverses its draft-strip decision
  (append-only entries + `shownOverlap` alignment + `draftTail` ring).
  Everything else PLAN-005 introduced (scrolling committed feed,
  paragraph-per-speaker log, pause/resume, `max-w-4xl` container) is
  unchanged.

## Scope

In scope:

1. `web/src/lib/use-live-session.ts`: reducer and state for the draft.
2. `web/src/lib/use-live-session.test.ts`: rewrite the draft cases.
3. `web/src/components/transcript.tsx`: only if needed; the existing
   `draft.map()` render already works with a 0-or-1-element array.

Out of scope: server, Deepgram options, committed feed (`finals`),
translation feed, pause/resume behavior, `Live.tsx` wiring, Markdown
format, `Review.tsx`.

## Design decisions (pinned)

**State shape** (`LiveState`):

- `draft: DraftEntry[]` is kept as the type (LiveStrip prop unchanged)
  but now holds **at most one element**: `{ id: 0, text }`. The id is
  constant so React reconciles the same `<RevealWords>` instance across
  interims: unchanged head words keep their spans (no re-animation),
  revised words update in place, only trailing new words animate.
- `draftSeq`, `draftTail` are deleted from `LiveState` and
  `initialState`.

**Reducer semantics**:

- `'partial'`: `const text = action.segment.text.trim()`; empty text
  returns `state` unchanged. Otherwise
  `draft: [{ id: 0, text }]` - the new interim replaces the old one
  verbatim. No alignment, no trimming: a single interim is naturally
  bounded.
- `'final'`: the dedup early-return is unchanged and runs first - a
  duplicate final leaves `draft` untouched, since it may hold a live
  interim of the next window. On the append path, add `draft: []` -
  the committed text now lives only in the feed.
- `'session'` with `active: null`: also `draft: []` (dead text must not
  outlive the session). `'session'` reporting `paused: true` does NOT
  clear the draft - the frozen display keeps its last interim.
- `'reset'`: unchanged (whole state resets).
- `'translation'`, `'speaker'`, `'ws'`, `'starting'`: untouched.

**Deleted code** (`use-live-session.ts`): `MAX_DRAFT_CHARS`,
`DRAFT_TAIL_WORDS`, `MAX_TAIL_DROP`, `MIN_DROPPED_MATCH`, `normTok`,
`shownOverlap`, the append-only design comment block, and the
now-stale inline comments inside the `'partial'` and `'final'` cases
(the `shownOverlap` rationale and the `draftTail` retention note).
A short replacement comment states the rule: the draft is the latest
interim verbatim and is cleared when the utterance finalizes.

**Rendering** (`transcript.tsx`): unchanged. `draft.map(e =>
<RevealWords text={e.text} />)` already handles 0 or 1 entries; the
2-line masked strip keeps its height and scroll pinning.

## Steps

### Step 1 - `web/src/lib/use-live-session.ts`

- Remove `draftSeq`/`draftTail` from `LiveState` and `initialState`.
- Rewrite the `'partial'` and `'final'` cases per the pinned semantics;
  extend `'session'` null to clear `draft`.
- Delete the helpers/constants listed above and the old design
  comment; add the short replacement comment.

### Step 2 - `web/src/lib/use-live-session.test.ts`

- Drop `MAX_DRAFT_CHARS` from the imports.
- Rewrite the `partial draft` describe to the new invariant:
  after every non-empty `'partial'`, `draftText(s)` equals that
  interim's trimmed text; after every `'final'`, `s.draft` is empty.
- Cover: verbatim replace on grow and on head/tail revision; final
  clears draft; `session` `active: null` clears draft; `paused` session
  event keeps draft; empty/whitespace interim is ignored.
- Replace the real-capture replay block: replay the same fixture and
  assert that after each partial the draft equals that interim, and
  after each final it is empty (the no-duplication invariant now holds
  by construction, so the 4-gram and phrase tests are dropped).

## Test plan

Automated:

- Updated reducer tests above.
- Gates: `npm run typecheck`, `npm test`, `npm --prefix web run build`,
  `npm --prefix web run lint`.

Manual acceptance:

- Speak continuously: the draft line shows the current utterance
  rewriting itself in place; once a segment finalizes, the draft line
  empties and the text exists only in the committed feed - the same
  sentence is never visible twice.
- Pause mid-utterance: the draft stays frozen; resume: it keeps
  replacing verbatim.
- Reload mid-session: committed feed backfills; the draft starts
  empty and fills with the next interim.

## Risks and notes

- Text under the reader can now change or disappear mid-read (accepted,
  see Context). If this proves distracting, a future refinement could
  animate the swap; not in scope.
- If a provider emits a late interim belonging to an already-finalized
  window, the draft repopulates until the next final. Cosmetic, and
  Deepgram orders events so this is rare. Symmetrically, a final can
  clear a just-arrived interim that belongs to the next window; also
  rare under ordered delivery, and self-heals on the following interim.
- `DraftEntry` keeps `{ id, text }` shape so `LiveStrip` and its props
  in `Live.tsx` are unchanged.

## Definition of Done

- [x] `'partial'` replaces `draft` with the verbatim interim (at most
  one `DraftEntry`); `'final'` and a null-`'session'` clear it;
  `paused` keeps it.
- [x] `draftSeq`, `draftTail`, `shownOverlap`, `normTok`, and the
  `MAX_*`/`MIN_*`/`DRAFT_*` constants are deleted.
- [x] Updated tests pass; `npm run typecheck`, `npm test`,
  `npm --prefix web run build`, `npm --prefix web run lint` all clean.
- [ ] Manual check: no duplicated text ever appears in the draft strip
  or between draft and committed feed.
- [x] No server, wire, Markdown, or `Live.tsx` changes.
