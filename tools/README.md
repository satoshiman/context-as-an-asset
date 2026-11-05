# event.py - Agent event log

`event.py` writes and queries the level-5 Agent Log: one append-only
Markdown file per working day, stored next to the script. It is
self-contained Python 3 (stdlib only, no dependencies).

Place it at `CONTEXTS/04-logs/event.py` in your repo. The project root is
the parent of `CONTEXTS/`; if the project root is a git repo, each event
auto-captures the HEAD commit so the log doubles as a revert index.

Agents never read or edit log files directly: every write and query goes
through the CLI, which keeps logging cost near zero (one call instead of
parsing a large file).

## Usage

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

# Log an event with no commit (research, planning)
python3 event.py log --no-commit \
    --title "..." --scope "..." --type Docs --desc "..."

# Search
python3 event.py search "keyword" --type Fix --from 2026-11-01 --to 2026-11-05
python3 event.py search --commit 99d8580
python3 event.py search --compact --limit 20

# Commit-link management
python3 event.py git unlinked
python3 event.py git verify
python3 event.py git auto-link

# Timeline for one day: merged git log + events
python3 event.py timeline --date 2026-11-05

# Revert the N most recent events: ALWAYS dry-run first
python3 event.py revert ~2 --dry-run
python3 event.py revert ~2 --yes
```

## Field rules

- `--request` captures what the user asked; `--reason` captures why the
  change was made and which decisions were taken. Always fill both: they
  are what make the log an audit trail instead of a changelog.
- Event types: `Feature`, `Fix`, `Refactor`, `Chore`, `Docs`.
- Commit first, then log. Logging with a dirty tree binds the event to
  the old commit; repair with `git link --event "YYYY-MM-DD HH:mm"
  --commit <hash>`.
