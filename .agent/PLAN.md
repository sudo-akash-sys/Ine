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

1. `EXECUTABLE` — **Improve context detection for `group` keyword.** When
   typing `group cards = `, autocomplete returns properties context for the
   word "group" (which resolves to nothing). The `group` keyword is a
   statement start, not a kind, and should return no context.
   - Fix: In `autocomplete.py:context()`, detect `group` keyword at line
     start and return `None`.
   - Add tests: `group `, `group cards = `, `group cards = card-1` all return
     `None`.
   - Verify: existing tests pass.

2. `EXECUTABLE` — **Improve context detection for `say` keyword.** After
   `say person `, autocomplete returns properties context for "say" as if it
   were an entity name. `say` is a keyword that accepts a string, number, or
   property reference — not properties or members.
   - Fix: In `autocomplete.py:context()`, detect `say` keyword pattern and
     return `None` (no completion after `say` statements currently).
   - Add tests: `say `, `say person`, `say person age` all return `None`.
   - Future work (not now): property reference completion inside `say`.

3. `EXECUTABLE` — **Add missing dictionary test coverage.** The test suite
   has good coverage but misses some edge cases:
   - `value_shape` for kinds with only `defaults` (no `properties` block).
   - `suggest()` for `viewport` (ambient entry, should return empty).
   - `properties_for` for `viewport` (ambient, should return width/height).
   Add these tests to `tests/test_ine.py` in the `DictionaryTests` class.

4. `EXECUTABLE` — **Clean up `.tmp/` directory.** The `.tmp/` directory
   contains 150+ `ineagent-*` temporary directories from test runs. Add a
   cleanup step to `test_ine_agent.py` to remove temp roots after tests,
   and document that `.tmp/` is gitignored temporary storage.

5. `EXECUTABLE` — **Update editor README for value completion.** The
   `editor/vscode-ine/README.md` says property values are "not suggested yet"
   but Session 31 added `value` context completion. Update the README to
   reflect current capabilities:
   - Context 4: `page title ` → `""` (quoted placeholder for text values).
   - Note: choice values are supported by the engine but no dictionary entry
     uses them yet (blocked on evidence).

6. `EXECUTABLE` — **Add type hints to dictionary.py.** The `dictionary.py`
   module lacks type hints on function signatures. Add hints for:
   - `find(kind: str) -> dict | None`
   - `makeable() -> list[str]`
   - `properties_for(kind: str) -> list[str]`
   - `value_hint(kind: str, property: str) -> str | None`
   - `value_shape(kind: str, prop: str) -> ValueShape`
   - `members(kind: str) -> list[str]`
   - `parents(kind: str) -> list[str]`
   - `suggest(kind: str | None = None) -> list[Suggestion]`
   - `for_model(model) -> list[Suggestion]`
   Verify: `python -m py_compile src/ine/dictionary.py` passes.

7. `BLOCKED` — **First enumerated `choice` value.** Add `"choice"`-style
   options to a `properties` block (e.g. `"layout": ["row", "column"]` in
   `card-group.json`), then teach the extension's snippet path to offer
   `choice` options. Precondition: a real program or decision showing a
   second `layout` value; only `"row"` is documented today.

8. `EXECUTABLE` — **Add error handling test for malformed dictionary JSON.**
    The `_load()` function in `dictionary.py` silently skips malformed JSON
    files (returns empty dict for that file). Add a test verifying that a
    malformed `dictionary/*.json` does not crash the loader and that valid
    entries are still loaded.

9. `EXECUTABLE` — **Document dictionary JSON schema in code comments.** Add
    a docstring to `dictionary.py` explaining the expected JSON structure:
    - `term`: unique identifier for the kind
    - `kind`: category (container, bar, surface, etc.)
    - `element`: HTML element tag
    - `meaning`: human-readable description
    - `defaults`: property hints and `contains` list
    - `properties`: typed property declarations (value → `"text"` or `["choice1", ...]`)
    - `provided-by`: marks ambient entries (excluded from `makeable`)
    - `universal`: marks the universal-properties pseudo-entry

10. `EXECUTABLE` — **Add integration test for editor-to-dictionary flow.**
    Create a test that simulates the full editor completion flow:
    - Start autocomplete.py subprocess
    - Send `make ` request, verify kinds returned
    - Send `page ` request, verify properties + members returned
    - Send `page title ` request, verify `""` value returned
    - Send `header inside ` request, verify parents returned
    This tests the protocol end-to-end beyond unit tests.

### Research & investigation — weakness-driven missions

These are research-first missions. Each produces a finding (a FILE note or
STATE.md update) before any code change. Do not invent solutions; discover
whether the weakness is real, how severe it is, and what the smallest
evidence-based fix would be.

#### Dictionary robustness & typing

11. `EXECUTABLE` — **Invalid dictionary entry feedback.** Investigate whether
    invalid dictionary entries (missing `term`, wrong types, missing required
    fields) silently disappear without useful feedback. Determine whether
    `_load()` should log warnings, and what the minimum useful feedback looks
    like. Do not add a validation framework — just check whether the current
    silent-skip behavior causes real problems.

12. `EXECUTABLE` — **Value-shape consistency review.** Audit
    `dictionary.py:_shape_from` and `autocomplete.py:_known_shape` together.
    Verify that value shapes are represented only when evidence supports them
    (i.e. `"text"` for quoted strings, `"length"` for ambient measurements,
    `"choice"` only when a list is declared). Check that no code path
    invents or infers a shape from data that does not declare one.

13. `EXECUTABLE` — **Dictionary type hints on autocomplete.py.** The
    `autocomplete.py` module also lacks type hints. Add hints for the public
    functions (`context`, `resolve_kind`, `complete`) and the internal helpers
    where it materially improves readability. Verify:
    `python -m py_compile src/ine/autocomplete.py`.

#### Autocomplete edge cases

14. `EXECUTABLE` — **Autocomplete edge cases: unusual cursor positions.**
    Test completion with unusual cursor positions: mid-line, at start of
    line, inside a quoted string, after a comment, after a blank line,
    after multiple spaces. Document which cases return correct results and
    which fail gracefully vs. crash. This is a test-and-document mission, not
    a fix mission.

15. `EXECUTABLE` — **Autocomplete containment completion.** Verify that
    `header inside ` returns the correct parents (`page`). Test edge cases:
    `card inside ` (should return `card-group`), `copy inside ` (should
    return `section`), `page inside ` (should return nothing — top-level).
    Add tests to `test_autocomplete.py`.

#### Editor diagnostics & error messages

16. `EXECUTABLE` — **Editor diagnostics investigation.** Determine whether
    VS Code users currently receive useful errors while editing. Check if
    the extension surfaces any diagnostics (red squiggles, hover errors)
    or if all errors only appear at compile/render time. Decide whether
    basic diagnostics (e.g. "unknown kind" on hover) are justified before
    committing to a full LSP. Produce a recommendation, not a
    implementation.

17. `EXECUTABLE` — **Backend/parser/semantic error message audit.** Review
    `LexError`, `SyntaxError`, `SemanticError`, `BackendError`, and
    `VisualError` for cases where the user gets an unhelpful message (e.g.
    class name only, no guidance). Identify the 3-5 worst offenders and
    propose improved messages. Do not change code — just produce a list with
    before/after suggestions.

#### Documentation

18. `EXECUTABLE` — **Minimum documentation review.** Read README.md,
    LANGUAGE.md, and dictionary readme as if unfamiliar with Ine. Identify
    the minimum documentation needed for someone to actually build something.
    Produce a gap list: what exists, what is missing, what is misleading.
    Do not write documentation — just identify the gaps.

#### Real-world examples & vocabulary

19. `EXECUTABLE` — **Real-world example: dashboard experiment.** Build a
    dashboard-style Ine program (data table, summary cards, maybe a chart
    placeholder). Use only existing dictionary vocabulary. Document every
    point where the vocabulary falls short (missing kinds, missing
    properties, missing containment). This is evidence collection for
    vocabulary expansion, not a feature request. Save the program and
    findings as notes in `.agent/`.

20. `EXECUTABLE` — **Real-world example: form experiment.** Build a form-style
    Ine program (inputs, labels, submit button, validation messages). Use
    only existing dictionary vocabulary. Document gaps. This discovers
    whether forms are expressible or whether the language lacks fundamental
    primitives.

21. `EXECUTABLE` — **Vocabulary reconciliation against real programs.** After
    experiments (missions 19-20), reconcile dictionary coverage against:
    hello.ine, topbar.ine, hero.ine, cards.ine, dictionary-demo.ine, and
    the new experiment programs. Classify each gap as: (a) already covered,
    (b) evidence-gated proposal (add to BLOCKERS.md), or (c) out of scope.
    Preserve unsupported concepts as discoveries, not inventions.

#### Responsive UI & styling

22. `EXECUTABLE` — **Responsive UI investigation.** Research whether the
    current language can express responsive intent naturally (e.g. "stack on
    narrow", breakpoints, conditional layout). Check if `card-group`'s
    `narrow-layout` default already covers this. Determine whether responsive
    behavior is a language concern or an implementation concern. Produce a
    recommendation.

23. `EXECUTABLE` — **Styling/theming limitation investigation.** Investigate
    the limitation caused by hard-coded backend styling in `backend_html.py`.
    Determine: (a) what users actually see (hard-coded CSS), (b) whether
    customization is currently possible via Ine programs, (c) what the
    smallest evidence-based solution would be if customization is needed.
    Do not design a theming system — just assess the gap.

#### Infrastructure

24. `EXECUTABLE` — **CI/regression infrastructure investigation.** Investigate
    what it would take to add automated repository-wide testing (GitHub
    Actions or equivalent). Determine: (a) what test command to run, (b)
    whether tests are hermetic (no external dependencies), (c) estimated
    CI cost, (d) whether this is justified at current project scale.
    Produce a recommendation with cost estimate.

25. `EXECUTABLE` — **Packaging/distribution investigation.** Investigate what
    is required to make Ine installable by someone outside the repository.
    Check: (a) pyproject.toml completeness, (b) entry points, (c) whether
    `ine` CLI works after `pip install .`, (d) whether the VS Code extension
    can be packaged (`.vsix`). Do not build a package manager or registry.
    Just assess readiness and gaps.

#### Editor architecture

26. `EXECUTABLE` — **Editor architecture evaluation.** Evaluate whether the
    current VS Code prototype (dictionary.py → autocomplete.py → extension.js)
    is sufficient for the next stage of editor work. Determine: (a) when
    diagnostics/formatting/hover become justified, (b) whether the JSON-lines
    protocol is sufficient or whether LSP is needed, (c) estimated effort
    for each path. Produce a recommendation with trade-offs.

#### Native backend

27. `EXECUTABLE` — **Native backend reality check.** Clarify what the current
    native/C backend (`backend_native.py`) actually provides. Separate
    genuine capability from aspirational positioning. Determine: (a) what
    programs it can handle, (b) what it outputs, (c) whether the output is
    usable beyond demonstration. Do not build a native runtime unless
    evidence makes it worthwhile.

#### Performance & reliability

28. `EXECUTABLE` — **Autocomplete worker reliability.** Test the persistent
    autocomplete worker over a long-running session: send 100+ requests,
    check for crashes, stale processes, timeout recovery, memory growth.
    Document findings. If reliability issues exist, identify root causes.

29. `EXECUTABLE` — **ine-agent reliability.** Test ine-agent over multiple
    cycles: verify it continues through executable missions without stopping
    prematurely. Check: (a) does it stop while missions remain? (b) are
    stop conditions correct? (c) does it handle worker crashes gracefully?
    Document findings.

#### Autonomous development system

30. `EXECUTABLE` — **ine-agent continuous execution fix.** There is a
    remaining issue where ine-agent can stop while executable missions
    remain. Investigate the root cause in `src/ine_agent/supervisor.py`
    (likely the stop-condition logic or prompt construction). Fix the issue
    and verify that the agent continues through all executable missions
    without premature termination.

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
