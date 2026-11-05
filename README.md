# context-as-an-asset

A starter kit for the **Context as an Asset** workflow: a five-level
document hierarchy (BDR -> ADR -> Plan -> Codebase -> Logs) that keeps
coding agents aligned with human decisions instead of rediscovering them
every session.

The kit contains everything needed to adopt the workflow in a repository:

- [`agent-rules/AGENTS.md`](./agent-rules/AGENTS.md): the full rulebook.
  Drop it into your repo root; AGENTS.md-compliant agents pick it up
  automatically. A condensed variant for Claude Code is in
  [`agent-rules/CLAUDE.md`](./agent-rules/CLAUDE.md).
- [`tools/event.py`](./tools/event.py): the agent event log. Self-contained
  Python 3, stdlib only. See [`tools/README.md`](./tools/README.md).
- [`docs/templates/`](./docs/templates/): blank record templates
  (BDR, ADR, PLAN) with per-section guidance.
- [`docs/examples/`](./docs/examples/): real records from a live
  deployment, plus two sanitized reproductions of client records.
- [`docs/hierarchy.md`](./docs/hierarchy.md): the model itself - levels,
  precedence vs. visibility, write ownership, design principles.
- [`metrics/`](./metrics/): schema for the companion metrics log.

## Quickstart

```bash
# In your own repository:
mkdir -p CONTEXTS/01-bdr CONTEXTS/02-adr CONTEXTS/03-implement-plan CONTEXTS/04-logs
cp agent-rules/AGENTS.md ./AGENTS.md          # or CLAUDE.md
cp tools/event.py CONTEXTS/04-logs/event.py
cp docs/templates/BDR.md  CONTEXTS/01-bdr/BDR-001-<slug>.md
```

Then work the loop: task -> clarify -> draft plan -> verification pass
(`review_count`) -> human approval -> implement -> commit -> log.

## Live deployment

The [fluent](https://github.com/satoshiman/fluent) repository is a working
deployment of this workflow: a local real-time transcription and
translation app built entirely under the hierarchy in a single working
day. Its `CONTEXTS/` tree carries six BDRs (two superseded), seven ADRs,
eleven implementation plans, and a commit-linked event log; the git
history interleaves `log:` commits with code commits.

## Citing

A preprint describing the model is in preparation. Until then, cite this
repository and the fluent deployment directly.

## License

MIT, including the document templates and examples. If you prefer a
documentation-specific license for your own records, CC-BY-4.0 is a
reasonable choice; state it in your repo's README.
