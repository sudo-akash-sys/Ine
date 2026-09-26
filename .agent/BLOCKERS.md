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

## RESOLVED — the provider-independence boundary (Session 52)

**Settled by the commander: keep ine-agent, remove the OpenCode agent file.**
Both questions are answered and written into DECISIONS.md; the text below is
kept because the reasoning and the accepted costs are the record.



The commander froze the product boundary: INE is an independent Python CLI that
drives external coding CLIs, and it must not modify a provider's UI,
configuration, agents, modes or plugins, nor depend on a provider-specific
project file. Two things in the repository contradict that today, and neither is
an ordinary implementation choice.

**1. The OpenCode agent file is a provider integration.** (DONE: file deleted,
--agent dropped, prohibitions moved into .agent/WORKER_INSTRUCTIONS.md,
ProviderIndependenceTests replaces the old agent-file tests.) The built-in `opencode`
profile passes `--agent ine-worker`, which only resolves because
`.opencode/agents/ine-worker.md` exists in the project. That file was added in
Session 50 as PLAN item 122 (`DONE`) to bound the agent's steps and restrict its
tools. Removing it is required by the new boundary; it also reverses a recorded
`DONE` item and removes a permission deny-list (no process control, no fetching
unrelated files). The guardrail would have to move into INE-owned text — the
prompt in `.agent/WORKER_INSTRUCTIONS.md` can carry the prohibitions, but it is
advisory to the model where the agent file was enforced by the tool.

- *Option A (recommended):* delete the agent file, drop `--agent ine-worker`,
  move the prohibitions into the INE prompt, and accept that they are advisory.
- *Option B:* keep the file for the `opencode` worker only, on the grounds that
  it is a worker definition rather than a UI change — but this keeps the
  dependency the boundary forbids.
- *Option C:* stop supporting the `opencode` profile entirely and drive only
  CLIs that need no project-side file.

**2. `ine run` collides with the language CLI.** The requested command surface is
`ine run`, but `ine` is already this repository's language CLI and already has a
`run` that executes a `.ine` file (`pyproject.toml` declares `ine = ine.cli:main`
and `ine-agent = ine_agent.cli:main`). Overloading the name means the language
CLI must dispatch to a subcommand that is not part of the language, and
`ine run foo.ine` and `ine run --worker claude` become one command with two
unrelated meanings.

- *Option A (recommended):* keep the orchestrator as `ine-agent` and make it
  reachable without editing JSON (see the pending `workers` / `use` work).
- *Option B:* add `ine mission` alongside the language's `ine run`.
- *Option C:* top-level dispatch inside `ine`, so `ine` decides by argv whether
  it is being asked to run a program or the mission queue.

Also recorded, not a question: the installed Claude Code rejects its own
configured model (`[claude-code:unrecognized_model]`, `deepseek-v4-flash`) and
the built-in `claude` profile passes no model argument, so that selection comes
from somewhere INE does not own. Per the boundary INE does not change it, does
not add fallback, and surfaces it in `doctor` instead. No credential manager is
in scope; external CLIs keep their own authentication.

## OPEN — may a `done` receipt with no changed files complete a mission?

**Question.** When a worker returns `status: done` with
`changed_files: []`, may the loop record the mission `DONE`?

**Evidence.** This is not hypothetical; it happened to a real plan item. A
diagnostic probe (a fake worker used to test output visibility) was run against
PLAN item 85, *Formatter implementation*. It returned
`{"status": "done", "summary": "visibility probe", "changed_files": []}` and
exited 0. The loop recorded item 85 as `DONE`, wrote
`.agent/compaction/85.md` reading `Files: (none reported)`, and moved the queue
to item 86 — on the strength of a receipt from a worker that had edited
nothing. The false record was detected and rolled back by hand (PLAN tag
restored to `EXECUTABLE`, compaction receipt deleted, attempt entry cleared,
STATE.md corrected). Nothing was implemented, so no work was lost — but the
loop was one unattended run away from recording a mission it never did.

The receipt contract (`receipt.contract()`) says `done` means "the mission is
finished and its verification passed", and describes `changed_files` only as
"repo-relative paths you edited". It does **not** say a `done` mission must
have edited something, so the current behaviour follows the letter of the
contract. That is the ambiguity.

**Options.**

1. **Reject: `done` with no changed files never completes a mission.** Record
   it as not completed, with the reason "claimed done but changed no files".
   - *For*: a mission is a request to change the repository; a `done` that
     changed nothing has not done it. This is the only defence against a
     plausible-sounding summary becoming a false `DONE`, and it costs nothing
     when workers behave.
   - *Against*: it forbids legitimate zero-change missions. A finding-only
     mission (per AGENTS.md, a planner audit has no source change) must then
     list its `.agent/NOTES.md` section in `changed_files` or be reported
     `failed` — a real, if narrow, false negative.
2. **Accept with evidence: a zero-change `done` completes the mission, and the
   run report must state that no file changed.** Cheap, and honest as long as
   nobody reads the `DONE` tag as proof of work.
   - *For*: no false negatives; the contract stays as written.
   - *Against*: the plan is the thing future cycles trust. A `DONE` that means
     "the worker said so" is precisely the failure mode just observed.
3. **Distinguish by intent: add a receipt field or status for "verified, no
   change needed".** Most honest long-term, and the contract already grows
   fields (`finding`, `follow_up`).
   - *For*: a verified no-op is a real outcome and deserves a real name.
   - *Against*: a contract change plus parser, prompt, and test work, and it
     only pays off if workers use the new status correctly.

**Recommendation.** Option 1 now, Option 3 later. Rejecting the zero-change
`done` is the conservative direction: the cost of a false negative is a mission
that stays `EXECUTABLE` and gets retried or re-planned, while the cost of a
false positive is a plan that claims work that never happened — and that is the
failure this loop exists to prevent. If a mission genuinely needs no change, the
worker can say so in `summary` and list the file it wrote (even a NOTES
section); the outcome is then recorded honestly.

**Consequences of deciding later.** Every unattended run before the decision
carries the hazard, and one already fired (above). The rollback contained that
one: item 85 was then genuinely completed by a later real run whose receipt
*did* list files, so no false `DONE` survives in the plan. The hazard itself is
untouched, though — nothing in the loop rejects a zero-change `done`, so the
next mission that reports one will be recorded as `DONE` unattended.

**Interim rule until this is answered:** treat a `done` receipt reporting no
changed files as unverified, and do not let it advance the queue unattended.

## ANSWERED — is a `make` body indented 4 spaces, or flush left? (superseded by the RESOLVED entry at the foot of this file)

> **Superseded below.** This analysis was written while a *partial* formatter
> sat in the tree; its **Consequences** paragraph describes that state and is
> **out of date** — the 16:37 run since added `tests/test_formatter.py`, the
> `{"format": true}` query, the editor provider and command, and `package.json`,
> and chose 4-space bodies. It is kept because the reasoning is what the answer
> was reached against. Read the `RESOLVED` entry, not this one, for current
> truth.

**Question.** In canonical form, are a `make` statement's properties and its
`inside` line indented under the `make`, or flush left?

**Evidence.** Three sources disagree, and the code follows the one nobody
wrote down:

- `.agent/missions/85.md` step 1 specifies "body properties indented by 4
  spaces; one property per line ` <name> <value>`".
- The docstring of the `src/ine/formatter.py` the real 15:23 Claude run left in
  the tree says the same thing: "the body of a `make` — the properties it
  carries and the `inside` line that places it — is indented 4 spaces under
  it", and its own header example shows indented bodies.
- The implementation emits **no indentation**. `format_program` turns
  `make card badge` / `card title "New"` / `card inside header` into exactly
  that, unchanged, at column 0.

So the formatter contradicts its own documentation and its own mission index.
Nothing else in the pipeline depends on the answer: the language surface is
untouched, `format_program` is idempotent and parse-tree-preserving either way,
and no test asserts an indent (there is no `tests/test_formatter.py` yet).

**Options.**

1. **Indent bodies 4 spaces**, as the index and docstring say. The formatter
   gains a nesting-aware emitter; canonical form becomes visually structured.
2. **Keep flush left**, and correct the index step and the docstring. The
   canonical form stays minimal, and `inside` reads as a peer statement, which
   matches how the current examples in the repo are written.

**Recommendation.** Option 2 unless the commander prefers visible nesting.
Indentation is a canonical-form decision — i.e. language surface — and the
repository's existing `.ine` samples are flush left, so keeping flush left
changes no example and makes the formatter's output match the code people
already write. The cost is editing the index and the docstring, which is
cheaper than adding nesting the language does not otherwise express.

**Consequences.** Whichever is chosen, mission 85 is not finished either way: no
`tests/test_formatter.py`, no `{"format": true}` query in `autocomplete.py`, no
`DocumentFormattingEditProvider` or `ine.format` command in `extension.js`, and
no `package.json` entry. Steps 1 and 2 are partly done; steps 3-5 are not
started. See `HISTORY.md` for how the work arrived in the tree unrecorded.

## RESOLVED — is a `make` body indented 4 spaces, or flush left? (answered 16:37 by the run that executed the index)

**Answered in code, by the run that executed the index: 4 spaces.** The
canonical form now emits

```
make card badge
    card title "New"
    card inside header
```

`format_program` is idempotent on that output, and the round-trip guard
(`parse(lex(formatted))` must equal `parse(lex(source))`) means the choice
cannot change meaning — indentation is presentation, not grammar, so no lexer,
parser or semantic rule moved. `tests/test_formatter.py` pins the layout.

This closes the question in the direction `.agent/missions/85.md` step 1
already specified, which is the right way for it to close: the planner's index
was the standing decision, the implementation now matches it, and the module
docstring and the code agree for the first time. My recommendation had been
flush left on the grounds that the repo's samples are flush left; the run
chose otherwise and the choice is defensible — visible nesting is what a
formatter is for, and canonical form is not obliged to match hand-written
files. No further decision is needed unless the commander prefers flush left,
in which case it is a one-line emitter change plus the layout tests.

**Note on what this cost.** The run also found and fixed two real defects in
the earlier partial work: the round-trip guard compared statement dataclasses
field-by-field *including* `line`, so any reflow that inserted the canonical
blank line was rejected and `format_program` silently returned its input
unchanged (a no-op for every non-canonical buffer, which is most of them);
and comment-bearing files were reformatted with their comments **deleted**,
which under `formatOnSave` would have destroyed work on every save. Neither
was visible from the outside — the first is a silent no-op, the second only
fires on a file that has comments. Found by reading, not by a failing test.
