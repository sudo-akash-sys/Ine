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
7. After completing coherent work, update `.agent/STATE.md` and
   `.agent/HISTORY.md`.

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
6. Determine the work required for THIS mission.
7. Implement it.
8. Run appropriate focused tests once per mission — at the end of the work,
   not after every edit.
9. Review the changes.
10. Update `.agent/STATE.md` and `.agent/HISTORY.md`, and tag the mission in
    `.agent/PLAN.md` (DONE / BLOCKED) — all in ONE final recording pass,
    never incrementally as you work.
11. Stop. See "Orchestrator division of labor" below for why.

Do not stop merely because one subtask is complete — drive the assigned
mission to a verified finish before you record it.

### Orchestrator division of labor (under ine-agent)

The deterministic supervisor in `src/ine_agent/` selects the next
EXECUTABLE mission, advances the plan between worker cycles, records
blocked / failed / human-gated missions, writes the durable run report
(`.agent/RUN_REPORTS.md`), and notifies the commander. The worker executes
exactly the assigned mission as a complete
research -> understand -> implement -> test -> verify -> record -> clean up
arc, then stops; it does NOT re-scan `.agent/PLAN.md` to select further
missions inside one invocation. That keeps what is genuinely autonomous
around *completing one mission well* while removing redundant model work.

## Do not ask the commander about ordinary implementation choices.

Make reasonable engineering decisions when:
- multiple implementations preserve the same semantics
- the choice is reversible
- existing project conventions provide guidance

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

Then inspect only files relevant to the current task.

Use repository state rather than replaying historical conversation.

## Resource efficiency (every tool call is a model request)

On quota-metered plans each model round-trip costs a request. When working
under a budget (e.g. the free tier), treat frugality as part of the task:

- Batch independent reads/greps/listings into a SINGLE message — a
  parallel tool batch is one request; sequential ones are several.
- Read files whole, once. Do not slice-re-read a file and do not re-read a
  file you just wrote.
- Run tests once per mission (focused tests at the end of the work; broader
  regression at meaningful checkpoints), not after every edit.
- Prefer direct work over spawning subagents or calling web fetch/search;
  each of those opens its own request chain.
- Keep context lean: read what the task requires, not the repository.

When running under ine-agent, the supervisor records observed
request/token usage per mission in `.agent/RUN_REPORTS.md`. Those numbers
are locally observed OpenCode usage, not the exact provider quota.

## Verification

Prefer focused tests during individual tasks.

Run broader regression tests at meaningful checkpoints.

Never claim work is complete without verification.

## Ine constraints

Do not change Ine's syntax or semantics without commander approval.

Preserve existing behavior unless the mission explicitly authorizes change.

Keep temporary/intermediate artifacts inside `.tmp/`.
