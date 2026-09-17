# .agent/STATE.md

Current ground truth as of autonomous Session 41
(Missions 42-53 of the 40-mission self-test batch are DONE: dictionary
advisory guards, autocomplete context fixes, the engine `validate` query,
CLI error columns, the multi-line buffer context matrix, malformed-payload
protocol tests, the prefix-completion research finding, control-plane plan
hygiene, the exit-code contract, crash-then-continue resilience,
attempts-reset-on-progress, and the evidence-gated vocabulary veto; Mission
111 is DONE (autonomous-worker request frugality + observed-usage
telemetry); Missions 64-65 are DONE (members/parents symmetry test +
backend metadata contract / golden guard) and the commander's notification
polish is wired (streamlined `Ine · …` banners, round-tile icon, chime);
the next EXECUTABLE is item 54, the pricing-page evidence experiment).

## Current focus

Autonomous improvement and stabilization of the Ine dictionary/editor system.
Session 41 continues the 40-mission self-test batch: 42-53 are DONE (items
42-47 implementative; item 48 research-only; item 49 the plan-hygiene test;
item 50 the exit-code contract; item 51 crash-then-continue resilience; item
52 attempts-reset-on-progress; item 53 the evidence-gated vocabulary veto —
see "Session 41 continuation" below). Mission 111 is DONE: autonomous-worker
request frugality (single-mission worker scope, distilled STATE snapshots,
orchestrator division of labor) plus warn-only observed-usage telemetry
(`src/ine_agent/usage.py`, `--usage-warn-requests`, per-run usage lines in
RUN_REPORTS.md). Commander's notification polish is wired: every banner is a
terse `Ine · <status>` title (task started/done/stuck/blocked/failed,
decision required, run complete, usage warning) with the mission headline as
the only body line; the popup uses the round-tile window icon
(`assets/icon.png`) and plays a soft chime (`assets/chime.wav`). Missions
64-65 (reliability nets) are DONE: members/parents exact-inverse test +
backend metadata contract/golden guard. Item 47 was found still tagged
`EXECUTABLE` in PLAN.md despite Session 40 implementation — corrected
(record gap). Next executable per the selection rule: item 54 (pricing-page
evidence experiment). Session 37 closed the research missions (11-30):
evidence-collection experiments (dashboard, form), a vocabulary
reconciliation, responsive / styling / CI / packaging / editor-architecture /
native-backend assessments (all findings in `.agent/NOTES.md`), a worker
stress test, and the ine-agent DONE-stop bug fix. Item 7 remains BLOCKED on
evidence (still no `choice` value or WORKBOOK decision).

## Health

- Test suite: **383 passing** (`python -m pytest tests`, 9 subtests) —
  lexer, parser,
  semantic, dictionary, CLI, autocomplete, extension protocol, ine-agent.
  Mission 111 added `UsageTests` (6) and CLI usage-warn tests (2) and
  pinned stale Session 41 notifier tuple/arg assertions; the notification
  polish added chime/icon-template, `default_chime_path`, tile-preference
  and task-stuck tests (NotifierTests, 101 in test_ine_agent.py); Missions
  64-65 added the members/parents exact-inverse guard and the
  `BackendMetadataContractTests` (3). The suite also
  carries `EvidenceGateTests` (4), `CrashContinueTests` (3),
  `ExitCodeContractTests` (9), `NotifierTests` (8),
  `Session41RecordingTests` (6), `Session41SupervisorTests` (4),
  `ResolveCliTests` (2), `PlanHygieneTests` (4), and the Mission 42-47
  additions. Mission 48 is research-only, no tests.
- Goldens (hello, topbar, hero, cards) **byte-identical**; `dictionary-demo.ine`
  renders.
- Environment: Windows / PowerShell 5.1, Python 3.13.14, node v24.17.0.
  Repo-root `ine.py` is a tracked shim that inserts `src/` into `sys.path`
  (it shadows the `ine` package — engine run as a script self-prepends `src/`).
- Full-suite runs occasionally show a transient tkinter `TclError` in
  `VisualBackendTests` under load; the class passes in isolation and on rerun
  (pre-existing flake, unrelated to these changes).

## Pipeline & entry points

- `src/ine/lexer.py` → `parser.py` → `semantic.py` → `backend_*.py`.
- `src/ine/cli.py`: `ine run <file>`, `ine render <file> -o out.html`,
  `ine visual <file>`, `ine --dict [kind|file]`.
- `src/ine/autocomplete.py`: stdin JSON-lines `{buffer, line, column, id?}`
  → stdout `{id?, line, column, context, items[]}` per line; 4 contexts
  (`make`→makeable, kind→members/properties, `value`→shape options,
  inside→parents). One-shot and streaming both work; worker persists across
  requests.

## Dictionaries (15 files)

- Base kinds: page, header, section, hero, container, card-group, card,
  card-1, copy, footer.
- Concepts: universal (content properties `title`/`text`, both shaped
  `"text"` in a `properties` block), ambient (viewport `width`/`height` →
  `"length"`), entity (the run), misc (logo, link, thumbnail), wizard.
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
  task classifier. Optional `--dry-run` prints the first executable task
  without launching anything.
- Files: `src/ine_agent/` — `state.py` (PLAN/STATE/HISTORY/BLOCKERS
  readers + append-only recorders: remarks, `mark_blocked`,
  `record_resolution`, `append_blocker`, run-report helpers, Task/Plan),
  `supervisor.py` (recording loop, stop conditions, prompt builders),
  `worker.py` (OpenCode/Claude subprocess workers + stubs),
  `notifier.py` (best-effort Windows balloon notifications; never raises),
  `cli.py` (argparse entry, `--root`, `--worker`, `--dry-run`,
  `--cycle-limit`, `--max-attempts`, `--notify`; `resolve` subcommand).
  Guardrails hard-coded in prompts: never invent semantics, never unblock
  evidence-gated work, never modify DECISIONS.md, keep temp artifacts under
  `.tmp/`.
- Blocked / failed / HUMAN_DECISION_REQUIRED missions are recorded durably
  (plan remark + BLOCKERS entry + run report, original text preserved) and
  deferred for the rest of the run: independent executable work continues
  (Session 41). Run report: `.agent/RUN_REPORTS.md`; notifications reference
  it. Exit codes: 0 clean, 1 a mission failed, 2 pending commander gate.
- Subprocess capture is explicitly UTF-8-safe: `CliWorker._capture` decodes
  stdout/stderr with `encoding="utf-8", errors="surrogateescape"` instead
  of the locale default (cp1252 on Windows crashed on non-CP1252 bytes like
  UTF-8's 0x90). Applies to the OpenCode and Claude worker branches alike.

## Session 39 changes

1. **Dictionary warning on skip** (src/ine/dictionary.py `_load`). Each
   skipped file now emits exactly one `warnings.warn` naming the file and
   the reason (cannot read / invalid JSON / not a JSON object / missing
   `term`); the silent-skip contract is preserved (a broken file never
   raises). Extended the malformed-JSON test to assert one warning per bad
   file and none for the valid entry. Full suite emits no stray warnings.
2. **`dictionary/README.md`** schema guide written (field-reference and
   value-shape tables, ambient + universal examples, "add a new kind"
   walkthrough verified against `ine --dict`).
3. **README misstatement fixes** (Mission 18): fake dictionary-JSON
   illustration replaced with card.json field-for-field; "151 passing" →
   `python -m pytest tests` 284 passing; multiplicity prose now leads with
   what IS implemented; three non-parsing intent-vs-implementation rows
   replaced with verified-parsing syntax (`logo inside header`,
   `footer position "bottom"`, `card padding "comfortable"`).
4. **`DictionaryIntegrityTests`** (tests/test_ine.py, 5 tests): reads the
   real `dictionary/*.json` and asserts term+meaning present, terms unique,
   containment members resolve (or are in a documented scope boundary),
   `properties` values are valid `_shape_from` inputs, every makeable kind
   declares an `element`.
5. **`VocabularyCoverageTests`** (tests/test_ine.py, 3 tests): parses every
   real program in `examples/` + `.agent/experiments/`, expands group
   statements (`cards → card-1..n` kinds), and asserts every kind, property,
   and containment pair resolves through the dictionary or is in the
   documented custom-domain boundary (alice.ine `person`/`name`/`age`/
   `height`).
6. **CONTRIBUTING.md** rewritten with real Ine content (layout, pipeline,
   dictionary advisory rule, three CLI entry points, pytest command, the
   Session 25 freeze, `.agent/` conventions) while keeping the CoC/DCO
   sections.
7. This session's earlier Missions 31-35 implementation + tests:
   dictionary skip warnings, dictionary README, README fixes, integrity and
   coverage guards; full suite **292 passing** (was 284).
8. **LANGUAGE.md §7 + stale-claims sweep** (Mission 38). Retitled §7 from
   "as of Session 22" and added a lead-in clarifying value shapes, dictionary
   discovery, the JSON-lines editor protocol, and ine-agent are current
   features (not limits); README no longer prints a hardcoded test count
   (states the command instead); editor README verified current. No code or
   golden changes.
9. **CI display-guard + GitHub Actions** (Mission 39). Added `_has_display()`
   + `_skip_without_display` in tests/test_ine.py and applied the guard to
   all 7 window-creating tests in `VisualBackendTests` so a headless runner
   skips them instead of failing. Added `.github/workflows/ci.yml`
   (ubuntu-latest, xvfb + pytest, `xvfb-run -a python -m pytest tests`).
   New `DisplayGuardTests` (3 tests) proves the probe returns False when
   tk raises (monkeypatched) and True when it succeeds, and asserts every
   window test carries the guard. Full suite now **295 passing**.


## Session 41 changes

1. **Mission 49: control-plane plan hygiene.** Added `PlanHygieneTests`
   (tests/test_ine_agent.py, 4 tests) parsing the REAL `.agent/PLAN.md`
   Active section independently of `read_plan` (to catch structural drift):
   Active items numbered 1..N in strict increasing order with no gaps; every
   tag is a convention tag (`EXECUTABLE` / `BLOCKED` / `DONE` /
   `CLAUDE_REVIEW` / unmarked); every `BLOCKED` item (7, 58, 59, 61) is
   cross-referenced by number in `.agent/BLOCKERS.md`; and
   `first_executable()` returns an item when executable work exists and None
   when none does. Verified: 4/4 pass; full suite 328 passing; goldens
   byte-identical.
2. **Reconciled six stale `SupervisorTests` against the in-tree recording-loop
   supervisor (Session 41 refactor, previously unrecorded).** The supervisor
   now prints the no-work message lowercase (the `_no_work()` capitalized
   form only appears on the no-work-at-start path), a HUMAN_DECISION_REQUIRED
   marker defers the mission (recorded, BLOCKED, or left DONE) and the final
   message is the generic "missions remain held for commander judgment;
   independent work completed." rather than naming the task, and a failing
   worker is recorded + deferred rather than retried to `max_attempts`.
   Updated: `test_executable_work_invokes_the_worker`,
   `test_live_worker_output_is_relayed_and_summarized`,
   `test_prose_marker_mention_does_not_stop_the_loop`,
   `test_review_prose_marker_does_not_stop_the_loop` (message casing),
   `test_own_line_marker_still_stops_and_reports_fresh_tag` (asserts exit 2,
   generic hold message, no abandoned-EXECUTABLE phrasing, and the plan shows
   the fresh `DONE` tag), and `test_worker_failure_does_not_retry_forever` →
   `test_worker_failure_is_recorded_deferred_and_stops_with_error` (1 call,
   exit 1, "recorded and deferred" message — failures no longer retry).
3. **Record gap fix: PLAN item 47 tagged `DONE`.** STATE/HISTORY documented
   Mission 47 (malformed-payload protocol robustness) as implemented and
   verified in Session 40, but PLAN.md still carried it as `EXECUTABLE`, so
   the selection rule would have re-picked finished work. Corrected the plan
   record (implemented + 7 ProtocolTests + the `_respond` id-echo fix).
   After this, `first_executable()` == item 50 (exit-code contract).
4. **Verification.** Full suite: **328 passing** (was 324; +4
   `PlanHygieneTests`), no new failures, goldens byte-identical, `.tmp/`
   empty after the run.

## Session 41 continuation: crash-then-continue resilience (Mission 51)

1. **Mission 51: crash-then-continue resilience.** Added
   `CrashContinueTests` (tests/test_ine_agent.py, 3 tests) pinning the
   combined case Mission 29(b) left untested — a worker exits nonzero BUT
   its side effect already advanced the plan (marked its task DONE before
   failing). The supervisor's `_outcome` re-reads the plan after the cycle
   and checks `fresh.tag == "DONE"` before the exit code, so the identity
   change is classified as `done` (not `failed`/`stuck`): attempts reset to
   0, the loop runs the NEXT EXECUTABLE task, and the run exits STOP_OK
   rather than bounded-stopping on the crashed worker. Tests:
   - `test_crash_after_marking_done_continues_not_bounded_stop` — two
     tasks, first worker exits 1 after marking DONE; second worker runs to
     completion; no "mission failed"/"deferred"/bounded-stop output;
     on-disk DONE tag preserved; run exits 0.
   - `test_crash_after_advance_confers_a_full_attempt_budget` — razor:
     `max_attempts=1` with crash+advance + a second task; if the crash had
     been counted as a stuck attempt the second task would never run (only 1
     call); the test asserts 2 calls, proving attempts were reset.
   - `test_run_report_records_advanced_crash_as_done` — durable report
     contains `"- [cycle 1] DONE"` and `"- exit: 0"`.
   No supervisor code change — the behavior was already correct, but
   untested. Verified: full suite **359 passing** (was 356); goldens
   byte-identical; `.tmp/` clean.

## Session 41 continuation: attempts reset on progress (Mission 52)

1. **Mission 52: attempts reset on progress.** Added
   `AttemptResetTests` (tests/test_ine_agent.py, 3 tests) pinning the
   attempts semantics behind the Mission 30 premature-stop fix. The
   supervisor's `_outcome` already classes a cycle that makes NO plan
   progress as `stuck` (increments `attempts`) and any plan change as
   done/blocked/failed/human (resets `attempts` to 0) — now locked:
   - `test_alternating_progress_and_stuck_runs_to_completion` — four-cycle
     worker alternating no-plan-progress with progress; without the reset
     the attempts would accumulate and bounded-stop the loop before the
     last task; with it the run completes (exit 0, 4 calls); the run
     report's per-cycle classification is asserted.
   - `test_progress_after_stuck_gives_the_next_task_fresh_attempts` — a
     done cycle resets the counter, so the next task's own stuck phase gets
     a full `max_attempts` budget.
   - `test_reset_does_not_disable_the_bounded_stop_guard` — a reset grants
     no immunity: genuine consecutive stuck cycles after a reset still
     accumulate and bounded-stop at `max_attempts` (exit 1, 3 calls).
   No supervisor code change. Verified: `test_done_marked_task_does_not_stop_the_loop`
   and the attempt-limit tests unchanged; full suite **362 passing** (was
   359); goldens byte-identical.

## Session 41 continuation: evidence-gated vocabulary veto (Mission 53)

1. **Mission 53: evidence-gated vocabulary veto.** Added
   `EvidenceGateTests` (tests/test_ine.py, 4 tests) reading the real reader
   API (`find`, `makeable`, `suggest`, `properties_for`, `members`,
   `value_shape`) to lock the Session 31/37 reconciliation forward:
   - `test_vetoed_kinds_are_not_declared` — `search`, `subtitle`,
     `description`, `input`, `table`, `chart` are undeclared: `find` is
     None, none are `makeable`, and `suggest(kind)` is empty.
   - `test_vetoed_properties_are_not_declared_anywhere` — `subtitle` /
     `description` / `search` appear as properties on no makeable kind
     (WORKBOOK §36 re-grounded only `title`/`text`).
   - `test_button_is_not_a_header_member` — `button` is not in
     `members("header")`; the evidence remains `button inside section`
     (dictionary-demo.ine), not WORKBOOK L544's proposal.
   - `test_card_group_layout_stays_unknown` — The Session 33 revert is
     locked: `value_shape("card-group", "layout")` is `unknown` with no
     choices until the first `choice` value (PLAN item 7) lands.
   These are the "only fails if someone unblocks a decision without commander
   approval" guard. Verified: full suite 366 collected / 364 passing (2
   transient tkinter flakes, green in isolation); goldens byte-identical.

## Session 41 continuation: Windows notifications + recording tests

1. **Windows notifications for the supervisor** (commander directive). New
   `src/ine_agent/notifier.py`: `NullNotifier` (no-op),
   `WindowsPowerShellNotifier` (hidden `powershell.exe -EncodedCommand`,
   persistent always-on-top WinForms popup, never raises),
   `notifications_enabled()` (flag
   `--notify` or env `INE_AGENT_NOTIFY=1/true/yes/on`) and
   `create_notifier()`. Banners are streamed to terse `Ine · <status>`
   titles — `Ine · task started`/`done`/`stuck`/`blocked`/`failed`,
   `Ine · decision required`, `Ine · run complete`, `Ine · usage warning` —
   with the mission headline as the only body line; the popup shows the
   round-tile window icon (`assets/icon.png`, preferred over the square
   logo; an `___ICON___` token with fallback) and plays a soft chime
   (`assets/chime.wav`, `System.Media.SoundPlayer` async `Play()` on an
   `___CHIME___` token). Every
   notification points at the durable run report. Notifications are
   best-effort: they never stop or delay execution.
2. **Durable run report** `.agent/RUN_REPORTS.md` (= `run_report_path()`).
   `begin_run_report` / `append_run_report` / `end_run_report` in state.py
   log the command, per-cycle missions, exit code, and summary; it is the
   source of truth the notifications link to.
3. **Recording discipline** (state.py, all append-only, original text
   preserved): `append_item_remark`, `mark_blocked` (only tags non-DONE
   items BLOCKED; a DONE item keeps its tag), `record_resolution` (adds
   `> resolution (commander): ...` remark, never rewrites the blocker), and
   `append_blocker` (appends under `## Blocked during autonomous runs` in
   BLOCKERS.md without touching existing entries). Fixed an in-session bug
   where `_rewrite_plan` applied the tag rewrite after appending the remark,
   overwriting the remark with a duplicate item line.
4. **Supervisor recording loop.** A mission that blocks or fails is recorded
   and deferred (`Plan.first_executable(skip=...)`), so independent
   executable work continues; the loop no longer retries a failing mission.
   Exit codes: 0 = clean, 1 = any mission failed this run, 2 = pending
   commander gate. Clean completion prints the standard "No executable work
   remains. / ine-agent stopped normally." both for the start-of-run and
   post-loop paths.
5. **CLI `resolve` subcommand.** `ine-agent resolve [--root] MISSION
   BLUEPRINT` records a commander resolution as a new remark under the first
   BLOCKED mission whose first line contains MISSION (case-insensitive);
   original blocker text is preserved.
6. **Tests.** `NotifierTests` (5: null/selection/env/non-Windows/missing
    powershell/timing), `Session41RecordingTests` (6: remark/mark_blocked/
    done-preserve/resolution/missing-item/blocker/run-report roundtrip),
    `Session41SupervisorTests` (4: blocked/failed/human defer + independent
    work continues + notifications + run-report written), `ResolveCliTests`
    (2). Seven stale `SupervisorTests` updated to the new deferred/recorded
    contract. Full suite: **347 passing** (was 328), goldens byte-identical.

## Session 41 continuation: exit-code contract (Mission 50)

1. **Mission 50: exit-code contract across stop classes.** Added
   `ExitCodeContractTests` (tests/test_ine_agent.py, 9 tests) pinning the
   documented supervisor exit-code mapping (Mission 29 confirmed these
   intentional; now regression-locked) with literal numeric assertions
   against the `STOP_*` constants:
   - `STOP_OK` (0): no-executable-work; dry-run; all-tasks-completed.
   - `STOP_ERROR` (1): bounded stop via the attempts limit (stuck worker,
     `"could not advance the plan"`, exactly `max_attempts` worker calls);
     bounded stop via the cycle limit (`"maximum of N worker cycle"`); and
     a worker failure (recorded + deferred, exit 1).
   - `STOP_HUMAN` (2): worker-output own-line marker; a pre-existing
     STATE.md gate (no worker launched); and a mid-run gate appearing from a
     worker's side effect (no further worker runs).
   Every test also asserts the durable run report's `- exit:` line matches
   the in-memory code, so the commander-facing record and the return code
   cannot drift apart. All reuse the existing `make_root` /
   `plan_containing` / `StubWorker` fixtures — worker_factory injection, no
   subprocess agents. This class closes the one gap the older tests left
   open: the attempts-limit stop path had no positive pin (only the negative
   assertion in `test_done_marked_task_does_not_stop_the_loop`).
2. **Verification.** `python -m pytest tests/test_ine_agent.py -k
   ExitCodeContract` = 9 passed; `tests/test_ine_agent.py` = 82 passed; full
   suite **356 passing** (was 347), goldens byte-identical, `.tmp/` clean
   after the run. PLAN item 50 tagged `DONE`; `first_executable()` == item
   51 (crash-then-continue resilience).

## Session 40 changes

1. **Mission 42: alice.ine custom-domain build guard**. Added
   `AliceCustomDomainTests` (tests/test_ine.py, 4 tests) reading the REAL
   `examples/alice/alice.ine`: (a) it builds through the full pipeline and
   executes to exactly `["Alice", 25, 1.7]` (entity `alice` / kind `person`);
   (b) the HTML target produces nothing today — `build()` raises BackendError
   and writes no file (alice.ine is a native/`say` program; this pins the
   actual output shape rather than inventing an HTML one, per the mission's
   verify clause); (c) `for_model` contributes nothing for the custom domain
   (companion to `test_for_model_skips_unknown_kinds`); (d) an ordinary page
   program (hello.ine) still yields 11 suggestions. Note: the mission text
   said "renders the intended HTML" — that is a misstatement (alice.ine never
   rendered HTML); the verify clause ("assert it, don't invent it") was
   followed and the discrepancy is recorded in PLAN item 42.
2. **Verification.** `python -m pytest tests/test_ine.py -k AliceCustomDomain`
   = 4 passed; full suite 300 collected / 298 passed (2 pre-existing
   `VisualBackendTests` tkinter flakes under load, green in isolation —
   unchanged, documented flake); goldens + EndToEnd byte-identical.
3. **Mission 43: complete `make` statement starts no context.** In
   `src/ine/autocomplete.py` `context()`, added: when `words[0] == "make"`
   and a second word is present, return None (autocomplete.py:67). This
   kills the Mission 14 misclassification where `make page ` / `make page
   # note ` produced a bogus `value` context (kind_word "make") with empty
   items. Tests: repurposed
   `test_cursor_after_inline_comment_misclassifies_but_is_graceful` →
   `test_cursor_after_inline_comment_is_no_context` and added
   `test_complete_make_statement_starts_no_context` (cases `make page `,
   `make hero banner `, `make page # note `, `make 3 card ` → None while
   `make p` / `make he` stay `kind`). Verified: 67 autocomplete tests pass
   incl. the end-to-end editor-flow integration test unchanged; full suite
   301 collected / 300 passing (1 transient tkinter flake green in
   isolation); goldens byte-identical.
4. **Mission 44: engine `validate` query.** `src/ine/autocomplete.py` now
   short-circuits queries carrying `{"validate": true, ...}` through a new
   `_validate()` (lex + parse only — never semantic, so the dictionary
   stays advisory). Responses are `{"validate": true, "diagnostics":
   [...]}` with `{line, column, message}` for LexError and `{line, message}`
   for SyntaxError (0-based, matching the completion protocol; `column`
   omitted when the parser has none); clean/empty buffers return `[]`; the
   request id is echoed. `ValidateTests` (8) cover clean/empty, unterminated
   string, unexpected-character column, syntax error, distinct shape, id
   echo, and live-subprocess validate-then-completion liveness. Verified:
   75 autocomplete tests pass; full suite 309 passing; goldens
   byte-identical.
5. **Mission 45: CLI error-column fix.** `_report_error` in src/ine/cli.py
   now prints `(line L, column C)` when the error carries a `column`
   attribute (LexError), and keeps the existing `(line L)` format for
   syntax/semantic/backend errors without a column; the message text is
   unaltered. New `CliErrorTests` (tests/test_ine.py, 3 tests): lex error
   asserts column appears; syntax error asserts line-only format; message-
   preservation test. Verified: full suite 312 passing; goldens byte-
   identical.
6. **Mission 46: multi-statement buffer context matrix.** Added
   `BufferContextTests` (tests/test_autocomplete.py, 5 tests) locking the
   buffer-scanning contract of `resolve_kind`: entities declared above the
   cursor resolve property (`make hero banner` / `hero titl`), value
   (`hero title `), and inside (`group cards = ...` above `cards inside `)
   contexts on later lines; multiplicity (`make 2 card` / `card-1 tit`)
   resolves the member kind; a `say` line yields no context while neighbors
   (`make p`, `page t`) still do. Verified: 80 autocomplete tests; full
   suite 317 passing; goldens byte-identical.
7. **Mission 47: malformed-payload protocol robustness.** Fixed `_respond`
   in src/ine/autocomplete.py to echo the request id even on error
   responses. Added 7 ProtocolTests: missing buffer/line/column keys
   default gracefully; null column uses the whole line; wrong-type line
   (`"x"`) becomes an error response; id echoed on error; and a live
   subprocess test feeding a series of malformed payloads (missing buffer,
   wrong-type line with id, validate over junk text) followed by a valid
   completion that still answers. Verified: 13 ProtocolTests pass; full
   suite 324 passing.
8. **Mission 48: character-based prefix completion research.** Finding in
   `.agent/NOTES.md` (`## Mission 48`). No code changes. The extension
   already triggers on every ASCII letter and space, and VS Code client-
   side filtering already ranks the full context lists against the typed
   word at the cursor — `make h` -> header, `page t` -> text/title — so
   engine-side prefix narrowing is not needed at list sizes <= 13 (Mission
   28: 300 queries in 0.18 s). Premise corrections: "hero" is not a
   makeable kind (hero.ine writes `make hero banner`); `card-1 t` on a
   single line returns empty by design. The one real friction is statement-
   start keyword completion (`make`/`say`/`group` never offered since no
   dictionary kind starts with `m`) — a syntax-keyword feature on the pure-
   proxy boundary, commander-scoped, and not required for prefix completion
   to work.

## Session 38 changes

1. **Human-gate false-positive fix** (src/ine_agent/state.py,
   supervisor.py). A live run stopped with "commander judgment is
   required for: `EXECUTABLE` — Improve context detection for `group`
   keyword." even though that mission was completed (autocomplete.py:67
   guard + tests match the plan; the same worker invocation marked all
   quick wins DONE). Root cause: `supervisor.run()` tested the worker
   transcript with a raw substring scan (`HUMAN_DECISION_REQUIRED in
   output`), and the phrase appears in the workers' own instructions —
   any transcript quoting the guardrail in prose halted the loop on a
   finished mission and mis-reported it to the commander.
2. **Fix.** New `output_marks_human_decision()` uses the same line-based
   marker convention already applied to `.agent/` files (the marker must
   start a line), wired into both the implementation-worker check and
   the Claude review pre-pass. `_human_stop` now reports the task's
   CURRENT plan tag (headline-keyed `_current_headline`), so a mission
   completed + marked DONE is never shown as an abandoned EXECUTABLE
   one. The file-based gate and the EXECUTABLE→DONE progress logic are
   unchanged.
3. **Tests.** +6: `output_marks_human_decision` unit tests (own-line
   detected, line-with-reason detected, prose mention ignored), a
   supervisor regression replicating the exact false positive (prose
   mention + mission completed → STOP_OK), own-line marker still stops
   and reports the fresh `DONE` tag, and Claude-review-branch parity.
   Full suite **284 passing**; live before/after reproduction confirmed
   the reported message (exit 2) before the fix and STOP_OK after.


## Session 38 (authoring addendum) — 40-mission self-test batch

Commander-directed: prepare the control plane for a large self-test of the
autonomous system by adding ~40 small, meaningful missions to `.agent/PLAN.md`
(Active section, items 31-70: 37 `EXECUTABLE` + 3 `BLOCKED`). The batch is
not a checklist: it is ordered so the loop can demonstrate
research -> decompose -> implement -> test -> verify -> record -> continue,
with research missions feeding later implementations and real-program
experiments feeding the evidence-gated decisions. Grounded entirely in
existing findings (`.agent/NOTES.md` Missions 11-30), the evidence gates in
BLOCKERS.md, the Session 25 freeze, and the goldens discipline — no Ine
syntax or semantics were invented and no frozen file was modified.

Major groups:

- **Dictionary health & discovery (31-35):** warn on skipped dictionary
  files (Mission 11 implementation), `dictionary/README.md` schema guide,
  README misstatement fixes (Mission 18), dictionary-integrity and
  vocabulary-coverage regression tests.
- **Documentation & reliability (36-42):** Ine-specific CONTRIBUTING.md,
  "what Ine can express today" inventory, LANGUAGE.md stale-claims sweep,
  display-guarded CI + GitHub Actions, experiments render guard,
  requires-python alignment, alice.ine custom-domain build guard.
- **Editor & autocomplete (43-48):** complete-`make`-statement context fix
  (Mission 14), engine `validate` query (Missions 16/26), CLI error-column
  reporting (Mission 17), multi-statement buffer-context and protocol-
  robustness test matrices, character-based prefix-completion research.
- **ine-agent — proving the loop (49-53):** plan-hygiene, exit-code
  contract, crash-then-continue, attempts-reset, and evidence-gated
  vocabulary veto tests.
- **Evidence experiments (54-55):** pricing page (link/navigation evidence)
  and settings panel (styling evidence), each written with only declared
  vocabulary and recorded as NOTES findings.
- **CSS/styling (56-59):** the stylable-surface audit (56) and the
  CSS-intent-to-HTML mapping proposal (57) are EXECUTABLE investigations;
  the two HTML-backend implementations (58, 59) are BLOCKED on a lifted
  freeze + commander scope.
- **Linking/navigation (60-62):** link-semantics (60) and dead-vocabulary
  (62) investigations are EXECUTABLE; the `link` implementation (61) is
  BLOCKED on a WORKBOOK/commander syntax decision + freeze lift.
- **Packaging & reliability nets (63-68):** dictionary data-in-package fix
  (Mission 25), members/parents symmetry test, backend-metadata contract +
  golden guard, editor README refresh, control-plane cross-file health,
  NOTES-to-PLAN cross-reference.
- **Self-test capstone (69-70):** full-suite + dry-run contract, and a test
  that README-documented commands actually run.

BLOCKED items 58/59/61 carry precise preconditions in `.agent/BLOCKERS.md`
(freeze lift + commander scope + the EXECUTABLE evidence missions/experiments
landing first). Validation performed NOW — the batch is NOT executed yet:
`read_plan` parses 70 items (37 EXECUTABLE, 4 BLOCKED, 29 DONE, sequential
1-70); `first_executable()` == item 31 ("Warn when a dictionary file is
skipped at load"); `ine-agent run --dry-run` prints item 31 and exits 0
without launching a worker; full suite 284 passing.

## Session 37 changes

1. **Research missions 11-30 closed** (all findings recorded in
   `.agent/NOTES.md` as `## Mission N` sections):
   - 11: invalid-dictionary feedback — silent-skip causes silent vocabulary
     loss; recommend `warnings.warn` per skipped file, no raise.
   - 12: value-shape consistency — shape production lives only in
     `_shape_from`; consistent; no change.
   - 13: `autocomplete.py` type hints (all public functions).
   - 14: cursor-edge-case tests (9) — incl. inline-comment misclassification
     note (`make page # note ` returns value context → empty, harmless).
   - 15: containment-completion tests (6) — corrected stale plan assumption
     (`copy → section`; `copy` is not a dictionary kind, so empty is right).
   - 16: editor diagnostics — no LSP; recommend minimal JSON-lines `validate`
     query → `DiagnosticCollection`; diagnostics stay UNDECIDED.
   - 17: error-message audit — worst messages + a systemic note that CLI
     drops the error column.
   - 18: documentation gap list — stale 151-test count (now 278), a fake
     dictionary-JSON example in README, misleading "Not Implemented Yet"
     multiplicity paragraph, intro examples using syntax that doesn't parse,
     no dictionary schema page / "how to add a kind" guide.
   - 19: dashboard experiment (`.agent/experiments/dashboard.ine`,
     builds+renders): default-name collisions for repeated structural kinds,
     multiplicity not reusable (always 1-indexed), no numeric/boolean/date
     values, no chart/table kinds, card-group only inside container, no
     status colors.
   - 20: form experiment (`.agent/experiments/form.ine`): zero field kinds,
     no label association, no interaction semantics — forms are unexpressible.
   - 21: vocabulary reconciliation → `.agent/BLOCKERS.md` (Session 37
     reconciliation section): 12 used kinds covered; evidence-gated gaps
     (fields, typed values, charts, multiplicity reuse) recorded.
   - 22: responsive — `narrow-class`/`narrow-layout` declared on card-group
     but read by no backend (backend freeze); recommendation: keep
     declarative, implement one narrow rule in HTML backend post-freeze.
   - 23: styling — backends emit only hard-coded styles; zero user styling
     today; smallest fix = wire declared `padding`/`corner-radius`/
     `border` metadata into HTML inline styles post-freeze.
   - 24: CI — no CI exists; suite is hermetic; tkinter window tests not
     display-guarded (fail headless); recommend GitHub Actions workflow
     with xvfb + display guards.
   - 25: packaging — `dictionary/*.json` is repo-root data NOT packaged;
     wheel installs yield an empty dictionary; need data-in-package +
     `importlib.resources` resolution.
   - 26: editor architecture — JSON-lines protocol is sufficient; add
     `validate` query now, hover cheap, formatting/LSP only after 3+
     features.
   - 27: native backend — verified with zig: `say` → C → `.exe` works;
     ALL UI statements silently dropped; research-only; no further build
     without a real user program.
   - 28: autocomplete worker stress — 300 subprocess requests in 0.18s, 0
     errors, survives malformed JSON; no fixes needed.
   - 29: ine-agent reliability audit — found the premature-stop bug (below);
     other stop conditions and crash handling are correct.
2. **ine-agent premature-stop fix** (`src/ine_agent/state.py`):
   `Task.executable` was `tag != "BLOCKED"`, so `DONE`-tagged tasks were
   re-picked; the supervisor stalled after `max_attempts` even when later
   EXECUTABLE missions remained. Now excludes `DONE` too (`tag not in
   ("BLOCKED", "DONE")`; unmarked/`CLAUDE_REVIEW` stay executable). Added
   `plugin_done_text` fixture + 3 tests (parse incl. DONE, skip-in
   `first_executable`, supervisor continues past a DONE-marked task).
   Verified against the real PLAN.md: `first_executable()` now returns
   item 28 (previously the first DONE item).
3. **Test count: full suite 278 passing** (was 266 mid-session + transient
   tkinter flake on one run; 278 collected now, `.tmp/` empty). This
   session contributed 15 autocomplete tests (CursorEdgeCaseTests 9 +
   ContainmentCompletionTests 6) and 2 ine-agent regression tests (plus one
   existing test extended).

## Session 36 changes

1. **Live-worker streaming for ine-agent** (worker.py, supervisor.py, cli.py):
   `CliWorker._stream` drains stdout/stderr with two reader threads
   (deadlock-safe on concurrent large payloads) and relays each line to an
   `on_line` callback while still returning the full captured output in
   `WorkerResult`, so streaming is purely additive. The supervisor prints a
   per-cycle banner (worker name + mission headline) and relays live lines,
   indented and ANSI-stripped by default; `--verbose` relays raw lines;
   `--quiet` suppresses live lines. `_safe_stdout` sets `backslashreplace`
   so relays never crash a cp1252 console on non-ASCII bytes.
   `StubWorker`/`TrackingStub` forward `on_line`. New `WorkerStreamingTests`
   cover relay correctness, 256 KiB x2 concurrent-pipe draining, and
   UTF-8/surrogateescape preservation through the streaming path.
   276 tests pass. No Ine language semantics or design decisions touched.

## Session 35 changes

1. **Quick wins 1-10 cleared.** Items 1-2 (group/say context) were already
   implemented in autocomplete.py (autocomplete.py:67 guard + tests); marked
   DONE with code references. Items 3, 5, 6, 8, 9, 10 implemented this
   session (tests + README + hints + schema docstring + end-to-end protocol
   test). Item 4 fixed the `.tmp/` leak (pytest autouse fixture; cleared 390
   stale dirs). Item 7 stays BLOCKED (first `choice` value needs evidence).
2. **Test count 247 → 252** (+5: three dictionary edge-case tests, malformed
   JSON loader test, editor-flow protocol integration test). `.tmp/` now
   stays empty after full runs.
3. **One corrected plan assumption:** the plan said `suggest()` on the
   ambient `viewport` "should return empty"; it actually returns the
   entry's declared property suggestions (width/height), which is what the
   editor needs. PLAN item 3 records this.

## Session 34 changes

1. **UTF-8-safe worker subprocess capture** (src/ine_agent/worker.py):
   `CliWorker.run`/`OpenCodeWorker.run` now decode captured stdout/stderr
   through a shared `CliWorker._capture` using
   `encoding="utf-8", errors="surrogateescape"` instead of the locale
   default. On Windows that default is cp1252 and crashed the live OpenCode
   run with `UnicodeDecodeError: 'charmap' codec can't decode byte 0x90`.
   The boundary is now explicitly UTF-8-safe and lossless (surrogate escape
   preserves unmatched bytes); the OpenCode and Claude worker branches
   behave identically. Added 3 regression tests in `WorkerEncodingTests`
   that pipe the crash bytes through a real subprocess for both workers.
   Ine language semantics and the supervisor/control-plane design are
   untouched. 247 tests passing.

## Session 33 changes

1. **Fixed `_shape_from` non-standard type handling** (src/ine/dictionary.py:162-173):
   - Previously returned `ValueShape("row")` for any string from `defaults`
   - Now validates against known value kinds (`"text"`, `"length"`)
   - Non-standard strings (like "row") return `ValueShape()` (unknown)
   - Hint strings remain accessible via `value_hint()` as intended
   - Added regression assertions `_shape_from("row") == ValueShape()` and
     `_shape_from("length") == ValueShape("length")`.

2. **`card-group layout` stays untyped (reverted).** A temporary change declared
   `"layout": "text"` in card-group's `properties` to "unblock editor completion".
   This contradicted the evidence rules: WORKBOOK §40–41 state only universal
   `title`/`text` are text-shaped ("every real program writes them quoted");
   `card-group layout` "is a single `"row"` string, not a known set" and takes
   bare words. Reverted the `properties` block; `value_shape("card-group",
   "layout")` returns `unknown` again, and the FIRST `choice` value stays on the
   evidence-gated BLOCKED item (PLAN item 7). The `_shape_from` fix from item 1
   makes the bad classification structurally unrepresentable, so it cannot
   silently reappear.

## Mission 111 — autonomous-worker request frugality + usage telemetry

Objective: cut unnecessary model requests on the free tier WITHOUT reducing
autonomy (commander-approved). Worker autonomy in-mission is unchanged;
mission selection and state bookkeeping moved to the deterministic
supervisor, and telemetry is warn-only.

- `supervisor.impl_prompt` now scopes a worker to ONE assigned mission per
  cycle ("execute it, STOP, report"), embeds a distilled STATE.md snapshot
  (current focus + health, ~1.6k chars) instead of whole-file context, and
  instructs a single final recording pass. `_distill_state` added. The
  worker no longer re-scans PLAN.md to self-select missions.
- `.agent/MISSION_PROMPT.md` distinguishes orchestrator-driven (stop after
  the assigned arc) vs standalone (decompose/continue) behavior.
- `AGENTS.md` "Autonomous operation" rewritten with the orchestrator
  division of labor; resource-efficiency rules folded in (batch reads, one
  focused test pass, one final recording pass).
- `src/ine_agent/usage.py` (new, read-only sqlite over `opencode.db`):
  `snapshot()`/`delta()`/`format_*`/`UsageReporter`. Supervisor runs record
  `- usage start:` / `- usage [cycle N]:` / `- usage end:` /
  `- usage delta (run):` / `- usage warning:` in RUN_REPORTS.md. Warning is
  once-per-run, purely advisory (`--usage-warn-requests`, env
  `INE_AGENT_USAGE_WARN_REQUESTS`), and treats observed OpenCode usage as
  OBSERVED numbers, NOT the provider quota — no hard stop until real runs
  validate the numbers against quota/rejection events.
- Bug fixed: `usage.snapshot()` returned shallow `dict(ZERO)` copies sharing
  `by_model`/`sessions` — snapshots bled into each other. Fresh containers
  per call now.
- Verified: `test_ine_agent.py` = 97 passed; full suite 375 passed (9
  subtests); live CLI demo with `--usage-warn-requests 1` produced the
  full usage line set and warned exactly once (10 observed requests in the
  demo window). Next executable stays item 54.

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
