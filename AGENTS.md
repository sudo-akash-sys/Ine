# Ine Agent Operating Rules

You are an engineering agent working on the Ine programming-language
project.

## Entry point

Start here. This file is the permanent entry point for autonomous work in
the Ine repository. Read the following in order, consulting the others as
listed rather than re-reading the whole repository:

1. `AGENTS.md` — these operating rules.
2. `.agent/MISSION.md` — the current objective.
3. `.agent/STATE.md` — current ground truth.
4. `.agent/PLAN.md` — relevant sections for executable work.
5. `.agent/DECISIONS.md` — before making architectural or language decisions.
6. `.agent/BLOCKERS.md` — before proceeding if something may require
   commander input.
7. `.agent/WORKER_PROMPT.md` / `.agent/MISSION_PROMPT.md` — the execution
   contract and the planning contract; see "Planning and execution".
8. After completing coherent work, make ONE recording pass (see "Recording").

## Commander

The commander defines:
- product direction
- language meaning
- syntax
- semantic decisions
- major architectural direction

The agent owns:
- implementation
- debugging
- testing
- refactoring
- documentation
- research
- engineering decomposition
- verification

## Autonomous operation

When given a mission:

1. Inspect the current repository state.
2. Read `.agent/MISSION.md`.
3. If the ine-agent orchestrator launched you, the current-state essentials
   are embedded in your prompt — use them and do not re-read the whole of
   STATE.md or PLAN.md. Otherwise read `.agent/STATE.md` and the relevant
   parts of `.agent/PLAN.md`.
4. Consult `.agent/DECISIONS.md` before making architectural or language
   decisions.
5. Check `.agent/BLOCKERS.md` if the task may require commander input.
6. Determine the work required for THIS mission — if you are the *planner*,
   that determination is the mission, and its output is the index at
   `.agent/missions/<item-number>.md`. If you are the *executor*, the work
   is already written there: follow it in order. See "Planning and
   execution".
7. Implement it.
8. Run appropriate focused tests once per mission — at the end of the work,
   not after every edit.
9. Review the changes.
10. Record, in ONE final pass — never incrementally. See "Recording".
11. Stop. See "Orchestrator division of labor" below for why.

Do not stop merely because one subtask is complete — drive the assigned
mission to a verified finish before you record it.

## Planning and execution

Planning and execution are separate roles with separate prompts, and the
seam between them is a written file.

**The planner** reads the objective, the plan, the code — whatever the
mission needs — works out *how* it should be done, and writes the answer
down as an execution index at `.agent/missions/<item-number>.md`, keyed on
the item's number in `.agent/PLAN.md`. The planner's prompt is
`.agent/MISSION_PROMPT.md`, and it is also what the supervisor's design
review uses.

**The executor** carries out one written index and stops. It does not
research, re-plan, re-scope or decompose — the planner already did that, and
re-doing it in every cycle is the largest avoidable token cost in the loop.
The executor's prompt is `.agent/WORKER_PROMPT.md`; under ine-agent it is
embedded automatically, together with the index, so the worker never has to
read the control-plane files to work out what to do.

**A mission with no index is refused.** The supervisor records it `BLOCKED`
with the reason, defers it, and spends no worker call. That is deliberate:
an un-indexed mission is an un-planned mission, and running one means paying
a model to plan work that should have been planned once.

The index contract in full — sections, and what belongs in each — is in
`.agent/MISSION_PROMPT.md`. The short version: **steps name the change, not
the investigation.** A step the executor cannot act on without thinking is a
planning defect, and the executor is instructed to stop and escalate rather
than fill the gap.

## Repository containment

**Every project artifact is written inside this repository.** No project file
goes to the user profile (`~/.claude/…`), the OS temp directory, or any path
outside the repo. The repo is the only place a later session can find it.

- `.agent/` holds **durable** records: `STATE` `HISTORY` `PLAN` `DECISIONS`
  `BLOCKERS` `NOTES` `MISSION_PROMPT` `WORKER_PROMPT` `RUN_REPORTS` and
  `missions/`. If a finding or artifact matters, it goes here.
- `.tmp/` is **scratch only** (gitignored). Prototypes, one-off scripts and
  probe files may live there. Nothing in `.tmp/` may be referenced as the
  location of a durable result: a path in STATE, HISTORY or NOTES pointing
  into `.tmp/` is a defect, because the reader cannot find it later. If the
  result matters, it belongs in `.agent/`.
- Orchestrator sessions are recorded in `.agent/RUN_REPORTS.md` (written by
  the supervisor). Interactive Claude Code sessions are **not** — see the
  exceptions below.

### Where project records live

Three places look like they should hold project state. Only one does:

- `~/.claude/projects/<slug>/…` on the C: drive — Claude Code's own session
  and `file-history` store. It grows on every chat. It is harness-internal,
  never a place to read or write project work (exception 1 below).
- `SESSION_STATE.md` and `RESEARCH_LOG.md` at the repo root — **retired.**
  They were the record through Sessions 1–30 only. Do not update, read for
  ground truth, or cite them as current. Their successors are
  `.agent/STATE.md`, `.agent/HISTORY.md` and `.agent/NOTES.md`.
- `.agent/` — the **live** control plane. This is where STATE, HISTORY, PLAN,
  NOTES, BLOCKERS, DECISIONS, RUN_REPORTS, attempts and missions/ are written
  and read. If a file matters for the project, it lives here or under a path
  cited from here.

The control-plane files are not written after every edit. Recording is one
pass at the end of coherent work (see "Recording"), and `attempts.json` and
`RUN_REPORTS.md` are only written by the ine-agent supervisor — never by an
interactive chat. A `git status` on `.agent/` shows real, recent writes; the
root `.md` and C: store staying quiet is normal.

Two sanctioned exceptions, so this rule is not read as absolute and then
quietly ignored:

1. **Claude Code's own session and `file-history` stores** under
   `~/.claude/` are harness-internal, not agent output. They cannot be
   relocated. They are never a place to put project work — the agent must
   not read project content from them or treat them as project storage.
2. **A test fixture that must not sit inside a git work tree** may use the OS
   temp directory, and must register for cleanup so it cannot leak. Fixtures
   created under `.tmp/` follow the same rule: they register and they are
   removed. A fixture directory that survives its test is a bug.

## Recording

Do it in **ONE pass, at the very end of coherent work** — never
incrementally, because each write costs a read of whatever it touches.

- **`.agent/HISTORY.md` — append only.** Add a session block for what
  happened. Never read it whole and never rewrite it. It is the durable
  narrative and it only grows.
- **`.agent/STATE.md` — bounded position, not a diary.** Rewrite only the
  head sections (`Current focus`, `Health`) to say where the project stands
  NOW. Per-session narrative belongs in HISTORY.md; STATE.md must stay small
  because every cycle reads it.
- **`.agent/PLAN.md` — tag the item.** Exactly one of `EXECUTABLE` /
  `BLOCKED` / `DONE` / `CLAUDE_REVIEW`. A compound tag (e.g.
  `` `DONE — GATE UNCLEARED` ``) parses as no tag and breaks mission
  selection.
- **`.agent/NOTES.md`** — append durable findings. Leave it alone if the
  work produced none.
- **`.agent/MISSION_PROMPT.md` / `.agent/WORKER_PROMPT.md`** — update only
  when the mission was about how planning or execution is instructed.
- **`.agent/missions/<item-number>.md`** — written by the planner, before
  execution. Mark the steps done as you finish them.

### Orchestrator division of labor (under ine-agent)

The deterministic supervisor in `src/ine_agent/` selects the next
EXECUTABLE mission, refuses any mission whose execution index is missing
(recording it `BLOCKED` and spending no worker call), advances the plan
between worker cycles, records blocked / failed / human-gated missions,
writes the durable run report (`.agent/RUN_REPORTS.md`), and notifies the
commander.

The **executor** carries out exactly the assigned index and stops. It does
not research the problem, re-scope it, or select a further mission inside one
invocation — the planner wrote the scope, and the supervisor advances the
plan. That keeps what is genuinely autonomous around *executing one mission
well* while removing the redundant model work of re-deriving it.

The **planner** is a separate pass: it reads the objective and the code,
writes `.agent/missions/<item-number>.md`, and records the proposal when the
mission's deliverable *is* a finding (an audit, an investigation). Missions
of that kind have no source-code change in them at all — their whole output
is the NOTES.md section the index names.

## Do not ask the commander about ordinary implementation choices.

Make reasonable engineering decisions when:
- multiple implementations preserve the same semantics
- the choice is reversible
- existing project conventions provide guidance

## Interactive session recording

Under interactive Claude Code (not the ine-agent supervisor), the
recording pass is the agent's own responsibility and there is no
supervisor to enforce it — so it is a hard stop condition, not a
suggestion. Before ending the session:

1. **Write STATE.md** — bounded position, not a diary. Rewrite only
   the head sections (`Current focus`, `Health`) to say where the
   project stands NOW. Per-session narrative belongs in HISTORY.md.
2. **Append to HISTORY.md** — one dated session block. Append only;
   never read it whole and never rewrite it.
3. **Tag PLAN.md items** — exactly one of `EXECUTABLE` / `BLOCKED` /
   `DONE` / `CLAUDE_REVIEW` for every item this session touched.
4. **Append to NOTES.md** — durable findings only. Leave it alone if
   the work produced none.
5. **Do not stop before this.** A session that ends without recording
   leaves STATE.md describing a project that has moved, and the next
   session starts from stale ground truth. The recording pass is part
   of the work, not a postscript.

## Interactive session recording

Under interactive Claude Code (not the ine-agent supervisor), the
recording pass is the agent's own responsibility and there is no
supervisor to enforce it — so it is a hard stop condition, not a
suggestion. Before ending the session:

1. **Write STATE.md** — bounded position, not a diary. Rewrite only
   the head sections (`Current focus`, `Health`) to say where the
   project stands NOW. Per-session narrative belongs in HISTORY.md.
2. **Append to HISTORY.md** — one dated session block. Append only;
   never read it whole and never rewrite it.
3. **Tag PLAN.md items** — exactly one of `EXECUTABLE` / `BLOCKED` /
   `DONE` / `CLAUDE_REVIEW` for every item this session touched.
4. **Append to NOTES.md** — durable findings only. Leave it alone if
   the work produced none.
5. **Do not stop before this.** A session that ends without recording
   leaves STATE.md describing a project that has moved, and the next
   session starts from stale ground truth. The recording pass is part
   of the work, not a postscript.

## Commander escalation

Stop and create `.agent/BLOCKERS.md` when a decision requires
the commander's judgment about:

- language syntax
- language semantics
- product direction
- fundamental architecture
- breaking compatibility
- conflicting interpretations of the intended behavior

Include:
- the question
- evidence
- options
- recommendation
- consequences

## Context efficiency

Do not read the entire repository unnecessarily.

Start with:
- AGENTS.md
- .agent/MISSION.md
- .agent/STATE.md
- .agent/DECISIONS.md
- .agent/BLOCKERS.md
- relevant PLAN section

Read those ONCE, at the start, and only as far as the mission needs. Under
the ine-agent orchestrator the essentials are already embedded in your
prompt, so control-plane files are for targeted lookups (grep a decision or
a blocker), not for re-reading. An execution worker reads **none** of this
list whole — its index and the embedded blocks are its whole scope.

Then inspect only files relevant to the current task.

A tool call is paid once; everything it returns is re-sent on every later
step. So the cost of a read is its size multiplied by the number of steps
that follow it. Locate before you read: grep for the symbol, property or
anchor you need and read only the matching region. A whole-file read to
answer one narrow question is the largest avoidable cost in a long run, and
reading the same file twice is never justified.

Use repository state rather than replaying historical conversation.

## Resource efficiency (every tool call is a model request)

On quota-metered plans each model round-trip costs a request. When working
under a budget (e.g. the free tier), treat frugality as part of the task:

- Batch independent reads/greps/listings into a SINGLE message — a
  parallel tool batch is one request; sequential ones are several.
- Read the smallest region that answers the question, once. Prefer
  locate-then-read (grep, then the matching range) to a whole-file read;
  read a file whole only when you genuinely need all of it. Never re-read
  a file and never re-read a file you just wrote.
- Run focused tests during the work and the full suite once, at the end —
  not after every edit. Test output stays in context for every later step.
- Prefer direct work over spawning subagents or calling web fetch/search;
  each of those opens its own request chain.
- Keep context lean: read what the task requires, not the repository.

When running under ine-agent, the supervisor records observed
request/token usage per mission in `.agent/RUN_REPORTS.md`. Those numbers
are locally observed OpenCode usage, not the exact provider quota.

## Verification

Prefer focused tests during individual tasks: run the specific test file
covering the surface you changed, not the whole suite.

Run the full suite once, at the end of the mission, before recording.

Never claim work is complete without verification.

## Ine constraints

Do not change Ine's syntax or semantics without commander approval.

Preserve existing behavior unless the mission explicitly authorizes change.

Keep temporary/intermediate artifacts inside `.tmp/` — and nothing durable
there. See "Repository containment" for what counts as durable.
