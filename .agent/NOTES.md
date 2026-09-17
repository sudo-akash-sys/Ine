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

## Mission 111 - Autonomous-worker request frugality (baseline metrics)

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