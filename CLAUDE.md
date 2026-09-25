# CLAUDE.md

**This repository's operating rules are in [AGENTS.md](AGENTS.md). Read it
before doing any work here.** AGENTS.md is the single source of truth for
process; this file deliberately does not restate it, so nothing here can drift
out of sync with it. If the two ever disagree, AGENTS.md is right and this file
is wrong.

## Load order

`AGENTS.md` → `.agent/MISSION.md` → `.agent/STATE.md` → the relevant
`.agent/PLAN.md` section → `.agent/DECISIONS.md` → `.agent/BLOCKERS.md`.

## The two steps easiest to miss

1. **Before work — check what is *not* decided.** `.agent/DECISIONS.md` marks
   each decision DECIDED / PROPOSED / UNDECIDED, and `.agent/BLOCKERS.md` parks
   scope. Work that looks obviously needed can be explicitly not-yet-decided,
   and a parked item usually has named preconditions. That is a signal to
   escalate, not to implement.

2. **After coherent work — one recording pass, never incremental.**
   `.agent/STATE.md` + `.agent/HISTORY.md` + tag the item in `.agent/PLAN.md`.
   The tag vocabulary is exactly `EXECUTABLE` / `BLOCKED` / `DONE` /
   `CLAUDE_REVIEW`; a compound tag (e.g. `` `DONE — GATE UNCLEARED` ``) parses
   as no tag and breaks mission selection.

**Always — write inside the repo.** Every project artifact belongs inside
this repository: never `~/.claude/…`, never the OS temp dir. `.agent/` is
durable, `.tmp/` is scratch, and no `.tmp/` path may be cited as the location
of a durable result. AGENTS.md, "Repository containment", has the rule and
its two sanctioned exceptions.

## Conventions

- Temporary artifacts live in `.tmp/` (gitignored), never committed.
- Tests: `python -m pytest tests` from the repo root.

Escalation triggers and the required format are in AGENTS.md, "Commander
escalation".
## Where project records live

See AGENTS.md, "Repository containment — Where project records live" for the
full rule. Three places look like they should hold project state; only
`.agent/` does:

- `~/.claude/projects/<slug>/…` (C: drive) — Claude Code's own session store.
  Harness-internal; never read project content from it or write project work
  there.
- `SESSION_STATE.md` and `RESEARCH_LOG.md` (repo root) — **retired** (Sessions
  1–30 only). Never update them or use them for ground truth; read
  `.agent/STATE.md` and `.agent/HISTORY.md` instead.
- `.agent/` — the live control plane. All durable project records live here
  (`STATE` `HISTORY` `PLAN` `NOTES` `BLOCKERS` `DECISIONS` `RUN_REPORTS`
  attempts `missions/`). Recording is one pass at the end of coherent work;
  `attempts.json` / `RUN_REPORTS.md` are written by the ine-agent supervisor
  only, never by an interactive chat.

