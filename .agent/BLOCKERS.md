# .agent/BLOCKERS.md

Open issues, unstarted work, and anything waiting on evidence. Update as
items resolve. Nothing here is a commitment — blocked means: not done,
not no.

## Blocked on evidence

- **First enumerated `choice` value.** The value-shape representation
  **can** express choices — a `properties`-block value that is a list of
  strings becomes a `"choice"` shape (e.g. `"layout": ["row", "column"]`).
  But **no current dictionary entry declares one**: no property carries
  enough evidence, and `layout` still documents only a single `"row"` option.
  Declaring a choice requires either a real program using a second option
  (e.g. `layout column`) or a deliberate WORKBOOK decision. Blocked until
  then.

## Not started / deferred (no decision)

- **Conditions / state** ("cards stack on narrow") — would be a fifth
  construct; needs a WORKBOOK §25 decision, not just vocabulary.
- **HTML fidelity pass** (fixed header shadow, stylesheet, palette) —
  UNDECIDED scope; goldens are intentionally minimal.
- **Diagnostics, formatting, packaging** of the VS Code extension.
- **Native target** is research-only; no runtime for arbitrary `.ine`.

## Coverage reconciliation (Session 31) — evidence-gated, correctly undeclared

- **`search` (header member):** WORKBOOK proposes it throughout (a header
  carries logo, navigation, search; `make search inside header`), but no real
  `.ine` program has ever used it and no dictionary entry exists. Declaring
  it needs a real program or a WORKBOOK decision. Blocked.
- **`subtitle` / `description` (content properties):** WORKBOOK §36 stripped
  them from `contains` and re-grounded only `title`/`text` (no evidence);
  they remain absent today, by decision. Blocked on evidence.
- **`button inside header` (WORKBOOK L544) vs `button inside section`
  (dictionary, evidence = dictionary-demo.ine):** the proposed roadmap and
  evidence-grounded containment disagree. Do not change containment without a
  real program or a WORKBOOK decision.
- **Custom domain kinds (`person`, `name`, `age`, `height` in
  examples/alice/alice.ine):** the dictionary enumerates a guided footprint,
  not user domains; arbitrary kinds are a first-class language feature, so
  this is a scope boundary, not a coverage gap.

## Constraints that are easy to forget

- No edits to `parser.py`, `semantic.py`, `backend_html.py`,
  `backend_visual.py` for dictionary/editor work (Session 25 freeze).
- Extension.js must stay a pure proxy — it may consume `value_shape`/
  `context` from the engine but must never hold its own Ine knowledge.
- Parser/semantic/backends restrict `title`/`text` to quoted strings;
  `value_shape` is advisory metadata, not enforcement.

## Vocabulary reconciliation (Session 37) — evidence from real programs

Two experiments (`.agent/experiments/dashboard.ine`, `.agent/experiments/
form.ine`) built with ONLY declared vocabulary surfaced the following.

**Already covered (no action).** All 12 kinds used in existing programs
(page, header, logo, navigation, container, banner, card-group, card,
section, button, image, footer) declare fine; layout properties carry
useful defaults; `--dict` discovery tools work.

**Evidence-gated proposals (need WORKBOOK or real-program evidence).**

- **Field kinds (`input`, `textarea`, `select`, `label`, `form`):**
  form.ine (mission 20) reduces a contact form to one `button` with no
  fields — zero field kinds exist. A form body cannot be expressed. Needs a
  WORKBOOK decision (language-shape question, not just JSON additions).
- **Numeric / boolean / date types:** dashboard.ine (mission 19) embeds
  KPI numbers ("99.98%") in `text`; `button.interactive` and
  `logo.interactive` document "not settable yet: Ine has no boolean
  values"; timestamps are strings. No `value`/`metric` property. Needs a
  WORKBOOK type-system decision.
- **Chart / table kinds:** no `chart`, `table`, `row`, `cell` kinds exist;
  dashboard.ine had to use `image` as a placeholder and could not express
  a data table at all. Needs evidence of a real program using a table.
- **Multiplicity reuse (no offset):** `make 3 card` always numbers from 1;
  a second batch of the same kind collides. Current workaround is
  explicit names. Needs evidence that the friction blocks a real program.

**Already working (not a gap).** `card-group` belongs inside `container`
only — this is by design (sessions 25-26), and sections hold (button,
image) only. Layout and spacing props are declared with defaults; users
cannot set them from `.ine` today (renderer concern, not dictionary).

**Dead vocabulary (noted, not proposed for removal).** `link`, standalone
`title`, and standalone `heading` are declared but appear in zero real
programs. They may become relevant if link navigation is built.## Evidence-gated implementations in PLAN (items 58, 59, 61)

These are the CSS/styling and link implementation missions. They are BLOCKED
in PLAN.md on a lifted Session 25 backend freeze and commander scope, not on
engineering. The evidence missions that feed each one are EXECUTABLE in
PLAN.md and must land first; do not unblock any of these by guessing.

- **58 — HTML backend: wire declared physical hints into inline styles.**
  Today the backends emit only hard-coded styles; the physical hints already
  declared on card/banner (`padding`, `corner-radius`, `border`) are read by
  no backend (NOTES Missions 23 / 56 / 57). Preconditions: Session 25 freeze
  lifted for `backend_html.py` for this change; the commander accepts the
  Mission 57 mapping scope; goldens updated deliberately (byte-identical
  discipline preserved).
- **59 — HTML backend: one narrow responsive rule.** `narrow-class` /
  `narrow-layout` are declared on card-group but read by no backend
  (NOTES Missions 22 / 56). Preconditions: freeze lifted for
  `backend_html.py`; commander accepts one `@media (max-width: 768px)`
  `row -> stack` rule; evidence from Missions 55/56 accepted. No fifth
  construct — conditions/state stay UNDECIDED.
- **61 — `link` navigation (kind or property).** `link` is declared but used
  by zero programs (below: dead vocabulary); there is no link syntax and no
  backend emits a clickable target. What a link is and how to express it is
  investigated in NOTES Mission 60 with real-program evidence from Mission 54
  (pricing page). Preconditions: a WORKBOOK or commander syntax decision
  (property vs kind); freeze lifted for the touched backend; Missions 54/60
  evidence accepted before any code.

Still evidence-gated, unchanged: PLAN item 7 (first `choice` value), field
kinds, numeric/boolean/date types, chart/table kinds, `search`,
`subtitle`/`description`, `button inside header`, conditions/state, HTML
fidelity pass, and the installed-copy packaging caveat (fixed by PLAN 63).
