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
3. Read `.agent/STATE.md`.
4. Read the relevant parts of `.agent/PLAN.md`.
5. Consult `.agent/DECISIONS.md` before making architectural or language
   decisions.
6. Check `.agent/BLOCKERS.md` if the task may require commander input.
7. Determine the next safe engineering task.
8. Implement it.
9. Run appropriate focused tests.
10. Review the changes.
11. Update `.agent/STATE.md`.
12. Update `.agent/HISTORY.md`.
13. Continue to the next safe task.

Do not stop merely because one subtask is complete.

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

## Verification

Prefer focused tests during individual tasks.

Run broader regression tests at meaningful checkpoints.

Never claim work is complete without verification.

## Ine constraints

Do not change Ine's syntax or semantics without commander approval.

Preserve existing behavior unless the mission explicitly authorizes change.

Keep temporary/intermediate artifacts inside `.tmp/`.
