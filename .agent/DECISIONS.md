# .agent/DECISIONS.md

Decided language/architecture decisions. Each entry is DECIDED unless marked
PROPOSED / EXPERIMENTAL / UNDECIDED. A conversation about an idea is not a
decision — nothing is copied here until it is real.

## DECIDED

- **Language identity** (Session 23): Ine, extension `.ine`, CLI `ine`.
- **Four constructs only** (Session 25): Entity (`make`), Kind (properties),
  Property Value, Container (containment). A fifth requires evidence +
  WORKBOOK §25 framework.
- **Universal content properties** (Session 25): `title` and `text` on every
  declared kind, written quoted (`page title "Hello"`).
- **Say / Multiplicity / Groups**: `say "…"` for output; `make 4 cards`
  → `card-1…card-N`; `card-group with 4 cards` → one entity owning the set.
- **Intersection semantics** (Session 16): if two structural children need
  different properties, each kind declares its own; models produce
  sub-trees.
- **Dictionary is advisory, never a validator** (Session 25).
- **`contains` records structural children only** (Session 25):
  page→section, container→card-group, section→copy — evidence-grounded,
  no sibling inference, `for_model` recomputes valid containment.
- **Reverse containment** (Session 26): `parents(kind)` + `--dict`
  `belongs inside:`.
- **Editor architecture** (Session 27): the VS Code extension is a thin
  proxy; the Python dictionary is the only vocabulary source; JSON-lines
  over stdin/stdout; contexts `make`/`kind`/`inside`.
- **Responsiveness** (Session 28): generic triggers (space + ASCII letters,
  not a word list); one persistent worker process (FIFO queue, timeout,
  respawn), not one per keystroke.
- **Value shapes live in the dictionary** (Session 30): a `properties`
  block maps property → value kind (`"text"`, `"length"`) or → a list of
  allowed options (`"choice"`). Readers `value_shape(kind, prop)`. Shape
  derivation in autocomplete.py removed — no second source of truth.
- **Evidence rule**: no value kind or containment entry is declared without
  support in existing dictionary data or real programs.
- **Temporary files** live in `.tmp/` (gitignored), never committed.
- **Autonomous-loop division of labor** (Mission 111): the deterministic
  ine-agent supervisor selects the next EXECUTABLE mission and advances the
  plan between worker cycles; a worker executes EXACTLY the assigned mission
  as one complete arc (research → implement → test → verify → record →
  clean up) and then stops — it does not re-select missions inside one
  invocation. STATE.md / HISTORY.md updates happen once, as the worker's
  final recording pass.
- **Observed-usage telemetry is warn-only** (EXPERIMENTAL, Mission 111): the
  supervisor reports locally observed OpenCode usage (requests/tokens/cost
  at run start, each mission boundary, and run end) and may warn/notify the
  commander once per run via `--usage-warn-requests`. These numbers are
  OBSERVED local usage, NOT the provider quota, and the warning is purely
  advisory — no hard pause or budget enforcement until real runs correlate
  observed usage with actual quota/rejection events.

## PROPOSED / EXPERIMENTAL / UNDECIDED

- **Enumerated choices** (PROPOSED): `"layout": ["row", "column"]` style
  entries; representation is final, no entry uses it yet (only `"row"` is
  documented — not enough evidence). Proposal derived from Session 30.
- **Conditions / state** (UNDECIDED): e.g. "cards stack on narrow" —
  no vocabulary, no evidence, would be a fifth construct.
- **CSS fidelity** for the HTML backend (UNDECIDED): stylesheet, fixed
  header shadow, the real color palette.
- **Extension packaging / diagnostics / formatting** (UNDECIDED).
- **Property-value completion** (PROPOSED): type property, get its shape —
  reader supports it, editor does not surface it yet.