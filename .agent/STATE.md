# .agent/STATE.md

Current ground truth as of Session 57. Position, not narrative: what stands
where today, and what the next cycle must know. The per-session story is
`HISTORY.md` (append-only) and the durable findings are `NOTES.md`; nothing
that belongs there is repeated at length here, because every cycle reads this
file and its size is a per-cycle cost.

The project is two things, and they are independent: the **Ine language**
(`src/ine/`, its dictionaries, its editor extension) and the **autonomous
worker** that executes this plan (`src/ine_agent/`). The language surface has
not moved since Session 42's styling prototype; every mission from Session 47
onward is tooling, recording discipline, or evidence gathering.

**Language**: 13 makeable kinds over 15 dictionary JSON files, five statement
kinds, the lexer → parser → semantic → backend pipeline, an autocomplete
service, and a VS Code extension that holds no Ine vocabulary. All goldens
(hello, topbar, hero, cards) are byte-identical unless a mission says
otherwise. Item 7 stays BLOCKED on evidence (no `choice` value, no WORKBOOK
decision). Session 42's HTML styling prototype shipped with its gate UNCLEARED
(item 58 was implemented without clearing the Mission 57 mapping-scope
precondition); the language surface did not move and the decision is in
`BLOCKERS.md`.

**Worker**: missions 119-124 are DONE. The supervisor selects the next
`EXECUTABLE` mission, refuses any mission whose execution index is missing
(recorded `BLOCKED`, no worker call spent), and hands one mission to one worker
invocation. A worker EXECUTES `.agent/missions/<item-number>.md` and returns a
bounded structured receipt; Python owns every `.agent/` write, so a worker
cannot half-record a mission. There is no automatic diagnosis call, no automatic
retry, and no notification per mission — one completion summary per run, plus an
immediate alert only for a commander gate or a run that completed nothing. A
receipt's follow-up is a proposal: appended to the plan under
`CLAUDE_REVIEW` **and** a `PROPOSAL_MARKER` that makes it non-executable, so
the next run cannot pick it up. The run ends when the queue has no `EXECUTABLE`
item, or when `--max-missions` is reached; `--max-attempts` defaults to 1.

Next: **item 85** (deterministic formatter investigation), indexed at
`.agent/missions/85.md`. Item 84 is **DONE** — the first real Claude mission to
run end to end (Session 53). Verified as the next EXECUTABLE by
`python -m ine_agent.cli run --dry-run`.

## Current focus

- Session 57 recorded mission 86 (``EXECUTABLE` — **Code actions/refactoring investigation.** Research`) as done: Investigated Ine code actions and recorded the proposal in .agent/NOTES.md: the statement-to-text-rewrite safety map, a seven-candidate cost table, and a proven `extract to group` rule. A scratch probe (.tmp/code-actions-probe/probe.py) implements extract_to_group as descending line-range edits and verifies 8 accepted cases for identical entities/properties/relationships plus byte-identical render
- Next executable work: `EXECUTABLE` — **Editor testing infrastructure.** Set up extension (item 87).
- This file is position-only: the per-mission detail is the receipt in `.agent/RUN_REPORTS.md`, the block in `.agent/HISTORY.md`, and the index at `.agent/missions/86.md`.

## Health

- Recording is deterministic: PLAN tags, this head, HISTORY and NOTES are written by `state.record_mission_outcome` from the worker's structured receipt, not by the model in prose.
- Last recorded verification for mission 86: python .tmp/code-actions-probe/probe.py: all cases verified: 8 edits, 7 refusals, 0 failure(s)
- Known caveats and the rest of the project's position are in the sections below and are not rewritten by a mission.

## Pipeline & entry points

- `src/ine/lexer.py` → `parser.py` → `semantic.py` → `backend_*.py`.
- `src/ine/cli.py`: `ine <file>.ine [-o out.html]`, `ine <file>.ine
  --native`, `ine <file>.ine --visual`, `ine --dict [kind|file]`.
- `src/ine/autocomplete.py`: stdin JSON-lines `{buffer, line, column, id?}`
  → stdout `{id?, line, column, context, items[]}` per line; 4 contexts
  (`make`→makeable, kind→members/properties, `value`→shape options,
  inside→parents). One-shot and streaming both work; worker persists across
  requests.

## Dictionaries (15 files)

- Base kinds (makeable): page, header, navigation, logo, container,
  card-group, card, button, banner, image, section, footer, title.
- Concepts: universal (content properties `title`/`text`, both shaped
  `"text"` in a `properties` block), ambient (viewport `width`/`height` →
  `"length"`).
- Reader API: `makeable`, `find`, `properties_for`, `value_hint`,
  `suggest` (`Suggestion(text, source, note)`), `for_model`, `members`
  (structural children), `parents` (reverse containment),
  `ValueShape(type, choices)` + `value_shape(kind, prop)`.

## Editor prototype

- `editor/vscode-ine/`: extension.js is a pure proxy (zero Ine vocab);
  DictionaryWorker spawns `python <root>/src/ine/autocomplete.py`, FIFO
  queue, 4 s timeout, respawn on death, `" "` + ASCII-letter triggers,
  snippets: `value_shape == "text"` → `SnippetString('title "${1}"')`.

## ine-agent (developer tooling, Session 32)

- `python src/ine_agent/cli.py run` (or `ine-agent run` once installed):
  reads `.agent/`, applies the PLAN selection rule (first EXECUTABLE item,
  in list order; `DONE`/`BLOCKED` items are not executable — Session 37
  fix), launches exactly one worker per cycle (sequential, never
  concurrent), rereads `.agent/` state after each cycle, and stops on the
  defined conditions. Exit codes: 0 = normal/no-work, 1 = error/bounded
  stop, 2 = HUMAN_DECISION_REQUIRED gate. The marker is recognized
  line-based (it must START its own line) in BOTH the worker transcript
  and `.agent/` files, so prose that merely quotes the guardrail never
  trips the gate (Session 38).
- Routing is deterministic: OpenCode is the implementation worker
  (`opencode run <prompt> --pure --dir <root>`); Claude is used only for
  `CLAUDE_REVIEW`-tagged tasks (review step, never implementation). No AI
  task classifier. Optional `--dry-run` prints the resolved profile, the
  resolved command, the budget and the index state without launching
  anything.
- The run drains the queue: it ends when the next mission lookup finds
  nothing `EXECUTABLE`, when the mission set is exhausted, or when
  `--max-missions` is reached — not on a cycle or wall-clock counter, so a
  mission given several attempts is still counted once. A worker classifies
  itself in-band and is never called a second time to explain itself; global
  usage counters are labelled as not-this-run's-cost. Notifications are one
  completion summary per run (completed / failed / blocked / deferred /
  refused, plus proposals filed), with an immediate alert only for a
  commander gate or a run that completed nothing. A receipt's follow-up is
  filed as a proposal: a `CLAUDE_REVIEW` plan item carrying
  `PROPOSAL_MARKER`, which `Task.executable` treats as non-executable.
- Files: `src/ine_agent/` — `state.py` (PLAN/STATE/HISTORY/BLOCKERS
  readers + append-only recorders: remarks, `mark_blocked`,
  `record_resolution`, `append_blocker`, run-report helpers, Task/Plan),
  `supervisor.py` (recording loop, stop conditions, prompt builders),
  `worker.py` (OpenCode/Claude subprocess workers + stubs),
  `notifier.py` (best-effort Windows balloon notifications; never raises),
  `usage.py` (warn-only observed-usage telemetry over `opencode.db`),
  `measure.py` (read-only re-measure harness over RUN_REPORTS + the ledger),
  `receipt.py` (the bounded structured receipt a worker returns), `profiles.py`
  (built-in + `.agent/workers.json` worker profiles, resolved by `doctor` and
  the dry run; the same file optionally carries `policy` and `verify`), `cli.py` (argparse entry, `--root`, `--worker`, `--model`,
  `--dry-run`, `--max-missions` (alias `--cycle-limit`, unset by default),
  `--max-attempts` (unset: the policy decides, and an explicit flag wins),
  `--max-failures`, `--stall-limit`,
  `--quiet`/`--verbose`, `--usage-warn-requests`, `--notify`; `doctor`,
  `measure` and `resolve` subcommands), `budget.py` (validated policy +
  defaults, and the over-budget report), `verify.py` (configured local checks
  run only after a `done` receipt; no model, no retry, bounded tail, 600s
  timeout).
  Guardrails in the prompts: never invent semantics, never unblock
  evidence-gated work, never modify DECISIONS.md, keep scratch under
  `.tmp/` and nothing durable there (AGENTS.md, "Repository containment").
  Since Session 46 the two prompts are split: `impl_prompt` embeds
  `.agent/WORKER_PROMPT.md` (execute the mission's index; do not research,
  re-plan or re-scope) plus the index itself, and the planner's
  `.agent/MISSION_PROMPT.md` is no longer embedded — a mission with no
  index at `.agent/missions/<item-number>.md` is refused, recorded BLOCKED
  and deferred, spending no worker call.
- One mission costs one process, and the guarantee is enforced rather than
  assumed: a mission completed by receipt alone, without a `PLAN.md` edit, is
  added to the run's deferred set so the re-read plan cannot re-pick it.
  Regression-tested (`test_a_receipt_completion_costs_exactly_one_invocation`,
  which fails with the fix reverted).
- Durable state the loop keeps outside the plan: `.agent/RUN_REPORTS.md` (one
  block per run, including usage deltas when a worker reports them) and
  `.agent/attempts.json` (per-mission failures: `attempts`, `runs`,
  `classification`, `reason`, `outcome`, `updated`). A mission that has failed
  in `max_failures` different runs (default 3, `--max-failures 0` disables) is
  parked and not re-picked until it is rewritten or its entry is deleted; the
  ledger is pruned at run start to the identities the plan still offers as
  executable, and completing a mission clears its entry. `--stall-limit`
  (default 3, 0 disables) stops a run after that many cycles that neither
  completed nor blocked anything and changed no file outside `.agent/`.
- Blocked / failed / HUMAN_DECISION_REQUIRED missions are recorded durably
  (plan remark + BLOCKERS entry + run report, original text preserved) and
  deferred for the rest of the run: independent executable work continues
  (Session 41). Run report: `.agent/RUN_REPORTS.md`; notifications reference
  it. Exit codes: 0 clean, 1 a mission failed, 2 pending commander gate.
- Subprocess capture is explicitly UTF-8-safe: `CliWorker._capture` decodes
  stdout/stderr with `encoding="utf-8", errors="surrogateescape"` instead
  of the locale default (cp1252 on Windows crashed on non-CP1252 bytes like
  UTF-8's 0x90). Applies to the OpenCode and Claude worker branches alike.
- Worker env overrides (`INE_AGENT_OPENCODE` / `INE_AGENT_CLAUDE`) are
  command lines, not bare executable names — see "Session 42 continuation:
  worker override + bridge permission" in HISTORY.md.

## Known caveats

- `ine --dict universal` (pseudo-entry) shows `a text` for title/text since
  universal.json now owns a `properties` block — valid, intended side
  effect.
- No value kinds beyond `text` (and ambient `length`) are declared — no
  evidence supports more.
- `button label` is dictionary-suggested, but renderers surface `text`.
- `group` and `say` at statement start are guarded in autocomplete.py:67
  (return no items), and `context()` on the purposes/kind line stays within
  the word under the cursor. The editor UI does not yet suppress
  completion popups on those lines, but the engine returns nothing there.

## Coverage (reconciled, Session 31)

All property and containment usage across every real program (hello, topbar,
hero, cards, dictionary-demo) is fully covered by the dictionary. Entity
aliases (`main` → `container`, `hero` → `banner`) resolve cleanly. `search`,
`subtitle`/`description`, and the WORKBOOK `button inside header` layout
are evidence-gated proposals that remain correctly undeclared — see
`.agent/BLOCKERS.md`. Custom domain vocabulary (`person`/`name`/`age` in
alice.ine) is a scope boundary of the advisory dictionary, not a gap.

## Records

- WORKBOOK.md §1–§41 (decisions/architecture).
- SESSION_STATE.md Sessions 1–30 (§12 tracks DONE bullets; Session 30 DONE).
- RESEARCH_LOG.md, LANGUAGE.md (spec), README.md.
- PLAN.md expanded Session 34: 30 active missions (10 executable quick wins, 20 research).
- `.agent/RUN_REPORTS.md` (one block per supervised run) and
  `.agent/attempts.json` (durable per-mission failure ledger, Session 46) are
  the loop's own records; `python -m ine_agent.measure` re-reads both.
- `.agent/WORKER_PROMPT.md` (execution contract) and
  `.agent/MISSION_PROMPT.md` (planning contract) are the two prompts; the
  planner's output is `.agent/missions/<item-number>.md`. Session 46 moved
  the per-session narrative out of this file into `.agent/HISTORY.md`, which
  is now append-only; STATE.md is bounded by test
  (`ControlPlaneHealthTests.test_state_md_stays_bounded`).
