---
id: BDR-NNN
status: proposed | accepted | superseded | suspended
date: YYYY-MM-DD
supersedes: <id of superseded record, if any>
---

# BDR-NNN: <Decision title>

## Status

proposed | accepted | superseded | suspended. When superseded, name the
superseding record and date.

## Context

The business facts forcing this decision: client requirements, budget,
team capacity, deadlines, regulatory obligations. Write what an engineer
cannot see by reading the code. Link to records this one supersedes and
explain what changed in the world.

## Decision

The commitment itself, as a short list of testable statements. Each bullet
should be checkable against a plan or a diff: "commission rules live in
configuration, never hardcoded", not "keep the system flexible".

## Consequences

What this decision makes easier, what it makes harder, and which technical
decisions it constrains (these become ADRs). Record accepted downsides
explicitly; an undocumented downside reads as an oversight, a documented
one reads as a choice.
