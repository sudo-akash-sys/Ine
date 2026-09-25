# .agent/BLOCKERS.md

Open issues, unstarted work, and anything waiting on evidence. Update as
items resolve. Nothing here is a commitment — blocked means: not done,
not no.

## Blocked on evidence

none currently — the first enumerated `choice` value was RESOLVED by
commander decision (below).

- ~~**First enumerated `choice` value.**~~ **RESOLVED** (Session 49
  interactive, commander delegation — "layout column, you could decide on
  your own"): `card-group.json` now declares `"properties": {"layout":
  ["row", "column"]}`. `value_shape("card-group","layout")` is the first
  `"choice"` shape; the snippet offers `${1|row,column|}`, `--dict
  card-group` prints `layout  choice: row, column`, and the advisory pass
  flags a written layout outside row/column. PLAN item 7 → DONE.

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
  `backend_visual.py` for dictionary/editor work — the Session 25 freeze was
  a WRONG reading of the archive; the commander confirmed (Session 41) there
  is no freeze. Backend/main changes are welcome provided they do not break
  existing behavior and align with the project's larger goals; deviations
  from original intent are acceptable when the implementation requires it.
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
programs. They may become relevant if link navigation is built.
> mission 62 (reconciliation): corrected — of the three, only `title` is a
> declared term (title.json); `link`/`heading` are semantic bucket names
> (navigation's `kind` is `link-collection`; title's `kind` is `heading`),
> never dictionary files (git history empty). `title` as a *kind* is
> unused (`make title` in zero programs) but the universal `title`
> property is in constant use.## Evidence-gated implementations in PLAN (items 58, 59, 61)

These are the CSS/styling and link implementation missions. They were BLOCKED
in PLAN.md on a Session 25 backend freeze and commander scope — but the
commander confirmed (Session 41) there is NO freeze, so the backend constraint
is lifted. The remaining gates are commander judgment calls (syntax/scope), not
engineering. The evidence missions that feed each one are EXECUTABLE and
landed (58/59 fed by 22/23/55/56/57; 61 fed by 54/60).

- **58 — HTML backend: wire declared physical hints into inline styles.**
  Today the backends emit only hard-coded styles; the physical hints already
  declared on card/banner (`padding`, `corner-radius`, `border`) are read by
  no backend (NOTES Missions 23 / 56 / 57). Gates: commander accepts the
  Mission 57 mapping scope; goldens updated deliberately (byte-identical
  discipline preserved). Backend freeze: none.
- **59 — HTML backend: one narrow responsive rule.** `narrow-class` /
  `narrow-layout` are declared on card-group but read by no backend
  (NOTES Missions 22 / 56). Gates: commander accepts one
  `@media (max-width: 768px)` `row -> stack` rule; evidence from Missions
  55/56 accepted. No fifth construct — conditions/state stay UNDECIDED.
  Backend freeze: none. **Gate cleared** (Session 49 interactive) and
  delivered by PLAN item 83: `backend_html._narrow_rule` emits one
  `@media (max-width: 768px) { .card-group { flex-direction: column; } }`
  rule, gated on the declared narrow defaults. Item 59 → DONE.
- **61 — `link` navigation (kind or property).** `link` is declared but used
  by zero programs (below: dead vocabulary); there is no link syntax and no
  backend emits a clickable target. What a link is and how to express it is
  investigated in NOTES Mission 60 with real-program evidence from Mission 54
  (pricing page). Gates: a WORKBOOK or commander SYNTAX decision (property
  vs kind); Missions 54/60 evidence accepted before any code. Backend
  freeze: none.

Still evidence-gated, unchanged: PLAN item 7 (first `choice` value), field
kinds, `boolean`/`date` type extensions (commander approved `number`
(Session 41); boolean/date have no vote and stay UNDECIDED), chart/table
kinds, `search`, `subtitle`/`description`, `button inside header`,
conditions/state, HTML fidelity pass, and the installed-copy packaging
caveat (fixed by PLAN 63).

## Commander decision — item 58 mapping values + palette (Session 42)

**Question.** PLAN item 58 was implemented without clearing its second
precondition ("the commander accepts the Mission 57 mapping scope"). The
mechanism is sound, the suite passes, and the language surface did not move —
but the *values* the dictionary now paints with are the agent's, and
DECISIONS.md lists "CSS fidelity … the real color palette" as UNDECIDED.
Accept, amend, or revert the mapping?

**Evidence.**

- M57 (DONE) proposed the contract: `card.padding` comfortable ->
  `padding:20px`; `card.border` subtle -> `border:1px solid #e0e0e0`;
  `card.corner-radius` slight -> `border-radius:8px`; `banner.padding`
  generous -> `padding:3rem`; `banner.text-alignment` center ->
  `text-align:center`. Scope: "first property only … inline styles,
  `backend_html.py` only".
- Shipped instead: `1.25rem`, `1px solid #e2e8f0`, `10px`,
  `3.5rem 1.5rem`, `text-align: center`. Only `text-align` matches.
  `1.25rem` (=20px) and `10px` trace to card.json's pre-existing
  `implementation.guess` (`padding: 20px`, `border-radius: 6-10px`);
  `#e2e8f0` traces to nothing — the guess says only "light", which is not a
  value.
- Scope shipped: 7 kinds (page, header, logo, navigation, banner, card,
  footer), a per-kind stylesheet rule plus inline overrides for
  entity-written values, and a `<meta viewport>` + `body` baseline. The last
  two appear in no proposal.
- Goldens: all four changed. M57's probe recorded `hello` / `topbar` as
  no-diff; both gained a viewport meta, a `<style>` block and `class`
  attributes. Byte-identical discipline held; this is still an output change.
- Language surface unchanged: no lexer, parser, semantic or interpreter edit.

**Options.**

- **(a) Accept the shipped mapping as-is.** Cheapest; the stylesheet
  architecture is less repetitive than inline-only and the site renders. But
  it lets a convenience hex become the project's palette by accident.
- **(b) Accept the mechanism, restate the values.** Keep `style` blocks +
  `style_declarations()`; the commander sets the numbers — in particular
  either one named colour token replacing `#e2e8f0`, or a decision that
  painting stays structural-only and colour waits.
- **(c) Revert to M57's contract.** Inline styles only, card + banner only,
  M57's five fragments, goldens regenerated. Most faithful to the gate;
  discards the extra kinds and the stylesheet.

**Recommendation.** (b). The mechanism is the engineering and it is good;
the numbers are the commander's. This is also the moment to settle the
palette question DECISIONS.md already flags, rather than letting a
convenience hex answer it by default.

**Consequences.** (a) makes an UNDECIDED decision by default. (c) loses
working, tested code and re-changes four goldens a second time. (b) needs
one more pass but leaves the palette decision where it belongs.

**Related.** `make <count> <kind>` reuse collision — hit independently while
writing `examples/site/site.ine` (two rows of three cards cannot both use
`make 3 card`; both rows are hand-named and grouped). Already recorded
above as evidence-gated with no PLAN entry. No new evidence, no action.

## Watch item — one unreproducible red full-suite run (Session 45)

Not a gate, and deliberately not a blocker. Recorded only so a future reader
who sees this claim elsewhere knows it was investigated and dismissed.

While verifying Mission 76, one `python -m pytest tests -q` reported **6
failures** in `tests/test_ine_agent.py` (`ExitCodeContractTests`,
`SupervisorTests`, four `CliTests`), printing the park-after-repeated-failures
message where the tests expect the cycle-limit message. Three later runs were
fully green (full suite ×2, the six tests in isolation), and the failing
output carried its own explanation: the supervisor invoked the real `opencode`
worker rather than the stub the test injected, with CLI *subprocess* tests
failing in the same run — an environment-side artifact rather than a code
regression. `make_root()` seeds a fresh temp root with no attempts state, so
persistent-state leakage was ruled out.

**If it recurs**, the question worth settling is a real one: whether the
whole-run `--cycle-limit` should still hard-stop with `STOP_ERROR` (item 50's
DECIDED contract) while parking stays scoped to a single mission's failure
budget. That would be the commander's call. No action until it reproduces.
