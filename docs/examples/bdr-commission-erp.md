---
id: BDR-EX1
status: accepted
date: YYYY-MM-DD
note: Sanitized reproduction of a client record. Names, dates, and domain
  details are changed; the structure and decision logic are preserved.
---

# BDR-EX1: Sales commission policy for the ERP system

## Status

accepted (sanitized example)

## Context

The client operates an ERP with a direct sales channel. Commission terms
are set by business policy, not by engineering: per direct sale, 10% goes
to the salesperson, 5% to their manager, and 7% to marketing. The policy
is negotiated at the business level and may be revised when contracts or
campaigns change.

## Decision

- Commission is owed per direct sale as follows: 10% to the direct
  salesperson, 5% to their manager, 7% to marketing.
- The percentages are business facts. They must be revisable by a new
  BDR without an architecture change.

## Consequences

- A derived ADR mandates that commission rules live in configuration,
  never hardcoded: a business ratio is exactly the kind of fact a future
  BDR will supersede.
- When the policy changes, the agent edits configuration under a new
  plan; the architecture is untouched. The hierarchy is what tells the
  agent where the invariant lives.
