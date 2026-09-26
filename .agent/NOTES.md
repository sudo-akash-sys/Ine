# .agent/NOTES.md

Research findings from the Active missions 11-30 (`.agent/PLAN.md`). Each
entry records what was investigated, what was found, and the smallest
evidence-based next step — findings first, code second.

## Mission 11 — Invalid dictionary entry feedback

**Question.** Invalid dictionary entries (syntax-broken JSON, a JSON value
that is not a dict, a dict with no `term`, wrong types) are silently
skipped by `_load()` (`dictionary.py`). Does that silent-skip cause real
problems, and should `_load()` warn?

**Finding.** Yes, it can, in exactly one way: silent vocabulary loss.
- `_load()` catches `(OSError, ValueError)` and `continue`s; a non-dict or
  `term`-less entry is skipped too. Nothing prints or logs.
- Consequences are all downstream and silent: the kind vanishes from
  `makeable()`, `find()` returns None, `suggest(kind)` / `value_hint` /
  `value_shape` return empty, and `ine --dict <kind>` exits 1 "unknown".
  A program that already names the kind still renders (the dictionary is
  advisory, never a validator), so the failure shows up only as *missing
  completions / missing hints*, with no pointer to the broken file.
- Severity at current scale is **low but real**: 15 small single-kind JSON
  files; most breakage is caught quickly by the dictionary test suite
  (which asserts `header`, `card`, `viewport`, etc. exist). The costly case
  is a *typo below the test surface* (a wrong `term` on a file the tests
  don't assert) or a syntax error during active editing, where the only
  symptom is "why did this suggestion disappear?".
- The repo has no logging setup anywhere; `dictionary.py` imports `json`,
  `os` only.

**Minimum useful feedback (recommendation, not yet implemented).**
- One `warnings.warn(...)` per skipped file at load time, naming the file
  and the reason (`invalid JSON`, `not an object`, `missing "term"`).
  `warnings` needs no new dependency and surfaces in `python -m pytest`
  output and console runs, so broken dictionaries become visible at the
  exact moment they load.
- Do NOT raise: a broken file must not take down the editor/completer, and
  the advisory contract stays unchanged.
- Do NOT add a validation framework: a warning per file + the existing
  loader test (item 8) is the whole fix. Optionally surface skipped files
  in `ine --dict` output later, only if a real user asks.

**Status.** Finding recorded; no code change yet — implementation is a
reversible one-liner (warn in `_load()`) if commander agrees it is worth
the noise.

## Mission 12 — Value-shape consistency review

**Question.** Are value shapes represented only when the dictionary data
declares them? Any code path that invents or infers a shape?

**Finding.** Consistent — no invention anywhere.
- Shape *production* lives in exactly one place:
  `dictionary._shape_from` (`dictionary.py:188`): a plain string only maps
  to a typed shape when it is the standard value kind `"text"` or `"length"`;
  any other string (e.g. `"row"`) yields `ValueShape()` unknown; a
  non-empty list of strings yields the `"choice"` shape; anything else is
  unknown. This is the Session 33 hardening, still holding.
- Shape *selection* — `dictionary.value_shape` — consults **only**
  `properties` blocks (the kind's own, then the universal entry for regular
  kinds); it never reads `defaults` hint strings, so a bare-word hint like
  `card padding: "comfortable"` can never become a shape. It returns a shape
  only when `_shape_from` did not say unknown.
- Shape *exposure* — `autocomplete._known_shape` (`autocomplete.py:117`)
  emits `None` for unknown so protocol items carry no fabricated shape. No
  other module constructs `ValueShape` (grep: producers/consumers are only
  these two modules).
- Data evidence today: `"text"` (universal `title`/`text`) and `"length"`
  (viewport `width`/`height`) are the only typed values declared; no
  dictionary entry declares a list, so the `"choice"` path never surfaces in
  production output (only in the mocked test
  `test_choice_shape_lists_allowed_options`), matching BLOCKED item 7.

**Recommendation.** No change. The representation and both readers are
aligned; the next shape to appear must come from real dictionary data, not
code.

## Mission 14 — Autocomplete edge cases: unusual cursor positions

**Question.** What happens at start-of-line, midline, inside a quoted
string, after a comment, after a blank line, after multiple spaces —
correct, graceful, or crash?

**Finding.** No crashes anywhere; the comment-stripping and
split-based context detection behave as follows (all now covered by
`CursorEdgeCaseTests` in test_autocomplete.py):
- Start of line / blank line / whitespace-only line: no context (None, empty
  items) — correct.
- Midline while typing (`make p`): `kind` context, kinds suggested — correct.
- Mid-identifier on a property (`card-1 tit`): `properties` context with the
  partial — correct.
- Inside a quoted value (`page title "Ho`): **no context** — acceptable
  (no completion inside strings today); graceful.
- After a complete `"value" ` with trailing space: no context (statement
  finished) — correct.
- Comment-only line (`# header `): no context — correct.
- After multiple spaces (`header     `): property context retained — correct.
- **After an inline comment on a statement line (`make page # note `): the
  comment is stripped, leaving `make page `, which misclassifies as a
  `value` context with `kind_word="make"`.** It does not crash: `resolve_kind`
  finds no kind named `make`, so items are empty. Harmless today, but the
  classification is wrong; documented rather than fixed per the mission.

**Recommendation.** No fix now. The one misleading case (`statement #
comment ` misclassified as a value context) resolves to empty items and
cannot produce wrong completions. If inline comments become common, the
context detector should run over the comment-stripped line minus a trailing
comment token.

## Mission 16 — Editor diagnostics investigation

**Question.** Do VS Code users get any in-editor errors, or only
compile/render-time messages? Is a basic diagnostics pass justified before
a full LSP?

**Finding.**
- The extension (`editor/vscode-ine/extension.js`) registers **only** a
  completion provider. There is no `DiagnosticCollection`, no `provideHover`,
  no code actions, no save/change validation. Errors surface **only at
  build/render time** via `ine run` / `ine render` / `ine visual`; in the
  editor an invalid file still gets completions (the dictionary is advisory).
- The engine side has **no validation endpoint**: `autocomplete.py` answers
  JSON-lines completion queries; it never lexes/parses/analyzes the buffer,
  so there is nothing today for the extension to turn into red squiggles.
- Ine's grammar is tiny (four constructs + say/group), so parse-level
  diagnostics are cheap: the lexer/parser already exist and already report
  `LexError`/`SyntaxError` (with no line context today) — surfacing them
  would mainly need position plumbing.

**Recommendation (no implementation this mission).** Do **not** build an
LSP. Before that, the minimum useful step would be a small `validate` query
on the existing JSON-lines protocol that parses the buffer and returns
`[{line, message}]`, pushed into a `DiagnosticCollection` by the extension
(≈50-100 LOC across engine + extension, reusing `lex`/`parse`). Justified
when a real user asks "why is this (not) an error in the editor?"; keep
diagnostics advisory (dictionary is not a validator) so unknown kinds do not
red-underline. DECISIONS.md status for diagnostics stays UNDECIDED.

## Mission 17 — Backend / parser / semantic error message audit

**Scope.** All engine errors carry `.message` and `.line`; the CLI prints
`error: {message} (line {line})` (`cli.py:_report_error`). No error displays
as a bare class name. With one exception every message names the offending
text; the audit targets guidance quality.

**Worst offenders (before → after):**

1. `parser.py:90` `cannot understand this line`
   → `cannot understand this line: '<line text>' — a statement starts with
   'make', 'say', 'group', or '<name> <property> <value>'`
   No content, no cause, no fix today.
2. `lexer.py:97` `unexpected character '-'`
   → `unexpected character '-' (line L, column C) — check for stray
   punctuation or an unclosed quote`
   Cryptic, and the column (which LexError knows) is not printed by the CLI.
3. `semantic.py:41` `'page' has a property but was not declared with 'make'`
   → append `— add 'make page' (or 'make <name> <kind>') before setting
   properties`
   Explains the violation but not the fix; new users do not know about
   `make` yet.
4. `backend_html.py:43/78` `the html backend does not support this kind yet:
   samt`
   → `...does not support this kind yet: 'samt' — run 'ine --dict' to list
   supported kinds`
   Practical help (what's supported, how to check) is missing.
5. `unexpected extra text` (`parser.py:101,143,161,178,199`)
   → `unexpected extra text: '<remaining source>'`
   Terse; does not echo what was found after the completed statement.

**Systemic (not an exception):** `_report_error` ignores `column` even when
the error carries it (LexError has `column`), so multi-word lines report the
wrong location. Printing the column when present would sharpen 2 and 5 for
free. Nothing to change per mission scope — this is the recommendation list.

## Mission 18 — Minimum documentation review

**Scope.** Read README.md, LANGUAGE.md, CONTRIBUTING.md as an unfamiliar
reader. Gap list only; no docs were written.

**What exists.** README (philosophy, quick start, statements table, three
backends, dictionary intro, what-works / not-yet split, links). LANGUAGE.md
(actual grammar, semantics, backend lowest-level detail, known limits).
CONTRIBUTING.md (generic boilerplate; nothing Ine-specific). Examples in
`examples/`. No `dictionary/README.md`.

**What is misleading / wrong.**
1. README "What Works Today" says *151 passing* (line 303) — the suite is
   now 252. A stale number undercuts the "test suite" selling point.
2. README's dictionary JSON illustration (card / card-group) uses a **fake
   shape** (`"description"`, `"properties": ["title", ...]`, `"layout"` at
   top level) that no real `dictionary/*.json` resembles (real: `term`,
   `meaning`, `kind`, `element`, `defaults`, `properties`+shapes,
   `provided-by`, `universal`). A reader opening `dictionary/header.json`
   will not recognize it.
3. README "Not Implemented Yet" §Multiplicity (lines 325-329) describes
   implemented features (`make 3 card`, `group`, expansion) before the real
   caveat ("no `every` keyword") — reads as if multiplicity/collections are
   NOT implemented when they are.
4. README's intent-vs-implementation table (`logo left, navigation right`,
   `footer stay at bottom`, `card with subtle shadow`) invents syntax that
   **does not parse in Ine** today. This is the intro's promise backed by
   unworkable examples.
5. README test command `python -m unittest discover -s tests` works but the
   canonical runner is `python -m pytest tests`; docs should state one.
6. LANGUAGE.md §7 is titled "as of Session 22" — stale for 21 onward bodies,
   and it omits everything after Session 22 (groups caveat is there, but
   value shapes, dictionary discovery, editor protocol, ine-agent are not
   listed as limits/features).

**What is missing.**
7. No `dictionary/README.md` and no developer doc of the JSON schema (only
   the `dictionary.py` docstring documents it). The dictionary is THE
   central concept, yet a newcomer has no orientation into `dictionary/`.
8. No "how to add a new kind/property to the dictionary" guide (field-by-
   field, where it surfaces in `ine --dict`, what tests to run).
9. CONTRIBUTING.md is boilerplate: no repo layout, no test commands, no
   "never change parser/semantic/backends casually", no `.agent/` rules.

**Minimum needed for someone to build something:** README example fix (3,4),
a real test count (1), and one page documenting the dictionary schema + how
to add a kind (7,8). Everything else is polish behind these.

## Mission 19 — Real-world example: dashboard experiment

Program: `.agent/experiments/dashboard.ine` (builds clean:
`python -m ine .agent/experiments/dashboard.ine -o .tmp/dashboard.html`).
Composed ONLY of declared vocabulary: page, header, logo, navigation,
container, card-group, card, section, button, image, footer, title/text.
Evidence collected by watching each line that the dictionary could not
guide.

**What worked.** A dashboard skeleton: header + brand + nav; KPI row
(container → card-group → `make 3 card` + `group`); chart placeholder
(section → image); second region + admin actions + footer. Rendered to HTML.

**Vocabulary fall-shorts (each is evidence, not a fix request).**
1. **Default entity-name collisions.** `make container` twice and
   `make section` twice each fail with "entity defined twice". A
   multi-region page ("container", "section", "card-group" repeated) is
   normal usage, but each repeat forces explicit `make <name> <kind>`.
2. **Multiplicity cannot be reused.** `make 3 card` always numbers
   card-1..card-3; a second batch of the same kind collides. No offset,
   index, or "start at" mechanism — second card row had to be hand-named
   (deploy-1..3).
3. **No numeric or boolean values.** KPI metrics ("99.98% trailing 30d",
   "12.4k req/min", "38 ms p95") are expressible only as `text` strings;
   no number formatting, no `value`/`metric` property. `logo.interactive`
   and `button.interactive` literally document "not settable yet: Ine has
   no boolean values".
4. **No chart/table vocabulary.** `chart`, `table`, `row`, `cell` do not
   exist. A data table (core to dashboards) is impossible; the chart slot
   had to be an `image`.
5. **card-group is contained only by container.** A `section` cannot host
   cards, and its member set is just (button, image). Regions that mix a
   heading with a row of cards must use a container, not a section.
6. **No status/semantic color.** Cannot express OK/warn/error states
   (e.g. a latency threshold) — no color or state properties exist.
7. **No date/time values.** Timestamps ("shipped 12:40 UTC", footer
   copyright) are embedded in `text`; there is no date type.
8. **Buttons can live only inside sections.** A page with no section has
   nowhere to put a button per the dictionary.

**Common shape behind 1-3:** the entity/type model is string-valued and
name-indexed, so repetition, counting, and non-text data all collapse onto
programmer-chosen names and `text` strings. The dictionary can say WHAT a
thing is (kind, members, line-valued properties declared in JSON) but not
"how many", "which row", or "what the number is".

## Mission 20 — Real-world example: form experiment

Program: `.agent/experiments/form.ine` (builds clean, rendered to
`.tmp/form.html`). A contact form written with ONLY the current dictionary
reduces to: a section titled "Get in touch", one `button` with
`text "Send message"`, and a footer. That is the entire expressible surface.

**Fall-shorts (evidence, not requests).**
1. **Zero field kinds.** `input`, `textarea`, `select`, `checkbox`,
   `radio`, `label`, `field`, `form` do not exist in the dictionary. The
   form body — every actual field — cannot be expressed at all. The only
   control kind is `button`.
2. **No field/label association.** Even with a hypothetical field, there is
   no "label for / belongs to the field named " relation; a label would
   have to be free-floating text.
3. **No interaction semantics.** No required/optional, no validation, no
   error/status text, no focus order, no submit/loading/disabled states.
   `button.interactive` is documented as not settable (no booleans), so the
   send button cannot even declare it triggers an action.
4. **Buttons only inside sections** (same constraint as Mission 19 finding
   8) — a bare page with a button needs an otherwise pointless section.

**Cross-experiment view (19 + 20 converge):** the vocabulary is structurally
complete for *static, display-oriented pages* (bars, sections, cards,
navigation) but has literally nothing for *input and interaction*. The two
missing pillars are (a) control/field kinds with an association mechanism,
and (b) boolean/numeric/date typed values (entry points for required,
disabled, interactive, status color). Both are language-shape questions, not
mere JSON additions — flagged as candidate vocabulary-expansion evidence
only; no syntax or dictionary change was made.

## Mission 22 — Responsive UI investigation

**Question.** Can Ine express responsive intent ("stack on narrow",
breakpoints, conditional layout) today, and is it a language or an
implementation concern?

**Evidence.**
- `card-group` DECLARES responsive intent in the dictionary:
  `narrow-class` = "viewport.width == narrow", `narrow-layout` = "stack
  members". This is the vocabulary for "stack on narrow".
- NO backend reads `narrow-*`. `backend_html.py:_open_tag` only consults
  the JSON `layout` field (`row` → flex; else static stack); generated HTML
  contains no `<meta viewport>` and no `@media` rules. `backend_visual.py`
  behaves identically (row vs stack only). Neither has breakpoints.
- There is therefore NO user-visible way to make anything responsive, and
  no way at all to author a breakpoint or conditional layout (no
  conditional construct exists; DECISIONS.md declares "Conditions / state"
  UNDECIDED as a possible fifth construct).

**Classification.** The intent lives in the dictionary (metadata), but the
behavior is entirely an implementation concern — as far as an Ine program is
concerned today, "responsive" does nothing. PLAN already lists a backlog
item ("Backend responsive implementation") for mapping `narrow-*` to HTML
CSS.

**Recommendation (no change made — backend freeze).**
1. Keep responsive intent declarative; `narrow-class`/`narrow-layout` are a
   reasonable stable interface and should stay as the vocabulary.
2. When the backend freeze lifts, implement ONE narrow rule in the HTML
   backend: wrap the page in a narrow media query and apply `layout: row →
   stack` for members that declare `narrow-layout`. No new language
   construct is needed for the "stack on narrow" case.
3. Do NOT add a conditions/state construct now — DECISIONS.md keeps it
   UNDECIDED; the dashboard experiment never needed one to be useful, and
   the backends can't honor it while frozen.

## Mission 23 — Styling/theming limitation investigation

**(a) What users actually see.** HTML backend emits hard-coded inline
styles only: the page gets a flat `div`, rows become `display:flex; gap:20px`
(via `_open_tag` reading the dictionary `layout` field), titles render as
`<h1>`/`<h3>`. There is no stylesheet anywhere; colors come from the OS
defaults (no background/foreground at all). Visual backend hard-codes
`KIND_COLORS`/`KIND_TEXT_COLORS` Python dicts ("the renderer's own choices —
backend detail, not language", per its own docstring) plus fixed fonts,
paddings, and a 800x600 window.

**(b) Can users customize from an .ine program?** No. Nothing visual is
settable: the dictionary declares structural/behavioral metadata (`element`,
`layout` row/stack, `position`) which the backends honor, and physical-form
hints (`card.padding` = comfortable, `card.corner-radius` = slight,
`banner.padding` = generous) which NO backend reads. There is no color,
font, spacing, or size property that reaches a renderer. Total user control
today = choosing kinds + row-vs-stack layout + title/text content.

**(c) Smallest evidence-based solution.** No theming system is warranted.
The smallest step is a backend-only change: wire the already-declared
physical-form metadata (`padding`, `corner-radius`, `border` on card/banner)
into the HTML backend's inline styles — e.g. a tiny CSS column per kind. That
touches only `backend_html.py` (one style map), requires no language or
dictionary change, and gives users the first honest "this property does
something" signal. Deferred until the Session 25 backend freeze lifts; then
submit as evidence for whether the metadata deserves to become first-class.

**Not a gap:** the freezing is intentional (Decisions Session 25). The backends
are a renderer detail; the thing to protect is that styling never spawns a
parallel ad-hoc theming surface before the WORKBOOK weighs in.

## Mission 24 — CI/regression infrastructure investigation

**(a) Test command.** `python -m pytest tests` — 267 tests collected, ~15s
run locally (`tests/test_ine.py`, `tests/test_ine_agent.py`,
`tests/test_autocomplete.py`; unittest.TestCase classes discovered by pytest).

**(b) Hermetic?** Yes. Test imports are entirely stdlib + the package itself
(json, mock, io, os, re, shutil, subprocess, sys, tempfile, unittest,
pytest; `ine.*`, `ine_agent.*`). No network calls, no third-party deps.
Native tests (`ine.backend_c` / `native`) auto-skip via
`@unittest.skipUnless(find_c_compiler() is not None, ...)`, so a CI box
without a C compiler just skips them. Two hazards:
1. **Tkinter window-creation tests are NOT display-guarded** — 4 tests
   build a real `tk.Tk()` (e.g. `test_visual_render_returns_a_tk_root`,
   `test_hero_int_visual_render_creates_window`, `test_cards_...`). On a
   headless runner these fail unless `DISPLAY` is set or `xvfb` is used.
2. One of those (`test_cards_visual_render_creates_window`) flaked once
   under full-suite load this session (failed in suite, passed in
   isolation) — display tests can be timing-flaky; CI shouldn't hard-fail
   on them.

**(c) Estimated cost.** GitHub Actions ubuntu-latest: one workflow, checkout
+ `sudo apt-get install -y xvfb python3-tk` + `pip install pytest .` +
`xvfb-run -a python -m pytest tests`. ~2-3 min wall clock, zero running
cost at current scale.

**(d) Justified?** Yes — marginal and standard. Value is a headless
cross-OS regression net at trivial cost. Two fixes make it deterministic:
mark the tkinter window tests `@unittest.skipUnless` on a display check
(e.g. probe `os.environ.get("DISPLAY")` / a `tk.Tk()` smoke), and pin the
workflow's visual step behind `xvfb-run -a`. Recommendation: add
`.github/workflows/ci.yml` on the next commit-touching checkpoint; no
framework changes needed.

## Mission 25 — Packaging/distribution investigation

**(a) pyproject.toml completeness.** Structurally complete: build-system
(setuptools>=61), name/version/description/readme/requires-python/license,
and correct entry points (`ine = ine.cli:main`,
`ine-agent = ine_agent.cli:main`). **One critical readiness gap: the
dictionary data is NOT part of the package.** `dictionary/*.json` (15 files)
lives at the repo root; `dictionary.py:62-63` resolves `DICTIONARY_DIR` via
`__file__` up to `<repo>/dictionary` — a source-checkout assumption. A wheel
install puts `ine/` in site-packages, so `DICTIONARY_DIR` points at a dir
that does not exist; no `package-data`, no `MANIFEST.in`, no data dir inside
`src/ine`. Result: `pip install .` succeeds but a fresh `ine` has an EMPTY
dictionary — CLI `--dict`, backend element/layout lookup, and autocomplete
are all dictionary-driven, so an installed copy is effectively broken.

**(b) Entry points / install.** Declared and correct; `python -m ine --dict`
works from a checkout. But until (a) is fixed the installed console scripts
run against an empty dictionary. Fix (single mechanical step): move the JSON
data into `src/ine/dictionary/` and resolve via the package dir
(e.g. `importlib.resources`), add `pyproject` package-data. This is a
packaging/`dictionary.py` change, NOT a parser/semantic/backend change —
reversible and outside the Session 25 freeze's spirit (dictionary work).

**(c) VS Code extension (.vsix).** `editor/vscode-ine/package.json` already
has the fields `vsce` needs (publisher `anomalyco`, engines, contributes,
main, activation events) so `vsce package` would produce a `.vsix`. BUT the
extension is a pure proxy that spawns `python` running the Ine engine
(`pythonTarget` → `process.env.INE_PYTHON || "python"`); a `.vsix` alone is
useless unless the Ine package is installed and callable. So extension
shipping is blocked on (a), not on packaging itself.

**(d) Not assessed / not recommended:** building a package manager or
registry. The single blocking item is the dictionary-as-data gap.

## Mission 26 — Editor architecture evaluation

**Current.** `dictionary.py` (single source of truth) → `autocomplete.py`
(cursor-context resolver + query cells) → `extension.js` (pure proxy),
over a JSON-lines subprocess with FIFO request matching. Protocol surface:
`context` (make/kind/properties/inside/value), `complete` returning
label/insert/detail/type/value_shape rows. `autocomplete.py` is already
decoupled from the wire — `context()`, `complete()`, `resolve_kind()` are
plain functions the editor protocol and any future server share.

**(a) When do diagnostics/formatting/hover become justified?**
- **Diagnostics: justified now (minimal).** The engine parses and
  semantic-analyzes whole files and already produces line-level errors;
  a `validate` JSON-lines query (lex+parse+analyze → `[[line, message], ...]`)
  is ~0.5 day with tests. Do it AFTER fixing the `_report_error` column-drop
  (Mission 17) so diagnostics aren't misleading. Editor can push results
  into a `DiagnosticCollection`.
- **Hover: not yet — cheap whenever.** The only hover data today is the
  dictionary meaning, already shown in the completion detail row. A hover
  query is ~0.25 day; worthwhile once diagnostics exist.
- **Formatting: not justified.** No formatter exists; the grammar is small
  but writing+testing a pretty-printer is real work with no user pull yet.
  Lowest priority by far.

**(b) JSON-lines vs LSP.** Stay JSON-lines. The protocol is stateless, tiny,
testable as plain unit tests, and single-feature — LSP buys capability
negotiation, lifecycle management, and multiple feature channels that
nothing here uses. Switch threshold: when the editor needs 3+ LSP-grade
features at once (diagnostics AND hover AND formatting), or when a shared
language server is wanted. Because `autocomplete.py`'s core is wire-
independent, an LSP server later is a new protocol adapter reusing the same
functions — the choice is reversible and cheap.

**(c) Recommended path.** 1) fix column in errors (Mission 17); 2) add
`validate` query + extension DiagnosticCollection; 3) hover when editor
work resumes; 4) formatting/LSP only past the 3-feature threshold. All
stays on the existing JSON-lines architecture — no LSP now.

## Mission 27 — Native backend reality check

**Actual capability (verified on this box, zig 0.16.0 present).**
`backend_c.emit` lowers ONLY `SayStatement`s (literals + already-resolved
references) to C `printf`s; `native.py` discovers the compiler
(zig/clang/gcc/cc or `INE_CC`) and builds a runnable executable. Full
pipeline worked: `python -m ine examples/say/say.ine --native` prints
"Hello, world!", emits `.tmp/native/say.c` + `.exe`. Note: `resolve()` turns
`say page title` into the literal "Hi" BEFORE emission, so print-path
references DO work.

**What it cannot do.** Every non-`say` statement (`make`, `inside`, group,
property) is silently dropped — a page-describing program compiles to a
binary that prints nothing (`hello.ine --native` ⇒ "no executable
statements"). There is no UI runtime, no linkage to the dictionary/enabled
members, no expressions, no input. The `.exe` filename is hard-coded
(inconsistent on non-Windows). Output is a console print stream only.

**Usable beyond demonstration?** No. The language's actual purpose is
page/UI description; the native target describes none of it. Its genuine
value today is (a) proving "lower to machine code via C" works, (b) a
testable pure emitter, (c) an experiment for future execution semantics.
The extension/console call it "research-only" — that matches reality.

**Recommendation.** Keep it research-only per BLOCKERS.md; do not build a
native UI runtime without a real user program that needs it (evidence
standard, consistent with the rest of the plan). If execution semantics
ever become first-class (conditions, loops), the C emitter is the right
place to start, but no further investment now.

## Mission 28 — Autocomplete worker reliability

**Test.** Sent 300 requests to the long-lived
`python src/ine/autocomplete.py` subprocess (JSON-lines, matched ids),
including malformed JSON and blank lines mid-session.

**Findings.** Worker survived cleanly: 300 requests processed in 0.18s
(~1600 req/s), 0 errors, 0 crashes, stayed alive through malformed input,
processed a real request successfully after the corruption. Responses
echoed correct ids throughout. Malformed JSON returns `{"error": ...,
"items": []}` — caught by `_respond`'s blanket except, protocol stays
alive. No memory measurement (psutil absent on this box) — not a concern
for the language; worth noting only if memory growth becomes a VSC concern.

**Worker architecture is sound.** `_respond` catches any exception; stdin/
stdout is line-buffered with immediate flush per response; on process death
the extension respawns automatically (`DictionaryWorker._down` in
`extension.js:58`). No timeout/health needed at prototype scale.

**Recommendation.** No fixes needed. Keep the current architecture. If
memory or latency becomes a VSC concern, the failure mode to watch is:
worker crash triggers respawn; unbounded respawns could accumulate if the
engine itself OOMs.

## Mission 29 — ine-agent reliability

**Scope questions, answered with the code (state.py / supervisor.py) plus a
new regression suite.**

- **(a) Does it stop while missions remain?** YES — this is Mission 30's
  bug. If a worker marks its finished task `DONE` (the realistic summary
  it writes) instead of deleting the item, `read_plan` next cycle sees a
  `DONE`-tagged item; `Task.executable` (then: `tag != "BLOCKED"`) treated
  `DONE` as executable, so `first_executable()` returned the SAME finished
  task, supervisor saw identical identity → `attempts++` → after
  `max_attempts` (default 2) it stopped with STOP_ERROR while later
  EXECUTABLE items were still pending. Fixed in Mission 30.
- **(b) Are stop conditions correct?** Yes, apart from (a). The four
  conditions are intentional: no-executable-work → STOP_OK; HUMAN_DECISION
  (state file or worker output) → STOP_HUMAN; same-task-after-N-attempts →
  bounded STOP_ERROR (prevents infinite loop on a stuck/failing worker);
  cycle-limit → hard bound. Unmarked and non-BLOCKED items are executable
  per the historical PLAN rule; `CLAUDE_REVIEW` runs review-then-impl.
- **(c) Worker crashes handled gracefully?** Yes. A nonzero worker exit is
  caught, its exit code + first 20 output lines printed, then the plan is
  re-read; if nothing advanced, `attempts++` → bounded stop. The
  supervisor never dies with the worker and never loops unboundedly.

**Verification.** `make_root`/`plugin_done_text` fixtures added so the DONE-
marking path is exercised at the supervisor level (see Mission 30).

## Mission 30 — ine-agent continuous execution fix

**Root cause.** `Task.executable` in `src/ine_agent/state.py` returned
`self.tag != "BLOCKED"`. A `DONE` tag therefore left the item executable;
after a worker finished a task and re-tagged it `DONE`, the next cycle
re-picked the same task, identity matched, and the supervisor stopped early
(STOP_ERROR after `max_attempts`) even though EXECUTABLE missions remained
below it in the plan.

**Fix.** `executable` now excludes both `BLOCKED` and `DONE`:
```python
return self.tag not in ("BLOCKED", "DONE")
```
Unmarked items and `CLAUDE_REVIEW` stay executable (unchanged).

**Tests added (`tests/test_ine_agent.py`).**
- `test_plan_parses_tags_and_executability` — extended with a `DONE` item:
  asserts it is NOT executable (and that the list keeps its contract for
  BLOCKED / EXECUTABLE / CLAUDE_REVIEW / unmarked).
- `test_done_items_are_not_picked_as_first_executable` — a `DONE` item is
  skipped in `first_executable()` in favor of the later EXECUTABLE one.
- `test_done_marked_task_does_not_stop_the_loop` (supervisor level) — worker
  marks the first task `DONE`; the loop continues to the second EXECUTABLE
  task, calls the worker twice, exits STOP_OK, output has no
  "could not advance". Uses a new `plugin_done_text` helper (renumbers the
  rest of the plan while leaving the finished item marked `DONE`).

**Verification.** `python -m pytest tests/test_ine_agent.py` → 44 passed.
The suite's classical stop tests (cycle-limit, attempts-limit,
no-work, human) all still pass, so the changed stop semantics are
restricted to DONE items.


## Mission 37 - What Ine can currently express (inventory)

**Scope.** Derive, from LANGUAGE.md, the dictionary reader, the backends,
and fresh renders of the real programs, a current-state inventory of what
a .ine file can express today. No code changes.

**Five statement forms (exact grammar, from LANGUAGE.md section 3).**

| Form | Grammar | Example |
| --- | --- | --- |
| Make | `make name [kind]` / `make count kind` | `make hero banner`, `make 3 card` |
| Property | `name property value` | `page title "Hello"` |
| Inside | `name inside name` | `logo inside header` |
| Say | `say value` / `say name property` | `say page title` |
| Group | `group name = name+` | `group cards = card-1 card-2 card-3` |

`name` = identifier (letters digits `_` `-`, not starting with a digit);
`value` = quoted string or number (integer/decimal); `count` = positive
whole number. One statement per line; blank lines and `#` comments allowed;
`inside` is reserved. Grammar is invariant - the implementation matches the
spec exactly (verified against `src/ine/parser.py`).

**Value kinds.** Three, all literals: strings (`"..."`), integers (`25`),
decimals (`1.75`). Property references (`say name property`) resolve at
COMPILE time into the stored literal - no runtime model, no variables, no
mutation, no expressions, no booleans, no lists, no escaping in strings.

**What each target actually renders.**

- **HTML** (`ine file.ine -o out.html`): requires exactly one entity of
  kind `page` (else BackendError). Page `title` -> `<title>` + `<h1>`;
  each entity maps via its dictionary `element` (page->div, header->header,
  logo->div, navigation->nav, card->article, button->button, image->figure,
  section->section, footer->footer, ...). Nesting is the `inside` tree.
  `layout:"row"` parents (card-group) render `style="display:flex;gap:20px"`;
  their children get `style="flex:1"`; `position:"bottom"` (footer) is
  pinned. A child `title` renders as `<h3>`, child `text` as element
  content. The `defaults`/`guess` fields are NOT read. Verified: fresh
  render of cards.ine matches the golden structure (`<div class="page">`,
  `<header class="header">`, `<article class="card-1">`,
  `<footer class="footer">`).
- **Visual** (`ine file.ine --visual`): tkinter window; same Model + same
  containment walk; per-kind colors/layout are a backend concern;
  `layout:"row"` packs children side-by-side equal-width,
  `position:"bottom"` pins the footer; a card renders `title` bold over
  `text`. Requires a display server; no headless mode; tests need a display
  (transient TclError flake under load).
- **Native** (`ine file.ine --native`): lowers ONLY `say` statements
  (printf %s/%d/%.17g for string/int/decimal; strings are data, never
  format text). Every `make`/`property`/`inside` statement is silently
  dropped - a page-describing program compiles to a no-op .exe. Needs
  `INE_CC` or zig/clang/gcc (`zig cc` recommended). Research-only; see
  Mission 27.

**What the editor completes (all four contexts + value shapes).**
`src/ine/autocomplete.py` over JSON-lines:
- `make ` / typing `m`..`make` -> `kind` context -> `makeable()` (13 kinds).
- `<name> ` -> `properties` context -> `dictionary.suggest(kind)`
  (properties + `child inside kind` concepts); kind resolved via
  `resolve_kind` (declared dictionary kind, `make name kind`, `make n kind`
  numbered entities, or a group's member kind).
- `<name> <property> ` -> `value` context -> `value_shape(kind, prop)`:
  `text` -> one `""` quoted item (universal title/text); `choice` -> one
  item per allowed option (none declared yet); else empty.
- `<child> inside ` -> `inside` context -> `dictionary.parents(child_kind)`
  (reverse containment).
`group`/`say` at statement start yield no context (guard,
autocomplete.py:67).

**Expressible today (boundary).** Declare entities/kinds with multiplicity
and then name the set as a group; set string and numeric properties; build
a tree-shaped containment model; `say` computed-at-compile-time values;
render the model to a layout HTML page or a tkinter window by the SAME
declared vocabulary. All programs in `examples/` + `.agent/experiments/`
are fully covered or documented (Mission 35 guard).

**NOT expressible today.** booleans, lists, expressions, runtime variables,
`every`; field kinds (input/textarea/select/label/form) - a form reduces
to a button; typed/status values (dashboard metrics like "99.98%" are
`text` strings); chart/table kinds; links with a destination (navigation
carries no `contains`, no `link` targets; a link can only be faked in
`text`); user styling reachable from `.ine` (styles are hard-coded;
`padding`/`corner-radius`/`border` hints are unread); responsive behavior
(narrow-class/narrow-layout declared but read by no backend);
conditions/state; a fifth relationship type (`beside`, `opens`); native
execution of anything but `say`. Each is evidence-gated in BLOCKERS.md,
not merely missing.

## Mission 48 - Character-based prefix completion (P1#1 investigation)

**Scope.** Candidate P1#1: whether engine-side prefix narrowing/ranking of
completion items is actually needed, or whether VS Code's client-side
filtering already yields the right result. Exercise the real editor path
(`make h` -> header placement, `page t`, `card-1 t`), record evidence, and
recommend the smallest justified change (if any). No code changes.

**How the real path works today.**

- The extension registers `provideCompletionItems` with trigger chars =
  space + every ASCII letter (`editor/vscode-ine/extension.js:17-20`), so
  completion fires on *every* keystroke, not only after a space. The
  "suggestions appear while typing" property already holds.
- The engine answers each query with the FULL list for the context, and
  records the partial prefix only inside `context` metadata — it never
  narrows or ranks by the partial (`_items` in autocomplete.py returns
  the whole `makeable()`/`suggest(kind)`/`parents(kind)` list). This is
  intentional: the dictionary supplies vocabulary, not ranking.
- VS Code then filters and ranks the returned list against the word under
  the cursor (the item range defaults to the current word range). Prefix
  matches rank first; non-matches are faded but still reachable.

**Evidence (live engine responses, full context lists).**

- `make h` / `make he` -> kind context, all 13 makeable kinds
  (banner, button, card, card-group, container, footer, header, image,
  logo, navigation, page, section, ...). VS Code filters to the `h`
  prefix -> `header` ranks at the top; the mission's "header/hero
  placement" premise is slightly off: **hero is not a makeable kind**
  (hero.ine writes `make hero banner`; header is the h-prefix kind).
- `page t` / `header t` -> properties context, full `suggest(kind)` list
  (page: 11 items incl. text/title; header: 8 items). VS Code ranks the
  `t`-prefix items (`text`, `title`) among them.
- `card-1 t` on a single line -> 0 items, because `resolve_kind("card-1")`
  needs the `make 2 card` line above it. In a real editor session the
  buffer is multi-line and the declaration resolves (locked by Mission 46
  `BufferContextTests`); same-line is an artificial one-shot case.
- List sizes are tiny (<= 13) and the payload cost is trivial — the
  Mission 28 stress test measured 300 subprocess queries in 0.18 s. A
  narrower payload buys nothing measurable.

**Real friction found (one item).** Statement-start keyword completion:
the kind context returns only dictionary *kinds*, and none of the 13
starts with `m`, so typing `m`/`ma` at line start opens a popup with no
matching item and the `make` keyword is never offered (the candidate's
"`m` -> make ranked high / `make` stays top exact match" ideal is unmet).
This is a *syntax-keyword* completion feature (offer `make` and arguably
`say`/`group` at line start), not dictionary prefix ranking — it touches
the "engine is a pure proxy" boundary, so it is a commander-scope decision,
not an autonomous implementation.

**Recommendation (no-code-change verdict).** Engine-side prefix
narrowing/ranking is NOT needed: VS Code client-side filtering already
ranks `make h` -> header and `page t` -> text/title correctly, lists are
small, and per-keystroke queries already work. Leave the engine returning
full context lists. The ONLY justified change would be statement-start
keyword items (`make`/`say`/`group`) — optional, commander-scoped, and
independent of Prefix completion. Recorded; nothing implemented.

## Mission 54 - Pricing page experiment (link / navigation evidence)

**Scope.** Write a realistic three-tier pricing page with ONLY the declared
vocabulary (page, header, logo, navigation, container, banner, card-group,
card, section, button, footer, title/text) to collect the real-program
evidence the BLOCKED `link` mission (PLAN 61) and the navigation claims are
gated on. Program: `.agent/experiments/pricing.ine`.

**What the program expresses (all dictionary-guided).** One page with a
header (logo + navigation), a container holding a banner and a card-group
of exactly three pricing cards (`make 3 card` + `group tiers`), a section
CTA, and a footer. It lexes, parses, analyzes, and renders to HTML (the
`ExperimentsRenderTests` guard covers it automatically; a manual render
contains the page title, all three tier names, and the CTA text).

**Every line the vocabulary could NOT guide (the finding).** Each is a
real friction a pricing page actually hits:

1. **Clickable navigation (the BLOCKED `link` reward).** `make navigation`
   / `navigation inside header` renders an empty strip. The `navigation`
   kind declares NO `contains` members (checked: `members("navigation")`
   is empty; only `link-style`/`link-spacing`/`order`/`orientation` and the
   universal `title`/`text` properties), and no dictionary kind carries a
   destination/URL. "Home / Pricing / Docs" targets simply cannot be
   expressed — there is nowhere to attach them and nothing to click.
2. **A link can only be faked in `text`.** The single reachable CTA
   statement is `pick text "View all plans at example.com/pricing"` — a
   bare display string. Nothing makes that text clickable and nothing gives
   it a destination. line-for-line:
   - `pick text "..."` — the only place a destination can even appear, and
     only inside quoted display text.
   - no statement exists that could carry a URL as a *value* (no `href` /
     `link`-style property on button or any kind).
3. **Per-tier prices and feature lists are untyped.** Each pricing card has
   `title` + ONE `text` string. The per-tier price ("$29/month") is fused
   into the text line, and the tier's features ("unlimited projects, …")
   can only be one comma-joined string — there is no list value, no numeric
   value, no per-item line. (Converges with Missions 19-21: no
   numeric/boolean/list values.)
4. **No per-card call-to-action.** A `button` belongs inside a `section`
   only, and a `section` belongs inside the page — so a "Choose plan"
   button cannot sit inside a pricing card (`button inside card` is an
   undeclared containment pair, and a section cannot be placed inside a
   card-group). One shared section-level CTA is the only structurally valid
   shape.
5. **No hierarchy/badge.** An "Enterprise — custom" card can't express a
   "Most popular" badge, a separate price line, or a "for teams" subtitle;
   only `title` and one `text`.

**Recommendation for the commander decision (feeds PLAN 61).** The evidence
narrows the link design: a *navigation* with clickable targets needs (a) a
member statement to put items under `navigation` and (b) a destination value
on each item. The smallest natural representation to weigh in Mission 60 is
a `link`-style member with a destination property (e.g. a `link` kind
contained by navigation carrying a `text` + destination value), not a
property on arbitrary kinds — but the syntax decision (kind vs property) and
the backend emission stay commander/WORKBOOK-scoped, exactly as BLOCKERS
item 61 records.

**Status.** Evidence recorded; program builds and renders. No code changes.

## Mission 55 - Settings panel experiment (styling evidence)

**Scope.** Write a settings-style panel (labeled groups, status rows, an
action row) with ONLY the declared vocabulary (page, header, logo,
container, card-group, card, section, button, footer, title/text).
Program: `.agent/experiments/settings.ine`.

**What the program expresses (all dictionary-guided).** One page with a
header (logo), a container holding two labeled card-groups of four setting
rows (`make 4 card` + two `group` splits), a page-level action section with
a save button, a status section, and a footer. It lexes, parses, analyzes,
and renders: the output contains all four setting rows, the save button,
and the status line (auto-guarded by `ExperimentsRenderTests`).

**Every inexpressible point (the finding).** Each is real friction a
settings panel actually hits:

1. **A setting row is one undifferentiated `title` + `text` card.** The
   dictionary's only way to group rows inside content is container ->
   card-group -> card. There is no toggle/checkbox/select/label/row kind,
   no boolean value, no enabled/disabled state — "Enabled" / "Off" are
   display strings, not data. (Converges with Missions 19-21 and 54: no
   typed values.)
2. **`make N kind` numbering restarts per statement.** A second `make 2 card`
   on the page re-offers card-1/card-2 and collides; the panel must use ONE
   `make 4 card` then split with `group`. For any page larger than one small
   group, numbered-instance naming is unstable and error-prone — a genuine
   naming gap in the core, not a styling concern.
3. **No state/status shape.** The status line is plain text; there is no
   indicator value, no busy/idle/error state, nothing machine-readable.
4. **No risk emphasis.** A risky setting ("Product updates: Off") cannot be
   emphasized; no color/emphasis property exists anywhere.
5. **The action row is forced to page level.** `button` is contained only by
   `section`, and `section` only by `page` — a save button cannot sit inside
   a settings card-group, so the CTA must live in a separate page-level
   section.
6. **No disabled button state.** The save button cannot be disabled or
   styled as destructive; no such property exists.

**Recommendation for the CSS missions (56-58).** Items 3, 4, and 6 are
exactly the "HOW" concerns the commander's review flagged: they should live
in a theme/template import layer, not the language's syntax. The one true
*core* gap here is item 2 (stable, scoped instance names), which is a
values/naming fix — the same seam the typed-value evidence already points
at — not a styling one.

## Mission 56 - Stylable-surface audit

**Scope.** Exhaustive inventory of what a `.ine` user can and cannot set
today: every property that reaches a renderer, every declared-but-unread
physical hint, and every style the backends hard-code. Feeds BLOCKED 58/59.

**What reaches a renderer today (inventory, verified against
`src/ine/backend_html.py` and `src/ine/backend_visual.py` line-by-line):**
- `element` (every kind) — read by the HTML backend only. backend_html
  `_element_for_kind` maps kind -> tag (page/header/nav/footer/...).
  The visual backend never consults `element`; it hand-builds per-kind
  widgets.
- `layout` (`"row"` on card-group; everything else defaults to stack) —
  read by BOTH backends. HTML: `display:flex;gap:20px` (backend_html
  `_open_tag`); visual: `_layout_of` side-by-side packing. It is the ONLY
  physical property that visibly works today.
- `position` (`"bottom"` on footer) — read by the VISUAL backend only
  (`_position_of`, pins the bar to the bottom edge). backend_html never
  reads `position`; a footer renders in normal flow (verified: footer is
  the page's last child, so the visual difference is incidental).
- Universal `title`/`text` (quoted strings) — HTML renders page title as
  `<title>`+`<h1>`, leaf/section titles as `<h3>`, text as raw content;
  visual renders labels.
- Totally hard-coded, settable by NOTHING:
  - HTML: `flex:1` on row children, `gap:20px`, `class` names, the `<h1>`/
    `<h3>` hierarchy, no stylesheet, no colors, no `<meta viewport>`.
  - Visual: `KIND_COLORS`/`KIND_TEXT_COLORS` Python dicts, Arial fonts
    (10-22pt), the 800x600 window, padx/pady values (4-48), card
    `highlightthickness=1` border.

**Declared-but-unread physical hints (dictionary vs backend, each file):**
- `card.json` defaults: `padding` (comfortable), `border` (subtle),
  `corner-radius` (slight) — read by NO backend. (`implementation.guess`
  even suggests the literal CSS: "border: 1px solid light",
  "border-radius: 6-10px", "padding: 20px".)
- `banner.json` defaults: `text-alignment` (center), `padding` (generous),
  `separation` — read by NO backend.
- `navigation.json` defaults: `orientation`, `link-spacing`, `link-style`,
  `order` — read by NO backend (a nav renders as an empty `<nav>`).
- `card-group.json` defaults: `fallback`, `narrow-layout` ("stack
  members"), `narrow-class` ("viewport.width == narrow") — the `narrow-*`
  responsive vocabulary is read by NO backend; `layout: row` IS read.
- `logo.json` defaults: `interactive` (false) — unread (also documents
  "not settable yet: Ine has no boolean values").
- `footer.json` `position: bottom` — visual-only (see above).

**Smallest backend-only change that makes the FIRST property honest.**
Mission 23's recommendation holds and the Mission 57 probe confirms it:
wire `card`'s three default hints and `banner`'s `padding`/`text-alignment`
into inline styles in `backend_html.py` ONLY — a single per-kind style map
in `_open_tag` (~5 lines), zero parser/semantic/dictionary changes. That is
the precise, reviewable surface for BLOCKED mission 58.

**Classification.** Everything unread is, without exception, the "HOW"
layer the commander wants out of the language: spacing, radius, borders,
alignment, and responsive collapse. The audit confirms the dictionary
should stay a *semantic* vocabulary; the physical hints are backend-flavored
metadata that one honest backend change (58) will either legitimize or
reveal as removable.

## Mission 57 - CSS-intent-to-HTML mapping proposal

**Scope.** Produce the concrete mapping from the already-declared physical
hints to HTML inline CSS and capture a literal before/after diff by running
the golden examples + evidence experiments through a TEMPORARY patched copy
of `backend_html.py` (`.tmp/backend_html_patched.py`) — the in-tree module
was never modified.

**Mapping (hint -> exact CSS fragment, from the dictionary's own
`defaults` + `implementation.guess`):**
- `card.padding` comfortable -> `padding:20px`
- `card.border` subtle -> `border:1px solid #e0e0e0`
- `card.corner-radius` slight -> `border-radius:8px`
- `banner.padding` generous -> `padding:3rem`
- `banner.text-alignment` center -> `text-align:center`
No other hint is proposed for mission 58's scope (navigation/card-group
hints stay out until separate decisions).

**Probe results (`.tmp/m57_probe.py`, diffs in `.tmp/m57_diffs.txt`):**
- In-tree build vs every golden: **byte-identical**
  (`tests/expected/{hello,topbar,hero,cards}.html` — GOLDENS_HONORED).
- Patched probe diffs — exactly the reviewable contract 58 will produce:
  - `hello`, `topbar`: no diff (no card or banner element).
  - `hero`: banner `div class="hero"` gains
    `style="padding:3rem;text-align:center;flex:1"`.
  - `cards`: banner gains the style; each card `article` gains
    `style="flex:1;padding:20px;border:1px solid #e0e0e0;border-radius:8px;flex:1"`.
  - `settings`: all four setting cards gain the card style.
  - `pricing`: banner + all three tier cards gain their styles.

**Quirk the probe exposed (must be part of the 58 contract).** A card
inside a `layout: row` card-group receives `flex:1` from the parent-row
rule AND the style column, producing a duplicate `...;flex:1`. The real
implementation must MERGE into the existing `style` attribute (dedupe
`flex:1`), not append blindly — otherwise the goldens change twice.

**Scope statement for BLOCKED mission 58.** First property only: the five
hint->CSS fragments above, inline styles, `backend_html.py` only, goldens
updated deliberately once the commander accepts this mapping scope.

## Mission 60 - Link semantics investigation

**Scope.** What is a link in Ine: a kind (a `link` entity inside
navigation) or a property (`<name> link "url"`)? Scan WORKBOOK for declared
link/navigation intent, reconcile with the unused `link` terminology
(BLOCKERS: dead vocabulary) and Mission 54's pricing evidence, and propose
the smallest natural representation.

**WORKBOOK intent (verified).** The homepage slice (Session 16/§28) is
page, header, logo, navigation; navigation's dictionary meaning is "An
ordered set of links to destinations in the software." Its `element` is
`nav`, its `implementation.guess` is "nav with anchor elements", and its
defaults describe link *styling* (`orientation`, `link-spacing`,
`link-style`, `order`) — but it declares NO `contains`, so a user has no
place to put a link and no way to attach a destination (Mission 54: a nav
renders as an empty strip; a CTA can only fake a link inside `text`).

**Candidate representations, with evidence for/against:**
- **(a) A `link` KIND contained by navigation.** `make link home` /
  `home inside navigation` / `home text "Home"` / `home href "index.html"`.
  - For: matches navigation's own meaning ("ordered set of links"); matches
    Mission 54's recommendation; the parser already accepts any property
    name with a quoted-string value (`parser._parse_property` — verified,
    no whitelist), so **zero language/parser/semantic changes** are
    needed — only a `dictionary/link.json` (element "a") and a small
    backend anchor-emission branch. Fits `contains` (structure) + Value on
    Property (text) inside the four-construct spine exactly.
  - Against: none of the four golden examples need it yet; a `link` kind
    outside navigation (a lone CTA) still needs `button`-level reach (but
    buttons can keep playing that role via the same href property).
- **(b) A `link` PROPERTY on arbitrary kinds** (`navigation link "..."`,
  `pick link "url"`).
  - For: smallest surface (one property).
  - Against: a URL is not a single-value concept in a nav ("Home", "Docs"
    need BOTH a label and a destination — one string can't carry both
    cleanly); the four-construct spine ties VALUE to a Property on an
    ENTITY, so a property-based nav forces N properties per item with no
    per-item entity; contradicts navigation's meaning of an *ordered set*.
- **(c) Property on `button`-style kinds only** (`pick link "url"`).
  - For: gives CTAs a destination without a new kind.
  - Against: still leaves *navigation* (the name says "links") with no
    items; the nav remains an empty strip — the exact friction Mission 54
    measured.

**Recommendation (for the commander decision gating 61).** Adopt
representation (a): a `link` kind contained by `navigation`, carrying the
universal `text` for the label and a destination property (dictionary
declares `href` with a `text` value shape, `"url"` hint). Exact markup a
`link` renders to: `<a class="<id>" href="<value>">label</a>`; navigation
emits its members as `<a>` inside the existing `<nav>`. Smallest backend
change: in `backend_html.py`, one per-kind branch (or the existing
leaf-render path armed by `element: a`) + one `src="href"` attribute from
the model property — nothing in the parser or semantic layer changes.

**Pending (keeps 61 BLOCKED).** A WORKBOOK or commander SYNTAX decision
(kind vs property), the Session 25 freeze lift for `backend_html.py`, and
acceptance of Missions 54/60 evidence. This finding deliberately does NOT
edit `dictionary/*.json`, parser, semantic, or any backend.

## Mission 62 - Dead-vocabulary kinds (`link`, `title`, `heading`)

**Scope.** Reconcile why `link`, standalone `title`, and standalone
`heading` are claimed as "dead vocabulary" (BLOCKERS Session 37) when they
appear in zero real programs.

**Finding (verified against the shipped dictionary and git history).** Two
of the three were never dictionary terms at all:
- `dictionary/link.json` and `dictionary/heading.json` NEVER existed
  (git log across all refs is empty for both). The current `makeable()`
  list is 13 kinds: banner, button, card, card-group, container, footer,
  header, image, logo, navigation, page, section, title.
- `link` and `heading` are SEMANTIC BUCKET names, not terms:
  `navigation.json` has `"kind": "link-collection"` and `title.json` has
  `"kind": "heading"`. The Session 37 record conflated a kind's
  `kind`-bucket with a declared vocabulary term.
- Exactly ONE declared term matches the claim: `title` (title.json, element
  `h3`, meaning "A heading or name, for a page, section, or card"). It is
  used in zero programs as a *kind* (`make title` appears nowhere — grep of
  all examples/experiments) but the `title` PROPERTY is used everywhere
  (universal.json declares `title`/`text` on every regular kind).

**Record correction (append-only, original preserved).** The BLOCKERS
bullet is amended with a mission-62 remark (see BLOCKERS.md) so future
workers don't chase a nonexistent `link`/`heading` vocabulary.

**Recommendation (no vocabulary removed, no code change).**
1. Keep `title` declared — it is the rendering contract for `<h3>` headings
   and the universal property model, and its term/kind distinction is
   legitimate. Optionally sharpen its `meaning` to note standalone `make
   title` is for a page/section name node and that headings normally come
   from the universal `title` property — do NOT gate or remove without the
   commander.
2. Treat `link`/`heading` as NON-KINDS unless link navigation (Mission 60)
   lands — at which point only a `link` term would be added, never `heading`.

## Mission 71 — Field kinds evidence experiment

Program: `.agent/experiments/contact-form.ine` (builds clean; guarded by
`ExperimentsRenderTests` + `VocabularyCoverageTests`). A realistic contact
form — name, email, topic, message, consent checkboxes, submit — written
with ONLY the declared vocabulary. It reduces to a container of three
card-groups (6 cards total) plus a page-level submit section: cards holding
`title` (the field label) and `text` (the literal display string), and one
`button`. That is the entire expressible surface for a form.

**Where the vocabulary fails (evidence, not requests).**
1. **No field kinds at all.** None of `input`, `textarea`, `select`,
   `checkbox`, `radio`, `label`, `field`, `form` is declared (0 of 8). The
   closest carrier is a `card` whose `text` is *display content*: there is no
   value/placeholder distinction, no editable value, and no way to attach the
   field to the submit. Mission 20's finding is unchanged at the vocabulary
   level; this experiment adds the *structure* the decision must cover.
2. **No multi-line control.** The message body is a single string
   (`card-4 text "How can we help?"`) — no rows/resize, no character count.
3. **No option set.** The `Topic` card can hold one literal string; the
   alternatives (Support, Sales) cannot be listed. This is exactly the
   missing first `choice` value (PLAN item 7 / BLOCKERS): a select or radio
   group is the real-program demand for `choice`.
4. **No boolean/state.** Consent checkboxes are `text "Unchecked"` — display
   text, not a checked/unchecked value the runtime can toggle. Same missing
   boolean as `button.interactive` ("not settable yet: Ine has no boolean
   values") and `card-group layout`'s missing choice.
5. **No label-for association.** A field label is just a card `title`; there
   is no relation binding a label to the field it names, and no focus order.
6. **No submit/interaction semantics.** No required/optional, no validation
   or error surface, no disabled/enabled submit, no loading, and no
   navigation target for the button.
7. **Property/renderer mismatch surfaced.** The dictionary suggests
   `button label`, but renderers surface `text` — writing a form makes this
   inconsistency concrete (`send text "Send message"` is what actually
   renders). Worth a small reconcile in the button entry (its own item).
8. **Grouping forces card-groups.** Cards can only sit inside a `card-group`,
   and a container only contains card-groups (or banners), so a form's field
   rows are one card-group per row and a single field still needs a
   one-member card-group. Structural fit is awkward but works.

**Minimal field-set assessment (the six candidates named by the mission).**
- *input / textarea*: both are needed and clearly distinct (single-line vs
  multi-line). A `field` surface kind with a `mode` property would compress
  them, but the two behaviours are different enough (validation, sizing) that
  a base `field` + typed `mode` is the cleaner shape to weigh.
- *select*: expresses a `choice` value — couples the field vocabulary to the
  typed-value decision (item 7), so it cannot land before `choice` does.
- *checkbox / radio*: both express a boolean/selected value; radio additionally
  needs a named option group (a `choice` with one selection). These share the
  boolean gap, so they belong to the same typed-value tier.
- *label*: not a kind but an association — the smallest honest form is a
  `label` property on a field (the field itself carries its label), avoiding a
  new relation construct.

**Dependency note for the commander.** The field set splits into two tiers:
(a) *control kinds that need no new value type* — input, textarea (and a
`label` property) — implementable with the current text-only value model once
a field/control vocabulary is approved; and (b) *controls that require the
typed-value decision first* — select, radio (choice) and checkbox (boolean),
which cannot land until item 7's first `choice` and a boolean exist. No
syntax, semantics, or dictionary change was made; this is evidence only.

## Mission 75 — State/conditions evidence experiment (dynamic UI)

Program: `.agent/experiments/dynamic-ui.ine` (builds clean to HTML; guarded
by `ExperimentsRenderTests` + `VocabularyCoverageTests`). A deploy console
that *tries* to express state change — expand/collapse panels, conditional
layout, a toggle button, collapsible groups — written with ONLY declared
vocabulary. Static intent works; every dynamic intent reduces to text.

**Where state fails (evidence, not requests).**
1. **No visible/expanded bit.** `details` ("Expanded logs - hidden until you
   expand") renders permanently with all its content; a collapsed panel
   cannot be expressed, so an expand/collapse toggle has no operand. The
   summary's "2 of 6 shown" is author-baked text; the count of hidden rows
   cannot be derived or changed.
2. **No conditions.** `primary` and `secondary` containers always render in
   sequence; there is no "if X, show secondary / stack on primary"
   expression. The only conditional any backend could honor today is
   Mission 59's BLOCKED single narrow media rule — and it is frozen, by
   design (conditions/state stay UNDECIDED).
3. **Buttons cannot change.** "Expand all" / "Pause auto-refresh" render but
   can never flip anything: no disabled/enabled flag (button.interactive =
   "not settable yet: Ine has no boolean values", also a Mission 72/74
   finding), no pressed state, no action trigger. A button is a static,
   inert element in every renderer.
4. **`group` is compile-time static.** `layers_rows` names a fixed set of
   already-made entities (`layer-1/2/3`) set once at authoring time; it can
   never expand, collapse, reorder, or animate. "collapsed" on the group is
   display text with no runtime meaning.
5. **Nothing recomputes.** No dynamic value exists in the pipeline — the
   runtime has no state to bind, no clock, no user input, no events. State
   change would be a **fifth construct** (WORKBOOK §25 gate), which this
   experiment confirms is not merely syntax: it is a semantic + runtime +
   backend capability that does not exist at any layer.

**Assessment for the conditions/state decision (BLOCKERS).**
- The dashboard/settings/metrics experiments show "state" in three distinct
  needs: (a) *display state that renders differently even without input*
  (enabled/disabled/expanded) — a value + style read, matches the boolean/
  typed-value+tier and styling tracks, NOT a new construct; (b) *collection
  dynamics* (show/hide/reorder known members) — needs a runtime binding that
  nothing in the pipeline has; (c) *live data* — needs an execution/runtime
  story beyond rendering. Only (a) is reachable today (via booleans +
  backend reads once the typed-value decision lands). (b)/(c) are full fifth
  constructs and stay UNDECIDED.
- No syntax, semantics, dictionary, or backend change was made; evidence
  only. PLAN item 75 tagged `DONE`; next EXECUTABLE = item 76 (native
  target expansion research).

## Mission 74 — Interactive controls investigation

Research-only; no code changed. Question: what is the minimal interaction
model for Ine forms/dashboards — which of submit / change / focus /
validation / error-state map to the existing `button` concept and which need
new constructs? Evidence base: the real-program experiments already in this
file (Missions 19/20 dashboard+form, 54 pricing, 55 settings, 71
contact-form, 72 metrics-dashboard, 73 data-table) plus the dictionary
entries that document interaction today.

**What interaction vocabulary is declared (and actually used).**
1. `button` is the only control kind (`kind: "control"`, `element:
   "button"`). Its declared defaults record the admission: `interactive` =
   "activation behavior - not settable yet: Ine has no boolean values".
2. `interactive` is also declared as a default on `logo` (see BLOCKERS /
   Mission 21 reconciliation) and is read by no backend — the only
   "interaction" metadata is a documented gap.
3. `navigation` declares `link-spacing`/`link-style`/`order` layout hints;
   no click target exists (BLOCKED item 61, `link`).
4. Everything interaction-shaped in real programs is fakery. In contact-form
   (71): a submit `button` that renders but fires nothing; consent "flags" as
   `text "Unchecked"`; no field association. In metrics-dashboard (72):
   STATE is display text. In data-table (73): `sort` button that connects to
   no column. In pricing (54): CTAs with no destination (link gap).

**The interaction concepts in the mission, mapped to what exists.**
- *submit* — today it is `button text "Send"` in a section; there is no
  action, no success/failure surface, no state change. Submission cannot even
  be *declared*, because declaring it needs semantics ("when clicked, do
  X") — a trigger construct that does not exist.
- *change* — a control reflecting a new value. There are no controls with
  values (fields don't exist, Mission 71; toggles don't exist, Mission 72),
  so change has no operand. It is gated behind the field + typed-value
  decisions.
- *focus* — keyboard/focus order exists only implicitly (HTML backend emits
  real `<button>` elements, so browsers apply native tab order); Ine has no
  focus vocabulary and no access to it.
- *validation* — nothing validates, by design (dictionary is advisory).
  Validation lives entirely at the renderer/user level, if at all. Needs
  value types first (a validated email is only meaningful on a field with a
  typed value).
- *error state* — no way to attach error/status text or emphasize a failing
  element (no state colors, no boolean-conditional class, no status value).
  The closest is a `section text "..."` prose line (settings, Mission 55) —
  content, not state.

**Finding: interaction has no first-class surface, and the smallest honest
model is a *trigger*, not a general event system.** The one universally
demonstrated need across all six experiments is "an element that, when
activated, does something" — the submit button, the sort button, the CTA.
That is a *trigger*: activation + a behavior reference. Everything else
(change/focus/validation/error-state) is gated on constructs that do not
exist yet (fields, booleans, typed values) and should NOT be designed ahead
of that evidence.

**Recommended minimal interaction model (for the commander/WORKBOOK
decision).**
1. **Trigger on a button, not a new construct.** Add a declared interaction
   property (e.g. `action`) whose value references a target — but note this
   is itself evidence-gated: `button.interactive` records "no boolean
   values", so even the *presence* of an action is currently inexpressible
   as a flag. The boolean (or first `choice`) decision (item 7 / BLOCKERS)
   is the true precondition for any trigger semantics.
2. **Defer event kinds (change/focus/submit lifecycle) entirely.** No real
   program needs them yet; writing them early invents semantics. Once fields
   (tier-a, Mission 71) and the typed-value number/boolean tiers (Mission
   72) land, `change`/`focus` get operands and should be revisited with
   real programs.
3. **Status is a value problem, not an event problem.** The dashboards need
   capitalized "Enabled/Disabled/Degraded" state and error emphasis; that is
   a boolean/status VALUE + a styling read, not an interaction model. It
   belongs on the typed-value (72) and styling (56-58) tracks, not here.
4. **Sort/CTA "buttons that do nothing" are the same symptom twice**
   (pricing CTA, data-table sort) — both are triggers pointing at a missing
   `link` target (BLOCKED item 61) or a missing action. Until either lands,
   buttons are decorative in every renderer, which is the honest status.

**Verification.** No code changed; no new tests (research-only). All
statements trace to dictionary entries (button.json `interactive` default),
the shipped dictionary members (section→button), and the experiments'
recorded `vocab gap:` lines (NOTES Missions 19/20/54/55/71/72/73). This
finding feeds the BLOCKED `interaction semantics` evidence gates and, once
buttons/fields/values exist, the interaction-model decision.

## Mission 73 — Data table evidence experiment

Program: `.agent/experiments/data-table.ine` (builds clean to HTML; guarded
by `ExperimentsRenderTests` + `VocabularyCoverageTests`). A deployments
table — header-shaped rows, cell values, and a sort affordance — written
with ONLY the declared vocabulary. It reduces to a card-group of cards whose
`title` carries the row's "column headers" and whose `text` carries the row's
"cells" as a single pipe-delimited string; the "table" renders as stacked
articles, never a grid.

**Where the table fails (evidence, not requests).**
1. **No table/row/cell kinds.** None of `table`, `row`, `cell`, `column`,
   `header` is declared. A row is a `card`; the row's structure can only be
   flattened: headers into the `title` string (`"Service | Version | Status
   | Region"`), cells into the `text` string (`"api | v2.14 | live |
   us-east-1"`). The separator is a source-text convention; nothing renders
   as aligned columns.
2. **No column identity.** A cell value cannot be referenced or formatted
   separately from the row string — no `row-1 status` property, no way to
   say "this value is the status of that row"; the whole row is one opaque
   string. The strength of a table is addressing a cell; here a cell is
   unreachable.
3. **No header/data distinction.** `title` doubles as the header row on the
   first card and as a value on others; there is no way to mark a row as a
   header, so skip-a-header semantics, sticky headers, or scope semantics
   are inexpressible.
4. **No sorting/column semantics.** The sort button (`Sort by version`)
   renders but connects to nothing: no column reference, no order pair, no
   interaction model (the same gap Mission 74 will document). Sorting cannot
   be expressed, so it cannot be reordered or serialized.
5. **Structural workaround asymmetries.** Rows sit only inside a card-group
   inside a container, so a table is a container → card-group → N cards — no
   horizontal headings row above the data rows, no footer/summary row, no
   row-span/col-span. Multiplicity numbering restarts per statement (Mission
   55/72 collision reproduced conceptually): building 6 rows requires `make N
   card` plus explicit names or a collision.
6. **Formatting limitation vs Mission 72.** Even where a cell "sorts" as a
   chapter of a string, values are text: numeric cells (`998`) cannot be
   right-aligned, locale-formatted, or compared; the same typed-value gap
   from Mission 72 lands on the column axis.

**Assessment for the table decision (BLOCKERS: chart/table kinds).**
- *table* can be approximated TODAY only as a display convention (the
  documented card-group workaround) — structurally it is rows of parallel
  cards, and a reasonable near-term representation is a declared `table`
  kind that contains `row` cards with per-cell properties (a row = card whose
  `title` is the primary cell + declared `cell-*` properties or a nested
  value list). It needs NO new value type for plain text cells, but column
  identity wants a per-cell property naming, and sorting/formatting wants
  typed values (Mission 72's number tier) + interaction semantics
  (Mission 74). It therefore splits across the same two tiers as fields:
  structural `table`/`row` can land on the text-value model; column
  sorting/formatting is gated on typed values + interaction.
- No syntax, semantics, dictionary, or backend change was made; evidence
  only, feeding the chart/table evidence gate.

## Mission 72 — Typed values experiment (metrics dashboard)

Program: `.agent/experiments/metrics-dashboard.ine` (builds clean to HTML;
guarded by `ExperimentsRenderTests` + `VocabularyCoverageTests`). An
operations dashboard — revenue/uptime/workload/queue KPIs, a status panel,
a deploy-timestamp panel, a footer sync time — written with ONLY the declared
vocabulary. The pipeline already lexes/parses numeric literals as NUMBER
tokens and stores real `int`/`float` values in the semantic model, and the
HTML backend prints them through `str()`. That is the whole numeric story
today; everything else is a string.

**Where typed values fail (evidence, not requests).**
1. **No number type / no formatting intent.** `card-1 text 1234567.89`
   renders exactly `1234567.89` — no thousands separator, no currency prefix,
   no decimal-count control, no percent sign. `99.98` (a percentage) and `42`
   (an integer count) render identically to their literals; the renderer
   cannot append "%" or "$" because the *meaning* of a number is never
   carried. `value_shape("card","text")` is `"text"`, so the editor's value
   completion offers a quoted-string snippet even for a numeric intent. All
   formatting must be pre-baked into the source as strings.
2. **Formatting-vs-value coupling.** `card-4 text "0 of 12"` is a
   concatenated string ratio: not sortable, not graphed, not differentially
   formatted. A typed pair (0, 12) would render and compute; a string only
   displays. This is the concrete "strings fall short" case — the value's
   structure is lost at authoring time.
3. **No boolean.** Status rows are `text "enabled"` / `"disabled"` /
   `"degraded"` — display strings, not a truth value. Nothing can toggle,
   no state color/icon derives, and no backend can branch on a given value.
   This is the same gap `button.interactive` / `logo.interactive` already
   document ("not settable yet: Ine has no boolean values").
4. **No date/timestamp.** Deploy times are literal strings
   (`"2026-09-17 12:40 UTC"`): no "3h ago" relative render, no sortable
   comparison, no timezone math, no validation (a typo is syntactically
   invisible). The footer's "Last synced 2 minutes ago" is baked at
   authoring time; a runtime cannot recompute it.
5. **Multiplicity collision again (bonus, already recorded).** The second
   `make N card` batch after `make 4 card` collides on card-1..card-N (Mission
   55 finding reproduced), so the status/timestamp panels used explicit
   names. Confirms the existing gap; no new decision.

**Assessment for the type-system decision (item 7 / BLOCKERS).** The three
candidate types split cleanly by how much they need:
- *number* — the pipeline already carries `int`/`float` values end to end.
  The smallest honest step is a dictionary-level value shape (e.g. a
  `"number"` shape w/ optional format) plus a backend formatting read;
  grammar/parser/semantic already accept numeric literals. Lowest cost.
- *boolean* — needs a `true`/`false` literal (lexer/parser) OR reusing a
  two-term `choice`; either way it finally makes `interactive` settable. The
  `choice`-first path was already recommended (Mission 7).
- *date* — highest cost: needs a parseable literal, a canonical
  representation, and rendering rules; the demonstrable need here is display
  formatting, not arithmetic. Recommend classing date with the display-only
  tier (like styling), not the core type tier, until a program needs
  date math.

No syntax, semantics, dictionary, or backend change was made; this is
evidence only, feeding the typed-value decision gates.

## Mission 115 - Autonomous-worker request frugality (baseline metrics)

Commander-approved enforcement arc: cut Big Pickle / OpenCode model-request
waste on the free quota tier without reducing in-mission autonomy. Baseline
measured before any change (all LOCAL observed OpenCode counts, sqlite at
`C:\Users\A-pc\.local\share\opencode\opencode.db`, resolved via
`opencode db path`):

- 39 total `message` rows before a probe; a trivial `opencode run` added 6
  (one `role=assistant` message ≈ 1 model request), so a near-empty agent
  invocation costs ~5 requests in practice. Past real worker sessions logged
  ~4-5 messages each.
- This planning session itself consumed ~45 requests by the time the demo
  ran (`- usage start: 93 requests ... big-pickle=91`), confirming
  interactive sessions are the dominant cost, not the supervisor.
- Live demo run (blocked-only temp root, `--usage-warn-requests 1`):
  `- usage start: 93 ...` → `- usage [cycle 1]: +6` → warning at 95 →
  `- usage [cycle 2]: +4` → `- usage end: 103` → `- usage delta (run): +10`.
  Warning fired exactly once. NOTE: the demo's `BLOCKED` tag was eaten by a
  PowerShell here-string (backtick = escape char in PowerShell), so the item
  parsed as EXECUTABLE and launched two real opencode workers (~10 requests).
  PowerShell quirk to remember for future plan fixtures.
- Interpretation: the observed numbers are local OpenCode accounting, NOT
  the provider quota. Decision (recorded in DECISIONS.md-adjacent
  conversation): keep the tracking warn-only, re-evaluate a hard budget
  only after several real runs correlate observed usage with actual quota /
  rejection events.
## Mission 77 — visual theming

The visual (tkinter) backend now takes spacing from the dictionary's
machine-readable hints instead of hard-coded literals. Scope: `padding`
only. Colors are untouched and are the subject of the finding at the end
of this section.

### Named size -> pixel table (what the resolver derives)

`_hint_lengths` reads `style.properties.<name>.values[<the entry's defaults
hint word>]` and converts: the leading number is the vertical value, `rem`
reads as 16px, a bare number is already px, and `border-radius: 0` is 0.
Values with no length in them (`none`) yield nothing.

| kind | hint | hint word (default) | named sizes -> px |
| --- | --- | --- | --- |
| `card` | `padding` | `comfortable` | `compact` 0.75rem -> 12; `comfortable` 1.25rem -> 20; `generous` 2rem -> 32 |
| `card` | `corner-radius` | `slight` | `none` 0 -> 0; `slight` 10px -> 10; `round` 999px -> 999 |
| `card` | `border` | `subtle` | `subtle` "1px solid #e2e8f0" -> leading length 1; `none` -> nothing |
| `banner` | `padding` | `generous` | `compact` "1rem 1.5rem" -> (16, 24); `comfortable` "2rem 1.5rem" -> (32, 24); `generous` "3.5rem 1.5rem" -> (56, 24) |
| `navigation` | `link-spacing` | `even` | `tight` 0.75rem -> 12; `even` 1.5rem -> 24; `wide` 2.5rem -> 40 |
| `logo` | `style` (font-weight) | `strong` | not a length: 700 / 400 -> nothing |

Two shapes the table exposes:

- **`padding` is declared by `card` and `banner` only.** `header` and
  `footer` carry their padding as a literal `base` declaration
  (`padding: 0.75rem 1.5rem`, `padding: 1.25rem 1.5rem`) rather than as a
  named hint, and `logo`/`navigation` declare none at all. So a
  `_padding_of` that reads hints answers for two kinds and falls back for
  the rest -- the split is the dictionary's, not the backend's.
- **A single length is a CSS shorthand for all four sides**, so `card`
  (one length) resolves to (20, 20) while `banner` (two) resolves to
  (56, 24). The backend takes the second length as the horizontal value
  when there is one.

### What the prototype now reads from the dictionary

`src/ine/backend_visual.py` gains `_hint_lengths(kind, name)`,
`_hint_px(kind, name)` (leading length, or `None`) and
`_padding_of(model, entity_id)` -> `(pady, padx)`. `_render_entity`
replaces three literals with that call: the `logo` label (`padx=16,
pady=8` -> the fallback, unchanged), the `navigation` frame (`padx=16` ->
the horizontal value, unchanged) and the `banner` label (`pady=48,
padx=24` -> the dictionary's 56/24). Every other geometry value in the
renderer is left alone.

The fallback pair is `(8, 16)` -- the literals the logo branch packed with
before this change. It is used whenever the kind declares no `padding`
hint, which today is `header`, `footer`, `logo`, `navigation`, `page` and
every future kind until its entry learns to declare one.

Two deliberate limits, both wider than this mission:

- The resolver reads only the entry's **defaults hint word**. A value a
  program writes for one entity (`card-1 padding 32`) reaches HTML through
  `style_overrides()` but not yet through the visual backend.
- Only the leading two lengths of a hint are read. `border` is a width, a
  style and a colour in one string; a tkinter border needs the width and
  the colour separately, which is a change to the helper's shape, not to
  the dictionary.

### Finding: dictionary-driven color needs a new schema field

**The dictionary cannot express color today.** Every `style.properties`
entry is a value *table for an Ine property* -- `padding`, `border`,
`corner-radius`, `link-spacing` -- and the color-bearing CSS in the
dictionary is buried inside a shorthand that the backend cannot reach: the
only colour a dictionary entry carries is `#e2e8f0` inside
`card.border.values.subtle`, which is part of `border: 1px solid #e2e8f0`,
not a value of its own. `dictionary/README.md` ("Physical declarations")
already states the intent -- the `style` block is "the only place a colour,
a length, or any other CSS value is written down" -- and `KIND_COLORS` /
`KIND_TEXT_COLORS` at the top of `backend_visual.py` are exactly the
second vocabulary that sentence forbids. Closing that gap is a
dictionary-schema change (a new field, plus a `dictionary/README.md`
schema note), not a backend detail, so it is recorded here and left for
the commander. It also touches `.agent/DECISIONS.md`, where the colour
palette is UNDECIDED (see `dictionary/README.md`, "Provenance of the
values above", Session 42).

The field it would take: a **`colors` block on the entry**, sibling to
`style`, holding background and foreground as the same kind of named-hint
table the rest of the dictionary uses -- e.g.

```json
"colors": {
  "background": { "css": "background-color", "values": { "surface": "#ffffff", "muted": "#f0f0f0" } },
  "foreground": { "css": "color", "values": { "body": "#333333", "on-dark": "#ffffff" } },
  "defaults": { "background": "surface", "foreground": "body" }
}
```

so a kind declares *which* named colour it uses and the palette itself
lives in one place, swappable without touching an entry. The open
questions are the commander's: whether the palette is authored per kind or
in a single shared table the entries reference; whether `logo` and
`navigation` should keep "inherit from parent" as a declared word
(`"inherit"`) rather than as a Python `None`; and whether
`KIND_TEXT_COLORS`' light-on-dark pairs (`header`, `banner`, `footer`) are
pairs a kind declares together (`"on-dark"`) or two independent choices
that a designer can put into conflict. Until that is decided the renderer
keeps its own table, and `KIND_COLORS` is unchanged by this mission.

## Mission 78 — multi-backend consistency

Read-only audit of how the HTML backend (src/ine/backend_html.py) and the
visual backend (src/ine/backend_visual.py) render the SAME semantic model.
`semantic.Model` (src/ine/semantic.py:21-26) is the whole interface both
backends see: `entities`, `properties`, `relationships`, `groups`.
No source file changed by this mission.

### Behaviour table

| behaviour | HTML | Visual | verdict |
| --- | --- | --- | --- |
| children layout, `layout: row` | `_layout_for_kind` (:49) reads `layout`; a row parent emits `display:flex; gap:20px` and each child carries inline `flex:1` (`_attrs`:136-140) | `_layout_of` (:140-145) reads the same entry; `_pack_children` (:319-330) packs row children with `side="left"` | **intentional** — same declared intent, target-idiomatic implementation (flexbox vs pack side=LEFT); only `card-group` declares `row`, and both backends honor it. |
| `position: bottom` (footer) | not read anywhere — grep shows `backend_html.py` has no `position` handling; a footer renders in normal document flow like any sibling | `_position_of` (:148-153) reads it and `_pack_children` (:327-328) packs such a child `side=tk.BOTTOM`, pinning it to the window's bottom edge | **bug** — the dictionary declares `footer` `position: bottom`; HTML ignores the declared intent while Visual honors it, so one program renders differently per target. |
| per-entity written properties | `_written` (:110-115) collects them; `_attrs` (:126-144) turns them into an inline `style` via `style_overrides`; `title`/`text` also become h3/text content (`_render_children`:159-180) | `_render_entity` reads only `text` (:215) and `title` (:216) from `model.properties`; `_padding_of` (:123-137) reads dictionary DEFAULTS, never a value the program wrote | **bug** — a program writing `card-1 padding 32` changes the HTML output and is ignored by the visual window; recorded already as a "deliberate limit" in Mission 77's finding, but the divergence is real. |
| dictionary style hints | fully consumed: `_stylesheet` (:95-107) emits one `.kind` rule per used kind via `style_declarations`, inline overrides via `style_overrides` (:141); padding/border/corner-radius/link-spacing all paint | reads ONLY `padding` via `_hint_lengths`/`_padding_of`; `border`, `corner-radius`, `link-spacing` are never consumed; colors remain in `KIND_COLORS` — the second vocabulary Mission 77 flagged | **bug** — same dictionary, different coverage: HTML consumes the whole `style` block, Visual consumes one hint class. |

### Candidate follow-up missions (recorded, not implemented)

- HTML footer pin: read `position` in `backend_html.py` and emit the declared
  bottom placement; pin with a new golden (footer-bearing program) asserting
  the footer element's style carries the position, and the four existing
  goldens stay byte-identical.
- Visual written-value parity: `_padding_of` (and the visual renderer) honor
  entity-written property values like HTML `style_overrides` does; pin with a
  unit test (no window) asserting an entity that wrote `padding` resolves to
  its written value.
- Visual style-block parity: consume `corner-radius` and `border` width in
  the visual backend; pin with a unit test asserting the resolver reads the
  dictionary hint for those names. No window.

## Mission 79 — backend plugin contract

Read-only investigation of what a new backend (React, Flutter, …) would
have to touch today, and the minimum contract that removes that cost.
No source file changed by this mission.

### The five-stage pipeline each CLI path repeats

`_html` (via `build`, cli.py:17-34), `_native` (cli.py:110-117) and
`_visual` (cli.py:133-140) each run the identical head:

    lex(source) -> parse(tokens) -> analyze(statements) -> resolve(...) -> execute(...)

The divergence is the last step: HTML renders the MODEL to a `str` and writes
a file; native compiles the RESOLVED STATEMENTS to C and runs the exe; visual
shows the model in a tkinter window.

### The consumption asymmetry

| backend | entry point | consumes | line |
| --- | --- | --- | --- |
| `backend_html` | `render(model)` | the **model** | backend_html.py:56 |
| `backend_visual` | `render(model, title_override=None)` / `show(model)` | the **model** | backend_visual.py:181/333 |
| `backend_c` | `emit(statements)` | the resolved **statements** | backend_c.py:30, called from native.py:36 |

Two backends speak the model; the native one speaks an earlier stage. There
is no uniform stage input.

Arguments, returns, failure:

- HTML: `render(model)` — one required arg; returns `str`. No override hook.
- Visual: `render(model, title_override=None)` — optional override; returns a
  live `tk.Tk` widget (not a string).
- C: `emit(statements)` — returns C source `str` (pure).
- Failure: three UNRELATED exception types can be raised behind one command —
  `BackendError` (backend_html.py:35), `VisualError` (backend_visual.py:257),
  `NativeError` (native.py:18) — no shared base, which is why cli.py:86 names
  all three (plus the lexer/parser/semantic errors) in one except tuple.

### The proposed minimum contract

```python
class BackendError(Exception): ...          # one base replaces the three

@dataclass
class Result:
    content: object        # str (html / c source) or a live widget (visual)
    artifact: str | None = None   # output path when the backend wrote a file

BACKENDS: dict[str, Backend] = {}   # registry, keyed by backend name

def render(backend, stage_input) -> Result: ...   # one entry point per backend
```

The CLI then reduces to: pick `stage_input` (model or statements) from the
dictionary entry's declared consumption, call `BACKENDS[name].render(...)`,
and map `BackendError` to the error report. Nothing new is designed here —
this is the smallest shape that removes the asymmetry of step 2.

### What a new backend still costs under the contract

| edit a new backend needs today | removed by the contract? |
| --- | --- |
| a new argparse flag + an `if args.cooltarget:` branch (cli.py:81-85) | the branch/selection is removed; a user-facing flag is still required (that is how a target is chosen) |
| a module import (`from .backend_react import ...`) | **removed** — the module registers itself in `BACKENDS` by name |
| a new `_react(source)` stage function repeating the five-stage head | **removed** — a shared pipeline helper feeds the stage input; the backend implements only `render` |
| a new error class + a new entry in the cli.py:86 except tuple | **removed** — single `BackendError` base |
| the backend module, its tests and goldens, dictionary coverage | still required (that is the point of a new backend) |

### What this mission did NOT decide

Whether the contract is worth its migration cost. Adopting it touches
`cli.py`'s public flags and both existing backends (visual's live-widget
return and native's statements-input would both have to fit the uniform
shape), and that is an architecture decision for the commander, not an
engineering reflex. A scratch registry under `.tmp/backend-plugin-probe/`
was type-checked to confirm the shape compiles; it is scratch and not cited
as the location of any durable result.

## Mission 80 — dictionary format exposure

`ine --dict <kind>` now prints the full structured entry — the shaped body
`make <kind>` should surface, instead of the flat suggestion list.

**footer** prints: `footer (bar)`, `element: footer`, the meaning, the defaults
(`content-position: center`, `height: compact`, `position: bottom of page,
always`), the style block (`display: flex`, `padding: 1.25rem 1.5rem`,
`content-position` → css `justify-content`, values `center|left|right`),
`belongs inside: page`, and `implementation.html: footer element`.

**card-group** prints the responsiveness data item 83 will consume:
`narrow-layout: stack members` and `narrow-class: viewport.width == narrow`
both come from its `defaults` block, along with `layout: row`, `member-width:
equal`, `member-spacing: even` and `contains: card`.

**Field coverage across all 13 makeable kinds:** every entry carries `term`,
`kind`, `element`, `meaning` and `implementation`. Two structural variations
the printer already handles: (a) `style` may have a `base` list and a
`properties` map, either alone — bare kinds (button, card-group, container,
image, section, title) have only `properties` or neither, footer/header/logo/
navigation have a `base` list; (b) `defaults` is optional — `title` is the
only kind with no `defaults` block, so the printer skips it rather than
printing an empty map. No dictionary JSON schema was changed.

## Mission 81 — kind body templates

`make <kind>` completion now offers an editable starting-point body built
from the dictionary entry (`kind_snippet` in `src/ine/autocomplete.py`),
delivered as a VS Code snippet whose first default value is the initial
tabstop; item 81 index executed 1-5, tests green.

**Template shape.** Two line kinds, dictionary-only: (a) each declared
member (`defaults.contains`) becomes a `make <member>` line plus a
`<member> inside <kind>` line; (b) every style/default property becomes a
`<kind> <property> "<default>"` statement, the property value resolving
from `defaults` first, a style spec's own `value` key second (none declare
one today), else omitted — no fabricated values. The snippet leads with the
kind name so insertion follows a typed `make `; `$0` anchors the final
cursor, `${1:...}` the first default.

**footer:**
```
make footer
footer content-position "center"
footer height "compact"
footer position "bottom of page, always"
```

**card-group:**
```
make card-group
card-group layout "row"
card-group member-spacing "even"
card-group member-width "equal"
card-group narrow-class "viewport.width == narrow"
card-group narrow-layout "stack members"
make card
card inside card-group
```

**Kinds that cannot yet generate a template:** only `title` (no `defaults`
block, no `style`, no `contains`) yields `None`, so `make title` completes
with no body — correct; nothing is invented. All other 12 makeable kinds
produce a body. Properties whose `defaults` value is a prose hint (logo
`interactive "false by default - not settable yet...`, image `source "the
asset the implementation pulls from"`) flow through verbatim as editable
start — editable but not settable, worth community itemizing later; item
82 will grow advisory checks.

**Boundary honored:** the template is editor/dictionary layer only — no
grammar, parser, or dictionary schema change; a user deleting the whole
body regresses nothing (completion degrades to the plain `insert`).
Protocol: kind items carry an optional `snippet` field; the extension
substitutes it as a `SnippetString`, so the editor holds no vocabulary
(`editor/vscode-ine/extension.js`, README updated).

## External assessment — verified against ground truth

An external reviewer's project rating claimed: (a) "13 kind files",
(b) "112 mission index", (c) only "two statement kinds observed",
(d) item 58 was "Mission 57 mapping … over-shipped" (palette UNDECIDED),
and (e) "describing vs doing" open / say compile-time-resolve only.

Verified against `.agent/` and source:

- **(a)** 15 JSON files under `src/ine/dictionary/`; **13 makeable kinds**
  (banner…title; universal.json + viewport.json are unmade metadata). The
  "13 kind files" claim is right only if it means *makeable kinds*, wrong
  if it counts *files*.
- **(b)** PLAN items run **1–118** (reindexed by the PlanHygiene fix), not
  112.
- **(c)** `parser.py` declares **five** statement kinds (MakeStatement,
  PropertyStatement, SayStatement, InsideStatement, GroupStatement). The
  interpreter executes only `Say`, which may explain the undercount, but
  the grammar has five.
- **(d)** Correct with a level off: the over-ship was **item 58** being
  implemented without clearing item 58's second precondition ("the
  commander accepts the Mission 57 mapping scope"); M57 itself (the
  mapping *proposal* and NOTES finding) was never in question. Palette
  (CSS fidelity) remains UNDECIDED; `#e2e8f0` traces to neither guess nor
  proposal.
- **(e)** Accurate: `semantic.resolve()` turns `say <ref>` into a concrete
  value at compile time; `interpreter.execute()` echoes it. There is no
  doing-side construct — `say` is the whole runtime surface.

Rating-level judgment is not a repo fact and is not recorded here as one.

## Mission 82 — dictionary-backed validation

Implemented the first real consumption of the "dictionary is the semantics
authority" decision (DECISIONS Session 49): `advisory_warnings(model)` in
`src/ine/semantic.py`, run after `analyze` by the CLI (`build`, `_native`,
`_visual`). Strictly advisory — warnings to stderr, exit status and model
unchanged. Three checks:

- **(a) property name** the kind does not declare, against
  `properties_for(kind)` (declared hints + universal `title`/`text`).
- **(b) property value** outside the kind's declared vocabulary — the
  `values` map of the property's `style` block (the same data
  `style_declarations`/`style_overrides` read). `title`/`text` have no
  values map, so free text is never flagged; numbers pass.
- **(c) containment** where the child kind is not in the parent's `members`
  (from `contains`/`parents`). Kinds the dictionary does not declare (Alice's
  `person`) are skipped entirely — no custom-domain false positive.

**Classification across the repository (no hits — zero GENUINE, zero FALSE
POSITIVE):**

| program | (a) props | (b) values | (c) containment |
|---|---|---|---|
| examples/dictionary-demo.ine | none | none | none |
| examples/alice/alice.ine | skipped (person undeclared) | skipped | n/a |
| examples/hello/hello.ine | none | none | n/a |
| examples/homepage-cards/cards.ine | none | none | none |
| examples/homepage-hero/hero.ine | none | none | none |
| examples/homepage-topbar/topbar.ine | none | none | none |
| examples/native/hello.ine | n/a (say only) | n/a | n/a |
| examples/say/say.ine | n/a | n/a | n/a |
| examples/site/site.ine | none | none | none |
| examples/test.ine | n/a (empty) | n/a | n/a |
| .agent/experiments/*.ine (8) | none | none | none |

Why: every shipped program was written against the dictionary's own
suggestions (`--dict` discovery), and the containment pairs (banner-inside-
container, button-inside-section, section-inside-page, card-group-inside-
container, card-inside-card-group) are exactly the dictionary's `contains`
entries. The experiments deliberately stay inside declared vocabulary.

**Verdict — safe to harden next:** all three checks produced zero hits on
real programs, so converting any of them to a hard `SemanticError` would
break no existing example today. Recommend hardening order by confidence:
(1) containment (c) — the dictionary's `contains` is the most authoritative
data and site.ine's comment chains match it exactly; (2) property name (a) —
guards typos like `colour`, needs commander opt-in only because `properties`
blocks could grow more kinds; (3) value vocabulary (b) — keep advisory
longest, because `style` values maps are just paint words and the escape
hatch (authors writing raw CSS) is a documented feature. No hardening happened
in this mission per the commander-opt-in rule.

**Tests:** `AdvisoryValidationTests` in `tests/test_ine.py` (12 tests): each
check flagged + still-builds, valid cases not flagged, universal title/text
free, Alice's custom domain free, CLI reports to stderr with exit 0, and a
full-examples sweep asserting zero warnings. Suite: 555 passed, 31 subtests.

## Mission 7 — the first enumerated `choice` value (commander decision)

The longest-standing evidence blocker (Session 33 revert, "`card-group
layout` stays unknown until a second option exists") was resolved by
commander delegation: "the thing is the layout column … you could decide on
your own." So `card-group.json` now declares the first `"choice"`:

- `"properties": {"layout": ["row", "column"]}` (bare option words; the
  grammar still writes them quoted: `card-group layout "column"`).
- `value_shape("card-group","layout")` → `ValueShape("choice",
  ("row","column"))`; the Session 33 revert test
  (`test_card_group_layout_stays_unknown`) became
  `test_card_group_layout_is_the_first_choice`.
- `kind_snippet` offers the options for choice-shaped properties —
  `card-group layout "${1|row,column|}"` — instead of a fixed default
  (VS Code choice placeholder).
- `--dict card-group` now prints a `properties:` section:
  `layout  choice: row, column` (the shaped body surfaces the options).
- The advisory pass's `_value_words` now joins the declared `choice` options
  with the style `values` map, so `layout "diagonal"` warns while
  `layout "column"` is clean. `--dict` and the whole ESG-triple agree.

Commander guidance recorded: keep the vocabulary minimal — "not much
unnecessary quotation brackets, everything has to have a meaning," a chess
analogy (few rules, massive combination). `column` is the second and last
layout word today; evidence (a real program) gates further layout options.

## Mission 83 — one narrow responsive `@media` rule (unblocks item 59)

Commander decision received: item 59's single-rule scope accepted — "cards
stack on narrow … you could decide on your own." `backend_html.py`:

- `_narrow_rule(kind)` — when the kind's entry declares `narrow-class` AND
  `narrow-layout` in `defaults` while its `layout` is `row` (card-group
  only today), contributes one
  `@media (max-width: 768px) { .<kind> { flex-direction: column; } }` rule.
- Gated on the *declared data*, never the kind name; a program with no such
  kind gains zero `@media` output. Hint translation documented in the module
  (not invented): `narrow-layout` "stack members" → column; the
  `narrow-class` condition is NOT evaluated (conditions/state UNDECIDED) —
  its presence is the gate; 768px is a platform document-level fact in the
  same class as the viewport meta.
- Members keep inline `flex:1` from the row layout; in a column stack the
  container is content-sized so there is no free space to grow into and each
  member keeps its natural height.
- Goldens: `tests/expected/cards.html` and `tests/expected/site.html`
  regenerated deliberately; each gained exactly one line (the @media rule).
  hello/topbar/hero goldens byte-identical, unchanged.

**Verification:** 5 `NarrowResponsiveRuleTests` (rule emitted for
card-group; no `@media` for kinds without narrow declarations; desktop row
output unchanged; declared-value change keeps exactly one rule), plus the
choice tests. Suite: **563 passed, 33 subtests**.

**Next:** PLAN item 84 (editor diagnostics) — verified next EXECUTABLE via
`python -m ine_agent.cli run --dry-run`; index `.agent/missions/84.md`
needed.

## Mission 124 - Queue to exhaustion, and what a proposal actually is

- **A bound is not a loop condition.** The run ends when the next mission
  lookup finds nothing `EXECUTABLE`, when the mission-number set is exhausted,
  or when an optional bound is reached. A cycle counter is not a mission
  counter: a mission given three attempts is one mission, so the bound keys on
  mission identity (`_counted`), not on attempts. `--max-attempts` stays a
  per-mission budget and defaults to 1.
- **An unset bound is still finite.** "Run until the queue is exhausted" is
  bounded because a mission is attempted at most once and is then `DONE`,
  `BLOCKED`, or `DEFERRED`, and a proposal is never executable. That is the
  only reason the default can be unlimited work rather than an infinite loop.
- **`CLAUDE_REVIEW` is NOT inert in this plan.** Mission selection treats it as
  executable and routes it to the claude review pre-pass. So filing a worker
  proposal under that tag alone would make the *next* run pick it up, refuse it
  for want of an execution index, and tag it `BLOCKED` — a suggestion
  manufactured as a blocker, and one that a human would then have to clear. The
  inertness comes from `PROPOSAL_MARKER` in the item text plus
  `Task.executable` returning False for it, which means the plan's own parsing
  enforces the contract, not the worker's good intentions.
- **Compare proposals on identity-bearing words, and read them back from the
  span you wrote.** Two traps, both hit here: comparing the raw headline text
  fails once the stored item carries its annotation, and comparing the whole
  item line makes every proposal unique because the annotation's own words
  differ. `state.content_words()` strips the tag, the bold markers and function
  words; `Task.proposed_text` recovers the proposal from the bolded span. With
  those, "finish the thing" is recognised as a restatement of
  "`EXECUTABLE` — **finish the thing.**", and a repeated proposal is caught
  without depending on the annotation's wording.
- **Refusals are not missions.** A refusal (no execution index) happens outside
  a cycle, so a run that refused everything has a full tally of zeros. The
  summary must add the refusal count from `self._refused`, or the run reports a
  clean queue while outstanding planner work waits — which is exactly the
  outcome a commander would not want to be told about by silence.

## Mission 125 - What the handoff costs, measured

The pilot: three missions in one run over a stub worker - one completes, one
fails (exit 1 + a `failed` receipt), one reports `needs_commander`. The
assertions are in `tests/test_ine_agent.py` (`PilotRunTests`, 5); the
measurement script was scratch (`.tmp/pilot.py`, deleted after the run).

**Per-mission handoff, after (measured on the pilot, 27 Sep 2025):**

| mission | prompt chars | prompt lines |
| --- | --- | --- |
| 1 (no related earlier mission) | 2,944 | 64 |
| 2 (one related snippet selected) | 3,111 | 68 |
| 3 (gate) | 2,944 | 64 |

Run totals: 3 missions, **3 worker invocations**, 8,999 prompt chars, 451 output
chars, **0.24 s** wall clock, exit 2. So the per-mission handoff is ~3 KB / ~65
lines, and the marginal cost of one related earlier mission is ~170 chars / 4
lines - which is the whole point of selecting snippets on declared signals
rather than resending the history.

**Before, for comparison:** the pre-arc handoff embedded these blocks whole,
and there was no mission index at all - the plan item was the only per-mission
content. Measured on today's files, those blocks are:

| block | chars | lines |
| --- | --- | --- |
| `WORKER_PROMPT.md` | 4,041 | 93 |
| `MISSION_PROMPT.md` | 3,628 | 92 |
| `PLAN.md` | 96,217 | 1,648 |
| `STATE.md` (distilled head) | 5,428 | 90 |
| `HISTORY.md` (last 80 lines) | 5,021 | 80 |
| **sum** | **114,335** | |

The plan alone is ~32x the new prompt, and it grew with the project. Read
honestly: the old prompt was a *distilled* STATE, so this sums whole files
where the old code sent excerpts - it is an upper bound on the old handoff and
an order-of-magnitude statement, not a byte-exact A/B. The part that is exact
is the direction and the shape: **the old prompt was dominated by content the
mission did not need, and it re-sent that content on every cycle.**

**Model requests per mission.** Not measured by this pilot, which is a stub: a
stub makes zero real requests, and no number from it would mean anything. The
honest numbers are the ones already recorded under Mission 115: a near-empty
`opencode run` costs ~5-6 requests in practice (one `role=assistant` message ~
one request), so 3 missions ~ 15-18 requests, and the *old* path added a
further diagnosis call whenever a worker printed no `CLASSIFICATION:` line
(Mission 116) - up to one extra invocation per failure. The new path spends
exactly one invocation per attempt, always, and never a second. This run
therefore does not claim a new request count: it claims the diagnosis call is
gone, which is a structural change, not a measurement.

**What the pilot changed in the code.** It found two tally defects that unit
tests had let through, because no single test had a mission that failed *and*
a mission that was gated in the same run:

1. A gated mission was counted twice as human (once in the diagnosis branch,
   once in the loop) and **not** counted as blocked at all - so a run whose
   plan said `BLOCKED` reported "0 blocked". The diagnosis path is now the
   single owner of the counts, and a gated mission is counted as both human
   and blocked.
2. A failed mission was counted as both `failed` and `deferred`. The buckets
   are now mutually exclusive: a mission that failed is `failed`, and
   `deferred` means held without a failure to report. The four counts now sum
   to the missions the run touched, which is the only version of this number a
   commander can use.

Also added: the run summary counts the follow-up proposals it filed, because
Mission 124 asked for it and the pilot is where its absence was visible
("1 follow-up(s) proposed").

**Documentation delivered.** `CONTRIBUTING.md` now documents the flow a
contributor actually uses (`doctor`, `run --dry-run`, `run --worker <name>`,
`--max-missions`, `--max-attempts`), how to author a mission index, what the
receipt contains, how related snippets are selected, and what the commander is
asked to decide - plus the two enforced rules (a worker never edits the control
plane; a follow-up is proposed, never executed).
`.agent/DECISIONS.md` records the approved architecture and the three rejected
alternatives (injected state snapshot, whole-history summaries, automatic retry
with diagnosis).

## Session 52 - The worker prompt is a file, and a test that lied about encoding

**The prompt was in Python, and the commander asked for it in a file.** The
instructions the implementation worker receives - do this, do not do that, do
not burn tokens - were a string literal inside `impl_prompt` in
`supervisor.py`. The stated requirement was that this should be *a place where
we could customize it whenever we want, without changing the entire working of
that particular script*. Editing behaviour meant editing a 2000-line module.
That is a defect against the spec, not a preference.

`.agent/WORKER_INSTRUCTIONS.md` is now the literal prompt, and the supervisor
only fills slots. `{{MISSION}}` and `{{RECEIPT}}` are required and validated
before a run; `{{RELATED}}`, `{{MISSION_NUMBER}}` and `{{MISSION_HEADLINE}}`
are optional. Three consequences worth knowing:

- Substitution is a literal `str.replace`, not `str.format`, so a `{` in prose
  (a regex, an example, a dict) is text and cannot crash the run or swallow the
  mission. A hand-edited file is full of braces; `format` would have made it a
  landmine.
- A missing, empty or tokenless file raises `ProjectError`, which `cli.main`
  turns into exit 1 with a remedy, and which `doctor` reports and fails on.
  There is deliberately **no** built-in fallback text: a silent default would
  mean the shipped file is not the only thing that can be sent, which is the
  property the change exists to establish.
- `{{RELATED}}` is substituted with its trailing newline stripped. `compaction`
  already returns text ending in `\n` and the old template added a literal one;
  leaving both put an extra blank line in, and made the file's own blank lines
  stop describing the output. Editing the file would then not be what changed
  the prompt, which is the whole premise.

**How the no-behaviour-change claim was checked.** The old `supervisor.py` was
materialised from the HEAD blob into a throwaway package beside the new one,
both `impl_prompt` functions were pointed at this repository, and the two
prompts were compared: 6525 chars each, byte-identical. The first attempt
differed by one blank line, which is how the trailing-newline rule above was
found. Worth repeating for any future "this should change nothing" edit: build
both versions and diff the output, do not reason about the template.

**A test passed or failed depending on the command line used to run it.** Three
`CliTests` help-text tests capture a subprocess with `subprocess.run(...,
capture_output=True, text=True)` and no `encoding=`. `text=True` decodes with
the *parent's* preferred codepage; the child writes with its own. Run pytest as
`python -X utf8 -m pytest` and the parent expects UTF-8 while the child emits
cp1252, and the em-dash in the help text (0x97) raises `UnicodeDecodeError` in
a reader thread. Run it without `-X utf8` and both sides are cp1252 and the
tests pass. They were passing in the Session 51 report for exactly that reason,
and the utf-8 invocation used here is what exposed them. Fixed with one helper,
`run_cli_process`, which pins `PYTHONIOENCODING=utf-8` on the child and
`encoding="utf-8", errors="replace"` on the parent, so a result means the same
thing twice.

**The plain-script import branch is not covered by the test suite.** `cli.py`
carries a second import block for `python src/ine_agent/cli.py`, taken when the
package-relative import fails. The tests import `ine_agent.cli` as a package, so
that branch never runs: the first real `doctor` after this change died with
`NameError: worker_instructions is not defined` while all 330 tests were green.
Any new name added to the `cli` import list has to go into both blocks, and
running the real command line once is the only thing that catches it.

**Still open, and it is a product decision rather than an implementation one.**
The commander's description of this script is: hand missions to a coding agent
one at a time, verify, keep snippets, stop for a decision when one is needed,
and spend as few tokens as possible. The queue, the receipt, the snippets, the
needs_commander stop, the per-mission metrics and the tests all match that. What
does not match is the failure machinery: a five-value classification vocabulary
with a schema, fuzzy parsing and aliases, an in-band diagnosis call, an attempts
ledger with parking, and a stall guard - roughly 800-1000 lines in a script meant
to be boring. The recommendation is to keep output bounding and the timeout (both
earned their keep; the timeout is what stopped the runaway loops) and cut the
diagnosis vocabulary, the ledger, parking and the stall guard, since
`--max-attempts` already covers trying again. **The cut has NOT been made** - it
changes what the tool does when a mission goes wrong, which is the commander's
call, not the agent's.

## Session 52 - The prompt, the budget, the checks, and what each one cost

Four changes, one theme: the loop spends tokens only where a decision needs
them. Measured, not asserted.

**The prompt shrank by making absence the default.** The `PRIOR WORK IN THIS
AREA` block went away, and with it the "nothing related" text that used to
fill it. A mission with no declared `Area:`, `Depends on:` or changed file in
common is now sent no prior-work block at all — a smaller prompt *and* a
truer one. A minimal mission (index + headline + contract) is **3,414 chars /
61 lines / ~854 tokens**; the agent body is 319 chars, so what the provider
is handed is ~3,733 chars against ~4,511 before, about 17% less. The prompt
itself grew ~300 chars; the body fell from ~1,400 to 319. That trade is the
finding: most of what a worker was told lived in the agent definition, not
the prompt, and moving it there is free.

**A 50-character trim of the receipt contract was reverted.** The contract
explains what each field *means*; shortening it to satisfy a length target
broke eight tests that assert its wording, which is the tests being right.
Length is a target to report, not a licence to delete meaning.

**`policy` reports an over-budget prompt instead of hiding it.** A mission
that needs more than `max_prompt_chars` is sent whole and the overage is
recorded. Truncating a mission the planner asked for is the one thing the
cap must never do: a worker silently handed half a mission reports `done` and
means something else.

**`verify` runs after `done` and nowhere else.** A deterministic local check
that also ran on failure would be a second, vaguer opinion on a failure
already reported; a check that called a model would be a second supervisor.
So the rules are structural rather than editorial: `verify.py` imports
neither the worker factory nor the supervisor it lives in, and there is a
test that reads the source and fails if that ever changes. A failed check
records the finding and fails the run; it does not re-run the mission,
because a deterministic check will fail identically and the retry would
spend a request to learn nothing.

**A completed mission was being invoked twice.** The plan is re-read after
every cycle, and a mission a worker finished by receipt alone — without
editing `PLAN.md` — can still look selectable for a moment. That broke the
one promise the arc is built on: one mission, one process. Fixed by adding
the task identity to the run's deferred set in the `done` branch, and
`test_a_receipt_completion_costs_exactly_one_invocation` was confirmed to
fail with the fix reverted (2 calls, not 1), rather than merely passing with
it in place.

**Three traps worth carrying forward.**

1. *A malformed config must not be a traceback.* `Supervisor` loads
   `workers.json` in its constructor, and the constructor sat outside the
   `try` that turns control-plane faults into `error: ...` plus exit 1, so a
   bad check list escaped as an unhandled `ValueError`. Construction moved
   inside the guard, and the CLI now names the offending entry
   (`verify[1]`, `unknown key`) instead of printing a stack.
2. *`sys.executable` is not always launchable.* On this machine it names a
   Windows Store app-execution alias that `CreateProcess` refused with
   `[WinError 2]` from inside the full suite, while the same check passed in
   isolation. Probing the candidate the way the supervisor starts a check —
   same executable, and from a working directory — is what makes it
   reliable; the probe is `working_python()` in `tests/test_ine_agent.py`. A
   test that shells out to "the interpreter" is asserting something about
   the machine, not about the code.
3. *Supervisor-level checks go through a seam.* The tests that assert the
   wiring pass a `verify_runner`; the one test that starts a real process is
   separate, and skips rather than fails. The wiring is the subject, and the
   wiring does not need a subprocess to be tested.

**Scenario coverage, as tested rather than as claimed.** One process per
mission (`test_a_crashing_worker_costs_exactly_one_invocation`, plus the
receipt-path regression above); queue progression without a plan edit
(`test_successful_cycle_advances_and_rereads_state`); a failure, a missing
prerequisite and a commander gate each recorded once with no second call
(`test_a_failed_cycle_spends_no_second_call_when_the_receipt_says_why`,
`test_missing_prerequisite_blocks_records_and_continues`,
`test_worker_failure_is_recorded_deferred_and_stops_with_error`); related
context only on declared signals, and none at all without them
(`test_the_prompt_carries_a_related_snippet_as_data`,
`test_an_unrelated_mission_is_sent_no_prior_work_at_all`); over-budget
reported not truncated
(`test_an_over_budget_prompt_is_reported_and_still_sent_whole`); policy
defaults, overrides and CLI precedence (`BudgetPolicyTests`); checks off by
default, run after `done`, all of them run, non-zero exit, no model, no
retry, timeout and bounded output (`VerificationTests`); per-mission cost
recorded and measured (`PerMissionCostTests`,
`MeasureMissionCostTests`); bad config reported rather than crashed out of
(`test_a_bad_config_is_reported_by_the_cli_not_crashed_out_of`).

**A run report had been left with a body and no header.** `RUN_REPORTS.md`
ended in a stray `- exit: 0` / `- summary:` pair with no `### run <stamp>` line
above it - the tail of a dry-run whose header never landed. `measure` splits
the file on that header, so the fragment was being read as part of the run
before it: a cost report quietly wrong rather than a parse error. The fragment
was removed and
`ControlPlaneHealthTests.test_every_run_report_block_carries_its_own_header`
now fails if any block lacks its timestamp, which is the difference between a
report that is wrong and one that says so.

**Suite: 369** in `tests/test_ine_agent.py`, **707 + 33 subtests** full (706 +
1 skipped without a display), 0 leaked `.tmp` fixtures. Nothing is committed.

## Session 52 - The control plane drifts; the code does not

Asked whether the loop is actually usable, and whether the reports fall behind
the codebase. The second question had a live answer inside the repo.

**`STATE.md` was wrong about the next mission.** It said item 84 "needs an
index written at `.agent/missions/84.md`". The index exists, is 3,827 chars,
and `run --dry-run` resolves it. A queue audit found **all 30** `EXECUTABLE`
items have written indexes (44 index files exist) - so the loop can run today
and the recorded blocker was fiction. Corrected in `STATE.md`.

**The general shape, stated once.** The worker reads the actual files, so its
knowledge of the codebase cannot go stale. What goes stale is the *prose about*
the codebase: `STATE.md`, `NOTES.md`, `DECISIONS.md`, and the older mission
indexes. Those are written by an agent at session end or at planning time, and
nothing in the loop can check a sentence. So after N missions the summaries
describe a project that has moved, while the work itself stays correct.

**What the loop already does automatically**, and should keep doing: plan tags
and remarks, run reports, compact receipts, the failure ledger, follow-up
proposals, one `HISTORY.md` block per completion. All of it derived from a
fixed-shape receipt, none of it needing judgement.

**What it cannot do without spending a model call**, and should not: rewrite
`STATE.md` / `NOTES.md` prose. That is a per-run cost on every mission to
maintain a summary, authored by a process nobody chose - the exact trade this
arc deleted when it removed the diagnosis call.

**The three options, cheapest first.**

1. A deterministic staleness check with no model and no tokens: fail the run
   when a cheap fact is checkable and false. Candidates that are all decidable
   from files already on disk - `STATE.md`'s next-item claim disagreeing with
   what the selector picks; an `EXECUTABLE` item whose declared `## Files` have
   changed since its index was written; N missions completed since the last
   state refresh. This is the existing `verify` mechanism pointed at the
   control plane instead of the code, so it needs no new machinery.
2. A budgeted refresh mission: when such a check trips, file a
   `CLAUDE_REVIEW` item that says "re-read the code, rewrite the stale parts of
   `STATE.md` and `NOTES.md`". One mission, when it is owed, instead of
   background work forever - and it goes through the normal plan, so it is
   visible and refusable.
3. Automatic prose rewriting per run: rejected, for the reason above.

Option 1 is a product decision (it changes what a run may report), so it is
the commander's to make; it is not a blocker for running missions today.

## Session 52 - 709 green tests, and the tool was broken on first use

The commander's first real `run` died immediately:

    TypeError: build_worker() missing 1 required positional argument: 'root'

**The cause was a duplicated contract.** `Supervisor` owns the worker-factory
contract and already binds both `root` and `model` into a one-argument factory
(`lambda name: build_worker(name, root=self.root, model=self.model)`). The CLI
passed `build_worker` in raw, which is a second copy of that contract - and a
wrong one: it needs three arguments and the supervisor calls it with one. The
CLI's copy was *also* silently dropping `--model`, so even a fixed arity would
have ignored the model the commander asked for. Fix: delete the line. One place
decides how a worker is built.

**Why 707 tests did not catch it.** Every test injects
`worker_factory=lambda name: worker` - which is the correct contract, so the
tests were testing the supervisor against a *stub that agrees with it* and
never against the factory the CLI actually supplies. And `--dry-run` cannot
catch it, because a dry run resolves a profile and never builds a worker: it
printed a correct command and the crash came on the next cycle. **A green suite
proves the parts agree with each other; it does not prove the seam between them
is wired.** The seam here was the one place a user touches first.

**The fix is two tests, and both were checked against the bug:**

1. `test_a_real_run_through_the_cli_builds_the_worker_it_printed` runs the whole
   real path - CLI -> factory -> profile -> subprocess -> receipt -> records -
   against a profile whose command is a local `python -c` that prints a
   receipt. It costs nothing, calls no model, and fails with exactly the
   commander's `TypeError` when the bug is present. This is the integration
   test the suite was missing: not "does the supervisor work" but "does the
   thing a person types work".
2. `test_the_supervisor_factory_is_the_only_place_a_worker_is_built` asserts
   `cli.py` contains no `worker_factory=`, so the second copy cannot come back.

**Also verified, not a bug.** A hand-written fixture with an unbackticked tag
(`1. EXECUTABLE - ...`) is re-tagged to `` 1. `DONE` EXECUTABLE - ... `` -
two tags. The parser takes the *first*, so `DONE` wins and the mission leaves
the queue, and `PlanHygieneTests` already requires exactly one tag per numbered
item. The real `PLAN.md` has zero double-tag lines because the loop's own
rewriter replaces a backticked tag in place. Recorded because a double tag that
happened to be ordered the other way would be a mission that silently never
leaves the queue.

**The limitation it retires.** The loop had never executed its own real path:
"707 tests, never a live mission" was true, and it is now narrower. The path is
exercised end to end against a local stand-in agent. What is still unproven is
the *worker* half - whether a real coding agent, handed this prompt, returns a
receipt worth reading - which is a question about the prompt, not the plumbing.

**Suite: 377** in `tests/test_ine_agent.py`, **715 + 33 subtests** full.

## Session 52 - A supervisor must never hand the worker a console

The first live Claude run did not fail fast; it hung, and the traceback ended
in `proc.wait(timeout=self.timeout)` until a human pressed Ctrl+C. The cause is
one kwarg, and it is the kind that stays invisible until a real CLI is on the
other end of it.

**What happened.** Claude hit an API error, printed `Execution errorTerminate
batch job (Y/N)?` and waited for a keypress. Nothing in the supervisor would
ever send one. Both launch paths passed `stdin=None` whenever the prompt
travelled as an *argument* - and `stdin=None` does not mean "no input", it
means **inherit this process's stdin**, which in a terminal is the operator's
console. With `prompt_transport: stdin` a PIPE was used and the prompt written,
so the stdin path was always safe; the argument path was the one every real
agent profile takes.

**The fix is `DEVNULL`, and the distinction is the whole finding.** An
immediately-EOF stdin lets the child decide for itself - abort, or proceed -
and never parks a queue on a keypress. Applied in `worker._capture` and
`worker._stream`, the two shared helpers, so every adapter inherits it, and in
`verify.run_checks`, where a prompting local check would otherwise burn the full
600s timeout before the report explaining the stall appeared. The stdin-transport
path is untouched and pinned by a test: `subprocess.run` takes `input` *or*
`stdin`, never both, so "there is a payload to send" and "the child is isolated"
are mutually exclusive by construction.

**Why the behavioural test alone was not trusted.** Three of the new tests
launch a child that prints a question and then reads stdin. They pass here
because this shell's stdin is already non-interactive, so they would also have
passed against the *old* code. The two assertions that inspect the launch
kwargs are the load-bearing guard, and both were verified to fail when the fix
is reverted. Recorded because "the test hung and then it passed" is not
evidence, and because claiming five regression tests where two are real is
exactly the drift this file exists to prevent.

**The boundary lesson is larger than the bug.** A deterministic supervisor must
treat every external process as hostile to its own liveness: non-interactive
stdin, a hard timeout, bounded output, and a receipt it can parse without asking
a human anything. An agent that stops to ask a question is not a worker INE can
use, so the fix belongs on INE's side of the pipe - not in the agent's config.
## Mission 84

Area: ine-editor

The editor's semantic findings ride inside the same validate response under `advisory`, so a buffer that does not lex reports no advisory at all — there is no semantic model to check. The extension therefore shows red-only for lex/parse breakage and warnings only for parse-clean semantic bugs; a broken program can legitimately display just one red line and no warnings.

## Session 53 - A non-interactive worker is refused, not prompted

The first live Claude mission ran 214s, read the code, settled a complete design
for item 84 — token scanner, hover resolution order, advisory shape, extension
wiring — and then wrote **nothing**. Every `Edit`, `Write` and `Bash` call came
back "requested permissions ... you haven't granted it yet". It reported itself
`stuck`, which is the loop working: the receipt said what happened and why.

**The rule worth keeping: in print mode a CLI cannot ask, so an ungranted tool
is a refusal, not a prompt.** A worker profile is therefore a *capability
grant*, not just a command line. A mission that needs to edit files and run
tests against a CLI that will not prompt has to be granted both, or it will
spend its whole budget discovering that it is unable to act. Nothing in the
profile, the doctor output or the dry run said so beforehand; the only evidence
was a failed mission and a receipt.

**And the failure was silent in the worst way.** Exit code 0, a well-formed
receipt, a plausible summary, a design that would have been right. If the
receipt had claimed `done` with no changed files, or if `changed_files` were not
part of the contract, this would have been recorded as a success. The contract
requiring a receipt to name the files it changed is what turned a stuck worker
into a legible result.

## Session 53 - A buffered supervisor is indistinguishable from a hung one

Asked why a run "isn't showing a thing", I assumed the provider was quiet and
nearly wrote that down as the answer. A probe said otherwise: a fake worker
that printed a marker, slept six seconds, and printed another produced **9.3
seconds of absolutely nothing** when its output was piped — including the
markers the worker had explicitly flushed — and then printed all of it at once
on exit.

**The cause was one missing keyword in this package, not in the provider.**
Python block-buffers stdout when it is not a terminal, and `ine_agent`
contained **zero** calls to `flush` across 68 print and write sites. A
supervisor that streams a worker nobody can see streaming has failed the only
test that matters to the person watching it. Two changes, deliberately
overlapping: `_safe_stdout()` now reconfigures with `line_buffering=True`,
which covers every print site at once including the ones nobody remembers
existing, and `Supervisor._print` passes `flush=True`, which holds even when
the stream cannot be reconfigured. The same probe afterwards showed 1 line at
1.5s and 5 by 4.3s.

**The lesson is about the order of the assumptions.** "The provider does not
stream" was true — `claude -p` emits its whole answer at the end — and it was
the *second* cause, not the first. It was also the cause I would have reported
had I not run the probe, and that answer would have been half true and
completely useless, because the fix for it (a heartbeat) does not help if the
loop's own output is stuck in a buffer. Verify which silence you have before
explaining it.

**A heartbeat, because silence is ambiguous.** Even with perfect buffering, a
non-streaming CLI is quiet for the whole mission, and "is it working or wedged?"
is the question this loop was asked most often — and got wrong once, on the
`Terminate batch job (Y/N)?` hang. `_Heartbeat` prints elapsed time every 30
seconds while a worker runs and stops the instant it returns. It writes only to
the console: a heartbeat in the run report would be a claim about what
happened, and it is not evidence of anything.

**A receipt that changes nothing is not a done mission, and I was wrong about
how that failure would show up.** I expected the loop to reject the probe's
`changed_files: []` on its own. It did not: the probe exited non-zero, so the
EPIPE masqueraded as a launch failure and I read the rejection as the strict
behaviour I wanted. Once the broken pipe was fixed, the same probe exited 0 —
and the loop recorded PLAN item 85 `DONE`, wrote a compaction receipt reading
`Files: (none reported)`, and advanced the queue, on the strength of a worker
that had edited nothing. Rolled back by hand. The guard I "already had" was
the exit code, and it was never a guard at all: it was a coincidence of a
broken probe. The real question — may an empty `changed_files` complete a
mission? — is a semantics decision, so it is in `BLOCKERS.md` rather than
decided here. The lesson is narrower and more uncomfortable than "verify your
assumptions": a passing test proved the code did what I believed, and the
belief was untested. The receipt contract never promised what I assumed it did.

**The broken pipe was not a probe artefact either.** It was a general defect,
and it lived only on the streaming path. Windows pipes buffer 4096 bytes, so a
prompt larger than that makes the parent's write *block*; a worker that never
reads stdin and is still running when the write blocks, then exits, fails the
blocked write with EPIPE. `run()` caught `OSError` and reported "could not start
claude" — discarding the exit code and the receipt the child had already
printed, while relaying those same lines to the console. The operator saw a
receipt; the classifier saw a launch failure. `_capture` never showed it,
because `subprocess.run`'s `communicate()` already swallows EPIPE, so only
`_stream` was affected. Two rounds of test-writing failed to reproduce it: the
first used a 30-character prompt (far below the buffer, so the write never
blocked) and the second forgot to pass `on_line`, silently testing the capture
path. Both "passed" against the bug. A regression test that cannot fail is
worse than no test, because it converts a guess into a green checkmark — the
fix was confirmed only by reverting it and watching the test go red with the
exact production message.


## Session 53 - A recorded mission grows STATE.md's session number

`record_mission_outcome` rewrites the bounded head of `STATE.md`, and its
session-header substitution was written as
`r"\g<1>" + str(session) + r"\g<2>"` — which *appends* the new session to the
digits it had just matched. Every recorded mission therefore grew the header:
`52` → `5352` on the first live mission that recorded an outcome, `535352` on
the next, and it would have gone on.

**It survived 709 tests, and the reason is structural rather than accidental.**
Nothing in the suite asserted the *value* of that header against a second
recording — the tests checked that the sections were replaced, that a sentinel
below them survived, and that a `DONE` mission wrote a HISTORY block. The
control-plane health test does compare the header against the latest HISTORY
heading, which is why it failed immediately and why the bug is worth more than
its size: a number that only ever grows is a number that eventually disagrees
with the thing it claims to summarise, silently, in a file every cycle reads.

**The lesson is about which invariant gets pinned.** "The head is rewritten" was
pinned; "the number in the head is *replaced*" was not. Idempotence of a
rewriter is a separate property from its effect, and it is the one that only
shows up on the second call.

## Session 54 - Cost is per *request*, not per token

The commander read the provider's request log after a run and reported it
"burning too crazy": ~$13.60 across three bursts, ~$4.50 per mission, against
an expectation of roughly $1 for a comparable manual session. The instinct is
that a long transcript means many tokens means high cost. The log says
otherwise, and says it clearly.

Measured over all 100 requests in the three bursts:

- **Correlation between tokens and cost is ~zero** (+0.42, -0.05, +0.22).
- **Cost per request is nearly constant at $0.13-0.14.** Total spend is
  `requests x $0.135`, to within a few cents.
- The single largest request in the log — 48,210 tokens — cost **$0.272, or
  5.6% of the run's $4.83**. The *smallest* (338 tokens) cost **$0.142**, twice
  as much as many mid-sized requests.
- The 27k/48k rows are also the *cheapest per token* in the log: they are the
  uncached first turn of a coding-agent session (system prompt plus tool
  definitions), flagged `Cache: 1` because nothing was cached yet. INE's own
  mission prompt is 6,904 characters and is not the thing being charged for.

So a mission is not expensive because it is long; it is expensive because the
agent took ~34 turns (one API call per tool round-trip, ~1 every 4.7 seconds in
the 15:23 run). **The lever is the number of requests, not their size.** Any
optimisation aimed at "shorter prompt" or "fewer tokens" targets a term the
data shows is nearly irrelevant.

**The lever that exists.** `claude --help` documents
`--max-budget-usd <amount>` — "Maximum dollar amount to spend on API calls
(only works with --print)" — and INE runs Claude in exactly `--print` mode, so
the ceiling is available and enforceable per mission. This build has no
`--max-turns`. Budget cap, not turn cap, is the available instrument.

**Why this went unnoticed for two runs: INE is blind to cost.** Every run
report says `usage: ... usage_unavailable (the provider reported no usage for
this mission; nothing is estimated)`, so the loop cannot see any of this and
cannot warn before $13 disappears. That blindness is the real defect here, and
it is worth more than the one that was fixed: a loop that cannot measure its
own cost will repeat an expensive mistake indefinitely, and will do so
silently, which is the failure mode this project keeps meeting.

**And the most expensive run in the log is the one that was killed.** The
15:23:38 run's report stops after its first mission line with no `exit:` line,
and there is no `KeyboardInterrupt` handling anywhere in `ine_agent` — Ctrl+C
kills the process mid-report. So ~$4.83 bought a half-written
`src/ine/formatter.py` (no tests, no receipt, no plan tag), and `RUN_REPORTS.md`
cannot distinguish *interrupted* from *crashed* from *still running*. An
interrupted run is a normal thing for a human to do, and the record treats it
like a mystery.
## Mission 85

Area: ine-editor

Statement dataclasses from parser.py are frozen with eq comparing every field, `line` included, so `parse(lex(text)) != statements` is a layout-equality test, not a meaning test — it cannot be used to check meaning preservation across any reflow that changes line counts. The formatter's `_bare()` clears `line` at every depth (including inside PropertyRef, which `say card.title` carries) to compare meaning only. Separately: the lexer discards comments, so any formatOnSave formatter that re-emits from the parse tree alone deletes every comment in the file; format_program now returns a commented file untouched, and tests/test_formatter.py pins that. Mission wordings taken as read: `ene.format` implemented as `ine.format`, and `make <kind> <id>:` implemented per the real colon-free grammar. FormatterError was not added — the mission's allowed alternative, reusing SyntaxError/ValueError, is what the code does.

## Windows worker isolation, and what a signal does not deliver (Session 56)

**`stdin=DEVNULL` does not stop `cmd.exe` prompting.** A Windows worker
launched via `claude.CMD` with `shell=True` still gets a console handle unless
the spawn says otherwise, and `cmd.exe` reaching `CONIN$` prints
`Terminate batch job (Y/N)?` and blocks. `creationflags=CREATE_NO_WINDOW |
CREATE_NEW_PROCESS_GROUP` is the fix; the new-process-group half is also what
makes a later `taskkill /T` able to reach the whole tree.

**A child is not a process tree.** `proc.kill()` kills `cmd.exe` and orphans
`node.exe`. `taskkill /F /T /PID <pid>` is the Windows equivalent of killing
the group, and it must be wired into every exit path — timeout, exception, and
operator interrupt — or a cancelled mission leaks a live process per attempt.

**`CTRL_BREAK_EVENT` is a hard kill; only `CTRL_C_EVENT` is a signal.** Sending
`CTRL_BREAK_EVENT` to a process started without `CREATE_NEW_PROCESS_GROUP`
terminates the *whole console group* — my first probe script killed itself and
its PowerShell parent and produced no output at all, which looked like a hang
and was not one. With the group created, the same call returns `0xC000013A`
(`STATUS_CONTROL_C_EXIT`): the process dies **without running Python
handlers**, so no `except KeyboardInterrupt` fires and nothing is recorded.
Real Ctrl+C (`CTRL_C_EVENT`) is what Python surfaces as `KeyboardInterrupt`,
and that is the path the interrupt handling is written for. Do not try to test
the handler with `CTRL_BREAK_EVENT`; it cannot reach it.

**`output 93 chars` is not evidence.** The failed run's report line said the
worker printed 93 characters and named none of them, so the single most useful
fact — the provider had rejected the model id — survived only on a console
that was already gone. Recording a bounded excerpt of a failed worker's own
words costs ~20 lines per failure and is the difference between debugging a
mission and re-buying it. A silently truncated report is worse than a verbose
one, because it reads like a complete record.

**A silent no-op is the hardest defect class to catch from outside.** The
formatter's round-trip guard compared statement dataclasses field-by-field
*including* `line`, so a reflow that inserted the canonical blank line was
rejected and `format_program` returned its input unchanged. The function was
correct, exported, documented, tested by nobody, and did nothing at all. It
took reading the guard to see, not a failing test.

## Mission 86 — code actions investigation

Investigation only. `src/` and `editor/` are untouched by this mission: the
deliverable is this section plus the scratch prototype
`.tmp/code-actions-probe/probe.py` (gitignored — **not** a durable location;
the rule it proves is stated here, and this section is the durable record).

Read for this section: `src/ine/parser.py`, `src/ine/lexer.py`,
`src/ine/semantic.py`, `src/ine/formatter.py`, `editor/vscode-ine/extension.js`
(`DictionaryWorker`, `canonicalText`, `provideDocumentFormattingEdits`,
`toDiagnostic`), `tests/test_ine.py` (`GroupSemanticsTests`, `SayTests`).

### 1. The text-span basis, and why every action is line surgery

The engine has no source mapping. A parsed statement carries `line` (1-based,
from the token) and nothing else — no column, no end position, no offset, no
byte span. `Token` has a `column`, but the parser drops it, and a statement's
`line` is the line of its *first* token. Consequences any code action must
live with:

- **One line holds one statement, with two exceptions.** `make <count> <kind>`
  is a single line that `_parse_make_many` turns into N `MakeStatement`s, all
  with the same line, naming entities (`card-1`…) that appear nowhere in the
  text. `group <name> = <m1> <m2> …` is one statement naming N entities on one
  line. Everything else is one statement per line, because the parser demands
  NEWLINE or EOF after each.
- **Comments are discarded by the lexer.** The formatter refuses any buffer
  holding a `#` outside a string (`formatter._commented`) for exactly this
  reason; a re-emitting code action must adopt the same refusal or it will
  silently delete comments.
- **What `analyze` reports is post-expansion.** `semantic._expand_groups`
  rewrites group-targeted statements into one statement per member before the
  model is built, so `model.relationships[card-1]` may come from a `cards
  inside page` line and have no per-member line to edit. Every precondition a
  text edit depends on must be checked against the **raw parse**, before
  expansion.
- **A group names entities; it does not declare them.** `_expand_groups` raises
  unless every member was declared with `make`, so a group line can never
  replace the `make` lines it collects, and a group name may not collide with an
  entity name (a semantic error).

So an action is a list of line-range replacements computed against the
**original** buffer — `(start_line, end_line, replacement)` — applied in
descending line order, or handed to VS Code as `vscode.TextEdit`s built from
`document.lineAt(line)`. `toDiagnostic` already clamps `entry.line` into the
document this way; edits need the same clamping, and a stale snapshot (the
document changed between sampling and applying) must be refused rather than
applied by position.

### 2. Statement map — what a text replace must change to be safe

| statement | text form | who refers to it | what a rewrite must handle |
|---|---|---|---|
| `MakeStatement` | `make <name>` or `make <name> <kind>` | the *name* is referred to by property, `inside`, `say` and group-member lines; the *kind* is referred to by nothing | the bare form sets `kind == name`, so renaming such an entity silently changes its kind unless the replacement writes it explicitly (`make <new> <old-kind>`); a `make <count> <kind>` line declares N entities with no text of their own |
| `PropertyStatement` | `<target> <name> <value>` | target by name; property name by `say <entity> <property>` | re-rendering the value changes its spelling (`1e3` → `1000.0`; `1` vs `1.0` is a real type difference), so retarget the leading name and leave the rest of the line byte-identical |
| `SayStatement` | `say <value>` or `say <entity> <property>` | nothing | the only place a *property name* appears; a property rename that misses it turns a valid file into a `resolve` error |
| `InsideStatement` | `<child> inside <parent>` | containment is unique per child — a second `inside` for the same child is a semantic error | adding a group *and* keeping the members' own `inside` lines is an error, so a collapse must be driven by raw statements only |
| `GroupStatement` | `group <name> = <m1> <m2> …` | statements targeting the group expand per member: `inside` and properties (not `say` — `say <group> <prop>` is an error) | members must already be `make`d; the name must not collide with an entity or another group |
| `PropertyRef` | inside a `say` line | — | not a statement; shares its `say`'s line, so editing one edits the other |

### 3. Candidate actions

| candidate | rough cost | why |
|---|---|---|
| extract to group | low — prototype exists (§4) | one inserted line plus retarget/delete of the members' shared `inside` and identical property lines |
| expand `make <count> <kind>` into N bodies | low | one line in, N lines out, no reference changes; but it is the **prerequisite** for every other per-entity action, since a synthetic entity cannot be addressed in text |
| inline group (flatten members into the parent) | low | replace each group-targeted statement, in place, with one per member, then delete the group line; in-place replacement preserves the last-wins order `_expand_groups` produces, so it is semantics-preserving by construction |
| declare the missing entity (quick fix on the existing "was not declared with `make`" diagnostic) | low | insert `make <name> <kind>`; needs a kind — the dictionary's `makeable()`/`suggest()` is the authority, else refuse |
| rename kind | low–moderate | kinds appear only on `make` lines (`make x k`, `make N k`) and no statement names one, so the scan is bounded; but renaming a *dictionary* kind to an undeclared one is a language change, so restrict it to non-dictionary (custom) kinds |
| rename entity | moderate | must rewrite property targets, `inside` children and parents, `say <entity> <prop>` refs, and group-member lists; plus the bare-`make` kind hazard, a collision check against entity/group names, and refusal (or expand-first) for members of a `make N` line |
| collapse N bodies back into `make <count> <kind>` | moderate | applicability is a heuristic — the names must be exactly `<kind>-1 … <kind>-N`, consecutive, all that kind, none referenced by a `make <count>` that would then duplicate them |

One paragraph per candidate: *extract to group* changes containment only — it
inserts `group <name> = <ids>` after the last member's `make` line and collapses
the members' shared `inside` line and any property line they hold *identically*
into one group-targeted line; it rewrites/retargets `InsideStatement` and
`PropertyStatement` leading names and must not touch `make`, `say`, or any
non-uniform property; the span basis is the members' `make`, `inside` and
property lines, the only lines involved. *Expand make-many* changes one line
into N `make` lines and rewrites nothing else; its span is that single line; it
is safe whenever the buffer is valid (the N names cannot already be declared)
and it is what unblocks per-entity actions on synthetic entities. *Inline group*
rewrites every statement whose target is the group into one statement per member
at the same position, then deletes the group line; it rewrites
`PropertyStatement`s and `InsideStatement`s, never `say` (already an error
against a group); spans are the group line plus each targeting line. *Rename
kind* rewrites only `make` lines; spans are those lines, and the reference-free
property of kinds holds throughout this grammar. *Rename entity* rewrites the
`make` line, every property line targeting it, `inside` lines on either side,
`say` refs, and group-member lists; spans are all of those, and it is the only
candidate whose correctness needs a global name-collision check. *Collapse to
make-many* rewrites N consecutive `make` lines into one; its span is that run,
and its applicability test (exact `<kind>-N` naming) is the only heuristic in
the list.

### 4. Prototype: extract to group — the exact rule

`extract_to_group(source, ids, name=None) -> str`, in
`.tmp/code-actions-probe/probe.py` (scratch). Preconditions, all on the raw
parse, all raising `ValueError` when unmet:

1. the buffer holds no `#` outside a string (the formatter's rule);
2. `ids` has ≥2 distinct ids, each declared by exactly one handwritten `make`
   line (never a `make <count> <kind>` line), all with one shared kind;
3. those `make` statements are consecutive in statement order (nothing between
   them but the other members' `make`s) — this is the "consecutive siblings"
   reading, and it is what makes a contiguous line selection a sufficient UI
   gesture;
4. each id has exactly one literal `<id> inside <parent>` line, all with the
   same parent, and the parent is not one of the ids;
5. the name — given, or defaulted to `<parent>-group`, uniquified with a `-2`,
   `-3` suffix against entity and group names — is not already taken and is not
   a keyword.

Edits, against original line numbers, applied in descending order:

- append `group <name> = <ids…>` to the **last** member's `make` line (the
  `make` lines stay: a group cannot declare its members);
- retarget the **first** member's `<id> inside <parent>` line to `<name> inside
  <parent>` and delete the other members' `inside` lines;
- for each property name that *every* member holds in exactly one statement with
  an equal value **of the same type**, retarget the first member's line to the
  group and delete the other members' lines; a property even one member lacks,
  or holds with a different value or type (`1` vs `1.0`), is left untouched —
  moving it onto the group would give it to every member;
- nothing else in the buffer is touched: no `make`, no `say`, no non-uniform
  property, no blank line.

Retargeting replaces only the leading name token and keeps the rest of the line
byte-identical, so no value is ever re-rendered. The output is *not* canonical
layout (deleted lines leave gaps); the existing format-on-save is the layout
pass, and it is safe here because the action already refuses commented buffers.

Before → after, from the probe:

```
make page                    make page
make card-1 card             make card-1 card
make card-2 card             make card-2 card
card-1 inside page     ->    group page-group = card-1 card-2
card-2 inside page           page-group inside page
card-1 padding "8"           page-group padding "8"
card-2 padding "8"
```

Verification the probe runs: for 8 accepted cases it re-parses the edited
buffer and asserts `analyze(parse(lex(edited)))` has **identical** entities,
properties and relationships to the original, that `groups` differs only by the
new declaration, that `render(model)` (backend_html) is byte-identical, and that
`execute(resolve(statements, model))` — the `SayTests`-style check — returns the
same `say` outputs. Cases cover a two-sibling extraction, a subset of three
siblings, a property only one member holds, a property with differing values,
`1` vs `1.0`, a surviving `say card-1 title` reference, a default-name collision
(→ `page-group-2`) and an explicit name. Seven refusal cases cover a member from
a `make 3 card` line, a comment, different parents, different kinds,
non-consecutive `make`s, members already grouped (no literal `inside` line), and
a single id. All 15 pass; `python .tmp/code-actions-probe/probe.py` prints
`all cases verified: 8 edits, 7 refusals, 0 failure(s)`.

### 5. What the real action still needs (the gap)

- **No source mapping.** The engine cannot say "this entity is at bytes 40–52",
  so ids must come from the *selection*: the extension sends the buffer plus the
  selected line range and the engine decides which lines are handwritten `make`s
  of one kind. The alternative — the extension scanning statements itself —
  duplicates the parser in JavaScript and should be rejected.
- **The worker contract already fits.** `DictionaryWorker` is one long-lived
  `python src/ine/autocomplete.py`, JSON-lines, one in-flight request, 4 s
  timeout, `id` echoed; `complete(payload)` dispatches on `payload.get(...)`
  keys. A new op `{"action": "extract-group", "buffer": …, "lines": [a, b],
  "name"?: …}` → `{"action": true, "text": …}` or `{"error": "…"}` follows the
  `format` op exactly, including its rule that a missing `text` is *no answer*,
  never "no change" (`canonicalText`). The engine entry point belongs in
  `src/ine/` next to the formatter, not in `autocomplete.py`.
- **The extension has no action provider yet.** One
  `vscode.languages.registerCodeActionsProvider({language: "ine"},
  {provideCodeActions}, {providedCodeActionKinds: [vscode.CodeActionKind.RefactorExtract]})`
  in `activate`; the edit should be per-line `vscode.TextEdit`s (minimal undo),
  not the whole-document replace the formatter uses.
- **A stale buffer must be refused.** VS Code applies edits by position, so the
  extension must check `document.getText()` against the sampled buffer before
  applying, and drop the action otherwise.
- **`group` names are a UI decision, not a language one.** The default
  `<parent>-group` is deterministic and collision-free, but a real action should
  prompt (QuickPick prefilled with it); `name` in the rule above is that prompt.

### 6. Recommended ordering for the remaining actions

1. **extract to group** — the rule is proven and nothing blocks it; it is also
   the action whose value grows most with the dictionary workflow
   (`group cards = …` plus one `cards inside page`).
2. **expand `make <count> <kind>`** — cheap, and it makes every other action
   total, because today each must refuse synthetic entities.
3. **inline group** — the inverse of (1), shares the line-edit machinery, and is
   semantics-preserving by construction.
4. **declare the missing entity** — cheap, and it retires the most common red
   diagnostic; the dictionary supplies the kind.
5. **rename kind** — bounded to `make` lines, no references, but needs the
   custom-vs-dictionary kind question answered before it is written.
6. **rename entity** — because it is the only candidate with a global blast
   radius (four statement kinds, group member lists, the bare-`make` kind
   hazard, and a name-collision check).
7. **collapse bodies into `make <count> <kind>`** — the only heuristic
   applicability test of the set; lowest value per unit of risk.

The ordering is a recommendation, not a decision; (1)–(2) are the pair that
makes the rest straightforward.

