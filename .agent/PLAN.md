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

## The four-construct spine (Session 25) — never add a fifth casually

Parser/semantic/backends are **frozen** for adding constructs. A proposed
addition (conditions, state, styling, import) must first exist as evidence in
examples, then be decided in WORKBOOK §25's framework before any code.
