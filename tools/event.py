#!/usr/bin/env python3
"""Event log manager for agents (write + search + git integration).

Context: this script lives in <project>/CONTEXTS/04-logs/ - level 5 (Agent
Logs) of the workspace document hierarchy. Daily log files (YYYY-MM-DD.md)
are written directly into the folder containing this script. The project
root is the parent of the CONTEXTS/ folder; if the project root is a git
repo, each event auto-captures the HEAD commit, otherwise events are
recorded without a commit.

Subcommands
-----------
    log      Append an event to the daily file (YYYY-MM-DD.md), auto-capture commit.
    search   Search events in the log (04-logs/).
    git      Manage commit links (unlinked, verify, link, auto-link).
    timeline Merge git log + events for one day.
    revert   Revert the N most recent events (git reset/revert + mark + log).

Usage
-----
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

    # Search by commit hash
    python3 event.py search --commit 99d8580

    # Search events with no commit
    python3 event.py search --no-commit

    # Verify event files match the commit diff
    python3 event.py git verify

    # Auto-link old events to commits
    python3 event.py git auto-link

    # Timeline for one day (git commits + events)
    python3 event.py timeline --date 2026-09-10
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

# ============================================================================
# Constants
# ============================================================================
# Shared definitions for the writer (log) and readers (search/git/timeline).

# Context: event.py lives in <project>/CONTEXTS/04-logs/. Daily log files are
# written directly into the folder containing the script. Project root =
# parent of the CONTEXTS/ folder.
SCRIPT_DIR = Path(__file__).resolve().parent
EVENTS_DIR = SCRIPT_DIR
DOCS_ROOT = SCRIPT_DIR.parent
PROJECT_ROOT = DOCS_ROOT.parent

# Map repo name -> root path. This context has a single repo: the project
# root. If it is a git repo, events auto-link to the HEAD commit.
REPO_ROOTS: dict[str, Path] = {PROJECT_ROOT.name: PROJECT_ROOT}

FALLBACK_REPO = PROJECT_ROOT.name

VALID_TYPES = {"Feature", "Fix", "Refactor", "Chore", "Docs"}

# Event header regex: "## HH:mm - Title..."
EVENT_HEADER_RE = re.compile(r"^##\s+(\d{2}:\d{2})\s+-\s+(.+?)\s*$", re.MULTILINE)

# Metadata line regex:
#   **Scope:** ... | **Type:** ... | **Commit:** <hash> @ <repo>
# The Commit part is optional (older events may not have it).
META_RE = re.compile(
    r"\*\*Scope:\*\*\s*(?P<scope>.*?)\s*\|\s*\*\*Type:\*\*\s*(?P<type>\w+)"
    r"(?:\s*\|\s*\*\*Commit:\*\*\s*(?P<commit>[0-9a-f]+)\s*@\s*(?P<repo>\S+))?\s*$",
    re.MULTILINE,
)

# Sub-section names inside one event block (in template order).
SUB_SECTIONS = [
    "Scope",
    "Type",
    "Commit",
    "User request",
    "Reason",
    "Description",
    "Files changed",
    "Notes",
]


def slugify(text: str) -> str:
    """GitHub-style markdown anchor slug: lowercase, strip punctuation, space -> '-'."""
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "-", text)
    return text


def _now() -> datetime:
    return datetime.now()


# ============================================================================
# Git utilities
# ============================================================================


def _repo_path(repo: str) -> Path:
    """Resolve a repo name or path to a Path."""
    return REPO_ROOTS.get(repo, Path(repo))


def git_cmd(repo: str, *args: str) -> str:
    """Run a git command in a repo, return stripped stdout."""
    result = subprocess.run(
        ["git", "-C", str(_repo_path(repo)), *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def git_cmd_lines(repo: str, *args: str) -> list[str]:
    """Run a git command, return a list of non-empty lines."""
    out = git_cmd(repo, *args)
    return [line for line in out.splitlines() if line.strip()]


def is_git_repo(repo: str) -> bool:
    """Check whether a repo name is a valid git repo."""
    path = _repo_path(repo)
    if not path.exists():
        return False
    return bool(git_cmd(repo, "rev-parse", "--show-toplevel"))


def is_dirty(repo: str) -> bool:
    """Check whether the working tree has uncommitted changes."""
    return bool(git_cmd(repo, "status", "--porcelain"))


def get_head_commit(repo: str) -> dict[str, str]:
    """Get HEAD commit info: hash, message, author, date."""
    return _get_commit_info(repo, "HEAD")


def get_commit_info(repo: str, hash_: str) -> dict[str, str]:
    """Get commit info for a specific hash."""
    return _get_commit_info(repo, hash_)


def _get_commit_info(repo: str, ref: str) -> dict[str, str]:
    fmt = "%H%n%h%n%s%n%an <%ae>%n%ci"
    out = git_cmd(repo, "log", "-1", f"--pretty=format:{fmt}", ref)
    if not out:
        return {}
    lines = out.splitlines()
    return {
        "full_hash": lines[0] if len(lines) > 0 else "",
        "hash": lines[1] if len(lines) > 1 else "",
        "message": lines[2] if len(lines) > 2 else "",
        "author": lines[3] if len(lines) > 3 else "",
        "date": lines[4] if len(lines) > 4 else "",
    }


def get_commit_files(repo: str, hash_: str) -> list[str]:
    """Get the list of files changed in a commit."""
    return git_cmd_lines(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", hash_)


def normalize_event_files(files: str) -> tuple[str, list[str]]:
    """Normalize the event file list to paths relative to the repo root.

    Events may record paths as `<repo>/sub/file`. Strip the `<repo>/`
    prefix and return (repo_hint, files_normalized).
    """
    repo_hint = ""
    out: list[str] = []
    for line in files.replace("\\n", "\n").splitlines():
        line = line.strip()
        if not line or line == "None":
            continue
        for name in REPO_ROOTS:
            if line.startswith(f"{name}/"):
                line = line[len(name) + 1 :]
                if not repo_hint:
                    repo_hint = name
                break
        if line:
            out.append(line)
    return repo_hint, out


def detect_repo(file_paths: str, scope: str) -> str:
    """Detect the repo from file paths and scope. Fallback: FALLBACK_REPO.

    Logic:
    1. Check each file path: if (repo_root / path) exists -> that repo.
       For deleted files: check whether the parent directory exists.
    2. Check whether the scope contains a repo name.
    3. Fallback: FALLBACK_REPO (project root).
    """
    # 1. Check file paths
    for line in file_paths.replace("\\n", "\n").splitlines():
        line = line.strip()
        if not line:
            continue
        for name, root in REPO_ROOTS.items():
            full = root / line
            if full.exists():
                return name
            # Deleted file: the parent dir usually still exists
            parent = full.parent
            if parent.exists() and parent != root and parent.is_relative_to(root):
                return name

    # 2. Check scope
    for name in REPO_ROOTS:
        if name in scope:
            return name

    # 3. Fallback
    return FALLBACK_REPO


def verify_files_against_commit(
    repo: str, commit_hash: str, event_files: list[str],
) -> tuple[list[str], list[str], list[str]]:
    """Compare event files with commit files.

    Returns: (matched, missing_in_commit, extra_in_commit)
    """
    commit_files = set(get_commit_files(repo, commit_hash))
    event_set = set(f.strip() for f in event_files if f.strip())

    matched = sorted(event_set & commit_files)
    missing = sorted(event_set - commit_files)
    extra = sorted(commit_files - event_set)

    return matched, missing, extra


def is_commit_pushed(repo: str, hash_: str) -> bool:
    """Check whether a commit has been pushed to a remote."""
    return bool(git_cmd(repo, "branch", "-r", "--contains", hash_))


def get_head_chain(repo: str, n: int) -> list[str]:
    """Get the N most recent commit hashes from HEAD (newest first)."""
    return git_cmd_lines(repo, "log", f"-{n}", "--pretty=format:%h")


def are_consecutive_at_head(repo: str, hashes: list[str]) -> bool:
    """Check whether hashes are the N consecutive commits at HEAD.

    hashes: newest-first order (reverse of git log).
    Returns True if hashes match exactly HEAD, HEAD~1, ..., HEAD~(N-1).
    """
    if not hashes:
        return False
    head_chain = get_head_chain(repo, len(hashes))
    return head_chain == hashes


# ============================================================================
# LOG command - append an event to the daily file
# ============================================================================


def build_event_section(
    time_str: str,
    title: str,
    scope: str,
    type_: str,
    desc: str,
    files: str,
    notes: str,
    request: str = "",
    reason: str = "",
    commit_info: dict[str, str] | None = None,
    repo: str = "",
) -> str:
    files_block = files.strip() if files and files.strip() else "None"
    notes_block = notes.strip() if notes and notes.strip() else "None"
    request_block = request.strip() if request and request.strip() else "None"
    reason_block = reason.strip() if reason and reason.strip() else "None"

    if commit_info and commit_info.get("hash"):
        meta_commit = f" | **Commit:** {commit_info['hash']} @ {repo}"
        commit_section = f"""
## Commit
- **Hash:** {commit_info['hash']}
- **Repo:** {repo}
- **Message:** {commit_info.get('message', '')}
- **Author:** {commit_info.get('author', '')}
- **Date:** {commit_info.get('date', '')}
"""
    else:
        meta_commit = ""
        commit_section = ""

    section = f"""## {time_str} - {title}

**Scope:** {scope} | **Type:** {type_}{meta_commit}

## Scope
{scope}

## Type
{type_}
{commit_section}
## User request
{request_block}

## Reason
{reason_block}

## Description
{desc}

## Files changed
{files_block}

## Notes
{notes_block}

---
"""
    return section


def build_toc_entry(time_str: str, title: str) -> str:
    slug = slugify(f"{time_str} - {title}")
    return f"- [{time_str} - {title}](#{slug})"


def create_new_day_file(
    path: Path, date_str: str, toc_entry: str, event_section: str,
) -> None:
    content = f"""---
date: "{date_str}"
events_count: 1
---

# Events on {date_str}

Total events: **1**

## Table of contents

{toc_entry}

---

{event_section}
"""
    path.write_text(content, encoding="utf-8")


def append_to_day_file(path: Path, toc_entry: str, event_section: str) -> None:
    text = path.read_text(encoding="utf-8")

    # 1. Bump events_count in the front matter
    m = re.search(r"^events_count:\s*(\d+)\s*$", text, flags=re.MULTILINE)
    if not m:
        raise RuntimeError(f"'events_count' not found in the front matter of {path}")
    old_count = int(m.group(1))
    new_count = old_count + 1
    text = re.sub(
        r"^(events_count:\s*)\d+\s*$",
        rf"\g<1>{new_count}",
        text,
        count=1,
        flags=re.MULTILINE,
    )

    # 2. Update the "Total events: **N**" line
    text = re.sub(
        r"(Total events:\s*\*\*)\d+(\*\*)",
        rf"\g<1>{new_count}\g<2>",
        text,
        count=1,
    )

    # 3. Add an entry to the table of contents
    toc_match = re.search(
        r"(## Table of contents\s*\n(?:- \[.*?\]\(#.*?\)\n)+)",
        text,
    )
    if not toc_match:
        raise RuntimeError(f"'## Table of contents' section not found in {path}")
    toc_block = toc_match.group(1)
    new_toc_block = toc_block + toc_entry + "\n"
    text = text[: toc_match.start()] + new_toc_block + text[toc_match.end():]

    # 4. Append the new event section at the end of the file
    if not text.endswith("\n"):
        text += "\n"
    text += event_section

    path.write_text(text, encoding="utf-8")


def cmd_log(args: argparse.Namespace) -> int:
    now_dt = _now()
    date_str = args.date or now_dt.strftime("%Y-%m-%d")
    time_str = args.time or now_dt.strftime("%H:%M")

    files = args.files.replace("\\n", "\n")

    commit_info: dict[str, str] | None = None
    repo = ""

    if not args.no_commit:
        # Detect repo
        if args.repo:
            repo = args.repo
        else:
            repo = detect_repo(files, args.scope)

        if not is_git_repo(repo):
            print(
                f"⚠️  Repo '{repo}' is not a git repo. "
                f"Event will be recorded without a commit.",
                file=sys.stderr,
            )
        else:
            # Commit-first workflow: warn if dirty
            if is_dirty(repo):
                head = get_head_commit(repo)
                head_hash = head.get("hash", "?") if head else "?"
                print(
                    f"⚠️  Working tree of {repo} has uncommitted changes.\n"
                    f"    Event will link to HEAD ({head_hash}).\n"
                    f"    Consider committing before logging the event.",
                    file=sys.stderr,
                )

            # Get commit info
            if args.commit:
                commit_info = get_commit_info(repo, args.commit)
                if not commit_info:
                    print(
                        f"❌ Commit {args.commit} not found in {repo}",
                        file=sys.stderr,
                    )
                    return 1
            else:
                commit_info = get_head_commit(repo)
                if not commit_info:
                    print(
                        f"⚠️  No commits in {repo}. "
                        f"Event will be recorded without a commit.",
                        file=sys.stderr,
                    )

            # Auto-pull files from the commit diff
            if args.from_commit and commit_info:
                commit_files = get_commit_files(repo, commit_info["hash"])
                if commit_files:
                    files = "\n".join(commit_files)

    event_section = build_event_section(
        time_str=time_str,
        title=args.title,
        scope=args.scope,
        type_=args.type,
        desc=args.desc,
        files=files,
        notes=args.notes,
        request=args.request,
        reason=args.reason,
        commit_info=commit_info,
        repo=repo,
    )
    toc_entry = build_toc_entry(time_str, args.title)

    EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    day_file = EVENTS_DIR / f"{date_str}.md"

    if day_file.exists():
        append_to_day_file(day_file, toc_entry, event_section)
        action = "Appended"
    else:
        create_new_day_file(day_file, date_str, toc_entry, event_section)
        action = "Created"

    commit_tag = (
        f" [{commit_info['hash']} @ {repo}]"
        if commit_info
        else " [no commit]"
    )
    print(f"{action} event '{time_str} - {args.title}'{commit_tag} -> {day_file}")
    return 0


def add_log_subparser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "log",
        help="Append an event to the daily file (YYYY-MM-DD.md).",
        description="Append an event to the daily file (YYYY-MM-DD.md). "
        "Auto-detects the git repo and captures the HEAD commit hash. "
        "If the day file does not exist, it is created with front matter, "
        "a header, and a table of contents. If it exists: bumps "
        "events_count, adds a TOC entry, appends the event section.",
    )
    p.add_argument("--title", required=True, help="Short title")
    p.add_argument("--scope", required=True, help="Affected package/app")
    p.add_argument(
        "--type",
        required=True,
        choices=sorted(VALID_TYPES),
        help="Event type",
    )
    p.add_argument("--desc", required=True, help="Short description of the work done")
    p.add_argument(
        "--request",
        default="",
        help="What the user asked for (verbatim or summarized)",
    )
    p.add_argument(
        "--reason",
        default="",
        help="Why the change was made, which decisions were taken",
    )
    p.add_argument(
        "--files",
        default="",
        help="List of changed files, one per line (use \\n)",
    )
    p.add_argument("--notes", default="", help="Notes, risks, follow-ups")
    p.add_argument(
        "--time",
        default="",
        help="Time HH:mm (default: current time)",
    )
    p.add_argument(
        "--date",
        default="",
        help="Date YYYY-MM-DD (default: today)",
    )
    # Git flags
    p.add_argument(
        "--commit",
        default="",
        help="Specific commit hash (default: auto-detect HEAD)",
    )
    p.add_argument(
        "--repo",
        default="",
        help="Repo name or path (default: auto-detect from --files/--scope)",
    )
    p.add_argument(
        "--from-commit",
        action="store_true",
        help="Auto-pull --files from the commit's git diff",
    )
    p.add_argument(
        "--no-commit",
        action="store_true",
        help="Do not link a commit (research, planning, meeting notes)",
    )
    p.set_defaults(func=cmd_log)


# ============================================================================
# Event parsing (shared by search + git + timeline)
# ============================================================================


@dataclass
class Event:
    date: str  # YYYY-MM-DD
    time: str  # HH:mm
    title: str
    scope: str
    type: str
    commit_hash: str = ""
    commit_repo: str = ""
    commit_message: str = ""
    commit_author: str = ""
    commit_date: str = ""
    scope_body: str = ""
    request: str = ""
    reason: str = ""
    description: str = ""
    files: str = ""
    notes: str = ""
    raw_section: str = ""

    @property
    def sort_key(self) -> tuple[str, str]:
        return (self.date, self.time)

    @property
    def has_commit(self) -> bool:
        return bool(self.commit_hash)


def _extract_subsection(block: str, name: str) -> str:
    """Get the text content of a `## <name>` sub-section in one event block."""
    pattern = re.compile(
        rf"^##\s+{re.escape(name)}\s*\n(.*?)(?=^##\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(block)
    return m.group(1).strip() if m else ""


def _extract_commit_info(block: str) -> dict[str, str]:
    """Extract commit info from the ## Commit section."""
    section = _extract_subsection(block, "Commit")
    if not section:
        return {}
    info: dict[str, str] = {}
    for line in section.splitlines():
        m = re.match(r"-\s*\*\*(\w+):\*\*\s*(.*)", line)
        if m:
            info[m.group(1).lower()] = m.group(2).strip()
    return info


def parse_events_from_file(path: Path) -> list[Event]:
    """Parse all events in one day file."""
    text = path.read_text(encoding="utf-8")
    date_str = path.stem

    headers = list(EVENT_HEADER_RE.finditer(text))
    if not headers:
        return []

    events: list[Event] = []
    for i, m in enumerate(headers):
        start = m.start()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        block = text[start:end].rstrip()
        block_clean = re.sub(r"\n---\s*$", "", block)

        time_str = m.group(1)
        title = m.group(2).strip()

        meta = META_RE.search(block_clean)
        scope = meta.group("scope").strip() if meta else ""
        type_ = meta.group("type").strip() if meta else ""
        commit_hash = meta.group("commit") if meta and meta.group("commit") else ""
        commit_repo = meta.group("repo") if meta and meta.group("repo") else ""

        # Extract details from the ## Commit section
        commit_detail = _extract_commit_info(block_clean)
        if commit_detail:
            commit_hash = commit_detail.get("hash", commit_hash)
            commit_repo = commit_detail.get("repo", commit_repo)
            commit_message = commit_detail.get("message", "")
            commit_author = commit_detail.get("author", "")
            commit_date = commit_detail.get("date", "")
        else:
            commit_message = ""
            commit_author = ""
            commit_date = ""

        scope_body = _extract_subsection(block_clean, "Scope")
        request = _extract_subsection(block_clean, "User request")
        reason = _extract_subsection(block_clean, "Reason")
        description = _extract_subsection(block_clean, "Description")
        files = _extract_subsection(block_clean, "Files changed")
        notes = _extract_subsection(block_clean, "Notes")

        events.append(
            Event(
                date=date_str,
                time=time_str,
                title=title,
                scope=scope,
                type=type_,
                commit_hash=commit_hash,
                commit_repo=commit_repo,
                commit_message=commit_message,
                commit_author=commit_author,
                commit_date=commit_date,
                scope_body=scope_body,
                request=request,
                reason=reason,
                description=description,
                files=files,
                notes=notes,
                raw_section=block_clean,
            )
        )
    return events


def load_all_events() -> list[Event]:
    """Load all events from every *.md file in EVENTS_DIR."""
    if not EVENTS_DIR.exists():
        return []
    files = sorted(EVENTS_DIR.glob("*.md"))
    events: list[Event] = []
    for f in files:
        events.extend(parse_events_from_file(f))
    return events


# ============================================================================
# SEARCH command - search events in the event log
# ============================================================================


def _split_multi(values: Iterable[str]) -> list[str]:
    """Split repeated flags or comma-separated values into a clean list."""
    out: list[str] = []
    for v in values:
        for part in v.split(","):
            part = part.strip()
            if part:
                out.append(part)
    return out


def filter_events(
    events: list[Event],
    keyword: str | None,
    types: list[str],
    scope: str | None,
    file_substr: str | None,
    date_from: str | None,
    date_to: str | None,
    date_single: str | None,
    commit: str | None,
    repo: str | None,
    no_commit: bool,
) -> list[Event]:
    """Apply all filters (AND). Return matching events."""
    kw = keyword.lower() if keyword else None
    sc = scope.lower() if scope else None
    fl = file_substr.lower() if file_substr else None
    types_lower = {t.lower() for t in types}
    commit_lower = commit.lower() if commit else None
    repo_lower = repo.lower() if repo else None

    d_from = date_from or date_single
    d_to = date_to or date_single

    result: list[Event] = []
    for ev in events:
        # Date filter
        if d_from and ev.date < d_from:
            continue
        if d_to and ev.date > d_to:
            continue

        # Type filter
        if types_lower and ev.type.lower() not in types_lower:
            continue

        # Scope filter
        if sc and sc not in ev.scope.lower() and sc not in ev.scope_body.lower():
            continue

        # File filter
        if fl and fl not in ev.files.lower():
            continue

        # Commit filter
        if commit_lower and commit_lower not in ev.commit_hash.lower():
            continue

        # Repo filter
        if repo_lower and repo_lower not in ev.commit_repo.lower():
            continue

        # No-commit filter
        if no_commit and ev.has_commit:
            continue

        # Keyword filter
        if kw:
            haystack = "\n".join(
                [
                    ev.title, ev.description, ev.files, ev.notes, ev.scope,
                    ev.scope_body, ev.request, ev.reason,
                ]
            ).lower()
            if kw not in haystack:
                continue

        result.append(ev)
    return result


def render_compact(ev: Event) -> str:
    """Compact line: date + time + type + scope + commit + title."""
    type_tag = f"[{ev.type}]" if ev.type else "[?]"
    if ev.commit_hash:
        commit_tag = f"{ev.commit_hash}@{ev.commit_repo}"
    else:
        commit_tag = "(unlinked)"
    return f"{ev.date} {ev.time}  {type_tag:<10} {ev.scope:<30} {commit_tag:<20} {ev.title}"


def render_full(ev: Event) -> str:
    """Full detail: print the original markdown section + a date header."""
    header = f"### {ev.date} {ev.time} - {ev.title}"
    body = ev.raw_section
    body = re.sub(
        r"^##\s+\d{2}:\d{2}\s+-\s+.*?$",
        header,
        body,
        count=1,
        flags=re.MULTILINE,
    )
    return body


def cmd_search(args: argparse.Namespace) -> int:
    types = _split_multi(args.type)
    for t in types:
        if t not in VALID_TYPES:
            print(
                f"❌ Invalid type: '{t}'. "
                f"Allowed: {', '.join(sorted(VALID_TYPES))}",
                file=sys.stderr,
            )
            return 2

    for d in (args.date_from, args.date_to, args.date_single):
        if d and not re.match(r"^\d{4}-\d{2}-\d{2}$", d):
            print(
                f"❌ Invalid date: '{d}'. Format: YYYY-MM-DD",
                file=sys.stderr,
            )
            return 2

    events = load_all_events()
    if not events:
        print(f"⚠️  No events found in {EVENTS_DIR}.", file=sys.stderr)
        return 1

    filtered = filter_events(
        events,
        keyword=args.keyword,
        types=types,
        scope=args.scope,
        file_substr=args.file,
        date_from=args.date_from,
        date_to=args.date_to,
        date_single=args.date_single,
        commit=args.commit,
        repo=args.repo,
        no_commit=args.no_commit,
    )

    filtered.sort(key=lambda e: e.sort_key, reverse=not args.oldest)

    if args.limit and args.limit > 0:
        filtered = filtered[: args.limit]

    if not filtered:
        print("No events match the filters.")
        return 0

    print(f"Found {len(filtered)} event(s):\n")
    if args.compact:
        for ev in filtered:
            print(render_compact(ev))
    else:
        blocks = [render_full(ev) for ev in filtered]
        print("\n\n---\n\n".join(blocks))
        print("\n---\n")

    return 0


def add_search_subparser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "search",
        help="Search events in the event log.",
        description="Search events in the event log. "
        "Supports filters by commit hash, repo, and unlinked events, plus "
        "full-text keyword, type, scope, file path, and date range. "
        "Default output is full detail, newest first.",
        usage='python3 event.py search [filters] "keyword"',
    )
    p.add_argument(
        "keyword",
        nargs="?",
        default=None,
        help="Full-text keyword (matches title/description/files/notes/scope).",
    )
    p.add_argument(
        "--type",
        action="append",
        default=[],
        help="Filter by event type. Repeatable or comma-separated.",
    )
    p.add_argument(
        "--scope",
        default=None,
        help="Substring filter on scope.",
    )
    p.add_argument(
        "--file",
        default=None,
        help="Substring filter on the 'Files changed' field.",
    )
    p.add_argument(
        "--from",
        dest="date_from",
        default=None,
        help="Start date (YYYY-MM-DD, inclusive).",
    )
    p.add_argument(
        "--to",
        dest="date_to",
        default=None,
        help="End date (YYYY-MM-DD, inclusive).",
    )
    p.add_argument(
        "--date",
        dest="date_single",
        default=None,
        help="Filter a single day (YYYY-MM-DD).",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max number of results (0 = unlimited).",
    )
    p.add_argument(
        "--compact",
        action="store_true",
        help="Compact output (one line per event) instead of full detail.",
    )
    p.add_argument(
        "--oldest",
        action="store_true",
        help="Oldest first (default: newest first).",
    )
    # Git filters
    p.add_argument(
        "--commit",
        default=None,
        help="Filter by commit hash (substring match).",
    )
    p.add_argument(
        "--repo",
        default=None,
        help="Filter by repo name (substring match).",
    )
    p.add_argument(
        "--no-commit",
        action="store_true",
        help="Only find events without a commit (unlinked).",
    )
    p.set_defaults(func=cmd_search)


# ============================================================================
# GIT command - manage commit links
# ============================================================================


def add_commit_to_event(
    file_path: Path,
    time_str: str,
    commit_info: dict[str, str],
    repo: str,
) -> bool:
    """Add/update commit info in one event section. Returns True if updated."""
    text = file_path.read_text(encoding="utf-8")

    # Find event header by time_str
    header_pattern = re.compile(
        rf"^(##\s+{re.escape(time_str)}\s+-\s+.+?)$",
        re.MULTILINE,
    )
    header_match = header_pattern.search(text)
    if not header_match:
        return False

    # Find section boundaries
    start = header_match.start()
    next_header = EVENT_HEADER_RE.search(text, header_match.end())
    end = next_header.start() if next_header else len(text)

    section = text[start:end]

    # 1. Update metadata line
    if "**Commit:**" in section:
        section = re.sub(
            r"\*\*Commit:\*\*\s*[0-9a-f]+\s*@\s*\S+",
            f"**Commit:** {commit_info['hash']} @ {repo}",
            section,
        )
    else:
        section = re.sub(
            r"(\*\*Type:\*\*\s*\w+)[ \t]*$",
            rf"\g<1> | **Commit:** {commit_info['hash']} @ {repo}",
            section,
            count=1,
            flags=re.MULTILINE,
        )

    # 2. Insert/update the ## Commit section
    commit_block = (
        f"## Commit\n"
        f"- **Hash:** {commit_info['hash']}\n"
        f"- **Repo:** {repo}\n"
        f"- **Message:** {commit_info.get('message', '')}\n"
        f"- **Author:** {commit_info.get('author', '')}\n"
        f"- **Date:** {commit_info.get('date', '')}"
    )

    if re.search(r"^## Commit\s*$", section, re.MULTILINE):
        # Replace existing Commit section (up to the next ## header)
        section = re.sub(
            r"## Commit\n.*?(?=\n##\s)",
            commit_block,
            section,
            flags=re.DOTALL,
            count=1,
        )
    else:
        # Insert before ## Description
        section = re.sub(
            r"(\n\n## Description)",
            f"\n\n{commit_block}\\g<1>",
            section,
            count=1,
        )

    text = text[:start] + section + text[end:]
    file_path.write_text(text, encoding="utf-8")
    return True


def cmd_git_unlinked(args: argparse.Namespace) -> int:
    events = load_all_events()
    unlinked = [e for e in events if not e.has_commit]
    if not unlinked:
        print("All events have a commit hash.")
        return 0

    print(f"Found {len(unlinked)} events without a commit:\n")
    for ev in unlinked:
        type_tag = f"[{ev.type}]" if ev.type else "[?]"
        print(f"  {ev.date} {ev.time}  {type_tag:<10} {ev.title}")
    return 0


def cmd_git_verify(args: argparse.Namespace) -> int:
    events = load_all_events()
    linked = [e for e in events if e.has_commit]
    if not linked:
        print("No events have a commit hash.")
        return 0

    all_ok = True
    for ev in linked:
        _, event_files = normalize_event_files(ev.files)
        if not event_files:
            print(f"⚠️  {ev.date} {ev.time} {ev.commit_hash} - no files in event")
            all_ok = False
            continue

        matched, missing, extra = verify_files_against_commit(
            ev.commit_repo, ev.commit_hash, event_files,
        )

        total = len(event_files)
        # Events only record "files changed" - the commit containing extra
        # files is normal. Only warn when an event file is NOT in the commit.
        if not missing:
            print(f"✅ {ev.commit_hash} - {len(matched)}/{total} files match")
        else:
            print(f"⚠️  {ev.commit_hash} - {len(matched)}/{total} files match")
            if missing:
                print(f"   Missing in commit: {', '.join(missing)}")
            if extra:
                print(f"   Extra in commit (not in event): {', '.join(extra[:5])}")
                if len(extra) > 5:
                    print(f"   ... and {len(extra) - 5} more")
            all_ok = False

    return 0 if all_ok else 1


def cmd_git_link(args: argparse.Namespace) -> int:
    # Parse --event "YYYY-MM-DD HH:mm"
    parts = args.event.split()
    if len(parts) != 2:
        print(
            f"❌ --event format: 'YYYY-MM-DD HH:mm' (got: '{args.event}')",
            file=sys.stderr,
        )
        return 2
    date_str, time_str = parts

    day_file = EVENTS_DIR / f"{date_str}.md"
    if not day_file.exists():
        print(f"❌ File not found: {day_file}", file=sys.stderr)
        return 1

    # Detect repo if not specified
    repo = args.repo
    if not repo:
        events = parse_events_from_file(day_file)
        ev = next((e for e in events if e.time == time_str), None)
        if ev:
            repo = detect_repo(ev.files, ev.scope)
        else:
            repo = FALLBACK_REPO

    commit_info = get_commit_info(repo, args.commit)
    if not commit_info:
        print(
            f"❌ Commit {args.commit} not found in repo {repo}",
            file=sys.stderr,
        )
        return 1

    if add_commit_to_event(day_file, time_str, commit_info, repo):
        print(f"✅ Linked event {date_str} {time_str} -> {commit_info['hash']} @ {repo}")
        return 0
    else:
        print(
            f"❌ Event {time_str} not found in {day_file}",
            file=sys.stderr,
        )
        return 1


def cmd_git_auto_link(args: argparse.Namespace) -> int:
    events = load_all_events()

    # Candidates: no commit yet, recorded hash was rewritten (rebase/amend ->
    # hash no longer in repo), or hash exists but 0 files match (logged
    # before committing -> captured the wrong old HEAD).
    candidates: list[tuple[Event, str]] = []
    for ev in events:
        if not ev.has_commit:
            candidates.append((ev, "unlinked"))
            continue
        repo_hint, event_files = normalize_event_files(ev.files)
        repo = ev.commit_repo or repo_hint or detect_repo(ev.files, ev.scope)
        if not is_git_repo(repo):
            continue
        if not git_cmd(repo, "cat-file", "-t", ev.commit_hash):
            candidates.append((ev, f"dead-hash {ev.commit_hash}"))
            continue
        existing = set(event_files)
        if existing and not (existing & set(get_commit_files(repo, ev.commit_hash))):
            candidates.append((ev, f"0-file-match {ev.commit_hash}"))

    if not candidates:
        print("All events have a valid commit hash.")
        return 0

    linked_count = 0
    for ev, reason in candidates:
        repo_hint, event_files = normalize_event_files(ev.files)
        if not event_files:
            print(f"⏭️  {ev.date} {ev.time} - no files, skip")
            continue

        repo = ev.commit_repo or repo_hint or detect_repo(ev.files, ev.scope)
        if not is_git_repo(repo):
            print(f"⏭️  {ev.date} {ev.time} - repo '{repo}' invalid, skip")
            continue

        # Rebase/amend changes the committer date - search within a ±3 day window.
        day = datetime.strptime(ev.date, "%Y-%m-%d")
        since = (day - timedelta(days=3)).strftime("%Y-%m-%d 00:00:00")
        until = (day + timedelta(days=3)).strftime("%Y-%m-%d 23:59:59")
        commits = git_cmd_lines(
            repo, "log",
            "--since", since,
            "--until", until,
            "--pretty=format:%h",
        )

        best_match = None
        best_score = 0
        for commit_hash in commits:
            commit_files = set(get_commit_files(repo, commit_hash))
            event_set = set(event_files)
            matched = len(event_set & commit_files)
            if matched > best_score:
                best_score = matched
                best_match = commit_hash

        if best_match and best_score > 0 and best_match != ev.commit_hash:
            day_file = EVENTS_DIR / f"{ev.date}.md"
            commit_info = get_commit_info(repo, best_match)
            if commit_info and add_commit_to_event(day_file, ev.time, commit_info, repo):
                print(
                    f"✅ {ev.date} {ev.time} -> {best_match} @ {repo} "
                    f"({best_score}/{len(event_files)} files, {reason})"
                )
                linked_count += 1
            else:
                print(f"❌ {ev.date} {ev.time} -> failed to update file")
        else:
            print(f"⏭️  {ev.date} {ev.time} -> no matching commit found ({reason})")

    print(f"\nLinked {linked_count}/{len(candidates)} events.")
    return 0


def add_git_subparser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "git",
        help="Manage commit links.",
        description="Manage links between events and git commits. "
        "Includes: unlinked (list events without a commit), "
        "verify (check files match), "
        "link (assign a commit to an event), "
        "auto-link (auto-assign commits to old events).",
    )
    git_sub = p.add_subparsers(
        dest="git_command",
        required=True,
        metavar="{unlinked,verify,link,auto-link}",
    )

    # unlinked
    p_unlinked = git_sub.add_parser(
        "unlinked",
        help="List events without a commit.",
    )
    p_unlinked.set_defaults(func=cmd_git_unlinked)

    # verify
    p_verify = git_sub.add_parser(
        "verify",
        help="Verify event files match the commit diff.",
    )
    p_verify.set_defaults(func=cmd_git_verify)

    # link
    p_link = git_sub.add_parser(
        "link",
        help="Link an event to a specific commit.",
    )
    p_link.add_argument(
        "--event",
        required=True,
        help="Event ID: 'YYYY-MM-DD HH:mm'",
    )
    p_link.add_argument(
        "--commit",
        required=True,
        help="Commit hash (short or full)",
    )
    p_link.add_argument(
        "--repo",
        default="",
        help="Repo name (default: auto-detect from event files/scope)",
    )
    p_link.set_defaults(func=cmd_git_link)

    # auto-link
    p_auto = git_sub.add_parser(
        "auto-link",
        help="Auto-link old events to commits (match by files + date).",
    )
    p_auto.set_defaults(func=cmd_git_auto_link)


# ============================================================================
# TIMELINE command - merge git log + events per day
# ============================================================================


def cmd_timeline(args: argparse.Namespace) -> int:
    date_str = args.date or _now().strftime("%Y-%m-%d")

    # Load events for this date
    day_file = EVENTS_DIR / f"{date_str}.md"
    events = parse_events_from_file(day_file) if day_file.exists() else []

    # Load git commits for this date from all repos
    commits: list[dict[str, str]] = []
    for repo_name in REPO_ROOTS:
        if not is_git_repo(repo_name):
            continue
        lines = git_cmd_lines(
            repo_name, "log",
            "--since", f"{date_str} 00:00:00",
            "--until", f"{date_str} 23:59:59",
            "--pretty=format:%h|%ci|%s",
        )
        for line in lines:
            parts = line.split("|", 2)
            if len(parts) == 3:
                commits.append({
                    "hash": parts[0],
                    "datetime": parts[1],
                    "message": parts[2],
                    "repo": repo_name,
                })

    # Merge into a timeline
    timeline: list[tuple[str, str, object]] = []
    for ev in events:
        timeline.append(("event", ev.time, ev))
    for c in commits:
        # Parse time from "2026-09-10 09:40:23 +0700"
        dt_parts = c["datetime"].split(" ")
        time_val = dt_parts[1][:5] if len(dt_parts) > 1 else "00:00"
        timeline.append(("commit", time_val, c))

    timeline.sort(key=lambda x: x[1])

    # Print
    print(f"{date_str}")
    print("─" * max(len(date_str) * 2, 20))
    if not timeline:
        print("No events or commits.")
        return 0

    for kind, time_val, item in timeline:
        if kind == "commit":
            c = item
            print(f"{time_val}  [commit] {c['hash']:<8} {c['message']}")
            print(f"               @ {c['repo']}")
        else:
            ev = item
            type_tag = f"[{ev.type}]" if ev.type else "[?]"
            print(f"{time_val}  {type_tag:<10} {ev.title}")
            if ev.commit_hash:
                print(f"               ↳ {ev.commit_hash} @ {ev.commit_repo}")
            else:
                print(f"               ↳ (unlinked)")

    return 0


def add_timeline_subparser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "timeline",
        help="Merge git log + events for one day.",
        description="Show a merged timeline of git commits and events for a "
        "day. Commits from all repos are queried and merged with events.",
    )
    p.add_argument(
        "--date",
        default="",
        help="Date YYYY-MM-DD (default: today)",
    )
    p.set_defaults(func=cmd_timeline)


# ============================================================================
# REVERT command - revert the N most recent events + mark + log
# ============================================================================


@dataclass
class RevertPlanItem:
    """One commit to revert + the events linked to it."""
    commit_hash: str
    repo: str
    pushed: bool
    action: str  # "reset" or "revert"
    events: list[Event]


def mark_event_reverted(
    file_path: Path,
    time_str: str,
    revert_commit_hash: str,
    revert_date: str,
) -> bool:
    """Mark an event as REVERTED: strikethrough title + add a note.

    Returns True on success.
    """
    text = file_path.read_text(encoding="utf-8")

    # Find the event header by time_str
    header_pattern = re.compile(
        rf"^(##\s+{re.escape(time_str)}\s+-\s+.+?)$",
        re.MULTILINE,
    )
    header_match = header_pattern.search(text)
    if not header_match:
        return False

    # Find section boundaries
    start = header_match.start()
    next_header = EVENT_HEADER_RE.search(text, header_match.end())
    end = next_header.start() if next_header else len(text)
    section = text[start:end]

    original_header = header_match.group(1)

    # 1. Strikethrough title + add (REVERTED) if not present
    if "REVERTED" not in original_header:
        # Format: "## HH:mm - Title" -> "## ~~HH:mm - Title~~ (REVERTED)"
        new_header = original_header.replace(
            f"## {time_str} - ", f"## ~~{time_str} - ", 1
        ) + "~~ (REVERTED)"
        section = section.replace(original_header, new_header, 1)

    # 2. Add a REVERTED note to the ## Notes section
    revert_note = f"\n**REVERTED** by commit {revert_commit_hash} on {revert_date}"
    notes_pattern = re.compile(
        r"(^## Notes\n)(.*?)(?=^##\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = notes_pattern.search(section)
    if m and "REVERTED" not in m.group(2):
        section = notes_pattern.sub(
            rf"\g<1>\g<2>{revert_note}\n",
            section,
            count=1,
        )

    text = text[:start] + section + text[end:]
    file_path.write_text(text, encoding="utf-8")
    return True


def cmd_revert(args: argparse.Namespace) -> int:
    n = args.count

    # 1. Load all events, sort newest first
    events = load_all_events()
    if not events:
        print(f"⚠️  No events found in {EVENTS_DIR}.", file=sys.stderr)
        return 1

    events.sort(key=lambda e: e.sort_key, reverse=True)

    # 2. Take the N most recent events
    target_events = events[:n]
    if len(target_events) < n:
        print(
            f"⚠️  Only {len(target_events)} event(s) found (requested {n}).",
            file=sys.stderr,
        )

    # Skip already-REVERTED events
    active_events = [e for e in target_events if "REVERTED" not in e.title]
    reverted_already = [e for e in target_events if "REVERTED" in e.title]
    if reverted_already:
        print(f"⏭️  Skipping {len(reverted_already)} already-REVERTED event(s):")
        for ev in reverted_already:
            print(f"   {ev.date} {ev.time} - {ev.title}")

    if not active_events:
        print("Nothing to revert.")
        return 0

    # 3. Group by unique commit
    commits_map: dict[tuple[str, str], list[Event]] = {}
    unlinked_events: list[Event] = []
    for ev in active_events:
        if ev.has_commit:
            key = (ev.commit_hash, ev.commit_repo)
            commits_map.setdefault(key, []).append(ev)
        else:
            unlinked_events.append(ev)

    # 4. Build plan: for each commit, check pushed + consecutive
    plan: list[RevertPlanItem] = []
    for (hash_, repo), evs in commits_map.items():
        pushed = is_commit_pushed(repo, hash_)
        plan.append(RevertPlanItem(
            commit_hash=hash_,
            repo=repo,
            pushed=pushed,
            action="revert" if pushed else "reset",
            events=evs,
        ))

    # 5. Check consecutiveness for reset
    # Group plan items by repo
    repo_to_items: dict[str, list[RevertPlanItem]] = {}
    for item in plan:
        repo_to_items.setdefault(item.repo, []).append(item)

    # For each repo, check whether the commits are consecutive at HEAD
    repo_can_reset: dict[str, bool] = {}
    for repo_name, items in repo_to_items.items():
        if not is_git_repo(repo_name):
            repo_can_reset[repo_name] = False
            continue
        hashes = [item.commit_hash for item in items]
        # Sort in git log order (newest first = items order)
        any_pushed = any(item.pushed for item in items)
        consecutive = are_consecutive_at_head(repo_name, hashes)
        repo_can_reset[repo_name] = consecutive and not any_pushed

    # Update actions
    for item in plan:
        if not repo_can_reset.get(item.repo, False):
            item.action = "revert"

    # 6. Print the plan
    print(f"{'=' * 60}")
    print(f"REVERT PLAN: {len(active_events)} event(s)")
    print(f"{'=' * 60}")

    print(f"\n📋 Events to be marked REVERTED:")
    for ev in active_events:
        type_tag = f"[{ev.type}]" if ev.type else "[?]"
        commit_tag = f"{ev.commit_hash}@{ev.commit_repo}" if ev.has_commit else "(unlinked)"
        print(f"  {ev.date} {ev.time}  {type_tag:<10} {commit_tag:<20} {ev.title}")

    if unlinked_events:
        print(f"\n⚠️  {len(unlinked_events)} event(s) have no commit (mark only, no git revert):")
        for ev in unlinked_events:
            print(f"   {ev.date} {ev.time} - {ev.title}")

    print(f"\n🔧 Git actions:")
    for repo_name, items in repo_to_items.items():
        can_reset = repo_can_reset.get(repo_name, False)
        if can_reset:
            oldest_hash = items[-1].commit_hash  # oldest = last in list
            print(f"  [{repo_name}] git reset --hard {oldest_hash}~1")
            for item in items:
                print(f"    ← {item.commit_hash} (not pushed, consecutive at HEAD)")
        else:
            for item in items:
                if item.pushed:
                    reason = "pushed"
                elif not are_consecutive_at_head(repo_name, [i.commit_hash for i in items]):
                    reason = "not consecutive at HEAD"
                else:
                    reason = "another commit in batch is pushed"
                print(f"  [{repo_name}] git revert {item.commit_hash} ({reason})")

    # 7. Dry-run or confirm
    if args.dry_run:
        print("\n--dry-run: no changes made.")
        return 0

    if not args.yes:
        print()
        response = input("Proceed? [y/N] ").strip()
        if response.lower() != "y":
            print("Cancelled.")
            return 0

    # 8. Execute git operations
    # git_actions: list of (repo, action_desc) - used for mark + log
    git_actions: list[str] = []
    revert_hashes: list[str] = []
    for repo_name, items in repo_to_items.items():
        can_reset = repo_can_reset.get(repo_name, False)
        if can_reset:
            oldest_hash = items[-1].commit_hash
            target = f"{oldest_hash}~1"
            print(f"\n🔄 [{repo_name}] git reset --hard {target} ...")
            result = subprocess.run(
                ["git", "-C", str(_repo_path(repo_name)), "reset", "--hard", target],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                print(f"❌ git reset failed: {result.stderr.strip()}", file=sys.stderr)
                return 1
            # Get the hash after reset (HEAD = target)
            new_head = get_head_commit(repo_name)
            reset_to = new_head.get("hash", target)
            git_actions.append(f"git reset --hard {target} @ {repo_name} (HEAD -> {reset_to})")
            print(f"✅ Reset OK -> {reset_to}")
        else:
            for item in items:
                print(f"\n🔄 [{repo_name}] git revert {item.commit_hash} ...")
                result = subprocess.run(
                    ["git", "-C", str(_repo_path(repo_name)), "revert", "--no-edit", item.commit_hash],
                    capture_output=True, text=True,
                )
                if result.returncode != 0:
                    print(f"❌ git revert failed: {result.stderr.strip()}", file=sys.stderr)
                    return 1
                # Get the new revert commit hash
                new_head = get_head_commit(repo_name)
                new_hash = new_head.get("hash", "?")
                revert_hashes.append(new_hash)
                git_actions.append(f"git revert {item.commit_hash} @ {repo_name} -> {new_hash}")
                print(f"✅ Revert commit: {new_hash}")

    # 9. Mark events
    now_dt = _now()
    revert_date = now_dt.strftime("%Y-%m-%d")
    git_action_str = "; ".join(git_actions) if git_actions else "(no git action: events unlinked)"
    revert_hash_str = ", ".join(revert_hashes) if revert_hashes else git_action_str

    print(f"\n📝 Marking {len(active_events)} event(s) as REVERTED ...")
    for ev in active_events:
        day_file = EVENTS_DIR / f"{ev.date}.md"
        if day_file.exists():
            if mark_event_reverted(day_file, ev.time, revert_hash_str, revert_date):
                print(f"  ✅ {ev.date} {ev.time} - {ev.title}")
            else:
                print(f"  ❌ {ev.date} {ev.time} - event not found in file")

    # 10. Log a new event
    event_titles = "; ".join(f"{ev.time} {ev.title}" for ev in active_events)
    desc = (
        f"Reverted {len(active_events)} event(s): {event_titles}. "
        f"Git action: {git_action_str}."
    )
    notes = (
        f"Reverted events: {', '.join(f'{ev.date} {ev.time}' for ev in active_events)}. "
        f"Old events are marked with ~~strikethrough~~ + REVERTED note."
    )

    # Build the files list from all events
    all_files: list[str] = []
    for ev in active_events:
        for f in ev.files.splitlines():
            f = f.strip()
            if f and f != "None" and f not in all_files:
                all_files.append(f)

    # Detect repo from files/scope
    files_str = "\n".join(all_files) if all_files else ""
    log_repo = detect_repo(files_str, active_events[0].scope if active_events else "")

    # Write the new event
    now_time = now_dt.strftime("%H:%M")
    now_date = now_dt.strftime("%Y-%m-%d")
    day_file = EVENTS_DIR / f"{now_date}.md"

    # Get the HEAD commit (the revert commit or the current one)
    commit_info = None
    if revert_hashes:
        commit_info = get_head_commit(log_repo)
    elif is_git_repo(log_repo):
        commit_info = get_head_commit(log_repo)

    event_section = build_event_section(
        time_str=now_time,
        title=f"Revert {len(active_events)} event(s)",
        scope=", ".join(sorted(set(ev.scope for ev in active_events))),
        type_="Fix",
        desc=desc,
        files=files_str,
        notes=notes,
        request="[REVERT] request",
        reason=git_action_str,
        commit_info=commit_info,
        repo=log_repo,
    )
    toc_entry = build_toc_entry(now_time, f"Revert {len(active_events)} event(s)")

    EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    if day_file.exists():
        append_to_day_file(day_file, toc_entry, event_section)
    else:
        create_new_day_file(day_file, now_date, toc_entry, event_section)

    print(f"\n📝 Logged revert event -> {day_file}")
    print(f"\n✅ Revert complete.")

    return 0


def _parse_revert_count(value: str) -> int:
    """Parse the count argument: accepts '3' or '~3' notation."""
    v = value.lstrip("~").strip()
    try:
        n = int(v)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid count: '{value}'. Use N or ~N (e.g. 2 or ~2).")
    if n < 1:
        raise argparse.ArgumentTypeError(f"Count must be >= 1 (got {n}).")
    return n


def add_revert_subparser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "revert",
        help="Revert the N most recent events (git reset/revert + mark + log).",
        description="Revert the N most recent events. Automatically: detects "
        "unique commits, checks push state (reset if unpushed + consecutive, "
        "revert if pushed), marks events with strikethrough + REVERTED, and "
        "logs a new Fix event. Default N=1. Prints the plan and asks for "
        "confirmation before executing (unless --yes).",
        usage="python3 event.py revert [~N] [--dry-run] [--yes]",
    )
    p.add_argument(
        "count",
        nargs="?",
        type=_parse_revert_count,
        default=1,
        help="Number of events to revert (default: 1). ~N notation allowed.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print the plan, make no changes.",
    )
    p.add_argument(
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt.",
    )
    p.set_defaults(func=cmd_revert)


# ============================================================================
# Entry point
# ============================================================================


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="event.py",
        description="Event log manager: write (log), search (search), "
        "git integration (git), timeline (timeline), revert (revert).",
    )
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        metavar="{log,search,git,timeline,revert}",
    )
    add_log_subparser(subparsers)
    add_search_subparser(subparsers)
    add_git_subparser(subparsers)
    add_timeline_subparser(subparsers)
    add_revert_subparser(subparsers)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
