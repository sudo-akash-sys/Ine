# .agent/PLAN.md

Current plan, by stage. Completed stages are kept for context; the active
next steps are what an agent should pick up.

## How an autonomous worker picks its next task

- **Executable** work is listed under "Active — next smallest steps" and has
  no unfulfilled precondition. Pick it up directly.
- **Blocked** work has an unmet precondition — missing evidence, a missing
  decision, or data that does not exist yet. Blocked items are tracked in
  `.agent/BLOCKERS.md` and are explicitly marked `BLOCKED` here.
- Selection rule: take the **first EXECUTABLE** item, in list order. Do not
  skip an executable earlier item for a later, more interesting one, and do
  not un-block a `BLOCKED` item by guessing. If nothing is executable, stop
  and record that fact in `.agent/BLOCKERS.md` / `.agent/STATE.md` instead of
  inventing work.
- `STATE.md` is the position, `HISTORY.md` is the log — PLAN.md is the menu.

## Stage 1 — Language core (COMPLETE)

- Lexer / parser / semantic model: `src/ine/{lexer,parser,semantic}.py`.
- Four semantic constructs (Session 25): **Entity** (`make page`, names),
  **Kind** (properties: `page title "…"`), **Property Value**, and
  **Container** (containment: `section` inside `page`).
- Relationships: **Say** (`say "Hello"` → output), **Multiplicity**
  (`make 4 cards` → `card-1…card-N`), **Groups** (`card-group with 4 cards` →
  one entity owning the set).
- Targets: **HTML** (`backend_html.py`, goldens in `tests/expected/*.html`,
  byte-identical discipline), **native** (C/zig research via backend),
  **visual** (`backend_visual.py` + Tkinter demo).
- CLI `ine` with `run` / `render` / `visual` / `--dict`; runtime in
  `runtime/`.

## Stage 2 — Dictionary layer (COMPLETE through Session 30)

- `dictionary/*.json` (15 files) is the single source of truth.
- `ine --dict` and `src/ine/dictionary.py` reader API:
  `makeable`, `find`, `properties_for`, `value_hint`, `suggest`,
  `for_model`, `members`, `parents` (reverse containment, Session 26),
  `ValueShape` / `value_shape` / `_shape_from` (Session 30).
- Containment entries are **structural children only**, evidence-grounded
  (page→section, container→card-group, section→copy).

## Stage 3 — Editor prototype (milestone COMPLETE, Session 30)

The **prototype milestone** (Sessions 27–30: JSON-lines engine, thin VS Code
extension, persistent worker, `value_shape` snippet) is complete and shipped
as `editor/vscode-ine/`. Further editor work is **not** part of the completed
milestone; it continues in "Active — next smallest steps" below.

- `src/ine/autocomplete.py`: JSON-lines engine (context detection,
  `make`→`kind`→`property` suggestions, stable worker protocol).
- `editor/vscode-ine/`: thin extension; trigger chars = space + ASCII
  letters; persistent `DictionaryWorker` with FIFO queue, timeout, respawn;
  `value_shape == "text"` renders the `title "${1}"` snippet.
- The extension holds **zero** Ine vocabulary — it is a pure proxy to the
  Python dictionary.

## Active — next smallest steps

Each item is marked `EXECUTABLE` (pick up now) or `BLOCKED` (precondition
missing — see `.agent/BLOCKERS.md`). Per the selection rule above, take the
first `EXECUTABLE` item in list order.

### Quick wins — small implementation tasks

1. `DONE` — **Improve context detection for `group` keyword.** Implemented
   (autocomplete.py:67 `words[0] in ("group", "say")` guard + tests at
   test_autocomplete.py:67-70). Verified: 50 autocomplete tests passing.

2. `DONE` — **Improve context detection for `say` keyword.** Implemented
   (autocomplete.py:67 same guard + tests at test_autocomplete.py:72-75).
   Verified: 50 autocomplete tests passing.

3. `DONE` — **Add missing dictionary test coverage.** Added three tests to
   `DictionaryTests` in test_ine.py:
   - `test_value_shape_defaults_only_kind_properties_are_unknown` — a kind
     with only a `defaults` block (no `properties` block) yields
     `ValueShape()` for its default properties (`card padding`,
     `card corner-radius`, `header orientation`).
   - `test_suggest_ambient_viewport_lists_declared_properties` — `suggest()`
     on the ambient `viewport` entry returns its declared `width`/`height`
     property suggestions (it does NOT return empty; the plan note said
     "should return empty," which proved mistaken — the editor needs
     `viewport ` → `width`/`height` completion while typing). Ambient kinds
     are only excluded from `makeable()`/no-arg `suggest()`.
   - `test_properties_for_ambient_viewport_returns_width_height` —
     `properties_for("viewport")` = `["height", "width"]`.
   Verified: dictionary test subset passes.

4. `DONE` — **Clean up `.tmp/` directory.** `test_ine_agent.py` now tracks
   every fixture root it creates under `.tmp/` (`_CREATED_ROOTS`) and removes
   them via a pytest autouse fixture (pytest does not invoke the unittest
   `tearDownModule` hook for unittest.TestCase subclasses, which was leaving
   `ineagent-*` dirs behind on every `python -m pytest` run); a
   `tearDownModule()` hook is kept for plain `python -m unittest` runs. The
   comment at `TMP = ...` documents that `.tmp/` is gitignored temporary
   storage. Cleared the 390 stale directories; full-suite run leaves `.tmp/`
   empty.

5. `DONE` — **Update editor README for value completion.**
   `editor/vscode-ine/README.md` now documents Context 4 (`page title `
   → `""` quoted placeholder), the query mapping for
   `kind property ` → `value_shape` in "How it works", and a status line
   clarifying that value completion is live, choice values are engine-ready
   but unused by any dictionary entry, and the remaining gaps (multi-kind
   `make` arguments, property-name completion before a trailing space).

6. `DONE` — **Add type hints to dictionary.py.** `find`, `makeable`,
   `properties_for`, `value_hint`, `value_shape`, `members`, `parents`,
   `suggest`, `for_model` (plus internal helpers `_load`, `_is_regular_kind`,
   `_universal_defaults`, `_shape_from`, `_label` and the `_ENTRIES` cache)
   now carry annotations; `for_model`'s `Model` parameter uses a
   `TYPE_CHECKING` guard so dictionary.py stays import-light. Verified:
   `python -m py_compile src/ine/dictionary.py` and 217 dictionary +
   autocomplete tests pass.

7. `DONE` — **First enumerated `choice` value.** Add `"choice"`-style
   options to a `properties` block (e.g. `"layout": ["row", "column"]` in
   `card-group.json`), then teach the extension's snippet path to offer
   `choice` options. Precondition: a real program or decision showing a
   second `layout` value; only `"row"` is documented today. RESOLVED by commander
   decision (Session 49): card-group `properties` declares `layout` as a
   choice; snippet offers `${1|row,column|}`, `--dict` prints it, advisory
   flags out-of-choice values.

8. `DONE` — **Add error handling test for malformed dictionary JSON.**
   `test_malformed_dictionary_json_is_skipped_without_crashing` in
   `DictionaryTests` points `_load()` at a synthetic directory containing a
   valid entry, broken JSON, plain text, a JSON array (not a dict), and a
   dict with no `term`, then asserts only the valid entry survives. The
   silent-skip behavior is preserved and now regression-covered.

9. `DONE` — **Document dictionary JSON schema in code comments.** The
   `dictionary.py` module docstring now has a `## dictionary/*.json schema`
   section covering `term`, `kind`, `element`, `meaning`, `defaults`
   (`contains` noted), `properties` (text/length/choice shapes), `provided-by`
   (ambient), and `universal` (pseudo-entry).

10. `DONE` — **Add integration test for editor-to-dictionary flow.**
    `test_editor_flow_end_to_end` in `ProtocolTests` drives one live
    autocomplete.py subprocess through all four editor contexts (`make `,
    `<kind> `, `<kind> <property> `, `<child> inside `) with request ids,
    asserting context type, items, and the echoed id on each response.

### Research & investigation — weakness-driven missions

These are research-first missions. Each produces a finding (a FILE note or
STATE.md update) before any code change. Do not invent solutions; discover
whether the weakness is real, how severe it is, and what the smallest
evidence-based fix would be.

#### Dictionary robustness & typing

11. `DONE` — **Invalid dictionary entry feedback.** Investigated — finding in
    `.agent/NOTES.md`. Silent-skip in `_load()` can silently drop vocabulary
    (kind vanishes from `makeable()`/`find()`/suggestions with no pointer to
    the file); severity low at current scale (15 small files, test suite
    catches most breakage). Recommended minimum feedback: one
    `warnings.warn(...)` per skipped file at load time, naming file + reason
    (invalid JSON / not an object / missing `term`); raise and validation
    framework explicitly ruled out. Implemented only if commander wants it —
    recording only, as this is a research mission.

12. `DONE` — **Value-shape consistency review.** Audited `_shape_from`,
    `value_shape`, `_known_shape` together — finding in `.agent/NOTES.md`.
    Consistent, nothing invents a shape: `_shape_from` types only the
    standard `"text"`/`"length"` strings and list-style `choice`s, `value_shape`
    reads only `properties` blocks (never `defaults`), `_known_shape` emits
    None for unknown, and no other module constructs `ValueShape`. Only
    `"text"` and `"length"` are declared today; no choice surfaces (BLOCKED
    item 7 intact).

13. `DONE` — **Dictionary type hints on autocomplete.py.** Annotated the
   public functions (`context`, `resolve_kind`, `complete`) and internal
   helpers (`_known_shape`, `_items`, `_respond`, `main`). Verified:
   `python -m py_compile src/ine/autocomplete.py` and 51 autocomplete tests
   pass.

#### Autocomplete edge cases

14. `DONE` — **Autocomplete edge cases: unusual cursor positions.** Nine
    `CursorEdgeCaseTests` added to test_autocomplete.py covering start of
    line, blank lines, multiple spaces, midline while typing, inside a
    quoted string, end of a complete value, comment-only lines, inline
    comments, and mid-identifier. No crashes anywhere; inline-comment
    misclassification documented in `.agent/NOTES.md` (resolves to empty
    items — harmless, not fixed per mission scope).

15. `DONE` — **Autocomplete containment completion.** `ContainmentCompletionTests`
    added to test_autocomplete.py: `header inside ` → `page`, `card inside `
    → `card-group`, `banner inside ` → `container`, `page inside ` → nothing
    (top-level), `Page inside ` → nothing (case-sensitive kinds). The plan's
    `copy inside ` → `section` expectation is **stale**: `copy` is not a
    dictionary kind and appears in no `contains` list, so it correctly
    returns nothing — consistent with the coverage reconciliation in
    `.agent/BLOCKERS.md` (no invented containment).

#### Editor diagnostics & error messages

16. `DONE` — **Editor diagnostics investigation.** Finding in
    `.agent/NOTES.md`. The extension registers only a completion provider —
    zero in-editor errors today; all errors appear at build/render time, and
    the engine has no validation endpoint. Recommendation: do NOT build an
    LSP; the minimum useful step is a `validate` query on the JSON-lines
    protocol (parse buffer, return `[{line, message}]`, push to a
    DiagnosticCollection), kept advisory so the dictionary never
    red-underlines. Justified by a real in-editor need; DECISIONS status
    stays UNDECIDED.

17. `DONE` — **Backend/parser/semantic error message audit.** Finding in
    `.agent/NOTES.md`. No error prints as a bare class name, but the five
    worst offenders are listed with before/after wording: `cannot understand
    this line` (parser.py:90), `unexpected character '<ch>'` (lexer.py:97,
    cryptic + column dropped by CLI), `'x' has a property but was not
    declared with 'make'` (semantic.py:41, no fix offered), the html-backend
    unsupported-kind message (no pointer to `ine --dict`), and the adjective
    `unexpected extra text` variants that echo nothing. Systemic note: the CLI
    ignores `.column` even when present. No code changed — list only.

#### Documentation

18. `DONE` — **Minimum documentation review.** Gap list in `.agent/NOTES.md`.
    Misleading: stale 151-test count (now 252), a fake dictionary JSON
    example that no real file resembles, a "Not Implemented Yet" subsection
    that reads as if multiplicity were unimplemented, and intro examples
    using syntax that does not parse. Missing: a `dictionary/README.md` /
    schema guide, a "how to add a kind" walkthrough, and Ine-specific
    CONTRIBUTING.md content. Minimum for a newcomer: fix the README's
    examples + test count, and one page documenting the dictionary schema.
    No docs written — list only.

#### Real-world examples & vocabulary

19. `DONE` — **Real-world example: dashboard experiment.** Program at
    `.agent/experiments/dashboard.ine`; builds and renders. Findings in
    `.agent/NOTES.md` (Mission 19): default-name collisions for repeated
    structural kinds; multiplicity not reusable (always 1-indexed);
    no numeric/boolean/date values; no chart/table kinds; card-group
    contained only by container; no status colors; buttons only inside
    sections.

20. `DONE` — **Real-world example: form experiment.** Program at
    `.agent/experiments/form.ine`; builds and renders. Findings in
    `.agent/NOTES.md` (Mission 20): zero field kinds, no label association,
    no interaction semantics, no booleans. Converges with Mission 19:
    vocabulary covers static display only.

21. `DONE` — **Vocabulary reconciliation against real programs.** Findings
    in `.agent/BLOCKERS.md` (Session 37 reconciliation). 12 kinds used by
    programs are covered; zero field kinds for forms; no numeric/boolean/
    date types; no chart/table kinds; multiplicity can't be reused;
    `card-group` contained only by `container` by design; `link`/`title`/
    `heading` kinds declared but never instantiated.

#### Responsive UI & styling

22. `DONE` — **Responsive UI investigation.** Finding in `.agent/NOTES.md`
    (Mission 22). `narrow-class`/`narrow-layout` are declared on
    `card-group` but NO backend reads them (this is the only "responsive"
    vocabulary; breakpoints/conditional layout don't exist). Responsive is
    currently metadata-only — behavior is entirely an implementation
    concern. Recommendation: keep it declarative, implement one narrow rule
    in the HTML backend after the freeze lifts; do not add conditions/state
    now.

23. `DONE` — **Styling/theming limitation investigation.** Finding in
    `.agent/NOTES.md` (Mission 23). Users see only hard-coded inline
    styles (`div`, flex row, `<h1>`/`<h3>` in HTML; fixed color/font/800x600
    in tkinter). Zero visual customization from `.ine` today — even declared
    physical hints (`card.padding`, `banner.padding`) are untyped and read
    by no backend. Smallest fix: wire existing padding/corner-radius/border
    metadata into HTML inline styles after the backend freeze lifts; no
    theming system recommended.

#### Infrastructure

24. `DONE` — **CI/regression infrastructure investigation.** Finding in
    `.agent/NOTES.md` (Mission 24). No CI exists; `python -m pytest tests`
    = 267 tests, fully hermetic (stdlib-only), native tests auto-skip
    without a C compiler. Two hazards: tkinter window tests are not
    display-guarded (headless CI fails) and one flaked under load this
    session. Recommendation: add a GitHub Actions workflow (xvfb +
    python3-tk) and display-guard the visual tests.

25. `DONE` — **Packaging/distribution investigation.** Finding in
    `.agent/NOTES.md` (Mission 25). pyproject + entry points are complete,
    but `dictionary/*.json` is repo-root data resolved via `__file__` to a
    source-checkout path — a wheel install yields an empty dictionary and a
    broken `ine --dict`/autocomplete. `.vsix` is packageable, but the
    extension spawns the Ine engine, so shipping depends on fixing the
    dictionary-data gap (single mechanical packaging step).

#### Editor architecture

26. `DONE` — **Editor architecture evaluation.** Finding in
    `.agent/NOTES.md` (Mission 26). JSON-lines architecture is correct and
    wire-independent (`context()`/`complete()`/`resolve_kind()` reusable by
    any future server). Diagnostics justified now (add a `validate` query,
    fix column-drop first); hover cheap whenever; formatting/LSP only past
    a 3-feature threshold. No LSP now — switch is reversible.

#### Native backend

27. `DONE` — **Native backend reality check.** Finding in `.agent/NOTES.md`
    (Mission 27). Verified end-to-end with zig. Genuine: `say` →
    C → `.exe` for print programs. Reality: all UI statements are silently
    dropped; page-describing programs compile to no-op binaries. Not usable
    beyond demonstration; keep research-only, no further investment without
    a real user program needing execution semantics.

#### Performance & reliability

28. `DONE` — **Autocomplete worker reliability.** Stress-tested the real
    subprocess worker (`python src/ine/autocomplete.py`): 300 requests in
    0.18s, 0 errors, survived malformed JSON/blank lines mid-session,
    recovered cleanly. Findings in `.agent/NOTES.md` (Mission 28). No fixes
    needed; worker is line-buffered + exception-guarded + respawn-enabled.

29. `DONE` — **ine-agent reliability.** Code audit + new supervisor-level
    tests in `.agent/NOTES.md` (Mission 29). Found the premature-stop bug
    (a `DONE`-marked task was still picked next cycle); the other three
    stop conditions and crash handling are correct. Fix in Mission 30.

#### Autonomous development system

30. `DONE` — **ine-agent continuous execution fix.** Root cause in
    `src/ine_agent/state.py`: `Task.executable` treated everything except
    `BLOCKED` as executable, so `DONE` items were re-picked and the
    supervisor stalled after `max_attempts`. Fixed to exclude `DONE` too;
    added `plugin_done_text` fixture + 3 tests (parse, first_executable,
    supervisor loop). `tests/test_ine_agent.py` → 44 passed. Real-plan
    check: `first_executable()` now returns item 28, not the first DONE
    item.

### Dictionary health & discovery

31. `DONE` — **Warn when a dictionary file is skipped at load.**
    Implemented (dictionary.py `_load`): each skipped file now emits one
    `warnings.warn(...)` naming the file and the reason (cannot read /
    invalid JSON / not a JSON object / missing `term`), while the
    silent-skip contract is preserved — a broken file still never raises.
    Test extended: `test_malformed_dictionary_json_is_skipped_without_crashing`
    now asserts exactly one warning per bad file (naming it) and that the
    valid entry loads with no warning. Verified: `python -m pytest
    tests/test_ine.py -k dictionary` = 41 passed; full suite 284 passed
    with no stray warnings for the shipped dictionary.

32. `DONE` — **documentation: `dictionary/README.md` schema guide.**
    Added `dictionary/README.md`: documents every schema field (`term`,
    `kind`, `element`, `meaning`, `defaults` incl. `contains`, `properties`
    with the `text`/`length`/`choice` shapes, `implementation`,
    `provided-by` ambient entries, the `universal` pseudo-entry), including a
    field-reference table, the value-shape table, an ambient-entry example
    (viewport) and the universal entry. Includes a worked "add a new kind"
    walkthrough verified against the real CLI (`ine --dict <term>` surfaces
    the kind; `python -m pytest tests/test_ine.py -k dictionary` passes), plus
    the advisory/evidence/no-second-vocabulary rules. No code changed; full
    suite still 284 passing.

33. `DONE` — **documentation: fix README misstatements.**
    Fixed all four Mission 18 issues in README.md: (a) the fake dictionary
    illustration replaced with card.json field-for-field; (b) the stale
    "151 passing" count replaced with the current `python -m pytest tests`
    result (284 passing) and the command canonicalized; (c) the "Not
    Implemented Yet" multiplicity bullet rewritten to lead with what IS
    implemented (multiplicity/collections) and name the `every`-keyword gap
    as the only missing piece; (d) the three fake intent-vs-implementation
    rows (`logo left, navigation right`, `footer stay at bottom`, `card
    with subtle shadow`) replaced with syntax Ine actually accepts
    (`logo inside header`, `footer position "bottom"`,
    `card padding "comfortable"`) — each verified to parse through the
    full pipeline. No invented syntax. Verified: `python -m pytest tests`
    = 284 passed, unmodified.

34. `DONE` — **test: dictionary integrity regression guard.**
    Added `DictionaryIntegrityTests` in tests/test_ine.py (5 tests):
    every entry has `term` + `meaning`; `term` values unique across files;
    every `defaults.contains` member resolves to a declared kind or a
    documented scope boundary; every `properties` value is a valid
    `_shape_from` input (`type != "unknown"`); every makeable kind declares
    an `element`. All read the real `dictionary/*.json` files directly
    (not the loader cache) so a duplicate term or typo in a containment
    list is caught at test time. Verified: `python -m pytest
    tests/test_ine.py -k integrity` = 5 passed; full suite 292 passed.
    No dictionary data changed.

35. `DONE` — **test: vocabulary-coverage reconciliation guard.**
    Added `VocabularyCoverageTests` in tests/test_ine.py (3 tests):
    parse every real program under `examples/` and `.agent/experiments/`,
    extract entity kinds, properties, groups, and containment pairs, and
    assert every one resolves through the dictionary (`makeable`,
    `properties_for`, `members`) or falls in a documented scope-boundary
    set (the `person`/`name`/`age`/`height` custom domain from
    alice.ine). Handles group expansion: `cards inside card-group` maps
    each card to the card kind before checking. Locks the Session 31/37
    reconciliation at test level. Verified: `python -m pytest
    tests/test_ine.py -k coverage` = 3 passed; full suite 292 passed;
    goldens byte-identical.

### Documentation & reliability

36. `DONE` — **documentation: Ine-specific CONTRIBUTING.md.**
    Rewrote CONTRIBUTING.md with real Ine content: repository layout
    (pipeline, dictionary, editor, .agent, tests), the language pipeline,
    the dictionary advisory rule, CLI entry points (repo-root shim,
    `python -m ine`, installed `ine`), canonical test command (`python -m
    pytest tests`), the Session 25 freeze (frozen files, when/how to
    change), `.agent/` conventions (PLAN selection rule, STATE/HISTORY,
    `.tmp/`). Kept the code-of-conduct and DCO/trademark sections. No code
    changed; full suite 292 passed.

37. `DONE` — **research: "what Ine can currently express" inventory.**
    Finding recorded in `.agent/NOTES.md` (`## Mission 37`): inventories
    the five statement forms and their exact grammar (verified against
    parser.py), the three value kinds (string/int/decimal, compile-time
    property references), what each target really renders (HTML verified
    against a fresh render of cards.ine; visual; native = say-only), the
    editor's four completion contexts plus value shapes (text/choice/
    unknown — no choice declared), and a crisp "expressible today" vs
    "NOT expressible today" boundary (booleans, fields, tables, links,
    styling, responsive, conditions, native-UI — each evidence-gated in
    BLOCKERS). No code changes; nothing but NOTES.md touched.

38. `DONE` - **documentation: LANGUAGE.md and stale-claims sweep.**
    Fix LANGUAGE.md section 7 ("Known limits (as of Session 22)") so it
    reflects the current state (value shapes, dictionary discovery, editor
    protocol, ine-agent are no longer "limits"), and sweep repo docs
    (README.md, LANGUAGE.md, editor README, SESSION_STATE.md) for stale
    session references and hardcoded test counts; update or remove them —
    prefer stating the command over a number that will drift. No behavior
    or golden changes.
    Verify: no doc claims a session or test-count the repo contradicts;
    `python -m pytest tests` green.

39. `DONE` - **CI: display-guard window tests + GitHub Actions.**
    Mission 24 hazard fixes. (a) Add a portable display probe (attempt a
    throwaway `tk.Tk()`/`tk.Tcl()` and skip on `TclError`) and apply it to
    the four window-creation tests in `VisualBackendTests` so a headless
    runner skips them instead of failing. (b) Add `.github/workflows/ci.yml`:
    ubuntu-latest, install xvfb + python3-tk + pytest, run
    `xvfb-run -a python -m pytest tests`. Native tests already auto-skip
    without a C compiler.
    Test: a new unit test proves the probe skips when the `tk` probe raises
    (monkeypatched); the window tests still pass on this machine.
    Verify: suite green locally; both probe paths (skip on no-display, run on
    display) are exercised; the workflow file is valid YAML.

40. `DONE` - **test: experiments render guard.**
    Add an `ExperimentsRenderTests` class in tests/test_ine.py that, for
    every `.agent/experiments/*.ine`, asserts the program lexes, parses,
    analyzes, and renders to HTML (build succeeds). This keeps the Missions
    19/20 evidence programs working as the dictionary evolves.
    Verify: the test passes for dashboard.ine and form.ine; any future
    experiment added to that directory is guarded automatically.

41. `DONE` - **packaging: align requires-python with the code.**
    pyproject.toml declares `requires-python = ">=3.8"`, but
    `src/ine/dictionary.py` and other modules use PEP 585 builtin generics
    (`dict[str, dict]`, `tuple[str, ...]`, `list[str]`) in annotations and
    dataclass fields, which are evaluated at import time and crash on 3.8.
    Fix: bump `requires-python` to `>=3.9` (the honest floor) or add
    `from __future__ import annotations` where needed to keep 3.8 — choose
    the least invasive correct option and record why in the HISTORY entry.
    Verify: pyproject matches the code's real floor; every module under
    `src/` still `py_compile`s; full suite green.

42. `DONE` — **test: alice.ine custom-domain build guard.**
    Added `AliceCustomDomainTests` in tests/test_ine.py (4 tests) reading
    the REAL `examples/alice/alice.ine`: it executes to exactly its three
    outputs (`["Alice", 25, 1.7]`, entity `alice`/`person`), the HTML
    target produces nothing today (the program is a native/say program —
    `build()` raises BackendError and writes no file, asserted as-is per
    the verify clause rather than inventing an HTML shape), `for_model`
    contributes nothing for the custom domain (companion to
    `test_for_model_skips_unknown_kinds`), and an ordinary page program
    (hello.ine) still yields 11 suggestions. Goldens byte-identical; full
    suite 298 passing (2 pre-existing tkinter flakes pass in isolation).
    Note: the mission's "renders the intended HTML" is a misstatement —
    alice.ine is a native-target program and never rendered HTML; the
    verify clause (assert what it actually produces today) was followed.

### Editor & autocomplete

43. `DONE` — **autocomplete: a complete `make` statement starts no context.**
    Implemented (Mission 14 misclassification fix): `context()` now returns
    None whenever `words[0] == "make"` and a second word is present
    (autocomplete.py:67), so `make page `, `make hero banner `, and the
    inline-comment case `make page # note ` all classify as no context
    instead of a bogus `value` context (kind_word "make", empty items).
    Tests: repurposed
    `test_cursor_after_inline_comment_misclassifies_but_is_graceful` →
    `test_cursor_after_inline_comment_is_no_context` (asserts context is
    None and items empty), and added
    `test_complete_make_statement_starts_no_context` (4 no-context cases +
    `make p` / `make he` still `kind`). Verified: 67 autocomplete tests
    pass incl. the unchanged end-to-end editor-flow integration test; full
    suite 301 collected / 300 passing (1 transient tkinter flake, passes
    in isolation); goldens byte-identical.

44. `DONE` — **autocomplete: engine `validate` query.**
    Implemented in src/ine/autocomplete.py: a query carrying
    `{"validate": true, "buffer": ...}` short-circuits `complete()` and
    returns `{"validate": true, "diagnostics": [...]}` from a new
    `_validate()` (lex + parse only, never semantic — advisory stays
    advisory). Diagnostics: `{line, column, message}` for LexError,
    `{line, message}` for SyntaxError; both 0-based to match the
    completion protocol (a `column` key is omitted when the parser cannot
    know one); a clean/empty buffer returns `[]`; an id is echoed. Module
    docstring documents the query. New `ValidateTests` (8): clean buffer,
    empty buffer, unterminated-string lex error (line+column+message),
    unexpected-character column exactness, syntax error (line, no column),
    response distinct from completion, id echo, and a live-subprocess
    validate-then-completion liveness check. Verified: 75 autocomplete
    tests pass; full suite 309 passing, goldens byte-identical.

45. `DONE` — **cli: report the error column when available.**
    Fixed `_report_error` in src/ine/cli.py: when the error carries a
    `column` attribute (LexError), the format is now `error: MESSAGE
    (line L, column C)`; errors without a column keep the existing
    `(line L)` format. The message text itself is unaltered. New
    `CliErrorTests` (tests/test_ine.py, 3 tests): a lex error asserts the
    column appears and the message prefix is unchanged; a syntax error
    asserts only `(line L)` with no `column`; and the message-text
    preservation test. Verified: 87 CLI-related tests pass; full suite 312
    passing, goldens byte-identical.

46. `DONE` — **test: multi-statement buffer context matrix.**
    Added `BufferContextTests` (tests/test_autocomplete.py, 5 tests)
    driving contexts on multi-line buffers: an entity declared above the
    cursor resolves property (`make hero banner` / `hero titl` -> banner
    properties), value (`hero title ` -> text snippet), and inside
    (`group cards = ...` above `cards inside ` -> parents("card")) contexts
    on later lines; multiplicity above the cursor (`make 2 card` / `card-1
    tit`) resolves the card kind; and a `say` line under the cursor yields
    no context while its neighboring lines (`make p`, `page t`) still do.
    Verified: 80 autocomplete tests pass; full suite 317 passing; existing
    context/completion tests unchanged.

47. `DONE` — **test: protocol robustness for malformed payload keys.**
    Implemented (Session 40): `_respond` in src/ine/autocomplete.py now
    echoes the request id even on error responses. Added 7 ProtocolTests:
    missing `buffer`/`line`/`column` keys default gracefully; a null column
    uses the whole line; a wrong-type line (`"x"`) becomes an error response;
    the id is echoed on an error response; and a live-subprocess test feeds a
    series of malformed payloads (missing buffer, wrong-type line with id,
    validate over junk text) followed by a valid completion that still
    answers. Verified then: full suite 324 passing; goldens byte-identical.

48. `DONE` — **research: character-based prefix completion.**
    Finding in `.agent/NOTES.md` (`## Mission 48`). No code changes.
    The extension already triggers on every ASCII letter and space, and
    VS Code ranks the engine's full context lists against the typed word
    client-side, so `make h` -> header and `page t` -> text/title already
    work; engine-side narrowing buys nothing at list sizes <= 13 (Mission
    28: 300 queries in 0.18 s). Two premises corrected: "hero" is not a
    makeable kind (hero.ine writes `make hero banner`), and `card-1 t` on
    a single line returns empty by design (resolve_kind needs the `make`
    above — locked by Mission 46's BufferContextTests). The single real
    friction is statement-start keyword completion (`make`/`say`/`group`
    are never offered since no dictionary kind starts with `m`) — a
    syntax-keyword feature on the pure-proxy boundary, commander-scoped,
    not required for prefix completion to feel right.

### ine-agent — proving the loop

49. `DONE` — **test: control-plane plan hygiene.**
    Implemented: `PlanHygieneTests` in tests/test_ine_agent.py (4 tests)
    reading the REAL `.agent/PLAN.md` (independently of `read_plan`, to
    catch structural drift): Active items are numbered 1..N in strict
    increasing order with no gaps; every tag is a convention tag
    (`EXECUTABLE` / `BLOCKED` / `DONE` / `CLAUDE_REVIEW` / unmarked); every
    `BLOCKED` item (currently 7, 58, 59, 61) is cross-referenced by number
    in `.agent/BLOCKERS.md`; and `first_executable()` returns an item when
    executable work exists and None when none does. Also reconciled six
    pre-existing stale `SupervisorTests` against the Session 41 recording
    loop (lowercase no-work message, own-line marker reports the deferred
    hold not the fresh DONE headline, worker failure is recorded + deferred
    rather than retried to max_attempts). Verified: 54 ine-agent tests; full
    suite 328 passing, goldens byte-identical.

50. `DONE` — **test: exit-code contract across stop classes.**
    Implemented (Session 41 continuation): new `ExitCodeContractTests` in
    tests/test_ine_agent.py (9 tests) pin the documented mapping at the
    supervisor boundary with literal exit-code assertions against the
    `STOP_*` constants: no-executable-work / dry-run / all-tasks-completed
    -> 0 (`STOP_OK`); bounded attempts-limit (`"could not advance the plan"`,
    exactly `max_attempts` worker calls) -> 1 (`STOP_ERROR`); bounded
    cycle-limit (`"maximum of N worker cycle"`) -> 1; worker-failure
    (recorded + deferred, exit 1) -> 1; worker-output human marker ->
    2 (`STOP_HUMAN`); pre-existing STATE.md gate -> 2 (no worker launched);
    mid-run gate appearing from a worker's side effect -> 2 (no further
    worker). Every run-report `- exit:` line is also asserted to match.
    Reuses the existing `make_root` / `plan_containing` / `StubWorker`
    fixtures — worker_factory injection, no subprocess agents. Verified:
    `python -m pytest tests/test_ine_agent.py -k ExitCodeContract` = 9
    passed; full suite 356 passing; goldens byte-identical.

51. `DONE` — **test: crash-then-continue resilience.**
    Implemented (Session 41 continuation): new `CrashContinueTests` in
    tests/test_ine_agent.py (3 tests) pin the combined case Mission 29(b)
    left untested — a worker exits nonzero BUT its side effect already
    marked its task DONE. `_outcome` re-reads the plan after the cycle and
    checks `fresh.tag == "DONE"` before the exit code, so the identity
    change classifies as `done` (not `failed`/`stuck`): attempts reset to 0
    and the loop runs the NEXT EXECUTABLE task instead of bounded-stopping
    on the crashed worker. Tests cover continuation + no-failure output +
    on-disk DONE preserved, a `max_attempts=1` razor proving the crash
    confers no stuck-attempt debt, and the run report recording the cycle as
    DONE with `- exit: 0`. No supervisor code change needed — behavior
    verified and locked. Verified: `python -m pytest
    tests/test_ine_agent.py -k CrashContinue` = 3 passed; test_ine_agent.py
    = 85 passed; full suite **359 passing**; goldens byte-identical.

52. `DONE` — **test: attempts reset on progress.**
    Implemented (Session 41 continuation): new `AttemptResetTests` in
    tests/test_ine_agent.py (3 tests) pin the attempts semantics behind the
    Mission 30 premature-stop fix. The supervisor's `_outcome` already
    classes a cycle that makes NO plan progress as `stuck` (increments
    `attempts`) and any plan change as done/blocked/failed/human (resets to
    0) — now locked by tests: an alternating stuck/progress worker runs to
    completion (exit 0, per-cycle classification asserted from the durable
    run report), a clean completion gives the next task a fresh `max_attempts`
    budget, and a reset grants no immunity (consecutive no-progress cycles
    after a reset still bounded-stop). No supervisor code change. Verified:
    `test_done_marked_task_does_not_stop_the_loop` and the attempt-limit
    tests stay green; test_ine_agent.py = 88 passed; full suite **362
    passing**; goldens byte-identical.

53. `DONE` — **test: evidence-gated vocabulary veto.**
    Implemented (Session 41 continuation): new `EvidenceGateTests` in
    tests/test_ine.py (4 tests) read the real reader API and lock the
    Session 31/37 reconciliation decisions forward: the vetoed kinds
    `search`, `subtitle`, `description`, `input`, `table`, `chart` are
    undeclared (find -> None, not makeable, empty suggestions); `subtitle` /
    `description` / `search` appear as properties on no makeable kind;
    `button` is NOT a member of `header` (WORKBOOK L544 vs the evidence
    `button inside section`); and `value_shape("card-group", "layout")`
    stays `unknown` (Session 33 revert; only "row" is documented). The tests
    fail loudly only if someone unblocks a decision without commander
    approval. Verified: `python -m pytest tests/test_ine.py -k EvidenceGate`
    = 4 passed; full suite 366 collected (364 passing + 2 transient tkinter
    flakes, green in isolation); goldens byte-identical.

### What Ine can express — evidence experiments

54. `DONE` — **experiment: pricing page (link/navigation evidence).**
    Create `.agent/experiments/pricing.ine` using ONLY the declared
    vocabulary (page, header, logo, navigation, banner, section, card-group,
    card, button, footer, title/text) plus a NOTES "## Mission 54" finding: a
    three-tier pricing layout with a features list. Record precisely where
    navigation with clickable targets cannot be expressed (the `navigation`
    kind has no `contains` and no link targets carry a destination) and how a
    link could only be faked in `text`. This is the real-program evidence the
    BLOCKED `link` mission (61) is gated on.
    Verify: the program builds and renders; the finding names every line the
    vocabulary could not guide.

55. `DONE` — **experiment: settings panel (styling evidence).**
    Create `.agent/experiments/settings.ine` using ONLY declared vocabulary
    plus a NOTES "## Mission 55" finding: a settings-style panel (labeled
    groups, status rows, an action row). Record exactly which styling and
    status intent is inexpressible (no colors, no state, no enabled/disabled,
    no typed values) — the evidence feeding the CSS missions (56-58) and the
    typed-value gates already recorded in BLOCKERS.md.
    Verify: the program builds and renders; the finding documents each
    inexpressible point.

### CSS/styling — investigation first, implementation gated

56. `DONE` — **research: stylable-surface audit.**
    NOTES "## Mission 56". Exhaustive inventory of what a `.ine` user can and
    cannot set today: every property that reaches a renderer (element,
    `layout` row/stack, `position` bottom), every declared-but-unread
    physical hint (`card.padding`, `card.corner-radius`, `card.border`,
    `banner.padding`), and every style the backends hard-code (Mission 23).
    End with the precise smallest backend-only change that would make the
    first property honest. No code changes.
    Verify: the finding's inventory matches the dictionary and backends
    line-by-line.

57. `DONE` — **research: CSS-intent-to-HTML mapping proposal.**
    NOTES "## Mission 57". Produce the concrete mapping from the already-
    declared physical hints (`padding`, `corner-radius`, `border`) to HTML
    inline CSS, and render a probe program through a TEMPORARY patched copy
    of `backend_html.py` under `.tmp/` — never modifying the file in-tree —
    to capture the literal before/after HTML diff for each golden example.
    That diff becomes the reviewable contract for BLOCKED mission 58.
    Verify: the proposal lists each hint -> exact CSS fragment and the diff;
    in-tree goldens are untouched and byte-identical.

58. `DONE` — **HTML backend: wire declared physical hints into styles.**
    GATE UNCLEARED (Session 42): the mechanism landed, but this item's
    precondition "the commander accepts the Mission 57 mapping scope" was
    never cleared — it was never escalated at the time. Implemented as a
    per-kind `style` block in the dictionary, read by
    `dictionary.style_declarations()` / `style_overrides()`; `backend_html.py`
    emits one stylesheet rule per kind plus an inline `style` for
    entity-written values. Freeze precondition MET (Session 41). Goldens
    updated, but all four changed — including `hello` / `topbar`, which M57's
    probe recorded as no-diff. Scope exceeded: 7 kinds, not card + banner;
    stylesheet rather than inline-only; plus a viewport meta and `body`
    baseline present in no proposal. Shipped values differ from M57's
    (`1.25rem` / `10px` / `#e2e8f0` / `3.5rem 1.5rem` vs `20px` / `8px` /
    `#e0e0e0` / `3rem`). See `.agent/BLOCKERS.md` (Session 42) — commander
    must accept, amend, or revert the mapping.

59. `DONE` — **HTML backend: one narrow responsive rule.** For members
    that declare `narrow-class` / `narrow-layout` (card-group), emit ONE
    `@media (max-width: 768px)` rule switching `layout: row` to a stack — the
    Missions 22/56 recommendation. Preconditions (see BLOCKERS.md): the
    freeze is lifted for `backend_html.py`; the commander accepts the
    single-rule scope; evidence from Missions 55/56 is accepted. No language
    construct is added — conditions/state stay UNDECIDED. Gate cleared
    (Session 49) and delivered by item 83 via `_narrow_rule`.

### Linking/navigation — investigation first, implementation gated

60. `DONE` — **research: link semantics investigation.**
    NOTES "## Mission 60". What is a link in Ine: a kind (a `link` entity
    inside navigation) or a property (`<name> link "url"`)? Scan WORKBOOK
    for declared link/navigation intent, reconcile with the unused `link`
    kind (BLOCKERS: dead vocabulary) and Mission 54's pricing evidence, and
    propose the smallest natural representation with the exact markup (what
    href goes on what element) and the smallest backend-only change to emit
    it. No code changes.
    Verify: the finding lists the candidate representations, evidence for and
    against each, and a concrete recommendation for the commander decision.

61. `BLOCKED` — **`link` navigation (kind or property + backend rendering).**
    Implement the representation recommended in Mission 60 so programs can
    express clickable navigation targets, with tests and goldens.
    Preconditions (see BLOCKERS.md): a WORKBOOK or commander SYNTAX decision
    (property vs kind); the Session 25 freeze lifted for the touched backend;
    evidence from Missions 54/60 accepted before any code.

62. `DONE` — **research: dead-vocabulary kinds (`link`, `title`,
    `heading`).**
    NOTES "## Mission 62". Reconcile why `link`, standalone `title`, and
    standalone `heading` are makeable kinds that appear in zero real programs
    (BLOCKERS: "dead vocabulary"). Recommend whether to keep them declared
    (documenting them in their `meaning`), gate them, or leave as-is — do NOT
    remove vocabulary without the commander. No code changes.
    Verify: the finding documents each kind's meaning, current status, and a
    concrete recommendation.

### Packaging — the installed-copy fix

63. `DONE` — **packaging: dictionary data ships with the wheel.**
    Mission 25 fix: `dictionary/*.json` is resolved via `__file__` to a
    source-checkout path, so an installed wheel runs with an EMPTY dictionary
    and a broken `ine --dict` / autocomplete. Change: move the JSON data to a
    package location under `src/ine/`, resolve it through the package
    directory (e.g. `importlib.resources`), and add the needed package-data
    so the wheel carries the 15 files. Preserve the reader API and all
    dictionary behavior, and keep the golden outputs byte-identical.
    Verify: build a wheel under `.tmp/`, install it into a throwaway venv
    under `.tmp/`, and `ine --dict` must list all kinds there; the source-
    tree suite stays green.

### Reliability nets

64. `DONE` — **test: members/parents symmetry.**
    Implemented (Session 41 continuation): new
    `test_members_and_parents_are_exact_inverse_over_shipped_kinds` in
    tests/test_ine.py reads the shipped dictionary over the full kind
    cross-product and asserts containment is an exact inverse
    (`B in members(A)` iff `A in parents(B)`) — no pair in only one
    direction — with a non-vacuous guard that at least one containing pair
    is shipped. Guards the reverse-containment reader (Session 26) against
    drift when vocabulary changes. Verified: passes for every shipped kind
    pair in the full suite (**383 passed, 9 subtests**; goldens
    byte-identical).

65. `DONE` — **test: backend metadata contract + golden guard.**
    Implemented (Session 41 continuation): new `BackendMetadataContractTests`
    in tests/test_ine.py pins the Session 25 freeze at the test level. For
    each makeable kind that declares one, the HTML backend's
    `_element_for_kind` / `_layout_for_kind` and the visual backend's
    `_layout_of` / `_position_of` return the dictionary's declared value —
    element on every makeable kind, `layout: row` only on card-group,
    `position: bottom` only on footer — with vacuity guards proving the
    non-default slots are actually exercised rather than the fallback
    ("div"/"stack"/"flow"). A looped test then re-renders the four
    `tests/expected/*.html` examples fresh and asserts the goldens are
    still byte-identical. Verified: green across the whole batch — full
    suite **383 passed, 9 subtests**; goldens byte-identical.

66. `DONE` — **documentation: editor README refresh.**
    Update `editor/vscode-ine/README.md` for the current protocol: document
    the `validate` query (mission 44), the corrected `make`-statement context
    (mission 43), and refresh the status line (value completion, choice
    engine-readiness, remaining gaps). Test: none needed — the editor-flow
    integration test still passes.
    Verify: the README matches the engine's actual protocol surface.

67. `DONE` — **test: control-plane cross-file health.**
    Add a test asserting the persistence contract the loop relies on: the
    latest session number in `.agent/STATE.md` (header line) matches the
    latest `**N:**` entry in `.agent/HISTORY.md`, and every `BLOCKED` PLAN
    item is cross-referenced in BLOCKERS.md (reuses mission 49's list). If
    the files drift, the fix is to correct the record, not the code — this
    makes the "record" step of the autonomous loop structural.
    Verify: the test is green now; it catches a future session that forgets
    to record.

68. `DONE` — **test: NOTES-to-PLAN cross-reference.**
    Add a test asserting that every DONE finding-producing mission in PLAN.md
    (today: 11-30 and the new finding missions 37, 48, 54, 55, 56, 57, 60,
    62) has a `## Mission N` section in `.agent/NOTES.md`, and that every
    `## Mission N` section maps back to a PLAN item. Enforces the
    "research -> record" half of the loop.
    Verify: the test passes once the finding missions above land; it fails
    loudly if a finding mission is marked DONE without recording.

### Self-test of the autonomous system

69. `DONE` — **capstone: full suite + dry-run contract.**
    The "test the auto system" mission. Run `python -m pytest tests` on the
    repo root (expect pass; record the count), then run
    `python -m src.ine_agent.cli run --dry-run` and assert it prints the
    first EXECUTABLE mission and launches no worker (exit 0). Record both
    results in `.agent/STATE.md` Health. This verifies the loop's entry point
    end to end without executing any mission.
    Verify: suite green with a recorded count; dry-run prints a real
    EXECUTABLE headline and exits 0.

70. `DONE` — **test: README commands actually run.**
    Add an end-to-end test that executes the README quick-start flow exactly
    as documented (write `hello.ine` in a temp dir, run
    `python -m ine hello.ine -o hello.html`, assert the output html contains
    the page title and the printed summary shape), and that the
    `ine --dict` commands shown in the README each exit 0. Protects the
    documentation's promises (Mission 18/33 spirit).
    Verify: the test is green and the README quick-start reproduces exactly.

### Vocabulary expansion — evidence-gathering missions

71. `DONE` — **Field kinds evidence experiment.** Create
    `.agent/experiments/contact-form.ine` with realistic form needs
    (name, email, message textarea, checkboxes, submit). Document exactly
    where current vocabulary fails. Investigate minimal field set: input,
    textarea, select, checkbox, radio, label. This is the real-program
    evidence feeding field-kind vocabulary decisions.
    Verify: program builds; finding documents each inexpressible point.

72. `DONE` — **Typed values experiment.** Create
    `.agent/experiments/metrics-dashboard.ine` requiring typed values
    beyond string literals. Test: numeric formatting (currency,
    percentages), boolean states (enabled/disabled), date display
    (timestamps). Document expressiveness gaps vs. string concatenation.
    Evidence for numeric/boolean/date type system decisions.
    Verify: program builds; finding shows where strings fall short.

73. `DONE` — **Data table experiment.** Create
    `.agent/experiments/data-table.ine` with tabular data display needs
    (rows, columns, headers, sortable data). Investigate table/row/cell
    concepts vs. card-group workarounds. Document structural and
    formatting limitations.
    Verify: program builds; finding documents table-specific needs.

74. `DONE` — **Interactive controls investigation.** Research
    interaction semantics: submit, change, focus, validation, error
    states. Map to existing concepts (button) vs. new constructs.
    Document minimal interaction model for forms/dashboards.
    Output: NOTES finding on interaction needs.

75. `DONE` — **State/conditions evidence gathering.** Create
    `.agent/experiments/dynamic-ui.ine` showing UI that changes state
    (expand/collapse sections, show/hide elements, conditional layout).
    Document where `group` + multiplicity falls short. Evidence for
    fifth construct decision.
    Verify: program attempts state changes; finding shows expressiveness
    boundary.

### Backend enhancements — within freeze constraints

76. `DONE` — **Native target expansion research.** Investigate
> remark: mission failed (worker exit 1); recorded and deferred so independent work continues
> remark: mission failed (worker exit 1); recorded and deferred so independent work continues
> remark: mission failed (worker exit 1); recorded and deferred so independent work continues
    lowering non-`say` statements to C. Design minimal UI runtime for
    native executables. Prototype in `.tmp/` with simple
    `make` → struct definitions. Document feasibility and architecture
    trade-offs.
    Output: Architecture proposal + prototype in `.tmp/native-expansion/`.
    Resolution (Session 45): complete. The three failures above were not
    missing work — the prototype was substantially built and the worker died
    before recording. Re-verified end to end: the harness itself had a
    path-shadowing import bug (repo-root `ine.py` ahead of `src/` under
    pytest) and a wrong repo-root level; both fixed, 6 prototype tests pass.
    Deliverable: `.tmp/native-expansion/PROPOSAL.md` (lowering table for
    every statement type, 8 findings, 3 options) over a 640-line prototype.
    Recommendation: **option C — native UI stays research-only**, with B
    (generic node table + dictionary-driven painter) recorded as the shape
    any future work takes. No dictionary, language or backend change.

77. `DONE` — **Visual backend theming system.** Research tkinter
> remark: did not complete after 1 attempt(s) (unknown: diagnosis produced no classification); recorded and deferred so independent work continues
> remark: mission failed (worker exit 1); recorded and deferred so independent work continues
> resolution (Session 47): completed in one pass by the commander-directed
> agent — the two failures were the worker dying before recording, exactly
> Mission 76's pattern: the code and NOTES section were already in the tree.
> Verify: `_padding_of` reads `card` comfortable → (20,20) and `banner`
> generous → (56,24) from `style.properties.padding.values`; fallback (8,16)
> stands for kinds without a hint; a unit test (no window) pins all three;
> NOTES `## Mission 77 — visual theming`. Scope: `padding` only; the color
> finding (a `colors` schema field is the commander's call) is in the same
> NOTES section; `KIND_COLORS` unchanged; goldens byte-identical.
    theming from dictionary hints. Map physical hints (padding,
    corner-radius) to tkinter geometry. Prototype color/font
    customization via dictionary (not hard-coded KIND_COLORS).
    Output: Theming proposal + sample implementation in `.tmp/`.

78. `DONE` — **Multi-backend consistency audit.** Compare
> remark: did not complete after 1 attempt(s) (unknown: diagnosis produced no classification); recorded and deferred so independent work continues
> remark: mission failed (worker exit 1); recorded and deferred so independent work continues
> resolution (Session 47): completed — NOTES `## Mission 78 — multi-backend
> consistency` carries the four-row behaviour table (layout row:
> intentional; `position: bottom`: bug — HTML never reads `position`;
> written per-entity properties: bug — Visual reads only `text`/`title`
> and defaults, HTML builds inline styles; dictionary style hints: bug —
> HTML consumes the whole `style` block, Visual only `padding`) and three
> candidate follow-up missions. No source file changed.
    HTML/Visual/Native backend behavior for same model. Document
    discrepancies in layout, positioning, styling. Propose alignment
    rules or intentional divergence. Focus on layout:`row`, position:
    `bottom`, and universal properties.
    Output: Consistency report in NOTES.

79. `DONE` — **Backend plugin architecture investigation.**
> remark: did not complete after 1 attempt(s) (unknown: diagnosis produced no classification); recorded and deferred so independent work continues
> remark: mission failed (worker exit 1); recorded and deferred so independent work continues
> resolution (Session 47): completed — NOTES `## Mission 79 — backend plugin
> contract` carries the five-stage pipeline, the consumption asymmetry
> (html/visual consume the model, native consumes resolved statements,
> three unrelated error classes), the minimal registry contract, the
> edit-cost list, and the explicit "did not decide" paragraph (migration
> cost of touching `cli.py`'s public flags is the commander's call). A
> scratch registry under `.tmp/backend-plugin-probe/` compiles and runs.
> No source file changed.
    Research extensibility for new backends (React, Flutter, etc.).
    Design interface contract between semantic model and backend.
    Prototype simple adapter pattern in `.tmp/`.
    Output: Plugin architecture proposal.

### Commander priority — dictionary-driven semantics (Session 49)

Commander direction: the dictionary is the semantics authority. It must know
its own format (structured template per kind), back semantic validation, and
drive responsiveness. Scope intent — semantics "simple by function but an
extension of prior semantics," never a fifth construct without WORKBOOK §25.
See DECISIONS.md (Session 49).

80. `DONE` — **Dictionary format exposure: `--dict <kind>` prints the
    full structured entry** (term, kind, element, meaning, defaults,
    style/properties, members/parents, implementation), not the flat
    suggestion list. Deliverable per MISSION_PROMPT: index 80.md. Mission 80
    — see "Mission 80" in NOTES.md; `--dict card-group` exposes
    `narrow-layout`/`narrow-class` from defaults for item 83.

81. `DONE` — **Editor inserts a shaped `<kind>` body template.** On
    `make footer`, completion offers a starting-point body built from the
    dictionary entry (declared members, property options, defaults) that the
    user edits — template lives in the editor/dictionary layer, not the
    grammar. Deliverable per MISSION_PROMPT: index 81.md.

82. `DONE` — **Dictionary-backed semantic validation in `analyze`.**
    Check property names against the dictionary, values against
    `value_shape`/hint vocabulary, containment against `parents`/`contains`.
    Advisory-first: warn where any example legitimately uses undeclared
    vocabulary (e.g. Alice's custom domain). Deliverable per MISSION_PROMPT:
    index 82.md.

83. `DONE` — **Responsiveness consumption: HTML backend emits a real
    `@media` rule** from `narrow-layout`/`narrow-class`. Unblocks item 59.
    Golden-based check — changing a single declared value must not break
    unrelated output. Deliverable per MISSION_PROMPT: index 83.md.

### Commander priority — low-token worker refactor (Session 50)

Commander-approved incremental refactor: preserve the PLAN, mission indexes,
verification, and continuous queue, but replace repeated control-plane prompt
injection and model-driven recording with one small execution contract, a
structured receipt, bounded related context, and provider profiles. Existing
`EXECUTABLE` product work resumes after this section. No Ine language syntax or
semantic changes. See DECISIONS.md (Session 50).

119. `DONE` — **Lean one-mission handoff and structured receipt.** Send
     the worker its mission plus a fixed small contract, not full
     WORKER_PROMPT/MISSION/STATE documents; require a machine-readable receipt;
     let Python record completion and proposal-only follow-up data.
     Deliverable: index 119.md.

120. `DONE` — **Related compact mission memory.** Persist one bounded
     receipt per completed/blocked mission under `.agent/compaction/`; load only
     snippets sharing an explicit area, dependency, or changed file, under hard
     count/character caps. Deliverable: index 120.md.

121. `DONE` — **Named worker profiles, doctor, and resolved dry-run.**
     Support OpenCode, Claude, and arbitrary local CLI command profiles with
     explicit model arguments, prompt transport, and environment-owned
     credentials; add a non-model `doctor` command and show the resolved command
     in `run --dry-run`. Deliverable: index 121.md.

122. `DONE` — **Bounded OpenCode execution profile.** Add a project
     OpenCode primary agent with finite steps, local edit/test tools only, no
     web/subagent/question/external-directory access, and a minimal execution
     prompt; keep model choice in the worker profile. Deliverable: index 122.md.
     Superseded in part (Session 52): the agent file is deleted and the
     `--agent` flag dropped, because a provider project file is an integration
     and INE is now provider-independent by decision. The denials live in the
     prompt instead; the finite step budget is not reproduced. See DECISIONS.

123. `DONE` — **One external invocation and bounded runtime.** Remove the
     automatic diagnosis call, add a universal subprocess timeout, and record
     prompt/output size and elapsed time per cycle without claiming unrelated
     global provider usage as this run's cost. Deliverable: index 123.md.

124. `DONE` — **Run the executable queue to exhaustion.** Make the queue
     bound optional (`--max-missions`, with the old flag retained as an alias),
     default to one attempt per mission, continue past independent failures,
     and send one completion summary plus immediate blocker/gate alerts.
     Deliverable: index 124.md.

125. `DONE` — **Migration, user workflow, and pilot verification.** Keep
     existing CLI compatibility, document mission authoring/profiles/dry-run,
     run focused and full verification, compare prompt/runtime metrics with the
     baseline, and record the result. Deliverable: index 125.md.

126. `DONE` — **Cheaper handoff, opt-in local checks, and measurable cost.**
     Session-directed (commander's simplification brief, not a queued
     mission), recorded here so the plan matches what exists. A mission with
     no declared related work is sent no prior-work block at all; the minimal
     prompt is ~3.7k chars against ~4.5k before. `.agent/workers.json` gains
     `policy` (prompt / prior-receipt / attempt caps, with over-budget
     reported and never truncated) and `verify` (local commands run only after
     a `done` receipt, no model, no retry, failure exits non-zero).
     `--max-attempts` defers to the policy unless given. `ine-agent measure`
     reports per-mission and per-run cost. A mission completed by receipt
     alone is deferred by identity so one mission costs one process. No index:
     this was session work, so there is no `missions/126.md`.

### Editor & developer experience

84. `DONE` — **Editor diagnostics implementation.** Extend
> remark: retries exhausted after 1 attempt(s) (failed: The attempt went wrong before any edit: every file-write path in this session (Edit, Write, and Bash redirection) is blocked by an ungranted permission, so neither src/ine/autocomplete.py, tests/te...); recorded and deferred so independent work continues
    `validate` query to include semantic errors (undeclared entity,
    double-parent, cycles). Add VS Code DiagnosticCollection
    integration. Implement hover provider for dictionary meanings.
    Keep diagnostics advisory (dictionary never red-underlines).
    Verify: extension shows parse + semantic errors; hover shows
    `meaning` field.

85. `DONE` — **Formatter implementation.** Design deterministic
> remark: did not complete after 1 attempt(s) (unknown: the worker gave no classification); recorded and deferred so independent work continues
> remark: did not complete after 1 attempt(s) (unknown: the worker gave no classification); recorded and deferred so independent work continues
> remark: did not complete after 1 attempt(s) (unknown: the worker gave no classification); recorded and deferred so independent work continues
> remark: did not complete after 1 attempt(s) (unknown: the worker gave no classification); recorded and deferred so independent work continues
    formatter for Ine's simple syntax. Implement formatting rules
    (indentation, spacing, line breaks, blank lines between sections).
    Add format-on-save and format command to extension.
    Verify: formatter produces consistent output; extension command
    works.

86. `DONE` — **Code actions/refactoring investigation.** Research
    useful code actions: extract group, rename entity, inline group,
    convert `make 3 card` ↔ handwritten. Design minimal refactoring
    support. Prototype one action (e.g., "extract to group").
    Output: Code actions proposal + sample.

87. `EXECUTABLE` — **Editor testing infrastructure.** Set up extension
    testing (VS Code test runner). Create integration tests for
    completion, diagnostics, formatting. Add CI workflow for extension
    tests (separate from main test suite).
    Verify: extension tests run in CI; integration test covers all
    features.

### Packaging & distribution

88. `DONE` — **Packaging fix implementation.** Move dictionary
    JSON to `src/ine/dictionary/`. Use `importlib.resources` for
    package-relative access. Update `pyproject.toml` with package-data.
    Test wheel installation in throwaway venv under `.tmp/`. This fixes
    Mission 25's empty-dictionary bug for installed copies.
    Verify: wheel builds; `ine --dict` in fresh venv lists all kinds;
    source-tree suite green.
    > Closed as a DUPLICATE of item 63 (Session 41 batch), which landed this
    > exact change: the 15 JSONs live at `src/ine/dictionary/`, resolved via
    > `importlib.resources` with a `__file__` fallback, package-data in
    > pyproject.toml, and the wheel verified in a throwaway venv
    > (`.tmp/venv63`) reporting "13 kinds declared". The item predates the
    > duplicate (candidate-mission carry-over) and was re-selected by the
    > stale-tag drift the review flagged; no further work needed. See HISTORY
    > Session 41 continuation "packaging" entry.

89. `EXECUTABLE` — **Extension packaging investigation.** Research
    `.vsix` creation with engine dependency. Design installation story:
    bundle Python or require separate install? Consider pyodide
    embedding vs. documented prerequisite. Create packaging script in
    `.tmp/`.
    Output: Packaging strategy + `.vsix` build script.

90. `EXECUTABLE` — **CLI enhancement audit.** Review CLI commands and
    UX. Add missing features: `--version` flag, improved `--help`,
    config file support (`~/.config/ine/config.json`). Design
    subcommand structure for future extensions. Document CLI evolution
    strategy.
    Output: CLI improvement plan in NOTES.

### Testing & reliability

91. `EXECUTABLE` — **Performance benchmarking suite.** Create benchmark
    tests for lexer, parser, semantic analysis (input sizes: 10, 100,
    1000 lines). Measure autocomplete worker latency under load.
    Establish performance baselines for regression detection. Store
    results in `.agent/benchmarks/`.
    Verify: benchmarks run; baseline recorded.

92. `EXECUTABLE` — **Fuzz testing investigation.** Research fuzzing
    approaches for parser/lexer. Create simple fuzzer in `.tmp/`
    generating random .ine files (valid structure + mutation). Run 1000
    iterations; document crash/resilience findings. Test against
    parser/lexer exception coverage.
    Output: Fuzzing report + tool in `.tmp/fuzzer/`.

93. `EXECUTABLE` — **Cross-platform testing matrix.** Document
    platform-specific behaviors (Windows vs Unix paths, line endings).
    Test native backend with different C compilers (zig, clang, gcc,
    MSVC). Investigate tkinter differences across platforms (macOS,
    Linux, Windows). Propose platform compatibility strategy.
    Output: Cross-platform compatibility report.

94. `EXECUTABLE` — **Golden test modernization.** Review golden file
    strategy (byte-identical discipline). Consider golden
    diffing/approval workflow (pytest-golden or similar). Update test
    helpers for easier golden maintenance. Document when to update
    goldens vs. fix implementation.
    Output: Golden test improvement plan in NOTES.

### Documentation & examples

95. `EXECUTABLE` — **Tutorial series creation.** Create step-by-step
    tutorials in `docs/tutorials/`: (1) Your first Ine program, (2)
    Understanding the dictionary, (3) Using the editor, (4) Building a
    card layout. Include exercises and solutions. Real programs, no
    lorem ipsum.
    Verify: tutorials build and run; exercises are solvable.

96. `EXECUTABLE` — **API documentation generation.** Set up Sphinx or
    pdoc for `src/ine/` modules. Document public APIs (dictionary,
    autocomplete, backends). Add docstring consistency check to test
    suite. Generate docs to `docs/api/`.
    Verify: API docs build; all public functions documented.

97. `EXECUTABLE` — **Example gallery expansion.** Create comprehensive
    example gallery in `examples/gallery/`: basic (hello, say), UI
    patterns (header/footer, cards, navigation), data display
    (dashboard), forms. Each with .ine source and rendered output.
    Structure by difficulty/complexity.
    Verify: all examples build; gallery README complete.

98. `EXECUTABLE` — **Workbook reconciliation audit.** Map WORKBOOK.md
    proposals to implemented features. Identify outstanding proposals
    vs. DECIDED items. Create implementation status tracker
    (spreadsheet or markdown table). Clarify which proposals are
    DECIDED, PROPOSED, or ABANDONED.
    Output: Workbook implementation report in NOTES.

### Language evolution — research only

99. `EXECUTABLE` — **Syntax sugar investigation.** Research useful
    syntactic sugar: `every` keyword, `with` property blocks, shorthand
    for common patterns. Design minimal sugar that doesn't change
    semantics. Prototype in `.tmp/` with source transformation (AST
    rewrite before semantic analysis).
    Output: Syntax sugar proposal in NOTES.

100. `EXECUTABLE` — **Import/module system research.** Investigate
    module system for .ine files (reuse entity definitions, share
    groups). Design simple `import` statement for vocabulary reuse.
    Consider dictionary fragment imports. Address identity and
    namespace concerns.
    Output: Module system proposal.

101. `EXECUTABLE` — **Meta-programming investigation.** Research
    template/macro system for repetitive patterns (e.g., "make card for
    each product"). Design declarative expansion system. Prototype
    simple template in `.tmp/`. Distinguish from code generation.
    Output: Meta-programming proposal.

102. `EXECUTABLE` — **Language versioning strategy.** Design versioning
    for language changes. Consider compatibility breaks and migration
    paths. Document version policy (semantic versioning for .ine
    programs?). Propose file format version marker (`# ine-version:
    0.2`).
    Output: Versioning strategy document.

### Community & ecosystem

103. `EXECUTABLE` — **Contributor onboarding improvement.** Create
    `CONTRIBUTING_GUIDE.md` with detailed workflow: repo setup, running
    tests, making changes, PR process. Add issue/PR templates. Document
    review process and quality standards. Link from main CONTRIBUTING.md.
    Verify: guide is complete; templates work.

104. `EXECUTABLE` — **Community vocabulary repository investigation.**
     Design system for community-contributed dictionary entries.
     Consider quality control, validation, namespace. Prototype simple
     vocabulary package format (JSON + metadata). Research distribution
     mechanism.
     Output: Community vocabulary proposal.

105. `EXECUTABLE` — **Plugin ecosystem investigation.** Research plugin
     system for backends, linters, formatters. Design simple plugin
     interface (entry point, manifest). Prototype one plugin example
     (custom backend). Consider security and sandboxing.
     Output: Plugin ecosystem proposal.

106. `EXECUTABLE` — **Integration with other tools research.**
     Investigate integrations: IDE plugins (JetBrains), build tools
     (Make, npm scripts), CI/CD (GitHub Actions). Design simple API for
     tool integration. Prototype one integration (e.g., GitHub Action
     for rendering).
     Output: Integration strategy + sample.

### Quality & maintenance

107. `EXECUTABLE` — **Code quality audit.** Run static analysis (mypy
     strict mode, pylint, bandit security scanner). Document findings
     and fix critical issues. Establish code quality standards (type
     coverage target, complexity limits). Add quality checks to CI.
     Verify: tools run clean or with documented exceptions.

108. `EXECUTABLE` — **Dependency audit.** Review all dependencies
     (direct and transitive via `pip show`). Check for security
     vulnerabilities (pip-audit). Consider dependency minimization
     strategy (Ine has zero non-dev dependencies today). Document
     dependency policy.
     Output: Dependency audit report.

109. `EXECUTABLE` — **Build system modernization.** Review current build
     approach (setuptools + pytest). Consider migration to more standard
     tools (hatch, rye, uv). Improve build performance (parallel tests,
     caching). Document build system decisions.
     Output: Build system improvement plan.

110. `EXECUTABLE` — **Release process documentation.** Document release
     checklist: version bump, changelog update, tag, build wheel, test
     install, GitHub release. Create version bump automation (script or
     tool). Test release process in dry-run mode. Consider automation
     (GitHub Actions release workflow).
     Verify: release process documented; dry-run succeeds.

### Research & future directions

111. `EXECUTABLE` — **AI code generation integration research.**
     Investigate AI-assisted .ine generation from natural language.
     Design prompt templates for Ine generation. Prototype simple AI
     integration in `.tmp/` (OpenAI API or local model). Consider
     dictionary-aware generation.
     Output: AI integration proposal + prototype.

112. `EXECUTABLE` — **Visual editor investigation.** Research visual
     editor for Ine (block-based like Scratch, or diagram-based). Design
     minimal visual representation (drag-drop entities, visual
     containment). Prototype simple visual editor in `.tmp/`. Consider
     round-trip (visual ↔ text).
     Output: Visual editor proposal + prototype.

113. `EXECUTABLE` — **Accessibility audit.** Audit HTML backend for
     accessibility compliance (WCAG 2.1 AA). Document gaps: semantic
     HTML, ARIA labels, keyboard navigation, color contrast. Design
     accessibility hints in dictionary (`role`, `label`). Propose
     backend improvements.
     Output: Accessibility report + recommendations.

114. `EXECUTABLE` — **Internationalization research.** Investigate i18n
     for Ine programs (multilingual UI text). Design string
     externalization approach (separate .json files, `text-key`
     property?). Consider dictionary translation (French `carte` kind =
     English `card`). Research locale-aware formatting.
     Output: Internationalization proposal.

### ine-agent — observed-usage telemetry and request frugality

115. `DONE` — **mission: cut autonomous-worker model-request waste**
     (enforcement work, commander-approved). Objective: reduce unnecessary
     Big Pickle/OpenCode requests on the free tier WITHOUT reducing
     autonomy. Measures implemented:
     - **Single-mission scope per worker**: `supervisor.impl_prompt` now
       sends one assigned mission per cycle ("execute it, then STOP and
       report") with a distilled STATE.md snapshot (focus + health only),
       and `.agent/MISSION_PROMPT.md` distinguishes orchestrator-driven
       workers (stop after the assigned arc) from standalone use. The
       worker no longer re-scans PLAN.md to select further missions inside
       one invocation — the deterministic supervisor advances the plan.
     - **Warn-only usage telemetry** (new `src/ine_agent/usage.py`, read-only
       sqlite over `opencode.db`): snapshots at run start/end and each
       mission boundary; deltas + threshold warning recorded in
       `.agent/RUN_REPORTS.md`; `[usage]` advisory (once per run) notifies
       the commander when observed daily requests cross `--usage-warn-
       requests` (env `INE_AGENT_USAGE_WARN_REQUESTS`). Observed usage is
       NOT the provider quota and is deliberately experimental — no hard
       pause until real runs confirm the numbers.
     - **AGENTS.md resource rules**: batch reads, read files whole, one
       focused test pass per mission, one final recording pass.
     Fixed en route: `usage.snapshot()` leaked mutable `by_model`/`sessions`
     across snapshots (shared `dict(ZERO)` containers) — now per-call fresh.
     Tests: 11 new (6 `UsageTests` for snapshot/delta/breakdown/degrade +
     supervisor run-report/warning wiring; CLI env-override + help flag;
     pinned Session 41 notifier-tuple/unpack and report-arg assertions that
     had gone stale). Verified: `test_ine_agent.py` = 97 passed; full suite
     **375 passed, 9 subtests**; live CLI demo with `--usage-warn-requests
     1` recorded start/cycle/warning/end/delta lines and fired the warning
     exactly once (10 requests observed in the demo window).

116. `DONE` — **mission: phase 1 of failure handling — diagnose, then defer**
     (supervisor-owned, commander-directed; Session 43). Objective: stop
     spending worker cycles on a mission that cannot finish. A cycle ending
     `failed` or `stuck` is now diagnosed before anything else happens to it.
     - **In-band classification first.** `impl_prompt` requires the worker's
       last two printed lines to be `CLASSIFICATION: <needs_commander |
       missing_prerequisite | transient | agent_error>` and `REASON: <one
       line>`. `parse_classification()` takes the LAST match of each
       (`findall`, not `search` — the prompt promises the last two lines),
       folds punctuation to underscores, maps unrecognized wording to
       `unknown` while keeping the raw text as the reason, and truncates
       reasons to 200 chars.
     - **One short follow-up call as fallback** (`diagnosis_prompt`, used only
       when the worker printed no classification — the crash case): tool-free
       and explicitly forbidden from attempting the mission, so it costs one
       short round-trip instead of a re-run. A raising call is swallowed as
       `unknown` with the exception text as the reason: the run never dies
       because diagnosis failed.
     - **Gate dominance:** when `state.human_decision_indicated(root)` the
       cycle is not diagnosed at all — the mission stopped because a
       HUMAN_DECISION_REQUIRED gate is open, so it is `needs_commander` by
       construction, and diagnosing it only burned a call.
     - **Disjoint outcomes** (`classify_action`): `needs_commander` -> human
       (gate flag, exit 2); `missing_prerequisite` -> blocked (recorded,
       deferred, exit 1); `transient` / `agent_error` -> retry while
       `attempts + 1 < max_attempts`, otherwise deferred.
     - **The retry-vs-defer rule for silence** (`retryable`): an unclassified
       cycle is retried only when the outcome was `stuck` (a clean exit that
       advanced nothing — the pre-existing bounded-retry semantics) and
       deferred when it was `failed` (a crash — Session 41's rule against
       re-burning an unexplained failure).
     - **`max_attempts` is no longer a stop condition.** Exhausting it defers
       that ONE mission and the run continues with independent work; the
       deferral set is keyed on `Task.identity` (the tag-stripped first line,
       so `> remark:` continuation lines never change identity) and honoured
       by `first_executable(skip=deferred)`. `max_cycles` remains the hard
       bound, and a run whose every remaining mission is deferred or blocked
       still exits 1.
     - **The retry carries the reason forward** (`retry_block`): the next
       attempt's prompt gains a `FAILED PREVIOUS ATTEMPT` note with the
       classification and reason, plus an instruction to classify and stop
       rather than repeat the failed approach.
     - **Every durable surface carries the reason**, not just the class: the
       RUN_REPORTS line, the `mark_blocked` text, the BLOCKERS entry, and the
       notification body ("Ine · decision required" / "task blocked" /
       "task stuck" / "task failed", the last distinguishing a nonzero exit).
     Tests: +27 (`ClassificationParseTests` 8, `ClassifyActionTests` 6,
     `Phase1DiagnosisTests` 13); 10 existing tests updated to the new call
     counts and deferral semantics, with
     `test_reset_does_not_disable_the_bounded_stop_guard` renamed to
     `test_retry_budget_defers_instead_of_stopping_the_run`. Fixed en route:
     `classify_action` first deferred every unclassifiable cycle, which
     regressed silent-no-progress retries and the exit-code contract —
     splitting them by outcome via `retryable()` restored both.
     Verified: `test_ine_agent.py` = 142 passed; full suite 449 tests / 18
     subtests, green apart from the known tkinter `TclError` flake (422 tests
     before this session). Caveat: the new diagnosis path is covered by stub
     workers only — it has not yet been exercised end to end against a live
     agent worker.

117. `DONE` — **mission: phase 2 of failure handling — a schema, not a string**
     (supervisor-owned, commander-directed; Session 44). Objective: make the
     Phase 1 classification vocabulary a TYPE that every parser pathway folds
     onto, so a malformed, misspelled or drifted worker answer can no longer
     reach a decision or a report as free text. Phase 1 matched substrings, and
     a substring match is not a decision procedure — `server error` contains
     `error`, so `agent_error` was reachable from a transient failure.
     - **The schema is the single source of truth.** `Classification` is a
       plain `enum.Enum` over the five vocabulary strings (plain, not a
       `str` mixin: `requires-python = ">=3.10"` and `enum.StrEnum` is 3.11+,
       and on 3.10 a str-mixin member FORMATS as `Classification.TRANSIENT` —
       so nothing formats a member into text; every text surface goes through
       `canonical()` or `.value`). `CLASSIFICATIONS`, `RETRYABLE`,
       `UNCLASSIFIED` and the two prompt menus (`_VOCABULARY`) are all derived
       from the enum, and a test asserts the menu the prompts print equals
       `" | ".join(CLASSIFICATIONS)` — the prompt and the parser can no longer
       drift apart.
     - **Whole-token alias matching replaces substring scanning.** A label is
       folded onto a class only by an exact canonical match (token-joined:
       `agent error`, `agent-error`, `AGENT_ERROR` all land EXACT) or by whole-
       token alias coverage against a curated synonym table (`transient_error`,
       `Transient-Error`, `flaky`, `timeout`, `my mistake`, `missing prereq`,
       `not implemented yet`, ...), with abbreviation tolerance requiring the
       shorter token to be >=4 chars and a prefix relationship, and longest
       alias winning on ties. A negation or hedge word blocks the alias it
       appears in *unless the alias itself owns that word* — so `not
       implemented yet` folds while `not a commander issue` and `maybe
       transient?` do not.
     - **Unreadable is not guessable.** Off-vocabulary text, the `<a | b | c>`
       placeholder echoed back verbatim, and a bare `CLASSIFICATION:` marker
       all read as no-match. They are recorded with the raw text preserved as
       the reason, and they do NOT trigger the follow-up call — only a
       genuinely ABSENT line does, because the follow-up is the expensive path.
     - **The safe default is `unknown`, deliberately NOT `agent_error`.**
       `agent_error` is unconditionally retryable, so defaulting gibberish to
       it would re-burn a worker cycle on every malformed answer — exactly the
       token waste this phase exists to stop. `unknown` defers a crash and
       still permits the bounded retry after a clean no-progress exit, which
       preserves the Missions 30/41/51/52 semantics untouched.
     - **Every answer is a `Diagnosis`** (`classification`, `reason`, `raw`,
       `match`, `source`), where `Match` is EXACT / ALIAS / EXPLICIT / NONE /
       ABSENT and `Source` is WORKER / FOLLOW_UP / GATE / ERROR.
       `parse_classification()` survives as the 2-tuple view of the same call, so
       the Phase 1 contract still holds and no existing test changed behaviour.
     - **`REASON:` now accepts real prose** (the phase's third objective): the
       last `REASON:` marker wins, and it takes the following text with no
       regard to whether it started on that line, wrapping across up to 4
       non-blank lines, stopping at the next tag or blank line, truncated to
       200 chars — so a wrapped explanation, an inline value and an inverted
       `REASON:`-before-`CLASSIFICATION:` order all read the same.
     - **Drift and fallback are durable, not silent** (`diagnosis_trace`): an
       ALIAS fold writes a `NOTE`, a NONE match writes a `WARNING` naming the
       raw text and the default it took, and a FOLLOW_UP or ERROR source writes
       a `WARNING` saying the class did not come from the worker. Warnings also
       print to the console; exact canonical reads and an explicit
       `unknown`/`n/a`/`unclear`/`?` stay silent, so the trail means something
       when it appears.
     Tests: +34 (`ClassificationSchemaTests` 7, `RobustParsingTests` 17,
     `DiagnosisTraceTests` 7, `DiagnosisTelemetryTests` 4). Five failed first
     and each one was right to: a test step passed a helper's callable where a
     3-tuple belonged; `unknown` read EXPLICIT instead of EXACT (fixed by
     removing `unknown` from the explicit-unknown synonyms list, so the
     canonical value travels the same path as the other four); `?` was
     punctuation-stripped to empty before the explicit check; four synonym
     expectations were ALIAS when the token-join already made them EXACT; and
     the blanket negation guard wrongly rejected `not implemented yet`, which
     forced the guard inside the alias loop where the alias's own tokens are
     known. Verified: `test_ine_agent.py` = 176 passed (was 142); full suite
     **483 tests / 18 subtests** green (449 before this session). Same caveat
     as item 116: the path is covered by stub workers only — no live agent
     worker has been run through it.

118. `DONE` — **mission: phase 3 of failure handling — memory, evidence, and
     re-measurement** (supervisor-owned, commander-directed; Session 46).
     Objective: close the loop's two remaining failings — it forgot between
     runs, and "did that help?" had no number. Measured first, then changed:
     see the baseline at the end of this item.
     - **The attempt ledger is durable and pruned** (`.agent/attempts.json`,
       new durable record; `attempts_path`/`read_attempts`/`write_attempts`/
       `record_failure`/`clear_mission_attempts`/`prune_attempts`/
       `parked_missions`). A failed cycle writes to it; a mission that has
       failed in `max_failures` (default 3) different RUNS is PARKED and is not
       picked again until it is rewritten or its entry is removed. RUNS, not
       attempts, decide parking: several failures inside one run are what
       `max_attempts` already governs, so a mission retried 20 times in one
       run is not parked by `max_failures`. That distinction was not designed
       in — two pinned cycle-limit tests failed when the ledger first counted
       every attempt, which is why the entry carries `runs` and `attempts`
       plus the `run_id` (`_new_run_id`: timestamp + process-global sequence)
       that last wrote it, and why `--max-failures 0` disables parking
       outright. Completing a mission clears its entry.
     - **Parked is reported, never silent.** Identity is `state.headline_key`
       (the tag-stripped first line), so `> remark:` continuation lines never
       change a mission's identity and a commander's resolution remark does
       not orphan its history. The ledger is PRUNED at run start to the
       identities still executable: without that, rewriting a headline left a
       phantom entry, which was reported as a parked mission forever and — once
       nothing executable remained — turned an honest exit-0 "no work remains"
       into a false exit-1 "everything is parked". Every run that starts with
       parked missions prints them once (`[parked] <headline> (failed in N
       run(s), M attempt(s); last <class>: <reason>) — not re-picked`), records
       the same line in RUN_REPORTS, and notifies once. Parking everything
       exits 1 with a message that names it: `every remaining mission is parked
       after repeated failures; commander action required.`
     - **Evidence per cycle, not just "it ran"** (`worktree_signature`,
       `--stall-limit`, default 3): a cycle that completes nothing, blocks
       nothing and changes no file OUTSIDE `.agent/` counts as no progress;
       `stall_limit` of those in a row ends the run early with the count
       stated. `.agent/` is excluded on purpose — the supervisor's own
       remarks, ledger and run report change on every cycle, so counting them
       would let a spinning loop look busy forever. The signature comes from
       `git status --porcelain` including untracked files; where git cannot
       answer (no repository, no git on PATH) it is unknown and the guard
       stays silent, because silence must never be read as a stall. The check
       sits after the cycle bound, so `--cycle-limit` remains the predictable
       hard stop.
     - **The re-measure harness** (new `src/ine_agent/measure.py`, read-only,
       `python -m ine_agent.measure [--root .]`): reads only
       `.agent/RUN_REPORTS.md` and the attempt ledger and prints one row per
       run plus the comparison numbers — cycles, completed, blocked, deferred,
       parked, "runs that completed nothing", "cycles per completion" and
       "completions per 1,000 requests", because "the same output, more
       cheaply" is exactly a ratio of the two. Two limits are printed rather
       than guessed at: usage numbers exist only for workers reporting into
       the OpenCode database (a `--worker claude` run shows zero requests
       instead of a fabricated figure), and a run with no `- exit:` line was
       interrupted rather than ended, so its exit prints as `-`.
     - **The baseline this phase has to move** (`python -m ine_agent.measure`,
       taken BEFORE the change shipped, over every run the loop has recorded):
       **17 runs, 20 cycles, 2 completions, 15 of 17 runs completed nothing,
       10.00 cycles per completion, 1 request observed (10,885 in / 35 out
       tokens)** — the same finding the commander-directed efficiency
       measurement reached: cost per line of output was never the problem,
       completion was. Phase 4 is measured against these numbers, and the
       harness is what makes that a number rather than a feeling.
     Tests: +29 (`AttemptLedgerTests` 7, `WorktreeSignatureTests` 4,
     `ParkedMissionTests` 5, `StallGuardTests` 6, `MeasureTests` 5, plus two
     `CliTests` pinning `--max-failures`/`--stall-limit` in `run --help` and
     their arrival at `Supervisor`). Fixed en route: the ledger counted
     attempts for parking (above); `measure.py` crashed on `exit {:<4s}` with
     an int exit code; the no-git worktree-signature test passed for the wrong
     reason until its fixture root moved outside the repository (a temp root
     under `.tmp/` is still inside this repo, so git answered `""` instead of
     nothing); and the stall-guard test used thresholds that let the guard fire
     before the cycle bound it was asserting. Verified: `test_ine_agent.py` =
     205 passed; full suite **512 tests / 18 subtests** green (483 before this
     session). Same caveat as items 116 - 117: stub workers cover this path — no
     live worker has run it end to end yet.
     Records: this session also closes two Session 45 watch items as side
     effects — the six `test_ine_agent.py` failures Session 45 attributed to
     "the supervisor invoked the real opencode worker" carry the exact symptom
     of this item's pre-fix ledger (the park-after-repeated-failures message
     where the cycle-limit contract expects its own), and STATE's "large
     uncommitted supervisor rewrite" watch item is the uncommitted Phase 1-3
     supervisor work itself (+1134/-54 lines against `HEAD`).

## Candidate missions — Ine authoring & UI capability (next-stage direction)

> **These are candidate missions, not a commitment to implement every item.**

Before implementing a candidate, verify that:
1. the need is demonstrated by an existing or newly created realistic example;
2. the current architecture supports it without unnecessary redesign;
3. it does not conflict with DECIDED language principles;
4. it does not require inventing unsupported semantics;
5. it is genuinely more valuable than the next available mission.

If the evidence is insufficient, preserve the idea as a lower-priority
research/future mission instead of implementing it. Preserve existing
functionality and regression behavior throughout. Verified, evidence-backed
candidates graduate into "Active — next smallest steps" with an `EXECUTABLE`
tag; unsupported ideas stay here. Items here are NOT picked up by the
selection rule.

### Priority 1 — Make autocomplete feel like a real programming language

1. **Character-based dictionary completion.**
   - Suggestions should begin appearing as the user types, not only after
     pressing Space. Typing `m` should surface relevant vocabulary with `make`
     highly ranked; `ma` should narrow toward `make`; `make` should keep `make`
     as the top exact match rather than requiring another character/space.
     Prefix matches ranked above weaker matches.
   - Only implement if the current dictionary/editor architecture can support
     this cleanly.

2. **Instant/contextual suggestions.**
   - Investigate why completion currently behaves primarily around trigger
     characters, and make suggestions appear naturally while typing. Preserve
     the dictionary as the vocabulary source; do not add a second vocabulary
     inside the extension.

3. **Context-aware ranking.**
   - The same typed letters should produce different useful suggestions
     depending on cursor position: `make h` → header; `header t` → title;
     `card-1 t` → title, text. Investigate whether this can be implemented
     without making autocomplete overly complex.

### Priority 2 — Complete syntax automatically where the language already requires it

4. **Value/snippet completion.**
   - When a property requires a quoted value, the editor should provide the
     syntax automatically: completing `page title` should naturally produce
     `page title ""` with the cursor inside the quotes. Do not hard-code
     property knowledge in the extension; use dictionary value-shape info.

5. **Automatic structural completion (investigation).**
   - Determine whether Ine can provide useful larger completions based on known
     structure (when creating a known UI entity, suggest the next natural
     pieces). Do **not** auto-generate large structures merely because possible;
     first determine whether this improves authoring without making Ine feel
     like a code generator.

6. **Completion for known choices (investigation).**
   - If the dictionary eventually contains evidence-backed choices, completion
     could offer the valid known options. Do not invent choices; keep currently
     evidence-blocked choices blocked.

### Priority 3 — Basic styling / visual intent

7. **Basic visual properties (investigation).**
   - Determine whether Ine should support a small set of visual intent:
     background, foreground/text color, borders, spacing, sizing, typography,
     corner radius, alignment, possibly opacity. The goal is **not** to
     recreate CSS. Only add properties that can be represented consistently
     across the relevant backend(s) and are justified by real examples.

8. **CSS/backend separation.**
   - Investigate how much styling is currently hard-coded inside the HTML
     backend, and whether styling should eventually become dictionary-driven.
     Preserve current rendered output (goldens) while experimenting. Do not
     redesign the backend merely to make it theoretically extensible.

9. **Basic theme/customization experiment.**
   - Build a small real example that requires changing colors, spacing,
     typography, etc., and use the experiment to discover what Ine actually
     needs. Preserve useful discoveries even if deferred.

### Priority 4 — More realistic UI structures

10. **More substantial UI example.**
    - Create or investigate a realistic example: dashboard, settings page,
      data-oriented interface, form, application shell. The purpose is to
      discover where Ine naturally stops being expressive — not simply to
      expand the dictionary.

11. **Tables.**
    - Investigate whether a table/data-grid concept is genuinely needed. If the
      realistic example demonstrates the need, research the smallest natural Ine
      representation. Do not add a table construct merely because HTML has tables.

12. **Forms and inputs.**
    - Same evidence-based approach: investigate inputs, labels, controls,
      selection, submission, etc. Only turn demonstrated requirements into
      language/dictionary work.

13. **More structural UI.**
    - Investigate things such as lists, modal/dialog, dropdown, navigation,
      sections/groups, reusable structures. Real usage determines priority.

### Priority 5 — Responsive design

14. **Responsive intent (investigation).**
    - Determine whether Ine can naturally express intent such as `on mobile`
      / `stack` or equivalent semantics — but do **not** invent syntax yet.
      First research/build a realistic responsive example and determine what
      information the language actually needs.
    - Note: `card-group` already documents a `narrow-layout` default; active
      mission 22 investigates whether that already covers this intent.

15. **Backend responsive implementation.**
    - Determine how responsive intent could map to HTML/CSS, preserving the
      distinction between Ine's intent and CSS implementation details.

### Priority 6 — Tooling / developer experience

16. **Editor diagnostics.** Investigate inline errors and warnings; determine
    the minimum useful diagnostic system before committing to a full LSP.
    (Active mission 16 covers this investigation.)
17. **Formatting.** Investigate whether Ine's intentionally simple syntax allows
    a deterministic formatter; only implement if it provides clear value.
18. **Hover/documentation.** Investigate showing dictionary meaning/value
    information directly in the editor.
19. **Packaging.** Investigate making Ine easily installable outside the
    repository. (Active mission 25 covers this investigation.)
20. **CI.** Add reliable automated regression testing if not already present.
    (Active mission 24 covers this investigation.)

## The four-construct spine (Session 25) — never add a fifth casually

Parser/semantic/backends are **frozen** for adding constructs. A proposed
addition (conditions, state, styling, import) must first exist as evidence in
examples, then be decided in WORKBOOK §25's framework before any code.

127. `CLAUDE_REVIEW` — **Extend the editor's `advisory` list beyond SemanticError with semantic.advisory_warnings(model) — the dictionary-backed property-vocabulary and containment warnings the CLI already prints — so the editor warns on `padding "banana"` and mis-nested containment too, still as warnings, never red..** (proposed by a workernot executable until a human reads it (after mission 84)

127. `CLAUDE_REVIEW` — **Surface why formatting was skipped. With formatOnSave now on for [ine], a commented buffer — and any buffer that does not parse — is returned unchanged and the editor reports nothing, so the user experiences a formatter that silently does not work and cannot tell a typo from a deliberate refusal. Add a refusal reason to the format response (e.g. {"format": true, "text": ..., "reason": "comment" | "unparseable"}) and have extension.js show it in the status bar; tests/test_formatter.py already pins the unchanged-text behaviour the reason would annotate..** (proposed by a workernot executable until a human reads it (after mission 85)

127. `CLAUDE_REVIEW` — **Implement extract-to-group for real per NOTES §4–§5: a `src/ine/` engine entry point, an `{"action": "extract-group", "buffer", "lines", "name"?}` op in autocomplete.py following the `format` op's no-answer-is-not-no-change rule, and a registerCodeActionsProvider in editor/vscode-ine/extension.js emitting per-line TextEdits with a stale-buffer refusal; precede it with the `make <count> <kind>` expand action that makes per-entity actions total..** (proposed by a workernot executable until a human reads it (after mission 86)
