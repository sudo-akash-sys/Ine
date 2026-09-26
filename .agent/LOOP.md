# `.agent/LOOP.md` — how the autonomous worker actually works

Human-facing reference. What the loop does, every command, and why each
decision was made. The worker's own instructions are
`.agent/WORKER_INSTRUCTIONS.md`; the plan it draws from is `.agent/PLAN.md`;
this file explains the machinery between them.

---

## 1. The idea

You give a coding agent one mission at a time. It does the work, reports back
in a fixed shape, and the script records what happened. Then it does the next
one. The script has no judgement of its own: it selects, hands over, records,
and stops. Everything it knows comes from `.agent/`.

**One mission, one process, one receipt.** That is the whole contract, and
everything below exists to keep it cheap and true.

## 2. The cycle

For each mission, in order:

1. **Select.** Take the first `EXECUTABLE` item in `PLAN.md` list order. Never
   skip an earlier item for a more interesting later one.
2. **Require an index.** The mission's plan must have a written execution
   index at `.agent/missions/<item-number>.md`. No index → recorded `BLOCKED`
   and skipped, **spending no worker call**. A mission that has not been
   planned is not the loop's to plan.
3. **Assemble the prompt.** The rules from `WORKER_INSTRUCTIONS.md`, the
   mission index, the receipt contract, and — *only* if the mission declares a
   shared area, an explicit dependency, or an overlapping changed file — up to
   3 compact receipts from earlier missions (2,000 chars total). Nothing else.
   No plan body, no `STATE.md`, no history, no file contents.
4. **Hand over.** Launch one worker process with that prompt as its final
   argument, from the project root, with a timeout.
5. **Read the receipt.** One JSON object after the marker `INE_RECEIPT_JSON`:
   status, summary, changed files, verification the worker ran, area, optional
   finding, optional follow-up.
6. **Record — in Python, never by the worker.** Based on the status:
   - `done` → tag the plan item `DONE`, write the run report, store the
     compact receipt, append a `HISTORY.md` block, clear any failure history.
   - `failed` / `missing_prerequisite` → record why, **defer for this run**,
     continue with independent work, exit non-zero at the end.
   - `needs_commander` → record as `BLOCKED` for you to decide, continue with
     independent work, exit `2`.
   A receipt that cannot be parsed counts as *no report* — never a reason to
   spend another request interpreting it.
7. **Optional checks.** If `verify` is configured, run the local commands now,
   only because the mission reported `done`. A failure is recorded and fails
   the run; it does not re-run the mission.
8. **Repeat** until the queue has no `EXECUTABLE` item, or a bound is reached.

After every cycle the plan and state are **re-read from disk**, so a receipt
recorded in step 6 is immediately authoritative.

## 3. What the worker gets — and what it never gets

Gets: its mission, the rules, the receipt contract, maybe 3 related receipts.

Never gets: the plan, the history, `STATE.md`, or the contents of the files it
is about to edit. It reads those itself, when it needs them. Re-sending a
snapshot that goes stale before the first step is worse than sending nothing.

It also never edits `.agent/`. Every record in the control plane is written by
Python from the receipt, so a worker cannot half-record a mission. A follow-up
it proposes is filed as a non-executable `CLAUDE_REVIEW` item, never as work.

## 4. Commands

Four. Two you will use weekly, two exist for diagnosis.

**How to invoke them.** `ine-agent` is declared as a console script in
`pyproject.toml`, but this checkout is **not pip-installed**, so the name is not
on `PATH` yet. Until it is, run either of these from the repo root - both are
the same entry point:

```
python -m ine_agent.cli <command>      # recommended
python src/ine_agent/cli.py <command>  # the plain-script form
```

`pip install -e .` puts the short `ine-agent` name on `PATH`; it changes only
your environment, not the repository.

### `run` — do the work

| flag | default | why it exists |
| --- | --- | --- |
| `--dry-run` | off | Print the profile, resolved command, next mission, prompt size and budget, then stop. The first thing to run when something looks wrong — it costs nothing and launches nothing. |
| `--worker NAME` | `opencode` | Which agent CLI to drive. Also switchable per project. |
| `--model NAME` | tool's own | Passed only to a profile that declares how it wants one. |
| `--max-missions N` | unset | Unset runs the queue to exhaustion, which is finite: a mission is attempted once and left `DONE`/`BLOCKED`/`DEFERRED`. Use it to bound a run while you watch. Old name `--cycle-limit` still works. |
| `--max-attempts N` | the policy's (1) | Attempts one mission may get in a run before it is deferred. One request per mission is the default; spending a second is your call, not the loop's. |
| `--max-failures N` | 3 | Failed attempts across *different runs* before a mission is parked and stops being picked, until you rewrite it or delete its ledger entry. Stops the loop re-paying for the same failure. |
| `--stall-limit N` | 3 | Consecutive cycles that complete nothing, block nothing, and change no file outside `.agent/` before the run stops early. A cheap "this is going nowhere" guard. |
| `--quiet` / `--verbose` | — | Hide live worker output, or relay it raw. |
| `--usage-warn-requests N` | env var | Warn once when observed requests for the day reach this. Advisory; never stops a run. |
| `--notify` | off | Windows notification on completion, failure, block, or gate. |
| `--root PATH` | search upward | Point at a different project root. |

**Exit codes:** `0` clean or nothing to do · `1` error, or a mission failed, or
a check failed · `2` your judgment is required (a `needs_commander` gate).

### `doctor` — what *would* run

Resolves the worker profile and prints the exact command, the instructions file
and its size, the model, and the timeout. Fails if the instructions file is
unusable. No model call. Run this after editing `WORKER_INSTRUCTIONS.md`.

### `measure` — what it cost

Reads the run reports and the ledger, then prints per run and per mission:
cycles, completions, deferrals, provider requests and tokens, prompt
characters, how many prompts went over budget, and how many runs completed
nothing. Read-only, launches nothing. This is the number to look at before
and after changing anything about the handoff.

### `resolve "headline" "your decision"` — unblock a mission

Records your resolution against a `BLOCKED` mission, preserving the original
blocker text. Exists so a decision lives in the record, next to what it
decided, instead of in a chat.

## 5. The one config file

`.agent/workers.json`, entirely optional. Two sections beyond worker profiles:

```json
{
  "policy": {"max_prompt_chars": 12000,
             "max_previous_receipts": 3,
             "max_previous_receipt_chars": 2000,
             "max_attempts": 1},
  "verify": ["python -X utf8 -m pytest tests/test_ine_agent.py -q"]
}
```

A `policy` cap is a **report, not a scissor**: a mission that needs more than
`max_prompt_chars` is sent whole and the overage is recorded. Truncating a
mission is the one thing a budget must never do — a worker handed half a
mission reports `done` and means something else.

A file that exists and cannot be understood **stops the run with its remedy**.
A policy you wrote and the loop silently ignored is the exact failure this
prevents. `0` disables a bound rather than erroring; absence of the file is
simply the defaults.

## 6. Why these choices

- **One process per mission.** A long-lived "supervisor agent" would spend
  tokens re-deciding what it already decided, and would accumulate context that
  has to be paid for on every subsequent call. A fresh process per mission
  starts from nothing and knows only what the mission needs.
- **Python records; the worker only works.** If the agent could write its own
  records, a truncated or confused write becomes a corrupted plan. Records are
  derived from a fixed-shape receipt, so they are always parseable.
- **The plan, not the model, decides what is next.** Selection is a text rule,
  not a judgement call. That is why it is reproducible and why it costs nothing.
- **No second opinion call.** An earlier version asked the agent to classify its
  own failure in a follow-up request. That doubled the cost of every failure
  and still could not see anything the receipt did not already say. The receipt
  carries the classification instead.
- **Bounded, declared memory.** Related work is offered only on three declared
  signals. An unfiltered snippet list is the history this design exists to
  replace.
- **Fail loudly on bad config, stay silent on absent config.** Absent is a
  default; wrong is an error.
- **The record is the product.** After the worker exits, what remains is
  `.agent/`. Every claim the project makes about itself should be checkable
  from those files by someone who was not there.

## 7. What is written automatically, and what is not

This is the honest division of labour, and the thing most likely to surprise
you.

**Automatic, by Python, every run:**
plan item tags and remarks · the run report · compact receipts · the failure
ledger · proposals from follow-ups · a `HISTORY.md` block per completion.

**By an agent, at the end of a session:** `STATE.md`, `NOTES.md`,
`DECISIONS.md`, `BLOCKERS.md`, mission indexes, and edits to
`WORKER_INSTRUCTIONS.md`.

**By you:** anything that is a judgement — language semantics, syntax, product
direction, and whether a blocked mission should stay blocked.

The consequence is real and worth stating: **the code is never stale, but the
control plane can be.** The worker reads the actual files, so it never works
from an out-of-date summary. But `STATE.md`'s claims about the plan are written
by an agent, and they drift. There is a live example: `STATE.md` currently says
item 84 "needs an index written at `.agent/missions/84.md`", and that index
exists, is complete, and `run --dry-run` resolves it. The loop cannot catch
that class of error by itself, because judging a sentence true requires reading
the code.

Three ways to narrow the gap, cheapest first:

1. **A deterministic staleness check** (no model, no tokens): fail the run when
   a cheap fact is checkable and false — e.g. `STATE.md`'s "next item" claim
   disagreeing with what the selector actually picks, an `EXECUTABLE` item whose
   declared files have changed since its index was written, or N missions
   completed since the last state refresh. This fits the existing `verify`
   mechanism exactly.
2. **A budgeted refresh mission**: when such a check trips, the plan gets a
   `CLAUDE_REVIEW` item that says "re-read the code and rewrite `STATE.md` and
   the affected `NOTES.md` entries". One mission, when it is owed, instead of
   background work forever.
3. **Automatic prose rewriting**: not recommended. It requires a model call per
   run to summarise sessions, which is the per-run cost this design deleted, and
   it hands authorship of the project's ground truth to a process you did not
   choose.

## 8. Known limits

- **You will see the loop's own lines immediately; the worker's output depends
  on the CLI.** Progress lines are flushed as they are written and stdout is
  line-buffered, so a piped or redirected run shows the cycle banner, the
  mission and every result as they happen. Whether the *worker's* own tokens
  appear live is the CLI's business, not the loop's: `opencode run` streams,
  while `claude -p` emits its whole answer at the end, so that run is quiet
  while it works. That is what the heartbeat is for — every 30 seconds it
  prints `still running, Ns elapsed`, which is a fact rather than an opinion.
  Silence plus a rising counter means working; silence with a frozen counter
  and no exit means something is wrong. (`--cycle-limit`-style bounds still
  apply: a worker cannot outlive its profile's timeout.)
- **A `done` receipt that changed no files is not proof of work.** A mission is
  a request to change the repository, so a worker claiming `done` with an empty
  `changed_files` has not demonstrated that it did anything — and the loop
  currently believes it, because the receipt contract does not forbid it. This
  is not hypothetical: a diagnostic probe with an empty receipt marked a real
  plan item `DONE` and advanced the queue (rolled back by hand; the open
  question is in `BLOCKERS.md`). Until that is decided, read `changed_files` in
  a run report before believing a `DONE`, and do not let a zero-change `done`
  advance the queue unattended.
- **A worker can no longer ask you anything.** Both launch paths give the child
  an immediately-EOF stdin (`DEVNULL`), never your console. This is deliberate:
  the first live `run` printed `Execution errorTerminate batch job (Y/N)?` and
  sat there until Ctrl+C, because a worker that inherits a terminal can park the
  queue on a keypress. If a CLI needs a real TTY to work at all, it is not a
  worker this loop can use - and the answer is to change INE's side of the pipe,
  not the agent's config. A local `verify` check gets the same treatment.
- **The first live mission failed at the model, not at the loop.** The installed
  Claude rejected its own configured model (`[claude-code:unrecognized_model]`)
  before doing any work, and the built-in `claude` profile passes no model
  argument - so that model is being chosen somewhere INE does not own. INE does
  not change it, and does not add routing or fallback to route around it.
- **A real mission has now completed end to end.** Mission 84 ran on
  `--worker claude`, edited three files, returned a `done` receipt, and was
  recorded with its verification — 729 tests green at the time. What the
  machinery is covered by is 729 tests, and the whole path — CLI, factory,
  profile, subprocess, receipt, records — is exercised end to end.
  Two things the live run cost, in order of how long they took to find: a
  worker needs its permissions granted on the command line (below), and the
  first attempt at anything is still the one most likely to be wrong in a way
  only a real agent can reveal.
- **A worker is granted its tools on the command line, and it matters.** In
  print mode a CLI cannot ask anyone for permission, so an ungranted tool is
  refused and the mission reports itself `stuck` — having done all the reading,
  settled a design, and written nothing. The `claude` profile therefore passes
  `--permission-mode acceptEdits` with explicit `--allowedTools` and
  `--disallowedTools`, reproducing the posture PLAN item 122 was approved on
  using documented flags instead of a provider config file. Nothing passes
  `--dangerously-skip-permissions`, and a test fails if it ever does.
- **Savings are still measured in prompt bytes, not in bills.** Per-mission
  provider usage reports `usage_unavailable` for `claude` runs, because that
  CLI reports none; the honest number today is elapsed time and prompt size.
- **The queue is ahead of the evidence.** 30 items are `EXECUTABLE` and all 30
  have written indexes, but most predate the language surface as it stands.
  An index that no longer matches the code is a mission nobody has re-planned.
- **Telemetry is thin.** Historical usage was captured before per-mission
  recording existed, so `measure` has almost no real provider data to report.
- **`needs_commander` is a judgement you must make.** The loop will not guess.
- **The loop cannot rewrite itself.** Changing how it behaves means editing
  `.agent/WORKER_INSTRUCTIONS.md` or `PLAN.md`, or asking for a mission.
