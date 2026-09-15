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

1. `BLOCKED` — **First enumerated `choice` value.** Add `"choice"`-style
   options to a `properties` block (e.g. `"layout": ["row", "column"]` in
   `card-group.json`), then teach the extension's snippet path to offer
   `choice` options. Precondition: a real program or decision showing a
   second `layout` value; only `"row"` is documented today.

Nothing else is EXECUTABLE right now, so per the selection rule an agent
stops here and records state rather than inventing work. Completed steps
(`value` completion context, dictionary coverage reconciliation — both
Session 31; the `ine-agent` autonomous supervisor tool — Session 32)
settled into `.agent/HISTORY.md`. Autonomous workers are driven by
`src/ine_agent/` (`ine-agent run`); their operating rules live in
`AGENTS.md`, and the menu/decision/blocked logic lives in these files.

## The four-construct spine (Session 25) — never add a fifth casually

Parser/semantic/backends are **frozen** for adding constructs. A proposed
addition (conditions, state, styling, import) must first exist as evidence in
examples, then be decided in WORKBOOK §25's framework before any code.