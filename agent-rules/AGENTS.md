# AGENTS.md - Working guide for agents

This file encodes the "Context as an Asset" model: a five-level document
hierarchy with precedence semantics for agents, visibility semantics for
humans, append-only mutation, and an agent-first workflow. Every agent
working in this workspace must follow it.

**Language: this repo is 100% English.** All artifacts - records, plans,
logs, code, comments, commit messages, and file contents - are written in
English, regardless of the language used in conversation.

## 1. Context Hierarchy

Decision documents live in `CONTEXTS/`, ordered by decreasing stability and
decision authority:

| Level | Location | Content | Rate of change |
|-------|----------|---------|----------------|
| 1. BDR | `CONTEXTS/01-bdr/` | Business Decision Records: decisions originating outside engineering (client requirements, budget, team capacity, business deadlines, regulatory obligations) | Very rare |
| 2. ADR | `CONTEXTS/02-adr/` | Architecture Decision Records: technical commitments made because of BDRs (storage, deployment topology, integration style) | Rare |
| 3. Plan | `CONTEXTS/03-implement-plan/` | Implementation Plans: tasks decomposed into scoped steps with acceptance criteria, referencing the constraining BDRs/ADRs | Per task |
| 4. Codebase | project root | The executable artifact produced under a plan | Daily |
| 5. Logs | `CONTEXTS/04-logs/` | Agent Logs: append-only execution records, written only via `event.py` | Daily |

Two properties justify this ordering:

- Rate of change decreases upward: code changes daily, plans per task, ADRs
  rarely, BDRs very rarely. Stable levels anchor volatile ones.
- Authority decreases downward: a BDR is an accountable human commitment,
  while a log is an observation. A decision violated at the top invalidates
  everything below; an inconsistency in a log invalidates nothing.

## 2. Two Axes of the Hierarchy

**Precedence (for agents):** the agent reads all levels. When two levels
disagree, the higher level wins:

- Code contradicts a plan: the plan is authoritative; the code is a bug or a
  stale artifact.
- A plan contradicts an ADR: the plan must be revised, not the ADR silently
  violated.
- An ADR contradicts a BDR: the ADR must be revised (via a new record), not
  the BDR silently violated.
- Agents may propose changes at any level but must NEVER silently violate an
  upper level. If the need for a new BDR/ADR surfaces at any point during
  the work, the agent pauses and asks the human whether to add it; when the
  new decision conflicts with an existing record, the proposal must include
  suspending or superseding that record. Conflicts escalate to the human.

**Visibility (for humans):** stakeholders read the levels appropriate to
their role: a client reads BDRs, a developer reads everything, an auditor
reads logs. Visibility restricts what a human sees; precedence restricts
what an agent may follow. The two axes are independent.

**Write ownership:**

| Level | Who writes |
|-------|------------|
| BDR, ADR | Human-owned. Agents may draft proposals but must ask before adding; new records take effect only on human approval. |
| Plan | Agent-proposed, human-approved. |
| Codebase | Agent-writable within task scope. |
| Logs | Agent-written automatically, only via `CONTEXTS/04-logs/event.py`; never read or edit log files directly. |

## 3. Design Principles

- **Generative direction:** each level is designed from the level above:
  BDRs motivate ADRs, ADRs constrain plans, plans generate code. Never
  reverse-infer intent from code.
- **Bidirectional verification:** after drafting a plan, the agent checks it
  back against BDRs, ADRs, and the codebase, patches divergences, and repeats
  the loop. The review threshold is 1: at least one full verification pass
  is mandatory before the plan may be implemented. A violation caught in a
  plan line is far cheaper than the same violation caught in implemented
  code.
- **Append-only mutation:** no document is edited in place. A changed
  decision produces a new record that supersedes the old one; the old record
  is retained with status `superseded` or `suspended`. History is
  first-class: it must always be possible to ask "what is the decision, what
  was it before, and when did it change".
- **Proportional documentation:** documentation depth scales with task size.
  Small tasks legitimately produce only log entries; only decisions with
  lasting consequences are promoted to plans, ADRs, or BDRs.
- **English only:** every artifact in the repo is written in English -
  BDRs, ADRs, plans, log events (including `--request`/`--reason`), code,
  comments, and commit messages. Conversation language never leaks into
  artifacts.

## 4. Daily Workflow

1. The developer issues a task, referencing relevant BDRs/ADRs.
2. The agent decomposes the task's requirements.
3. Clarification loop: the agent asks the developer about anything the
   document levels cannot resolve. Asking is far cheaper than guessing wrong.
4. If the exchange reveals a missing business or architecture decision, the
   agent may draft a BDR/ADR capturing it, but must ask the developer before
   adding it. The same rule applies at every later phase, including during
   implementation: discovering a needed decision pauses work, the agent
   proposes the record, and waits for approval. If the new decision
   conflicts with an existing BDR/ADR, the proposal must also retire the old
   record (`supersedes` pointing to it, old status flipped to `superseded`
   or `suspended`); the agent must never silently violate or silently
   override it.
5. The agent reviews in precedence order: BDRs, then ADRs, then the relevant
   codebase.
6. The agent drafts an implementation plan in `CONTEXTS/03-implement-plan/`.
7. Verification loop: check the draft plan against BDRs/ADRs/codebase, patch
   divergences, repeat. The plan MUST record `review_count` and `patch` in
   its frontmatter (see section 5). Review threshold: `review_count` >= 1.
8. The developer approves or edits the verified plan.
9. The agent implements within the plan's scope. HARD GATE: the agent MUST
   NEVER implement a plan that has not been reviewed (`review_count: 0`) or
   that still has unpatched divergences (`patch: pending`). Every task
   follows the loop: implement -> commit -> log event via `event.py` (see
   section 6). Non-code work (research, planning) logs with `--no-commit`.
10. When a plan's implementation is finished, the agent closes it out:
    every DoD item is checked off inside the plan document, `status` is set
    to `implemented`, the record change is committed, and a completion event
    is logged. A task is not done until the plan record reflects the outcome.
10. The developer reviews the diff and the log; detected conflicts are
    traced upward to the level that owns the decision.

## 5. Record Format

BDRs and ADRs share one template (a BDR is the ADR convention extended to
the business level):

```markdown
---
id: BDR-001
status: proposed | accepted | superseded | suspended
date: YYYY-MM-DD
supersedes: <id of superseded record, if any>
---

# <ID>: <Decision title>

## Status
...

## Context
...

## Decision
...

## Consequences
...
```

Plans carry their own frontmatter recording the verification state:

```markdown
---
id: PLAN-<NNN>-<slug>
status: draft | reviewed | approved | implemented | superseded
date: YYYY-MM-DD
review_count: <integer>
patch: n/a | not-needed | pending | applied
---
```

Field rules:

- `review_count` is the number of verification passes run on the finished
  plan document. It is `0` when the plan is first written. Checks the
  drafting agent performs while authoring do not count; it increments only
  when a pass re-checking the plan against BDRs, ADRs, and the codebase is
  run at the developer's request (or by another reviewer). Threshold is 1:
  a plan must be reviewed at least once before it may be implemented.
- `status` transitions are shared. The agent always writes plans as `draft`;
  agent verification passes only update `review_count` and `patch`, never
  `status`. Only the developer moves a plan to `reviewed` or `approved`.
  After implementing, the agent moves the plan to `implemented` itself (see
  the DoD rule below) and logs the completion.
- Plans MUST carry an explicit Definition of Done (DoD): a checklist of
  verifiable conditions (gates, tests, acceptance checks) that must all hold
  before the plan may be marked `implemented`. When implementation finishes,
  the agent ticks every satisfied item in the DoD list inside the plan
  document and only then sets `status: implemented`. An item that cannot be
  satisfied stays unchecked and is called out to the developer.
- `patch` records whether a review found divergences: `n/a` (no review has
  run yet; always the value when `review_count` is `0`), `not-needed` (clean
  pass), `pending` (divergences found, not yet patched), `applied`
  (divergences found and patched). `patch` may only carry
  `not-needed`/`pending`/`applied` after at least one verification pass;
  claiming `not-needed` on an unreviewed plan asserts a clean pass that
  never happened.
- HARD GATE: never implement a plan with `review_count: 0` or
  `patch: pending`. Fix the plan first, then re-review.

### Plan body requirements

Plans have no fixed template, but every plan MUST pin down the decisions an
implementer must not improvise. Required content:

- **Governing records:** the BDRs/ADRs constraining the work, each with one
  line on how it constrains this plan.
- **Scope:** what is in, what is explicitly out, and why.
- **Steps:** one step per file or cohesive change, anchored to concrete
  file paths. Each step states behavior, edge cases, defaults, failure and
  cleanup semantics, and platform constraints.
- **Contracts written literally:** anything that is itself a deliverable
  artifact or a cross-boundary agreement appears verbatim in the plan:
  function/type signatures, schema definitions, wire field names and
  casing, file formats, user-facing strings, prompt or template text.
  Implementation bodies are described, not pasted: the codebase is the
  single source of truth for code, and pasted bodies go stale and then
  outrank the real code under the precedence rules.
- **Test plan:** which automated tests are added or updated, and which
  acceptance checks are manual.
- **Risks and notes:** known pitfalls, platform limits, follow-ups.
- **Definition of Done:** the verifiable checklist (see frontmatter rules).

Calibration test: a plan is too vague when a reviewer cannot predict, from
the plan alone, the API shapes, wire formats, and files that will change.
It is too detailed when it re-states code the diff will contain anyway. Pin
down decisions and contracts; describe implementation.

File naming:

- `CONTEXTS/01-bdr/BDR-<NNN>-<slug>.md`
- `CONTEXTS/02-adr/ADR-<NNN>-<slug>.md`
- `CONTEXTS/03-implement-plan/PLAN-<NNN>-<slug>.md`
- `CONTEXTS/04-logs/<YYYY-MM-DD>.md` (created by `event.py`, never by hand)

Append-only rule: changing a decision means creating a new record with
`supersedes` pointing to the old one, and flipping the old record's status
to `superseded`. Never edit the content of an old record.

## 6. Agent Logs (event.py)

Logs are level 5: lowest precedence, yet written most often. Each working
day produces one `<YYYY-MM-DD>.md` file in `CONTEXTS/04-logs/`.

Each event records: title, scope, type (`Feature`/`Fix`/`Refactor`/`Chore`/
`Docs`), **user request** (what the user asked), **reason** (why the change,
which decisions were made), description of what was done, touched files, and
free-form notes (risks, follow-ups). Events are commit-linked: logged after
the commit so the script binds the HEAD hash.

Agents NEVER read or write log files directly. All writes and queries go
through the script (one CLI call instead of reading a large file):

```bash
cd CONTEXTS/04-logs

# Log an event (auto-detect repo + capture HEAD commit)
python3 event.py log \
    --title "Title" --scope "src/licenses" --type Feature \
    --desc "Description" --files "file1.ts\nfile2.ts" --notes "notes" \
    --request "what the user asked" --reason "why the change"

# Log an event + auto-pull files from the commit diff
python3 event.py log --from-commit \
    --title "..." --scope "..." --type Feature --desc "..."

# Log an event with no commit (research, planning, meeting notes)
python3 event.py log --no-commit \
    --title "..." --scope "..." --type Docs --desc "..."

# Search
python3 event.py search "keyword" --type Fix --from 2026-11-01 --to 2026-11-05
python3 event.py search --commit 99d8580        # by commit hash
python3 event.py search --no-commit             # unlinked events
python3 event.py search --compact --limit 20    # one line per event

# Commit-link management
python3 event.py git unlinked                   # events with no commit
python3 event.py git verify                     # event files vs commit diff
python3 event.py git link --event "2026-11-05 09:30" --commit abc1234
python3 event.py git auto-link                  # link old events by files + date

# Timeline for one day: merged git log + events
python3 event.py timeline --date 2026-11-05

# Revert the N most recent events: ALWAYS dry-run first
python3 event.py revert ~2 --dry-run
python3 event.py revert ~2 --yes
```

### When to log

Agents MUST log an event for every task that changes the codebase. This is
what makes the log a searchable project history instead of a changelog:

- Add new features -> `Feature`
- Fix bugs -> `Fix`
- Refactor code (no behavior change) -> `Refactor`
- Perform maintenance tasks -> `Chore`
- Update documentation -> `Docs`
- Make any other significant change to the codebase
- Research, planning, or discussion outcomes worth keeping -> log with
  `--no-commit` (no commit to link, but still log)

Do NOT log events for changes inside `CONTEXTS/04-logs/` itself - that is
tooling plus the log store; a normal commit there is enough.

### Order: commit first, then log

**ALWAYS commit before logging.** The event binds to HEAD, so logging with
a dirty tree links the event to the OLD commit, not the one containing the
changes. Correct order:

1. Commit the code changes.
2. Log the event (the script captures HEAD automatically).
3. Task produced no code change? Use `--no-commit`, but still log.
4. Logged too early by mistake? Repair the link with
   `python3 event.py git link --event "YYYY-MM-DD HH:mm" --commit <hash>`.

A task is not done until its event exists in `CONTEXTS/04-logs/`.

### Field rules

- `--request` captures what the user asked for; `--reason` captures why the
  change was made and which decisions were taken; `--notes` captures risks
  and follow-ups. Always fill request and reason - they are what make the
  log an audit trail instead of a changelog.
- `[REVERT] ~N` requests: always run `revert ~N --dry-run` first, present
  the plan, wait for confirmation, then `revert ~N --yes`. The script picks
  `git reset` (unpushed + consecutive at HEAD) or `git revert` (pushed),
  marks old events with strikethrough + a REVERTED note, and logs a new
  `Fix` event.

## 7. When NOT to Maintain the Full Hierarchy

Document infrastructure has a fixed cost. For throwaway prototypes, solo
scripts, or tasks small enough to fit in one prompt, a log entry is enough.
The hierarchy pays off when work must outlive a session, a repo, or an agent
tool.
