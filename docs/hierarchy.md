# The Context Hierarchy

The model organizes everything an agent needs into five levels, ordered by
decreasing stability and decision authority:

| Level | Content | Rate of change |
|-------|---------|----------------|
| 1. BDR | Business Decision Records: decisions originating outside engineering (client requirements, budget, team capacity, deadlines, regulatory obligations) | Very rare |
| 2. ADR | Architecture Decision Records: technical commitments made because of BDRs | Rare |
| 3. Plan | Implementation Plans: tasks decomposed into scoped steps with acceptance criteria | Per task |
| 4. Codebase | The executable artifact produced under a plan | Daily |
| 5. Logs | Agent Logs: append-only execution records | Daily |

Two properties justify the ordering:

- **Rate of change decreases upward.** Code changes daily, plans per task,
  ADRs rarely, BDRs very rarely. Stable levels anchor volatile ones.
- **Authority decreases downward.** A BDR is an accountable human
  commitment; a log is an observation. A decision violated at the top
  invalidates everything below; an inconsistency in a log invalidates
  nothing.

## Two axes

**Precedence (for agents).** The agent reads all levels. When two levels
disagree, the higher level wins: code contradicting a plan is a bug, a
plan contradicting an ADR must be revised, an ADR contradicting a BDR must
be revised (via a new record). Agents may propose changes at any level but
must never silently violate an upper level; conflicts escalate to the
human.

**Visibility (for humans).** Stakeholders read the levels appropriate to
their role: a client reads BDRs, a developer reads everything, an auditor
reads logs. Visibility restricts what a human sees; precedence restricts
what an agent may follow. The axes are independent.

## Write ownership

| Level | Who writes |
|-------|------------|
| BDR, ADR | Human-owned. Agents may draft proposals but must ask before adding; records take effect on human approval. |
| Plan | Agent-proposed, human-approved. |
| Codebase | Agent-writable within task scope. |
| Logs | Agent-written automatically, only via `event.py`. |

## Design principles

- **Generative direction.** Each level is designed from the level above:
  BDRs motivate ADRs, ADRs constrain plans, plans generate code. Never
  reverse-infer intent from code.
- **Bidirectional verification.** A draft plan is checked back against
  BDRs, ADRs, and the codebase at least once (`review_count >= 1`) before
  implementation. A violation caught in a plan line is far cheaper than
  the same violation in code.
- **Append-only mutation.** No document is edited in place. A changed
  decision produces a new record that supersedes the old one; the old
  record is retained with status `superseded` or `suspended`. History is
  first-class.
- **Proportional documentation.** Documentation depth scales with task
  size. Small tasks legitimately produce only log entries; only decisions
  with lasting consequences are promoted to plans, ADRs, or BDRs.

## When not to use it

Document infrastructure has a fixed cost. For throwaway prototypes, solo
scripts, or tasks that fit in one prompt, a log entry is enough. The
hierarchy pays off when work must outlive a session, a repo, or an agent
tool.
