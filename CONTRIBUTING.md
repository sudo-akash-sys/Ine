# Contributing to Ine

Thank you for your interest in contributing to Ine! This document provides
guidelines for contributing to the project.

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## Repository layout

```
src/ine/               pipeline: lexer.py → parser.py → semantic.py → backend_*.py
src/ine/autocomplete.py   JSON-lines editor engine (standalone)
src/ine_agent/            autonomous development supervisor (loop, workers, CLI)
src/ine/dictionary/*.json   the single vocabulary source (15 files)
editor/vscode-ine/        thin VS Code extension (pure proxy to the Python dictionary)
tests/                    pytest suite: lexer, parser, semantic, dictionary, CLI,
                          autocomplete, extension protocol, ine-agent
.agent/                   autonomous control plane (PLAN/STATE/HISTORY/BLOCKERS)
```

## The language pipeline

`.ine` → `lexer.py` → `parser.py` → `semantic.py` → `backend_html.py` /
`backend_visual.py` / `backend_c.py`. Each stage is documented in
`LANGUAGE.md`. `src/ine/dictionary.py` reads `src/ine/dictionary/*.json` and
answers discovery questions; it is the only vocabulary source.

## The dictionary

The dictionary is **advisory, never a validator**. It guides autocomplete
and renderer hints but never rejects a program. A kind with no dictionary
entry has no suggestions (this is intentional — see
`examples/alice/alice.ine`).

New vocabulary is added as a `.json` file under `src/ine/dictionary/` and verified
with `ine --dict <kind>` and `python -m pytest tests/test_ine.py -k integrity`.
See `dictionary/README.md` for the JSON schema.

## Running the CLI

Three ways, all equivalent:

```bash
# 1. From the repo root (shim: adds src/ to sys.path)
python ine.py <file> -o out.html

# 2. As a module (recommended for development)
python -m ine <file> -o out.html

# 3. After pip install (installed entry point)
ine <file> -o out.html
```

Same for `ine-agent` (installed) or `python -m src.ine_agent.cli` (development).

## Running tests

```bash
python -m pytest tests          # canonical runner
python -m pytest tests -k integrity   # dictionary integrity only
```

The suite is fully hermetic (stdlib only, no network). Native tests auto-skip
without a C compiler. The tkinter visual tests may emit a transient `TclError`
under full-suite load; the class passes in isolation and on rerun (pre-existing
flake).

## Session 25 freeze

There is no code freeze. The four-construct spine and golden-output
discipline are architectural commitments (see `.agent/DECISIONS.md`), but
backend and main changes are welcome provided they do not break existing
behavior and stay aligned with the project's larger goals — deviations from
original intent are acceptable when the implementation requires it
(commander clarification, Session 41).

## How to contribute

### Reporting issues

- Check existing issues before creating a new one
- Provide a clear description of the problem
- Include steps to reproduce the issue
- Share your environment details (OS, Python version, etc.)

### Submitting changes

1. Fork the repository
2. Create a new branch for your feature or fix
3. Make your changes following the project's coding standards
4. Write or update tests as needed
5. Run `python -m pytest tests` and confirm all tests pass
6. Submit a pull request

### Pull request guidelines

- Keep changes focused and atomic
- Write clear commit messages
- Reference related issues in your PR description
- Add tests for new features; update documentation as needed

## Working with the autonomous control plane (`.agent/`)

`.agent/` is the development plan (`PLAN.md`), the current position
(`STATE.md`), the append-only narrative (`HISTORY.md`), the durable findings
(`NOTES.md`), the open decisions (`BLOCKERS.md`, `DECISIONS.md`) and one
execution index per mission (`missions/<item-number>.md`). The supervisor in
`src/ine_agent/` reads it, hands one mission to one worker, and writes every
record itself.

### The loop, as you actually use it

```sh
ine-agent doctor              # is this toolchain usable? read-only, no model call
ine-agent run --dry-run       # what would run next, with the resolved command
ine-agent run --worker opencode            # run the executable queue
ine-agent run --worker opencode --max-missions 3   # stop after three missions
```

- `doctor` resolves the worker profile, the command, the prompt position and
  the timeout, and reports what is wrong with a remedy. It launches nothing.
- `ine-agent` is the mission runner's name, deliberately not `ine run`: `ine` is
  the language CLI and its `run` executes a `.ine` file. A worker profile drives
  an external CLI by command line only — INE creates no agent, mode or plugin
  inside that tool, and needs no provider project file to run.
- `--dry-run` prints the profile, the exact command, the budget, the next
  mission and its index state, and how much of the plan is still `EXECUTABLE`.
- `--worker <name>` takes a built-in (`opencode`, `claude`) or one declared in
  `.agent/workers.json`. `--model` is a refinement, not a selector: a profile
  that does not declare how it wants a model does not get one.
- The run drains the queue: it ends when nothing is `EXECUTABLE`, when the
  mission set is exhausted, or when `--max-missions` is reached. A mission gets
  `--max-attempts` (default 1) invocations, and is counted once however many it
  takes.
- One completion notification per run — not one per mission. An immediate alert
  is reserved for a commander gate and for a run that completed nothing.

### Authoring a mission index

A mission is a numbered PLAN item plus an execution index at
`.agent/missions/<item-number>.md`. **A mission with no index is refused**,
recorded `BLOCKED`, and costs no worker call, so the index is the deliverable
that makes a mission runnable. The index states the *change*, not the
investigation: each step names what to do, not what to go and find out. A step
the worker has to think its way into is a planning defect.

Suggested shape (`.agent/MISSION_PROMPT.md` is the contract):

```markdown
# Mission <n> — <title>
Area: <subsystem>
Depends on: <item numbers>
Goal: <what is true when this is done>
## Files      # the files you expect to touch
## Steps      # each names the change
## Constraints
## Done when  # how you will know
```

### What the worker gets, and what it returns

The worker is handed a lean handoff: the mission, the rules for carrying it
out, the receipt contract, and — only when an earlier mission actually worked on
the same thing — that mission's compact receipt. It is **not** handed the plan
body, the history, or a snapshot of STATE: those were re-sent in full on every
cycle, and a snapshot that goes stale before the first step is worse than none.
A worker that needs one of them reads it itself, at the point it needs it.

**The rules are a file, not code.** `.agent/WORKER_INSTRUCTIONS.md` is the
literal prompt a worker receives, with `{{TOKEN}}` placeholders the supervisor
fills: `{{MISSION}}` and `{{RECEIPT}}` are required, and `{{RELATED}}`,
`{{MISSION_NUMBER}}` and `{{MISSION_HEADLINE}}` are optional. Change how a
worker is told to behave by editing that file — no Python change, and no
restart-free redeploy of the loop. It is validated before a run: a missing,
empty or tokenless file stops the run with a remedy rather than sending a
worker a prompt with no mission in it. `ine-agent doctor` reports the file and
its size, and fails if it is unusable. A bare `{` or `}` in the file is prose,
not a placeholder.

Related compact snippets are selected on three declared signals only — the same
`Area:`, an explicit `Depends on:`, or a changed file in common. A mission that
declares none of them is offered nothing, which is the safe default.

The worker ends by printing one JSON object after the marker line
`INE_RECEIPT_JSON`:

```json
{"status": "done", "summary": "what happened",
 "changed_files": ["src/thing.py"], "verification": ["pytest -q: 12 passed"],
 "area": "ine-agent", "finding": "a durable fact", "follow_up": "a proposed next mission"}
```

`status` is one of `done`, `failed`, `missing_prerequisite`,
`needs_commander`. Every field is optional and bounded, and a receipt that
cannot be read is treated as "this worker did not report", never as a reason
to spend another request interpreting it.

Two rules make this safe, and both are enforced rather than asked for:

- **A worker never edits the control plane.** The plan, state, history and
  notes entries are written by Python from the receipt, so a worker cannot
  half-record a mission.
- **A follow-up is a proposal, never work.** It goes to the run report, and a
  real deliverable is appended to the plan as a `CLAUDE_REVIEW` item carrying a
  marker that makes it non-executable. Nothing runs a proposal until a human
  re-tags it.

### Budgets, checks and cost

Everything above runs with no configuration at all. Two things are opt-in, and
both live in one optional file, .agent/workers.json:

`json
{
  "policy": {"max_prompt_chars": 12000,
              "max_previous_receipts": 3,
              "max_previous_receipt_chars": 2000,
              "max_attempts": 1},
  "verify": ["python -X utf8 -m pytest tests/test_ine_agent.py -q"]
}
`

**policy sets the context budget.** max_prompt_chars is the cap on the
whole prompt; the two max_previous_* keys are the related-receipt caps. A
mission that needs more than the cap is **reported as over budget and sent
whole** — the loop never quietly truncates a mission the planner asked for.
max_attempts is the per-mission attempt budget, and the CLI flag wins over it
when both are given: --max-attempts 1 means one, --max-attempts 3 means
three, and saying nothing defers to the policy. A file that exists and cannot
be understood stops the run with its remedy — a policy you wrote and the loop
ignored is the failure this exists to prevent.

**erify adds local checks.** Each entry is a command to run in the project
root, written as a string or as an argv list. They run **only after a worker
reports done**, never for a failure, and they cannot call a worker or a model:
if a check fails, the finding is recorded, the mission is not re-run, and the
run exits non-zero so the failure cannot be mistaken for success. Every check
runs even after one fails, each has a 10-minute timeout, and only the tail of
its output is kept. A malformed erify list is an error, not a skipped check.
ine-agent run --dry-run shows what is configured without running any of it.

**ine-agent measure** reads the durable run reports and prints what missions
actually cost: cycles, completions, provider requests and tokens, prompt sizes,
how many prompts went over budget, and per-mission rows. It is read-only, needs
no provider call, and is the number to look at before deciding a change made
missions cheaper or more expensive.

### What you are asked to decide

You are asked for the things an agent must not decide for itself: language
syntax and semantics, product direction, fundamental architecture, breaking
compatibility, and any conflicting reading of intended behaviour. Those go to
`.agent/BLOCKERS.md` and stop the run with exit code 2. Ordinary engineering
choices — an implementation that preserves the semantics, a reversible
decision, a choice the project already has a convention for — are the agent's
to make and it makes them without asking.

### Conventions

- **PLAN tags:** every numbered item carries exactly one of `EXECUTABLE` /
  `BLOCKED` / `DONE` / `CLAUDE_REVIEW`. A compound tag parses as no tag and
  breaks mission selection.
- **`.tmp/`** is the only location for scratch (gitignored). Every durable
  artifact belongs in this repository; nothing durable may live in `.tmp/`.
- **Dictionary is advisory:** the autonomous agent never unblocks
  evidence-gated work by guessing — evidence-gated means evidence is needed.

## License and Copyright

By contributing to Ine, you agree that your contributions will be licensed under
the Apache License, Version 2.0.

### Developer Certificate of Origin

By making a contribution to this project, you certify that:

- You created the contribution entirely yourself, or you have the right to
  submit it under the project's license
- You understand and agree that your contribution is public and that a record
  of the contribution is maintained indefinitely
- You grant sudo-akash-sys and the project a perpetual, worldwide, non-exclusive,
  royalty-free, irrevocable license to use, modify, and distribute your
  contribution under the Apache-2.0 license

## Trademark Usage

Note that while your code contributions are licensed under Apache-2.0, the Ine
name and logos remain trademarks of sudo-akash-sys. See [TRADEMARKS.md](TRADEMARKS.md)
for details.

## Questions?

If you have questions about contributing, feel free to open an issue for
discussion.