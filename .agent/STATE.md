# .agent/STATE.md

Current ground truth as of Session 51. Position, not narrative: what stands
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

Next: **item 84** (editor semantic diagnostics), which needs an index written at
`.agent/missions/84.md`. Verified as the next EXECUTABLE by
`python -m ine_agent.cli run --dry-run`.

## Current focus

The autonomous-worker arc (missions 119-125) is **complete and documented**.
What it produced, in one line: the supervisor hands one mission to one fresh
worker process, the worker executes a written index and returns a bounded
structured receipt, Python writes every record, and the run drains the queue on
its own. The flow a contributor uses is documented in `CONTRIBUTING.md`, the
architecture and its three rejected alternatives are in `DECISIONS.md`, and the
per-mission cost is measured in `NOTES.md` ("Mission 125 - What the handoff
costs, measured"): ~3 KB / ~65 lines per mission, one invocation per attempt,
no diagnosis call, one completion notification per run.

The next work is back on the language side. Per `run --dry-run` the next
EXECUTABLE item is **84** (editor semantic diagnostics), which needs an index at
`.agent/missions/84.md`. Items 85-94 remain EXECUTABLE behind it.

Constraints that hold for everything, and were paid for: the language surface
is commander-owned and has not moved since Session 42; every project artifact
lives in this repo (`.agent/` durable, `.tmp/` scratch, nothing durable in
`.tmp/`); the recording pass is part of the work, not a postscript. Three traps
worth carrying forward: `CLAUDE_REVIEW` is *executable* in this plan (a proposal
needs `PROPOSAL_MARKER` to stay inert); a run that refuses everything has a
tally of all zeros, so the refusal count must be reported separately; and a
tally assembled from single-outcome tests is not yet a contract — the two count
defects in mission 124 were only visible with a failed *and* a gated mission in
the same run.

## Health

- Test suite: **659 tests, 33 subtests** (`python -m pytest tests` from the
  repo root) — green: 659 passed, with **322** of the total in
  `tests/test_ine_agent.py` (including `PilotRunTests`, the end-to-end pilot:
  one request per mission, one completion summary, a lean prompt, no duplicated
  control-plane records, a terminating run). The tkinter `TclError` flake is
  tamed, not fatal: the display-guarded `VisualBackendTests` window tests catch
  a runtime `tk.TclError` and skip via `_render_window` instead of failing, so
  a load-triggered flake reports one `skipped` (pinned by
  `DisplayGuardTests.test_render_window_skips_on_runtime_tcl_error`).
- Control-plane guards are tests, not conventions: STATE.md bounded and
  position-only (no `## Session N` headings, under the byte/line ceiling) and
  its header session matching the latest HISTORY heading; every `BLOCKED` PLAN
  item cross-referenced in `BLOCKERS.md`; every NOTES finding mission having
  its NOTES section and back again; the plan tag on every numbered item exactly
  one of `EXECUTABLE` / `BLOCKED` / `DONE` / `CLAUDE_REVIEW` (a compound tag
  parses as no tag and breaks mission selection).
- Goldens (hello, topbar, hero, cards) byte-identical; `dictionary-demo.ine`
  renders. Dictionary JSON ships at `src/ine/dictionary/*.json` (resolved via
  `importlib.resources` with a `__file__` fallback;
  `[tool.setuptools.package-data] ine = ["dictionary/*.json"]`); the root
  `dictionary/README.md` stays as the schema guide.
- Environment: Windows / PowerShell 5.1, Python 3.13.14, node v24.17.0.
  Repo-root `ine.py` is a tracked shim that inserts `src/` into `sys.path`
  (it shadows the `ine` package — the engine run as a script self-prepends
  `src/`).
- PowerShell content cmdlets (`Get-Content` / `Set-Content` / `Out-File`)
  corrupt Unicode in this repo, and a backtick in a double-quoted
  here-string is an escape character — both have cost time. Use `edit` /
  `write`, or Python with an explicit `encoding="utf-8"`. Scratch goes in
  `.tmp/`.

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
  the dry run), `cli.py` (argparse entry, `--root`, `--worker`, `--model`,
  `--dry-run`, `--max-missions` (alias `--cycle-limit`, unset by default),
  `--max-attempts` (default 1), `--max-failures`, `--stall-limit`,
  `--quiet`/`--verbose`, `--usage-warn-requests`, `--notify`; `doctor` and
  `resolve` subcommands).
  Guardrails in the prompts: never invent semantics, never unblock
  evidence-gated work, never modify DECISIONS.md, keep scratch under
  `.tmp/` and nothing durable there (AGENTS.md, "Repository containment").
  Since Session 46 the two prompts are split: `impl_prompt` embeds
  `.agent/WORKER_PROMPT.md` (execute the mission's index; do not research,
  re-plan or re-scope) plus the index itself, and the planner's
  `.agent/MISSION_PROMPT.md` is no longer embedded — a mission with no
  index at `.agent/missions/<item-number>.md` is refused, recorded BLOCKED
  and deferred, spending no worker call.
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
