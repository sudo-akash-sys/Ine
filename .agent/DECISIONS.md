# .agent/DECISIONS.md

Decided language/architecture decisions. Each entry is DECIDED unless marked
PROPOSED / EXPERIMENTAL / UNDECIDED. A conversation about an idea is not a
decision — nothing is copied here until it is real.

## DECIDED

- **The worker architecture** (Missions 119-125): one fresh process per
  mission, executing a written index and nothing else. Specifically DECIDED:
  - **Lean handoff** — the worker is given the mission, the rules, the
    receipt contract, and only the compact receipts of missions related by a
    *declared* signal (same `Area:`, `Depends on:`, or a changed file in
    common). Not the plan body, not the history, not a STATE snapshot.
  - **Structured receipt** — a worker ends with one bounded JSON object after
    the `INE_RECEIPT_JSON` marker. Python writes every `.agent/` record from
    it, so a worker never edits the control plane and cannot half-record a
    mission. An unreadable receipt means "did not report", never a second
    request spent interpreting it.
  - **Selective compact memory** — a mission that declares no relation is
    offered nothing. An unfiltered snippet list is the history this replaces.
  - **Provider profiles** — named worker profiles (`opencode`, `claude`, or
    `.agent/workers.json`), resolved and reported by `doctor` and the dry run
    before anything is launched. A model is a refinement a profile must
    declare how it wants, not a selector the caller forces.
  - **One invocation per attempt** — a worker classifies itself in-band in its
    receipt. There is no automatic second call to ask why, and no automatic
    retry: `--max-attempts` is a per-mission budget the commander sets
    explicitly, and it defaults to 1.
  - **Queue-to-exhaustion** — a run ends when nothing is `EXECUTABLE`, when
    the mission set is exhausted, or when the optional `--max-missions` bound
    is reached. `--max-missions` defaults to unset, which is finite because a
    mission is attempted at most once and a proposal is never executable.
  - **Follow-ups are proposals** — a receipt's follow-up is filed as a
    `CLAUDE_REVIEW` item carrying a non-executable marker. The tag alone is
    not enough: `CLAUDE_REVIEW` is itself executable in this plan, so without
    the marker a proposal would be picked up by the next run and turned into a
    blocker.
- **Ine language identity** (Session 23): Ine, extension `.ine`, CLI `ine`.
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
- **`number` is a standard value kind** (Session 41, commander): recognized
  by `_shape_from()` alongside `text`/`length`; a property declared
  `"number"` accepts a bare numeric literal (already parsed to int/float).
  Editor value-completion for a `"number"` property offers a numeric
  placeholder. Commander approved the number tier of Mission 72's typed-value
  recommendation; `boolean` and `date` remain UNDECIDED (no vote).
- **No baseline freeze** (Session 41, commander): there was no actual
  freeze on parser/semantic/backend code — implementing a change is welcome
  so long as it does not break existing behavior and stays aligned with the
  project's larger goals; deviations from the original intent are acceptable
  when required by the implementation.
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
- **REJECTED — injecting a distilled state into every prompt** (Missions
  119-125): the snapshot was re-sent in full on every cycle, so its cost was
  paid once per mission for context the mission's own index already stated,
  and it went stale between the read and the worker's first step. A stale
  position is worse than none. A worker that needs a control-plane file reads
  it, at the point it needs it.
- **REJECTED — whole-history summaries** (Missions 119-125): the same cost
  problem, worse. Related compact receipts on declared signals carry what is
  actually relevant; a mission with no declared relation is offered nothing.
- **REJECTED — automatic retry with a diagnosis call** (Missions 116, 123):
  a second model request to ask a worker why it failed is a request spent
  making a decision the worker was already asked to make in its receipt, and
  it is how a bounded runner becomes an unbounded one. Failure handling is
  now a budget the commander sets (`--max-attempts`) plus durable deferral.

- **Dictionary is the semantics authority** (Session 49, commander, supersedes
  "Dictionary is advisory, never a validator" from Session 25): the dictionary
  is no longer a passive suggestion list. It must (a) *know its own format* —
  `make footer` surfaces the shaped body (element, defaults, style, members,
  enclosing context) as a starting-point template the user edits, never a
  constraint on experts; (b) back semantic validation in `analyze` — property
  names, property values against `value_shape`/hint vocabulary, and containment
  against `parents`/`contains` — rolled out **advisory-first**, hardened only
  where no example breaks; (c) drive responsiveness — `narrow-layout` /
  `narrow-class` are consumed by the HTML backend to emit a real `@media` rule
  (unblocks item 59). Scope intent: semantics "simple by function but an
  extension of prior semantics" — not so small that every idea needs endless
  manual expression, not so large that the language surface grows a fifth
  construct without the WORKBOOK §25 framework. Templates live in the
  editor/`--dict` layer, not in the grammar.

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