# .agent/HISTORY.md

Running log of what happened and why. Sessions 21+ are precise (project
work); a compact digest is retained instead of full detail for the earlier
design arc — see RESEARCH_LOG.md / WORKBOOK.md for that era.

- **41 (continuation):** Mission 53, evidence-gated vocabulary veto. New
  `EvidenceGateTests` (tests/test_ine.py, 4 tests) read the real reader API
  and lock the Session 31/37 reconciliation decisions forward: the vetoed
  kinds `search`, `subtitle`, `description`, `input`, `table`, `chart` stay
  undeclared (find -> None, not makeable, empty suggestions); `subtitle` /
  `description` / `search` stay absent from every makeable kind's
  properties; `button` is not a header member (WORKBOOK L544 vs the evidence
  `button inside section` from dictionary-demo.ine); and
  `value_shape("card-group", "layout")` remains `unknown` (Session 33
  revert). The guard only fails if a future vocabulary addition overrides an
  evidence gate without commander approval. Full suite 366 collected (364
  passing + 2 transient tkinter flakes green in isolation), goldens
  byte-identical; next executable = item 54.

- **41 (continuation):** Mission 52, attempts reset on progress. New
  `AttemptResetTests` (tests/test_ine_agent.py, 3 tests) pin the attempts
  semantics behind the Mission 30 premature-stop fix: a cycle that makes NO
  plan progress increments `attempts`, but any cycle whose plan changed
  (done/blocked/failed/human) resets it to 0 — so a worker alternating stuck
  and progress runs to completion instead of bounded-stopping early. Tests
  cover the alternating run-to-completion scenario (exit 0, 4 calls, per-
  cycle report classification), a fresh budget given to the next task after
  a progress cycle, and the proof that a reset grants no immunity (consecutive
  stuck cycles still bounded-stop). No supervisor code change; behavior
  verified and locked. Full suite **362 passing** (was 359), goldens
  byte-identical; next executable = item 53.

- **41 (continuation):** Mission 51, crash-then-continue resilience. New
  `CrashContinueTests` (tests/test_ine_agent.py, 3 tests) pin the missing
  combined case: a worker exits nonzero BUT its side effect already advanced
  the plan (marked its task DONE before failing). `_outcome` re-reads the
  plan after the cycle and checks the fresh tag before exit code, so the
  identity change classifies as done (attempts reset, loop continues to the
  next executable task) rather than stuck or failed (bounded-stop or
  deferral). Three test facets: continuation with no-failure output and
  on-disk DONE preserved; a `max_attempts=1` razor proving the crash
  confers no stuck-attempt debt; and the durable run report recording the
  cycle as DONE with exit 0. No supervisor code change needed — behavior
  verified and locked. Full suite **359 passing** (was 356), goldens
  byte-identical; next executable = item 52.

- **41 (continuation):** Mission 50, the exit-code contract. New
  `ExitCodeContractTests` (tests/test_ine_agent.py, 9 tests) pin the
  documented supervisor mapping at the boundary with literal exit-code
  assertions against the constants: STOP_OK (0) for no-executable-work /
  dry-run / all-completed; STOP_ERROR (1) for the bounded attempts-limit
  stop (`"could not advance the plan"`, exactly `max_attempts` calls), the
  bounded cycle-limit stop, and a recorded+deferred worker failure; STOP_HUMAN
  (2) for the worker-output own-line marker, a pre-existing STATE.md gate, and
  a mid-run gate appearing from a worker side effect. Each test also asserts
  the run report's `- exit:` line, so the durable record cannot drift from the
  return code. Reuses `make_root` / `plan_containing` / `StubWorker`
  (worker_factory injection, no subprocess agents); this closes the sole gap
  where the attempts-limit stop had no positive regression. PLAN item 50
  tagged DONE. Full suite **356 passing**, goldens byte-identical; next
  executable = item 51.

- **42:** Windows notifications + recording discipline (commander directive).
  New `src/ine_agent/notifier.py`: `NullNotifier`, `WindowsPowerShellNotifier`
  (hidden `powershell -EncodedCommand` balloon, 20 s timeout, never raises),
  `notifications_enabled` (`--notify` / `INE_AGENT_NOTIFY`), `create_notifier`.
  Supervisor now RECORDS outcomes (append-only, original text preserved):
  blocked/failed/human missions are marked + remarked in PLAN.md, logged to
  BLOCKERS.md under "Blocked during autonomous runs", and deferred via
  `Plan.first_executable(skip=...)` so independent work continues; a durable
  `.agent/RUN_REPORTS.md` (`run_report_path`, begin/append/end helpers) records
  command, cycles, exit code, summary and is what every notification links to.
  CLI gains `--notify` plus a `resolve` subcommand
  (`ine-agent resolve [--root] MISSION BLUEPRINT`) that records a commander
  resolution as a new `> resolution (commander):` remark without rewriting
  the blocker. Exit codes: 0 clean, 1 a mission failed this run, 2 pending
  gate; clean completion prints the standard no-work lines on both paths.
  Fixed an in-session `_rewrite_plan` bug (tag rewrite was overwriting the
  appended remark with a duplicate item line). Tests: `NotifierTests` (5),
  `Session41RecordingTests` (6), `Session41SupervisorTests` (4),
  `ResolveCliTests` (2), + 7 `SupervisorTests` reconciled to the
  deferred/recorded contract. Full suite **347 passing**, goldens
  byte-identical.

- **41:** continued the 40-mission batch. **49** control-plane plan hygiene:
  `PlanHygieneTests` (4) parse the REAL `.agent/PLAN.md` independently of
  `read_plan` and assert sequential numbering with no gaps, valid convention
  tags, every `BLOCKED` item (7/58/59/61) cross-referenced in BLOCKERS.md by
  number, and `first_executable()` agreement. Reconciled six `SupervisorTests`
  that were stale against the in-tree recording-loop supervisor (Session 41
  refactor, previously unrecorded): no-work message casing, the deferred
  human gate now reporting a generic "missions remain held for commander
  judgment" message (exit 2, no abandoned-EXECUTABLE phrasing), and worker
  failure now recorded + deferred instead of retried to `max_attempts`
  (`test_worker_failure_is_recorded_deferred_and_stops_with_error`). Fixed a
  record gap: PLAN item 47 still tagged `EXECUTABLE` despite Session 40
  implementation — marked DONE so the selection rule stops re-picking
  finished work. Full suite **328 passing**, goldens byte-identical.

- **40:** Missions 42-48. **42** alice.ine custom-domain build guard (4
  tests); **43** complete-`make`-statement context fix (+ regression); **44**
  engine `validate` query (`ValidateTests`, 8); **45** CLI error-column fix
  (`CliErrorTests`, 3); **46** multi-line buffer context matrix
  (`BufferContextTests`, 5); **47** malformed-payload protocol robustness:
  `_respond` now echoes id on error; 7 `ProtocolTests` additions (missing
  buffer/line/column, null column, wrong-type line, id on error, live
  malformed-then-valid session); **48** prefix-completion research (findings
  in NOTES: VS Code client-side filtering already works at list sizes <= 13;
  the only real friction — statement-start keyword `make` never offered — is
  a commander-scoped syntax-keyword feature, not dictionary prefix ranking).
  Full suite **324 passing**, goldens byte-identical; Mission 48 is research-
  only (no code changes).

- **39:** dictionary-health batch: (1) dictionary `_load` now emits one
  `warnings.warn` per skipped file (invalid JSON / not a dict / no term)
  while preserving the silent-skip contract; extended the malformed-JSON
  test to assert exactly 4 warnings for the synthetic bad-files with zero
  for the valid entry; no stray warnings in the shipped dictionary.
  (2) `dictionary/README.md` schema guide: every field documented, value-
  shape table, ambient/universal examples, "add a new kind" walkthrough
  verified against the real CLI. (3) README.md fixes: fake dictionary
  illustration replaced with card.json field-for-field; "151 passing"
  replaced with the `python -m pytest tests` command (no hard number that
  would drift); multiplicity paragraph rewritten to state what IS
  implemented; three non-parsing intent-vs-implementation rows replaced with
  verified-parsing Ine syntax. (4) `DictionaryIntegrityTests` (5 tests):
  term+meaning, uniqueness, contains-member resolution, shape validity,
  element declarations — all read the real dictionary files. (5)
  `VocabularyCoverageTests` (3 tests): parse every real program, expand
  groups, verify kinds/properties/containment resolve through dictionary
  or the documented alice.ine boundary. (6) CONTRIBUTING.md rewritten with
  real Ine content (pipeline, dictionary advisory rule, CLI entry points,
  Session 25 freeze, `.agent/` conventions). (7) LANGUAGE.md §7 retitled
  from "as of Session 22" with a lead-in naming value shapes, dictionary
  discovery, editor protocol, and ine-agent as current features; sweep
  confirmed editor README current and left SESSION_STATE.md/WORKBOOK.md
  session refs intact as historical records. (8) Mission 39 CI display-
  guard: `_has_display()` probe + `_skip_without_display` applied to all 7
  window-creating VisualBackendTests (the plan said "four" but the file
  has seven — guard applied to every real window test); new
  `DisplayGuardTests` (3) prove probe False/True branches via monkeypatch
  and assert every window test carries the guard; `.github/workflows/ci.yml`
  added (ubuntu-latest, xvfb, `xvfb-run -a python -m pytest tests`), YAML
  structurally verified. Full suite **295 passing**. Missions 31-39 DONE.

- **1–8 (design arc):** language identity, the `.ine` / `ine` naming, going
  native vs keeping one source with many targets, motivating examples, the
  start of the dictionary idea. Full detail lives in RESEARCH_LOG.md.
- **9–20:** the semantic model takes shape — Entity/Kind/Property/Container,
  the four-construct discipline, Say, multiplicity, groups, HTML backend
  with byte-identical goldens, the visual backend.
- **21:** multiplicity `make 4 cards` → `card-1…card-N` (kind names carry
  the index).
- **22:** groups — `card-group with 4 cards` produces one entity owning the
  set; dictionary vocabulary added around them.
- **23:** official naming — Ine, `.ine`, CLI `ine` (filename flip
  `mylang.py` → `ine.py`).
- **24:** goldens + dictionary-demo; the dictionary becomes a real layering
  between the model and the backends.
- **25 (decision session):** the four-construct spine, `title`/`text`
  universal content properties, dictionary is advisory (never validator),
  `contains` = structural children only, an evidence rule for vocabulary.
- **26:** reverse containment — `parents(kind)`, `--dict` prints
  `belongs inside:`; added page→section, container→card-group (159 tests).
- **27:** first editor prototype — `src/ine/autocomplete.py` engine +
  `editor/vscode-ine`; extension is a pure proxy; `make` / kind / inside
  contexts over JSON-lines (190 tests).
- **28:** responsiveness — generic space/letter triggers, one persistent
  worker (FIFO, 4 s timeout, respawn); 0.3 ms warm vs 140 ms cold (193
  tests).
- **29:** value-shape snippets — `value_shape: "text"` for title/text →
  `title "${1}"` with cursor between the quotes (199 tests).
- **30:** value shapes move into the dictionary — `universal.json`
  `properties: {title: "text", text: "text"}`, new readers
  `ValueShape` / `value_shape` / `_shape_from`, autocomplete.py special
  case removed. Representation already supports enumerated `"choice"`
  lists, none declared yet (204 tests).
- **31:** property-value completion + dictionary coverage reconciliation.
  Engine gained a `value` completion context — `<name> <property> ` answers
  from `value_shape(kind, prop)`: text → `""` quoted placeholder (detail =
  `value_hint`), choice → one item per allowed option, unknown → empty; the
  extension needed no change (a thin proxy surfaces value items for free).
  8 tests, 212 total. Coverage check reconciled every real program:
  all properties and containment pairs are dictionary-covered (entity
  aliases hero/main → banner/container resolve cleanly); two stale
  self-flags in dictionary-demo.ine corrected (card-group/section now have
  dictionary parents); `search`, `subtitle`/`description`, and WORKBOOK's
  `button inside header` confirmed evidence-gated and left undeclared;
  alice's `person` vocabulary flagged as a scope boundary, not a gap. Per
  the PLAN selection rule, nothing EXECUTABLE remains — session ends.
- **32:** the `ine-agent` autonomous supervisor (developer tooling, NOT
  the language). `.agent/` control-plane created (MISSION/STATE/PLAN/
  DECISIONS/BLOCKERS/HISTORY); AGENTS.md is the agent entry point and
  operating rules. `src/ine_agent/` implements the loop: read `.agent/`
  state every cycle, pick the first EXECUTABLE task (deterministic, list
  order; unmarked items are executable, `CLAUDE_REVIEW` triggers an
  optional Claude review then the implementation worker), run exactly one
  worker per cycle (sequential, never concurrent), reread state, stop
  cleanly. Stop conditions: no executable work (exit 0),
  `HUMAN_DECISION_REQUIRED` marker in output or `.agent/` files (exit 2),
  no plan progress after `--max-attempts` (exit 1), or `--cycle-limit`.
  Routing is deterministic per task tag, never an AI classifier. OpenCode
  is the default implementation worker; Claude only for review. Guardrails
  are hard-coded in the worker prompts. 22 focused tests (scripted stubs,
  no real agent ever launched), installed entry point
  `ine-agent = "ine_agent.cli:main"`, live smoke test on the real repo
  exits 0. 234 tests total — session ends.
- **33:** dictionary/editor stabilization under `ine-agent`. Fixed `_shape_from`
  to reject non-standard value kinds — a plain string like `"row"` now yields
  `ValueShape()` (unknown) instead of a bogus `ValueShape("row")`, so only
  declared value kinds (`"text"`, `"length"`) and list-style `choice`s survive;
  regression assertions added (`_shape_from("row")`, `_shape_from("length")`).
  A companion change that declared `card-group layout: "text"` to "unblock
  editor completion" was found to contradict WORKBOOK §40–41 — only universal
  `title`/`text` are text-shaped; `layout` is a bare-word renderer hint — and
  was reverted. `value_shape("card-group", "layout")` returns `unknown` again;
  the first `choice` value remains BLOCKED on evidence. PLAN renumbered
  (10 executable items + the blocked choice). 242 tests — session ends.
- **33 (addendum):** captured the commander's next-stage plan as a
  `## Candidate missions` section in PLAN.md — Ine authoring & UI capability:
  character-based completion and context-aware ranking, automatic
  value/structure/choice completion, basic visual intent (not "add CSS"),
  realistic UI structures (dashboard, tables, forms), responsive intent, and
  tooling (diagnostics, formatting, hover, packaging, CI). Each candidate has a
  five-point verification gate (real-example evidence, architecture fit,
  no conflict with DECIDED principles, no invented semantics, value vs. the
  next available mission) and must graduate to Active before implementation.
  The section is outside Active on purpose, so the selection rule never picks
  candidates as executable work; overlapping active research missions are
  cross-referenced instead of duplicated.
- **34:** ine-agent subprocess encoding hardening (real-run fix). The live
  OpenCode run on Windows crashed with `UnicodeDecodeError: 'charmap' codec
  can't decode byte 0x90` because `worker.py`'s `subprocess.run(..., text=True)`
  decoded stdout/stderr with the locale codec (cp1252). Both `CliWorker.run`
  and `OpenCodeWorker.run` now decode through a shared `CliWorker._capture`
  that passes `encoding="utf-8", errors="surrogateescape"` explicitly: agent
  output with non-CP1252 bytes decodes losslessly instead of crashing, on the
  OpenCode and Claude worker branches alike. Added 3 focused regression tests
  (`WorkerEncodingTests`) that pipe a probe script containing the crash bytes
  (`"\xd0\x90"`, a lone `0x90`, and a non-ASCII stderr line) through the real
  subprocess boundary for both workers. No language semantics or control-plane
  design touched. 247 tests — session ends.
- **35:** quick wins 1-10 cleared (all DONE except the evidence-gated choice
  item 7). Confirmed items 1-2 (group/say keyword context) were already
  implemented in autocomplete.py and marked them DONE. Added dictionary
  edge-case tests (defaults-only `value_shape` = unknown; `viewport`
  `properties_for`/`suggest`), an end-to-end editor-flow protocol test, a
  malformed-JSON loader test, README value-completion documentation, type
  hints across `dictionary.py` (via `TYPE_CHECKING` for `Model`), and a JSON
  schema section in the module docstring. Fixed `.tmp/` leak: pytest does not
  invoke the unittest `tearDownModule` hook for unittest.TestCase classes, so
  `test_ine_agent.py` now cleans its fixture roots with an autouse pytest
  fixture (keeping `tearDownModule` for `python -m unittest`); cleared 390
  stale `ineagent-*` dirs. Corrected one plan assumption along the way:
  `suggest("viewport")` legitimately returns the ambient entry's declared
  properties (needed by the editor), not empty. 252 tests — full-suite runs
  leave `.tmp/` empty. (Transient tkinter TclError in VisualBackendTests can
  appear under full-suite load; passes in isolation/rerun.)
- **36:** ine-agent live-worker streaming (commander UX request). Worker boundary
  gains `on_line` streaming: `CliWorker._stream` uses `Popen` with two reader
  threads draining stdout/stderr concurrently (prevents deadlocks on large pipe
  buffers) while relaying each line to a callback; the captured output is still
  returned in `WorkerResult` so streaming never loses data. Supervisor prints a
  per-cycle banner (worker name + mission headline) and a live stream of worker
  output lines, indented and ANSI-stripped by default; `--verbose` relays raw
  and unindented; `--quiet` suppresses live lines. `_safe_stdout` sets
  `backslashreplace` so non-UTF-8 console bytes never crash the relay.
  StubWorker and TrackingStub forward the `on_line` parameter; the regression
  boundary test suite (`WorkerStreamingTests`) verifies relay correctness,
  256 KiB × 2 concurrent-pipe draining without deadlock, and UTF-8/surrogateescape
  preservation through the streaming path. 276 tests — session ends.
- **37:** research missions 11-30 closed (findings in `.agent/NOTES.md` as
  `## Mission N` sections). Evidence collection: dashboard experiment
  (`.agent/experiments/dashboard.ine` — repeated `make container`/`make
  section` collide on the default entity name; `make 3 card` not reusable,
  always 1-indexed; no numeric/boolean/date values; no chart/table kinds;
  card-group contained only by container; no status colors) and form
  experiment (`.agent/experiments/form.ine` — zero field kinds, no label
  association, no interaction semantics; forms are unexpressible).
  Vocabulary reconciliation written into `.agent/BLOCKERS.md` (Session 37
  reconciliation: 12 used kinds covered; evidence-gated gaps recorded;
  `link`/`title`/`heading` kinds declared but never instantiated).
  Assessments: responsive (`narrow-class`/`narrow-layout` declared on
  card-group but read by no backend — backend freeze), styling (backends
  emit hard-coded styles only; zero user styling; smallest fix = wire
  declared physical hints post-freeze), CI (none; suite hermetic; tkinter
  window tests not display-guarded), packaging (`dictionary/*.json` is
  repo-root data NOT in the wheel → pip-installed `ine` runs with an empty
  dictionary), editor architecture (stay JSON-lines; add `validate` query
  after fixing the CLI column-drop), native reality check (verified with
  zig 0.16: `say` → C → `.exe` works end-to-end; ALL UI statements silently
  dropped; page programs produce no-op binaries; research-only). Autocomplete
  worker stress: 300 subprocess requests in 0.18s, 0 errors, survives
  malformed JSON/blank lines. **ine-agent fix:** `Task.executable` in
  `src/ine_agent/state.py` excluded only `BLOCKED`, so `DONE`-tagged tasks
  were re-picked and the supervisor stalled after `max_attempts` even when
  EXECUTABLE missions remained; now excludes `DONE` too. Added a
  `plugin_done_text` fixture + 2 new tests (skip-DONE in
  `first_executable`; supervisor continues past a DONE-marked task) and
  extended the tag-executability parse test to a DONE item. Real-plan check:
  `first_executable()` now returns item 28, not the first DONE item. Also
  15 autocomplete tests (CursorEdgeCaseTests 9, ContainmentCompletionTests
  6). 278 tests — session ends.
- **38:** human-gate false-positive fix (from a commander-investigated live
  run). The run had stopped with "commander judgment is required for:
  `EXECUTABLE` — Improve context detection for `group` keyword." even though
  the mission was in fact completed (guard at autocomplete.py:67 + tests at
  test_autocomplete.py:67-75 match the plan exactly; all quick wins were
  marked DONE by that same worker invocation). Root cause:
  `supervisor.run()` decided the HUMAN_DECISION_REQUIRED gate with a raw
  substring scan (`state.HUMAN_MARKER in result.output`), and the phrase
  lives inside the workers' own instructions — so a transcript that merely
  QUOTES the guardrail in prose ("this task did not need
  HUMAN_DECISION_REQUIRED") halted the loop on a finished mission, and the
  "judgment required" message named a mission the plan now shows as DONE.
  Fixed: `state.output_marks_human_decision()` applies the same line-based
  marker convention already used for `.agent/` files (the marker must START
  a line), and it is used for both the implementation-worker output and the
  Claude review pre-pass. The stop message now also reports the task's
  CURRENT plan tag (`supervisor._current_headline`, headline-keyed so the
  EXECUTABLE→DONE re-tag is seen), so a mission completed alongside a
  genuine marker is never shown as an abandoned EXECUTABLE one. Regression
  tests: prose mention must NOT stop the loop, an own-line marker still
  must, the fresh-tag message, review-branch parity, plus state-level
  helper unit tests. 284 tests — session ends.

- **38 (addendum):** 40-mission self-test batch authored into
  `.agent/PLAN.md` (Active, items 31-70: 37 EXECUTABLE + 3 BLOCKED), per a
  commander directive to prepare a large self-test of the autonomous
  development system. Grounded in the existing NOTES findings (Missions
  11-30), the BLOCKERS evidence gates, the Session 25 freeze, and the
  golden-output discipline; grouped into dictionary health (31-35),
  docs & reliability (36-42), editor/autocomplete (43-48), ine-agent
  "prove the loop" tests (49-53), evidence experiments (54-55), CSS/
  styling investigation + gated implementation (56-59), linking
  investigation + gated implementation (60-62), packaging/reliability nets
  (63-68), and a self-test capstone (69-70). The CSS/link implementations
  (58, 59, 61) are BLOCKED with precise preconditions — backend-freeze
  lift + commander scope + the EXECUTABLE evidence missions landing first —
  and were recorded in `.agent/BLOCKERS.md` so the plan-hygiene test can
cross-check them. Validation now (the batch is NOT executed yet):
  `read_plan` parses 70 items with no gaps, `first_executable()` = item 31,
  `ine-agent run --dry-run` prints item 31 and exits 0, and the full suite
  passes (284).

- **111:** mission: cut autonomous-worker model-request waste (commander-
  approved). Objective: reduce unnecessary Big Pickle/OpenCode requests on
  the free tier WITHOUT reducing autonomy. (a) Worker scope narrowed to one
  assigned mission per cycle — `supervisor.impl_prompt` embeds a distilled
  STATE.md snapshot (`_distill_state`: current focus + health only) and
  instructs the worker to execute the complete arc then STOP and report,
  with a single final recording pass; `.agent/MISSION_PROMPT.md` now
  distinguishes orchestrator-driven (stop after assigned arc) from
  standalone (decompose/continue) use; AGENTS.md documents the orchestrator
  division of labor (deterministic supervisor selects missions, records
  blocked/failed/human outcomes, writes RUN_REPORTS, notifies) and folds in
  resource-efficiency rules (batch reads, read whole files, one focused
  test pass per mission, one final recording pass). (b) Warn-only observed-
  usage telemetry — new `src/ine_agent/usage.py` (read-only sqlite over
  `opencode.db`): snapshots at run start/end and each mission boundary,
  per-mission deltas, and an advisory once-per-run `[usage]` warning
  (threshold via `--usage-warn-requests` / `INE_AGENT_USAGE_WARN_REQUESTS`)
  all recorded in `.agent/RUN_REPORTS.md`. Numbers are locally OBSERVED
  usage, NOT the provider quota — deliberately no hard pause until real
  runs validate them. (c) Fixed a latent bug: `usage.snapshot()` shared the
  mutable `by_model`/`sessions` containers of `dict(ZERO)` across calls, so
  snapshots bled into each other. Tests: 6 `UsageTests` (assistant-message
  counting, day window, per-session breakdown, delta, degraded-database,
  supervisor run-report recording + warning-once-with-notify), 2 CLI tests
  (env-override precedence, `run --help` shows the flag), and pinned three
  stale Session 41 notifier assertions (3-tuple call unpacking + the report
  is the third notify argument). Verified: `test_ine_agent.py` 97 passed;
  full suite **375 passed, 9 subtests**; live CLI demo
  (`--usage-warn-requests 1`) recorded the full usage line set and warned
  exactly once (10 observed requests in the demo window). Next executable
  remains PLAN item 54.

- **41 (continuation):** notification streamlining + Missions 64-65
  reliability nets. (a) Commander's notification polish:
  `src/ine_agent/notifier.py` now uses the round-tile window icon
  (`assets/icon.png`, generated from `logo.png` via Region-clip rounded
  corners + 4x supersampled alpha + HQ downscale to 256 px) through a new
  `___ICON___` token that falls back to the square logo
  (`create_notifier` prefers a `icon.png` tile sitting beside the logo),
  and plays a soft two-tone chime (`assets/chime.wav`, synthesized 44.1 kHz
  exponential-decay sine stack) via `System.Media.SoundPlayer` async
  `Play()` on a new `___CHIME___` token dispatched by the popup's message
  loop; `default_chime_path()` resolves the repo asset. Every supervisor
  banner is now a terse `Ine · <status>` title — `Ine · task
  started`/`done`/`stuck`/`blocked`/`failed`, `Ine · decision required`,
  `Ine · run complete`, `Ine · usage warning` — with the mission headline
  as the only body line (the old "recorded and deferred ..." noise
  dropped); a per-cycle `task started` banner fires plus new `task done`
  and `task stuck` outcome banners. (b) Mission 64:
  `DictionaryIntegrityTests.test_members_and_parents_are_exact_inverse_over_shipped_kinds`
  proves containment is an exact inverse for every shipped kind pair
  (`B in members(A)` iff `A in parents(B)`), with a non-vacuous guard.
  (c) Mission 65: `BackendMetadataContractTests` (3) pins the Session 25
  freeze — HTML `_element_for_kind`/`_layout_for_kind` and visual
  `_layout_of`/`_position_of` return the dictionary's declared value
  (element on every makeable kind, `layout: row` only on card-group,
  `position: bottom` only on footer) with vacuity guards, and a looped
  test re-renders the four `tests/expected/*.html` examples fresh and
  asserts byte-identical goldens. PLAN items 64-65 tagged DONE. Verified:
  `test_ine_agent.py` 101 passed; full suite **383 passed, 9 subtests**
  (goldens byte-identical); next executable = item 54.
