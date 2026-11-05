---
id: PLAN-NNN-<slug>
status: draft | reviewed | approved | implemented | superseded
date: YYYY-MM-DD
review_count: 0
patch: n/a
---

# PLAN-NNN: <title>

## Status

draft. `review_count` starts at 0 and increments only when a verification
pass re-checks the finished plan against BDRs, ADRs, and the codebase.
`patch` is `n/a` until the first review, then `not-needed`, `pending`, or
`applied`. HARD GATE: never implement a plan with `review_count: 0` or
`patch: pending`.

## Governing records

The BDRs/ADRs constraining this plan, one line each on how they constrain
it.

## Scope

What is in, what is explicitly out, and why.

## Steps

One step per file or cohesive change, anchored to concrete file paths.
Each step states behavior, edge cases, defaults, failure and cleanup
semantics, and platform constraints. Write contracts literally (function
signatures, schema fields, wire names, user-facing strings); describe
implementation bodies, do not paste code that will go stale.

## Test plan

Which automated tests are added or updated, which acceptance checks are
manual.

## Risks and notes

Known pitfalls, platform limits, follow-ups.

## Definition of Done

A checklist of verifiable conditions. Every item must be ticked before
`status` becomes `implemented`; an item that cannot be satisfied stays
unchecked and is called out to the developer.
