# SESSION_STATE.md

Last updated: 2026-09-14

This file captures the complete project state so any AI session can
continue without losing context. It is NOT a conversation summary.
It IS the project's working memory.

---

## 1. Project Identity

**Working name:** Ine

**Core mission:** Create a simple way for a person to describe what
software should be, how it should behave, what constraints matter, and
what it should look like — without requiring deep knowledge of
implementation syntax.

**Status:** Building. First real Ine program exists
(`examples/homepage/`): the semantic representation of the homepage
(hand-authored, no tool reads it yet). A real toolchain exists in
`src/ine/` (Session 9, renamed Session 23): lexer → parser → semantic → HTML backend → CLI.
Session 10 added the requested **Say vertical slice**: `say "..."` →
lexer → parser → interpreter → stdout, verified. The language now has
two kinds of statements (describing: `make`/property → model → target;
doing: `say` → execution → stdout). The language name, extension, and
CLI command are all **Ine/ine** (DECIDED, Session 23): `.ine`, invoked
as `ine <file>.ine` (or `python -m ine`).

---

## 2. Current Decision Status

### DECIDED

Direction (DECIDED by user, Session 8): stop running experiments as the
goal. Process = have an idea → make it real → hit a problem → solve it →
continue. HTML/CSS was only a concrete target; HTML is NOT MyLanguage.
Architecture stays: Human intent → MyLanguage semantic representation →
AI/engine implementation → HTML/CSS/JS/etc.

### PROPOSED — Semantic Model v0.1 (6 concepts)

The current candidate foundation for the language's meaning:

1. **Entity** — a thing that exists in the software
2. **Property** — a characteristic of an entity (width, price, color)
3. **Relationship** — how entities are connected (inside, beside, opens)
4. **State** — how an entity changes over time (open/closed, visible/hidden)
5. **Condition** — when behavior changes (when user clicks, if price < 100)
6. **Multiplicity** — how many (three cards, all products)

**Status:** PROPOSED, NOT DECIDED.

**How we got here:** Started with 12 workbook primitives. Reduced to 10. Then 7. Then tested 7 against 18 examples, found Property was missing from the original list. Reduced to 7 (Entity, Property, Relationship, State, Condition, Multiplicity, Reference). Classified Reference as a representation mechanism, not semantic. Arrived at 6.

**Key reasoning:**
- Entity is the anchor. Without it, nothing exists.
- Property describes what things are like. Nearly every example uses it.
- Relationship describes structure. Cannot be reduced to properties.
- State captures change over time and modes of existence.
- Condition captures triggers and behavioral change.
- Multiplicity captures quantity and groups.
- Reference was eliminated as a representation mechanism (how we point to things, not what things mean).

### PROPOSED — Concepts reclassified as VOCABULARY

These are NOT separate semantic primitives. They are specific types of
entities, states, or relationships defined in the dictionary:

- User / Human actor → entity with special type
- External resource / Asset → entity with special type
- Platform / Context → entity with special type
- Visibility → specific type of state (visible/hidden)
- Focus → specific type of state (focused/not focused)
- Persistence → property of states (stored vs. transient)
- Error / Failure → specific type of state (failed/denied)
- Show / Hide / Open / Close → specific types of state changes

### PROPOSED — Concepts reclassified as REPRESENTATION

These are needed to construct a model but are not part of what the
model MEANS:

- Reference — how we point to entities
- Forward reference — pointing to something not yet defined
- Source text preservation — tracking where meaning came from
- Entity naming — how we identify entities

### PROPOSED — Concepts reclassified as IMPLEMENTATION

These belong to compilers, runtimes, platforms, or target technologies:

- Specific interaction types (click, tap, swipe)
- Specific UI mechanisms (DOM, CSS, React)
- Data storage mechanisms (database, file, cache)
- Network protocols (HTTP, WebSocket)
- Platform APIs (browser, OS, device)

### PROPOSED — Concepts that are DERIVABLE from the 6 core

These do NOT need to be separate primitives:

- **Action** = Entity + State change ("show menu" = menu.visibility = visible)
- **Event** = Entity + State change + Condition (event triggers a condition)
- **Actor** = Entity that appears in conditions as source of state changes
- **Collection / Group** = Entity + Multiplicity
- **Data** = Entity + Property
- **Data flow** = Entity + Relationship + State change
- **Transformation** = Entity + Relationship + State change
- **Selection** = Entity + Multiplicity + State
- **Filtering** = Entity + Multiplicity + Property + Condition
- **Sorting** = Entity + Multiplicity + Property + State
- **Order** = Entity + State (position) or Entity + Multiplicity + Property + State
- **Recursion** = Condition-based repetition (implementation pattern)
- **Iteration** = Multiplicity + Condition

### UNDECIDED — Whether 6 concepts is the final count

The adversarial test found two meanings the 6 concepts cannot
faithfully represent:

1. **Nondeterminism** — "the result is uncertain" (all states must
   have specific values in the current model)
2. **Prohibition** — "must not" (the model has conditions but not
   explicit constraints/prohibitions)

If these are genuinely semantic (not implementation concerns), a
seventh concept is needed. Candidates:
- **Possibility** — "this can be A or B" (covers nondeterminism)
- **Constraint** — "must not" (covers prohibition)

**This is NOT resolved.** It needs more investigation.

**Concrete evidence (Session 2):** The real homepage experiment
confirmed the Constraint gap in a concrete example — "cards are equal
width" cannot be represented with the 6 concepts. It also surfaced a
NEW gap not previously flagged as a candidate: **distinct instances**
of a group ("Card 1, Card 2, Card 3" with different content) cannot be
represented. Multiplicity says HOW MANY, not WHICH ONE. This makes the
7th-concept question more substantial than before, but still UNDECIDED.

### UNDECIDED — Whether State is actually necessary

State might be derivable from Property + Condition. "Menu opens" could
be "menu.visibility changes from hidden to visible, triggered by user
click." But the adversarial test showed State captures "modes of
existence" that are hard to replace. Needs more investigation.

### UNDECIDED — Whether Multiplicity is actually necessary

Multiplicity might be derivable from Entity + Relationship (a group
is a set of entities with containment). But the adversarial test
showed "three cards" and "sort products" require Multiplicity. Needs
more investigation.

---

## 3. What Was Rejected

- **12 original workbook primitives as the final set** — too many,
  some overlap, some are vocabulary not structure
- **Reference as a semantic primitive** — it is a representation
  mechanism, not a meaning
- **Action as a semantic primitive** — derivable from Entity + State
  change
- **Event as a semantic primitive** — derivable from Entity + State
  change + Condition
- **User/Human actor as a separate concept** — it is a vocabulary
  term for a specific entity type
- **External resource as a separate concept** — it is a vocabulary
  term for a specific entity type
- **Collection/Group as a separate concept** — derivable from Entity +
  Multiplicity

---

## 4. The Semantic Model v0.1 (from early analysis)

A structured representation was proposed to capture the 7 original
examples. Here is the shape (PROPOSED, NOT DECIDED):

```
{
  "entities": [
    { "id": "string", "type": "string", "source": "optional" }
  ],
  "relationships": [
    { "from": "entity_id", "relation": "vocabulary_term", "to": "entity_id" }
  ],
  "actions": [
    { "actor": "entity_id", "action": "vocabulary_term", "target": "entity_id" }
  ],
  "constraints": [
    { "target": "entity_id", "rule": "string", "value": "any",
      "condition": { "when": "string", "operator": "string" } }
  ],
  "state": [
    { "entity": "entity_id", "states": ["string"], "initial": "string" }
  ]
}
```

**Note:** This model was designed before the reduction analysis.
It may need revision now that Action and Event are considered
derivable, and Reference is considered representational.

---

## 5. Adversarial Test Findings

The 6-concept model was tested against 30 categories of programming
meaning. Results:

**Fully preserved (10):**
One-time events, external output, creation, destruction, copying,
moving, mutation, ownership, errors, user interaction

**Derivable (14):**
Repeated operations, timers, causality, external input, identity,
cancellation, recursion, iteration, aggregation, streaming,
asynchronous behavior, randomness, physical/device interaction,
sequences (partially)

**Partially preserved (6):**
Irreversible operations, reversible operations, concurrency,
authorization, transactions, nondeterministic behavior

**Not preserved (1):**
Nondeterminism (the result is uncertain)

**Key finding:** The 6 concepts are remarkably robust. The only
genuine semantic gaps are nondeterminism and prohibition. Everything
else is either fully representable or derivable.

---

## 6. Semantic Closure Test Findings

20 concepts were tested against the 6 core. All 20 were either
DERIVABLE, VOCABULARY, REPRESENTATION, or IMPLEMENTATION.

The closure test suggested the 6 concepts form a closed foundation.
The adversarial test partially confirmed this but found edge cases.

---

## 7. Project Structure

```
MyLanguage/
├── AGENTS.md          — AI behavior rules (DECIDED: authority rules)
├── WORKBOOK.md        — Vision and decisions (699 lines)
├── LANGUAGE.md        — Language spec (EMPTY — not started)
├── RESEARCH_LOG.md    — Research session records
├── SESSION_STATE.md   — THIS FILE — project working memory
├── src/               — Source code (EMPTY — not started)
├── dictionary/        — Vocabulary definitions (EMPTY)
├── templates/         — Reusable templates (EMPTY)
├── examples/          — Example programs (EMPTY)
├── tests/             — Tests (EMPTY)
├── output/            — Build output (EMPTY)
└── .tmp/              — Temporary work (EMPTY)
```

---

## 8. File Extension

**DECIDED (Session 20, renamed Session 23):** Ine source files use
the extension `.ine` (the name and extension are the same word), e.g.
`hello.ine`, `homepage.ine`. The language's name is **Ine** (previously
"Intent Expression", renamed Session 23). Do NOT use
`.semantic.json` as the human-written source format going forward — JSON
was a prototype of meaning; `.ine` is the actual language humans write.

---

## 9. Compilation Target

**NOT DECIDED.** The user explicitly said: native machine-code
compilation is a desired capability being investigated, but NOT yet
a locked architectural decision. Do not assume x86-64, ARM, LLVM,
WASM, custom bytecode, a VM, or any other execution target. Do not
assume HTML/CSS/JavaScript is the primary target.

---

## 10. Workflow Rules

From the user:

1. Test in very small chunks (5 to 10 basic designs first)
2. Use small tests to verify the language works as intended
3. Evaluate strengths, weaknesses, and oversights
4. src/ is for general sources and images, NOT an information catalog
5. temp/ is strictly for temporary work and testing
6. Always keep the workbook updated with ideas
7. Fix issues as they arise, or communicate in advance
8. Do not make major language-design decisions autonomously
9. Present options and trade-offs before implementing changes

---

## 11. What Happened in This Session

1. Read AGENTS.md, WORKBOOK.md, LANGUAGE.md
2. Established authority rules in AGENTS.md
3. Created project directory structure
4. Analyzed 7 original examples for semantic primitives
5. Proposed Semantic Model v0.1 (structured representation)
6. Tested model against 11 new examples — found gaps
7. Identified 7 candidate concepts: Entity, Relationship, Constraint,
   Conditional, Multiplicity, Event, Action
8. Reduced to 6 concepts through analysis: Entity, Property,
   Relationship, State, Condition, Multiplicity
9. Performed semantic closure test — all 20 tested concepts derivable
10. Performed adversarial test — 30 categories tested, found 2 gaps
    (nondeterminism, prohibition)
11. Created SESSION_STATE.md to preserve project state

### Session 2

12. Built one real small homepage (`.tmp/homepage-experiment/`) with
    header/logo/nav/hero/footer and three distinct cards
13. Represented it using ONLY the 6 concepts — found 7 concrete problems
14. Classified the problems: 4 genuine missing capabilities
    (per-instance data, constraints, positional intent, ambient
    entities), the rest representational/implementation
15. Verified the HTML implementation in a browser (works)
16. Recorded findings in RESEARCH_LOG.md and this file
17. Made NO decisions — the semantic gaps are presented to the user,
    who owns the language-design decision

### Session 3 (findings only)

18. Reanalyzed the four gaps (`.tmp/homepage-experiment/GAP-REANALYSIS.md`)
  - distinct instances → PRESERVED WITH COMPOSITION (one Entity per
    instance; count falls out of counting entities)
  - constraints (equal width) → PRESERVED WITH COMPOSITION (group
    Property)
  - positional intent → PRESERVED (Relationship to container + State)
  - ambient entities → PRESERVED (Environment-supplied Entity +
    dictionary convention)
19. Central finding: 3 of 4 gaps dissolve on re-reading; the concept
    that weakened instead was **Multiplicity**; constraints still the
    most strained, but homepage did not need the normative "must" force

### Session 4 (findings only)

20. Product-list experiment (`.tmp/product-list-experiment/`)
  - Session 3's enumeration-composition does NOT survive an unbounded
    "many products" — requires Multiplicity to carry instance-
    independence semantics
  - "price must be positive" → first genuinely MISSING requirement
    (universal per-member invariant + "must" force)
  - ambiguity exposed: "products have different values" = per-instance
    independence vs mutual distinctness

### Session 5 (findings only)

21. Three-rules experiment (`.tmp/rules-experiment/THREE-RULES-ANALYSIS.md`)
  - price positive = domain knowledge (dictionary) OR program rule —
    ambiguous sentence; dictionary reading needs no new concept
  - names unique = genuinely program-imposed, no dictionary escape —
    the strongest signal for new meaning
  - image required = schema (Property) + requiredness (template)
  - failure shape: SAME skeleton ("for every member: P must hold"),
    DIFFERENT absorber (dictionary/template/program)
  - "must" force already has a PROPOSED home: workbook §8 priority model
  - conclusion: don't add a blunt "Constraint"; investigate member
    indexing + §8 priorities + dictionary/templates first

### Session 6 (findings only)

22. Single-problem test: `products must have unique names`
    (`.tmp/unique-names-experiment/UNIQUE-NAMES-ANALYSIS.md`)
  - strongest representation: collection predicate + §8 MUST, with the
    predicate meaning supplied by the Dictionary
  - works IFF priorities can attach to propositions (truth-claims), not
    only behaviors — currently undefined
  - the genuinely new element is the PROPOSITION, not "constraint"
  - **member indexing is NOT a semantic prerequisite** (REVISES
    Sessions 4-5); it is engine implementation, like an SQL UNIQUE index
  - refined Session 5 claim: "equal width" vs "unique names" share the
    SAME semantic shape (`MUST · proposition over a collection`);
    generation-vs-verification is enforcement, not semantics
  - verdict: convergent evidence for a real, recurring shape, but the
    gap is small enough that completing PROPOSED §8 (priority-to-
    proposition attachment) may suffice instead of a 7th core primitive

### This window (ideas recorded)

23. User proposed the intent-expression spectrum (WORKBOOK §2a) and the
    minimum-utterance definition of "easy" (WORKBOOK §2b). The
    minimum-utterance experiment is PENDING — not yet run.

### Session 7 (findings only) — Minimum-Utterance Experiment

24. Ran the minimum-utterance experiment
    (`.tmp/minimum-utterance-experiment/`): one real page (the existing
    homepage), a browser-verified baseline, correct-reproduction defined
    BEFORE minimizing, and four utterance levels (L0 over-specified, L1
    reasonable, L2 minimal natural, L2+ responsive-clause-dropped probe).
  - L0/L1/L2 all reproduce the page correctly (7 axes, 0 console errors).
    Minimum utterance ≈ 50 natural-language words: owned content + entity
    structure + multiplicity with per-instance shape + one behavior
    ("cards stack on mobile").
  - Implementation detail contributed ZERO necessary words — every CSS
    mechanism, pixel, color, and breakpoint was correctly inferred.
  - **Mobile responsiveness is NOT an inferred default (measured):** L2+
    had no media query; mobile only survived via a flex-wrap side effect.
    The human must say the responsive intent.
  - **Card content under-determination:** "three cards, each with its own
    title and description" supplies shape but not content; the AI must
    invent placeholder or ask (workbook §9). The source page's own card
    text is placeholder too.
  - **"Each with its own" is human-trivial but model-hard** — the 
    distinct-instances representation question from Sessions 2-4, located
    on the MODEL side, not the human interface side.
  - No "constraint" capability was needed for this page: equal width was
    correctly inferred as a default (no "must" spoken).
  - Evidence FOR the core hypothesis, but only one simple page. No
    decisions, no concept finalized, LANGUAGE.md/WORKBOOK.md untouched.

---

### Session 8 (building) — First Real MyLanguage Program

25. **Direction change (DECIDED):** no more experiments as the goal.
    Process = build → hit problem → solve → continue. HTML is only a
    target, not the language.
26. Built the first real semantic program: `examples/homepage/`
    (homepage.semantic.json + 9 dictionary entries + byte-identical
    homepage.html + BUILD-NOTES.md).
27. The old gaps survived contact with a real artifact:
    - distinct instances → one Entity per instance, `kind` = shared
      schema, card-group + multiplicity tie them. No new concept.
    - footer-at-bottom → "footer" as a kind + page default (vertical
      stack, growing middle child). No position concept needed.
    - cards-stack-on-mobile → condition + state on environment-provided
      `viewport`; "narrow" is a dictionary class, 768px is implementation.
    - side-by-side/equal-width/even-spacing → card-group dictionary
      default, out of the program.
28. Provenance solved structurally: program = intent, dictionary =
    defaults (a per-property `source` tag was dropped as noise).
29. Verified: JSON valid, all references resolve, all content properties
    match the verified homepage.html; responsive condition matches the
    browser-verified behavior.
30. NOT done: no parser/compiler/runtime/extension/syntax; LANGUAGE.md
    still empty; no concept finalized.

### Session 9 (building) — First real implementation

31. **Direction change (DECIDED, user):** MyLanguage is no longer a
    research/prototype exercise — build it as a real language, by using
    it. `.ine` (intent expression) is the working file-extension choice
    (PROPOSED).
    Do NOT build "natural language → HTML"; HTML is one target of a real
    language pipeline.
32. **Smallest useful program:** `examples/hello/hello.ine`:
    `make page` then `page title "Hello, MyLanguage"`. It is exactly the
    two-statement program the user proposed as Stage 2, discovered rather
    than invented.
33. **The pipeline was built real, one stage at a time:**
    `src/mylang/lexer.py` (text → tokens; keywords, identifiers allowing
    `-`/`_`, quoted strings, numbers, `#` comments, line-based),
    `src/mylang/parser.py` (tokens → syntax statements; `make <name>
    [kind]` and `<name> <property> "value"`), `src/mylang/semantic.py`
    (statements → Model with entities + properties; VALIDATES: property
    on undeclared entity = error, duplicate entity = error),
    `src/mylang/backend_html.py` (Model → HTML), `src/mylang/cli.py`
    (command line). Entry: `python mylang.py <file.ine> [-o out]`.
34. **Verified:** 24 unittest tests pass (lexer/parser/semantic/backend/
    end-to-end + a golden-output comparison); output HTML browser-verified
    (document title and body heading render "Hello, MyLanguage", 0
    console errors).
35. **First real limitation (found by using, not by speculating):** the
    HTML backend only understands kind `page`. `make header` fails with
    "the html backend does not support this kind yet". The dictionary/
    kind system is therefore NOT wired into the engine — hard-coded in
    the backend today. Also: property values are strings only; entities
    cannot yet be related (no `inside`), so nothing can nest in a page.

### Session 10 (correction + Say vertical slice)

36. **Correction (user):** Session 9 built a DIFFERENT milestone than
    requested. The requested vertical slice was
    `say "Hello, world!"` → lexer → parser → interpreter → stdout.
    Explicit instructions: keep the existing `make page` pipeline and
    tests; do NOT translate `say` into HTML; do NOT make `say` another
    entity/property; `say` must execute and print to stdout; verify by
    actually running it; do not move on until verified.
37. **Implemented (smallest change):** `say` added as a keyword
    (`KEYWORDS = {"make", "say"}`), a `SayStatement` in the parser
    (`say-stmt := "say" "value"`), and a new pipeline stage
    `src/mylang/interpreter.py` with `execute(statements)` producing the
    runtime output values. The CLI prints each output to stdout BEFORE
    the summary lines. A program with no page writes no target
    (`target: the program does not describe a page`) — `say` never
    reaches HTML. `examples/say/say.ine` added; existing
    `examples/hello/hello.ine` untouched.
38. **Verified:** 33 tests pass (24 preserved + 9 new for `say`).
    `python mylang.py examples/say/say.ine` prints `Hello, world!` to
    stdout; `python mylang.py examples/hello/hello.ine` still writes
    `output/hello.html`. A `.tmp` program with `make page` + `say` in one
    file showed both (stdout line + HTML file, exit 0) working together.
39. **What the language revealed by building (OPEN, not decided):** the
    program now clearly has TWO kinds of statements — **describing**
    (`make page`, `page title "..."`: model → target) and **doing**
    (`say "..."`: execution → stdout). Not solved abstractly; recorded as
    the real question the next real program must answer. See WORKBOOK
    §26 and LANGUAGE.md §5a.

### Session 11 (native-execution direction + emit-C target)

41. **Direction refinement (user, recorded PROPOSED, NOT a locked
    decision):** MyLanguage is its own language and semantic system;
    existing languages/APIs/runtimes/browsers/machine-code technologies
    are things it can interoperate with or target, not what defines its
    meaning. The old "translation layer" framing is an earlier working
    hypothesis. HTML is one backend, not the destination.
42. **User priority for this phase:** actual execution over exhaustive
    testing — first prove that MyLanguage source becomes something the
    real computer executes.
43. **Built the smallest native slice:** `.ine → lexer/parser →
    backend_c.emit → external C compiler → .exe → run on CPU`.
    - `src/mylang/backend_c.py` — lowers `say` statements to
      `printf("%s\n", "value")` (value is DATA, never format — a
      correctness detail found while building).
    - `src/mylang/native.py` — compiler discovery (`MYLANG_CC`, `zig`,
      `clang`, `gcc`), compile, run. All artifacts to `.tmp/native/`.
    - `src/mylang/cli.py` — added `--native` flag; HTML path untouched.
    - `examples/native/hello.ine` — `say "Hello, native machine code"`.
    - 39 tests pass (native e2e test skipped: no compiler on machine).
44. **Tooling blocked (found, not predicted):** clang was installed but
    cannot link on this machine — missing MSVC runtime `libcmt.lib`. The
    chosen toolchain is **Zig** (`zig cc`): bundles clang + lld + libc,
    produces native Windows executables with no extra SDK. When the user
    installs it, `test_native_executable_prints_on_the_cpu` must run
    green and `python mylang.py examples/native/hello.ine --native`
    must print the say value after running the exe.
45. **Permanent Temporary-File Policy** recorded in AGENTS.md: every
    MyLanguage-generated probe/source/exe/object/compiler-test/
    intermediate artifact goes in project `.tmp/` (gitignored); final
    committed outputs stay in `output/`.

### Session 12 (native milestone VERIFIED)

46. **Zig 0.16.0 installed by the user** (user PATH). Toolchain gate is
    now OPEN.
47. **All 39 tests pass, none skipped** — the native e2e test
    (`test_native_executable_prints_on_the_cpu`) now compiles AND runs
    on this machine.
48. **VERIFIED — smallest native slice works end to end:**
    `python mylang.py examples/native/hello.ine --native` →
    lexer → parser → `backend_c.emit` → `.tmp/native/hello.c` →
    `zig cc` → `.tmp/native/hello.exe` → CPU → stdout
    `Hello, native machine code`, exit 0. The `.exe` is a valid Windows
    PE binary (first two bytes `4D 5A`, ~778 KB, x86-64 machine code),
    not a script. It runs standalone.
49. **HTML backend still verified** alongside: `hello.ine` still writes
    `output/hello.html` byte-identical. Both targets coexist.
50. First real confirmation of the Session 11 direction: MyLanguage
    source now demonstrably becomes something the actual computer
    executes.

### Session 13 (typed values: strings + numbers)

51. **User tested the language with a real program:**
    `make person` / `person name "Alice"` / `person age 25`. It failed:
    `error: property value must be written in quotes (line 3)`. The wall
    was real and obvious — a person's `age` is a number, not a string.
52. **User decision:** add numbers. Also: keep the language simple and
    working efficiently/("dynamically") — typed values are the point of
    the language.
53. **Implemented (smallest change):** values are now typed.
    - Parser: property and `say` values accept a NUMBER token; number
      text becomes `int` when it has no `.`/`e`, else `float`.
    - Semantic: the model stores typed values unchanged.
    - Native backend: `printf("%s\n")` for strings, `printf("%d\n")` for
      integers, `printf("%.17g\n")` for decimals.
    - HTML backend: `str()` applied before escaping (a numeric title no
      longer crashes).
54. **Verified:** 47 tests pass, including 3 new parser tests, 2 new
    interpreter tests for numbers, and 2 native e2e tests (numbers print
    from the CPU). `make person` + `person age 25` now builds a model
    with `age: 25` (int). Native `say 25` prints `25` from real machine
    code.
55. **Not changed (design questions untouched):** `say person age`
    (reading a property at runtime) is still invalid — that is the
    describing/doing composition question (workbook §26), deliberately
    NOT solved yet. Values are only strings and numbers today.

### Session 14 (say name property — describing feeds doing, compile-time)

56. **Question answered in practice:** the workbook §26 open question
    "can description feed behavior?" is now concretely tested. The
    program `make person`/`person name "Alice"`/`person age 25`/`say
    person age` previously failed with "expected a string or a number
    after 'say'". The user chose **Choice A: compile-time property
    resolution** with compile-time errors for missing properties.
57. **Implemented (smallest change):**
    - Parser: `say-stmt := "say" value | "say" name property`. A
      `PropertyRef(target, name, line)` appears as the value until
      resolved.
    - Semantic: new `resolve(statements, model)` turns a `PropertyRef`
      into the model's stored literal. Missing property or undeclared
      entity → `SemanticError` with the offending line.
    - CLI: both `--native` and HTML paths resolve before executing.
    - No runtime model, no variables, no mutation, no expressions, no
      dynamic lookup — deliberately.
58. **Verified:** 57 tests pass (10 new: parser ref, 7 resolution, 2
    native e2e). The exact real program `say person age` now prints
    `25` from a native PE exe; `say person height` → "'person' has no
    property 'height' (line 3)"; `say ghost age` → "'ghost' was not
    declared" — both compile-time errors, exit 1. HTML path and
    `hello.ine` golden output untouched.
59. **Recorded design facts:** resolve is COMPILE-TIME only. The
    interpreter/backends only ever see literal values; `say person age`
    and `say 25` lower to identical output (`printf("%d\n", 25)`).

### Session 15 (audit: every implemented capability now has a real example)

60. **Audited** code, tests, examples, docs. Found three implemented
    capabilities that were covered by tests but had NO real example
    program: `make name kind` (explicit kind), float values, and
    `say name property` read natively.
61. **Built the smallest real example** that exercises all three at once
    using only existing capabilities — `examples/alice/alice.ine`:

    ```
    make alice person
    alice name "Alice"
    alice age 25
    alice height 1.7

    say alice name
    say alice age
    say alice height
    ```
62. **Verified natively:** `python mylang.py examples/alice/alice.ine
    --native` prints `Alice`, `25`, `1.7` from a real PE exe (exit 0).
    Emitted C uses `printf("%s\n", ...)`, `printf("%d\n", 25)`,
    `printf("%.17g\n", 1.7)` — confirming the float round-trip slice
    works end-to-end.
63. **No new language concept was needed** — the exercise exposed a
    documentation/coverage gap, not a missing capability. Full suite:
    57 tests pass. `.tmp/native/` cleared of stale probe artifacts.

### Session 16 (the real homepage slice: containment "inside")

64. **The project's real task became the driver:** the homepage in
    `examples/homepage/` is the language's one real test. The user
    chose the smallest slice first: **page, header, logo, navigation,
    containment.** The user's explicit constraints: don't add
    multiplicity/conditions/states/animations/runtime models unless the
    slice genuinely requires them; don't redesign the architecture;
    preserve both backends; use `.tmp/`; keep proposed/decided distinct.
65. **What "inside" means here (EXPERIMENTAL, decided for this slice):**
    a containment relationship `X inside Y` — a tree, not a graph. X is
    a child of Y. Both must be declared first; one parent per entity; no
    self-parenting; no cycles. Recorded as EXPERIMENTAL because it is
    the smallest real slice of the PROPOSED Relationship concept, not a
    decision about the full concept.
66. **Implemented:**
    - Lexer: `inside` is a keyword.
    - Parser: `InsideStatement(child, parent, line)`; `name inside name`.
    - Semantic: `model.relationships` (`child → parent`), with
      compile-time errors: undeclared child/parent, double parenting,
      self-parenting, cycles.
    - HTML backend: now dictionary-driven. `dictionary/<kind>.json`
      gained a machine-readable `element` field (page→div, header→header,
      logo→div, navigation→nav); the backend renders the page tree by
      nesting children, and rejects kinds with no dictionary entry.
    - Native backend: unchanged — `inside` produces no native output
      (`say` still the only lowered statement).
67. **The real slice:** `examples/homepage-topbar/topbar.ine`:

    ```
    make page
    page title "Company Name"
    make header
    header inside page
    make logo
    logo text "Company Name"
    logo inside header
    make navigation
    navigation inside header
    say page title
    ```

    Renders a real nested page (golden `tests/expected/topbar.html`),
    and `--native` prints `Company Name` from the compiled exe — one
    program, both targets.
68. **72 tests pass** (15 new). This is the first time the engine
    actually used the dictionary, and the first real Relationship.
    `hello.ine` golden output is byte-identical (page path untouched
    when a page has no children).

### Session 16b (the hero slice: deeper nesting, still no new concept)

69. **Next homepage slice, smallest possible:** the hero region. Reuses
    everything — `inside` now nests three levels deep
    (`page > main > hero`), and two more dictionary kinds come into
    play (banner, container).
70. **What changed:** dictionary gained `element` for banner (div) and a
    new `container` kind (div). `examples/homepage-hero/hero.ine`:

    ```
    make main container
    main inside page
    make hero banner
    hero text "Welcome to Our Site"
    hero inside main
    ```

71. **Verified:** 73 tests pass (golden `tests/expected/hero.html`). The
    program renders nested HTML AND compiles to native (`Company Name`
    from the exe). No new language concept was needed — the correct
    kinds were simply named explicitly (`make hero banner`), which is
    what make-with-kind was built for.
72. **Recorded:** the dictionary now declares kinds: page, header,
    logo, navigation, banner, container, card, card-group, footer,
    viewport. `defaults`/`guess` still unused by the engine.

### Session 17 (visual renderer experiment)

73. **User chose a backend experiment instead of the next language
    feature.** Build the smallest possible visual proof that the semantic
    Model can drive a non-HTML target. No Multiplicity, no new language
    concepts. The HTML backend and native backend remain untouched.
74. **Built:** `src/mylang/backend_visual.py` — a tkinter adapter that
    consumes the SAME Model that the HTML backend consumes and opens a
    real OS window. Each dictionary kind maps to a distinct color and
    layout. The containment tree is walked recursively, just like the HTML
    backend's `_render_children`.
75. **CLI:** `--visual` flag added to `mylang.py`. Invoked as
    `python mylang.py <file.ine> --visual`. Opens a tkinter window, prints
    entity/property counts to stdout, runs mainloop.
76. **Verified:** `examples/homepage-hero/hero.ine` opens a real window
    with title "Company Name", 800x600, showing: white page frame with
    title heading, dark header bar with bold white logo text on the left
    and navigation on the right, light gray container filling the middle,
    and blue banner with "Welcome to Our Site" in large white text.
    Window created and destroyed cleanly. All three backends coexist: HTML
    golden output byte-identical, native exe prints "Company Name", visual
    window opens.
77. **17 new tests** added to `VisualBackendTests` in
    `tests/test_mylang.py`. Test the pure helper functions
    (`_children_of`, `_kind_of`, `_bg`, `_fg`, `_is_leaf`, `_has_text`)
    and the `render()` function (returns a `tk.Tk`, title override works,
    no-page/multiple-pages raise `VisualError`, hero.ine builds a valid
    model and creates a window). Total: **90 tests pass**.
78. **What was NOT changed:** no new language concepts. No dictionary
    changes. No semantic model changes. No parser/lexer changes. The
    renderer is a pure backend adapter experiment — it reads the Model,
    nothing else.

### Session 18 (the three-cards slice: layout & repetition discovered)

79. **Next slice:** expand `hero.ine` with three feature cards inside the
    main container, using EXISTING concepts only — no new syntax, no
    Multiplicity yet. Built `examples/homepage-cards/cards.ine` (27
    lines, 11 entities, 10 properties): hand-written `card-1/2/3` with
    `make <name> card`, `title`/`text` properties, `inside card-group`.
80. **Dictionary:** `card`, `card-group`, `footer` gained the `element`
    field (article, div, footer) so the HTML backend can render them —
    the only dictionary change, and it extends the existing pattern the
    engine already relies on.
81. **All three backends validated:**
    - HTML: golden `tests/expected/cards.html` (byte-identical test).
    - Native: PE exe prints `Company Name`, exit 0.
    - Visual: window opens; widget geometry measured (below).
82. **Pain point 1 — no side-by-side layout (measured):** all cards
    render full-width and STACK vertically (card-1 y=4, card-2 y=86,
    card-3 y=168; each 784px wide in an 800px window). The dictionary's
    `card-group` entry already declares `layout: row` but NO engine
    applies it. HTML emits no CSS; the visual backend packs generic
    siblings top-to-bottom (only the header is hard-coded LEFT/RIGHT).
83. **Pain point 2 — card titles silently dropped:** cards carry
    `title "Fast"/"Simple"/"Reliable"` in the model, but NEITHER backend
    renders `title` on a card (only `text` becomes content; `title` is
    special-cased only for the page root). Dictionary says cards contain
    `["title", "description"]` but no backend reads it.
84. **Pain point 3 — repetition / Multiplicity:** expressing "three
    cards" took 9 near-identical statements (make + property + inside per
    card). This is the concrete measured case for the PROPOSED Multiplicity
    concept — the workbook's prediction that three cards would be the
    first slice needing it is now confirmed empirically.
85. **Pain point 4 — footer not pinned:** footer renders at y=454 of a
    600px window despite `footer.json` declaring
    `position: "bottom of page, always"`; neither backend implements it.
86. **Full suite: 94 tests pass** (90 + 2 golden/HTML for cards + 2
    visual for cards). Full findings in `.tmp/cards-slice-findings.md`
    including options presented but NOT implemented (backend honors dict
    `layout: row`; backend renders card titles; Multiplicity as the next
    language feature). No language feature was added this session.

### Session 19 (cards made to work: backend-only, no language change)

87. **User directive:** "make this language functional as fast as
    possible, even if it is not exactly complete." Any of the three
    proposed directions is fine; working results give motivation. Agent
    chose options 1+2 (backend/dictionary renderer work) — the fastest
    path to a working homepage with zero language risk. Multiplicity
    stays PROPOSED.
88. **Dictionary:** machine-readable top-level fields added to two
    entries, as renderer hints in the same class as `element`:
    `card-group.json` → `"layout": "row"`; `footer.json` →
    `"position": "bottom"`. These are backend configuration, NOT
    language semantics (AGENTS.md guard respected).
89. **Visual backend rewritten** (`src/mylang/backend_visual.py`): new
    helpers `_dictionary_entry`, `_layout_of` (row/stack, default
    stack), `_position_of` (bottom/flow, default flow); `_render_entity`
    now takes a `side` parameter and `_pack_children` places children
    side-by-side (row), pinned-bottom, or in-flow; the `card` kind
    renders `title` as a bold heading + `text` as a wrapped body with a
    highlight border. All existing helper names kept so the 17 Session-17
    tests still pass.
90. **HTML backend updated** (`src/mylang/backend_html.py`): `_read_entry`
    + `_layout_for_kind`; `_open_tag` emits `style="display:flex;gap:20px"`
    on a row-layout node and `style="flex:1"` on children of a row parent;
    `_render_children` gained a `parent_kind` parameter and renders a
    leaf's `title` as `<h3>`. Text-only leaves stay single-line, so the
    hero/topbar/hello goldens are byte-identical (verified).
91. **Measured (geometry probe, `.tmp/geometry_probe.py`):** cards now
    render SIDE-BY-SIDE in the row (card-1 x=6 w=271, card-2 x=289
    w=246, card-3 x=547 w=239, all y=6) instead of stacked full-width.
    Footer pinned at y=561 of 600px (was y=454, floating). Card titles
    "Fast"/"Simple"/"Reliable" visible as headings in BOTH backends.
92. **Tests:** `tests/expected/cards.html` golden regenerated; 8 new
    tests (HTML row-layout styles, HTML card `<h3>` titles, `_layout_of`
    unit, `_position_of` unit, visual cards-packed-left integration,
    visual footer-pinned-bottom integration). **Full suite: 102 tests
    pass** (94 + 8). No new language features were added.

### Session 20 (name + extension DECIDED)

93. **Rename (DECIDED by user):** the language's name is **Intent
    Expression** (replacing the temporary working name
    "Intent-First Programming Language" in WORKBOOK/SESSION_STATE/
    RESEARCH_LOG identity and status), and the source-file extension is
    now **`.ine`** (ine = intent expression), DECIDED — no longer
    PROPOSED. All example programs renamed (`git mv`), and every
    `.int` reference in docs, tests, and code (cli help, lexer docstring,
    example comments) updated to `.ine`. Kept per the user's scope choice:
    "MyLanguage"/`mylang` remain the project/tool name.
94. **Verified:** full suite 102 tests pass; `python mylang.py
    examples/hello/hello.ine` still writes `output/hello.html`.

### Session 21 (Multiplicity — `make <count> <kind>`)

95. **User chose Multiplicity as the next feature** (from the §12
    options), and chose **Option A** for its form: a count on `make` that
    creates N named entities; grouping into a container stays a separate
    `inside` statement. No new keyword — `make 3 card` is grammar-only.
96. **Implemented (parser-only expansion):** `make <count> <kind>` parses
    into N `MakeStatement`s — ids `<kind>-1` … `<kind>-<count>`, all of
    kind `<kind>`. The lexer, semantic analyzer, and all three backends
    are untouched: the model holds one entity per member, byte-identical
    to writing them by hand. Count must be a positive whole number
    (`make 0 card`, `make 3.5 card` → syntax error; `make -3 card` can't
    even lex).
97. **`cards.ine` rewritten with the feature:** the three handwritten
    `make card-N card` lines became one `make 3 card`. **The golden
    `cards.html` is unchanged (byte-identical test still passes)** — a
    direct proof that multiplicity is sugar over the same model. 11
    entities, 10 properties, same as before.
98. **Verified:** full suite **113 tests pass** (102 + 11 new). Native
    probe in `.tmp/multiplicity-probe/people.ine`:
    `make 3 person` expanded to person-1/2/3, `say person-1 name` etc.
    printed `Alice`/`Bob`/`Cara`/`30`/`35` from a real PE exe, exit 0.
99. **Recorded limits (still PROPOSED, not decided):** grouping and
    per-instance properties still use existing `inside`/property
    statements; there is no way to NAME a group, say "all members", or
    apply a property to every member at once. Those need the
    collection/group semantics that remain PROPOSED.

### Session 22 (Collection & Group semantics — `group <name> = <members>`)

100. **User chose the next architectural horizon: collection & group
    semantics** (group naming, per-member property application, collective
    addressing), then picked **Option A (group only, minimal)** from the
    three scope levels presented. What was actually implemented ended up
    covering a small extra slice of goal 2 — a property whose target is a
    group applies to every member — because it is the same 8 lines of
    expansion logic as the collective `inside`. Flagged to the user; they
    may narrow it later.
101. **Implemented (semantic-analysis expansion, parser-only otherwise):**
    - Lexer: `group` is a keyword; `=` is a new EQUALS token.
    - Parser: `GroupStatement(name, members, line)`; `group <name> = <m1> <m2> ...`.
    - Semantic: `model.groups` records each group; `_expand_groups` runs
      BEFORE entity validation and rewrites group-targeted statements into
      one ordinary statement per member (collective `inside` → N
      `inside`s; group property → N property statements). All existing
      checks (undeclared child/parent, self-parenting, double-parenting,
      cycles) apply unchanged to the expanded statements. Group names are
      NOT entities and may not collide with entity names; a group cannot
      be `say`n and cannot be a member of another group (flat groups).
    - Backends: untouched — they only ever see the expanded model.
102. **`cards.ine` rewritten again:** the three `cards inside card-group`
    lines became `group cards = card-1 card-2 card-3` + `cards inside
    card-group`. **Golden `cards.html` is unchanged (byte-identical test
    still passes)**. Full suite: **130 tests pass** (113 + 17 new
    GroupSemanticsTests).
103. **Verified natively:** probe `.tmp/group-probe/team.ine` —
    `make 3 member` + `group team = ...` + `team inside department` +
    `team role "engineer"` → the native exe prints `Engineering`,
    `engineer` ×3 (group property applied to all three members), and
    `Alice`/`Cara` (per-member values). `say cards title` correctly fails
    ("not declared with make") — a group cannot be read as an entity.
104. **Recorded limits:** no `every` keyword, no "all members of every
    group", group as a member of a group unsupported, collective `say`
    unsupported. These remain PROPOSED.

### Session 23 (Naming: language "Ine", CLI `ine`, package rename)

105. **User named the language (DECIDED):** "Ine" — the language name,
    file extension `.ine`, and the terminal command are all `ine`
    (`ine hello.ine -o hello.html`, `ine hello.ine --native`). The
    GitHub repository moved from `intent-language` to
    https://github.com/sudo-akash-sys/Ine (remote updated locally;
    repo renamed on GitHub by the user).
106. **Implemented the rename:**
    - `src/mylang/` → `src/ine/` (git rename, history preserved);
      internal imports were already relative, so only `cli.py`
      (prog="ine"), `native.py` (`MYLANG_CC` → `INE_CC`), and the
      visual backend's default window title ("MyLanguage" → "Ine")
      changed.
    - Root launcher `mylang.py` → `ine.py`; tests
      `tests/test_mylang.py` → `tests/test_ine.py` (imports updated).
    - Added `pyproject.toml` (setuptools, `src` layout) with the
      console script `ine = "ine.cli:main"`; `pip install -e .` builds
      an `ine` command. Windows Store Python puts `ine.exe` in a
      `Scripts/` dir NOT on PATH, so `python -m ine` is the documented
      fallback (identical behavior).
    - `*.egg-info/` added to `.gitignore` (build artifact).
107. **Verified:** full suite renamed green — **130 tests pass**;
    `python -m ine examples/hello/hello.ine -o .tmp/...` and
    `python ine.py ...` both work identically; `pip install -e .`
    succeeds. Docs current-usage references updated (README commands,
    LANGUAGE.md invocations, clone URLs); historical log entries retain
    the old `src/mylang/` wording as a record of then-current state.

---

### Session 25 (dictionary correction: properties vs structural members)

107. The read-only semantics investigation (Q1–Q8 + sections A–F) found
    `defaults.contains` mixed content-properties (title, text,
    description, subtitle) with genuine child entities. **User decisions
    (DECIDED):** the language has four semantic constructs (Entity, Kind,
    Property, Relationship; Value attaches to a Property); `title`/`text`
    are properties in real programs; `contains` = structural children
    only; canonical direction is `child inside parent`; no sibling
    inference from kind buckets; the dictionary stays advisory (never a
    validator); no syntax change, no autocomplete, no synonym
    normalization.
108. **Data:** `dictionary/universal.json` added — universal `title`/
    `text` content properties on every regular kind. `contains` lists
    re-grounded in real programs: page → header/footer/container (topbar,
    cards, hero), header → logo/navigation (topbar, cards), container →
    banner (hero), card-group → card (cards), section → button/image.
    title/text/description/subtitle removed from all `contains` lists.
    `interactive` in button/logo de-booleaned — Ine has no boolean
    values; it is now a string hint marking the concept unsupported.
109. **Reader (`src/ine/dictionary.py`):** `properties_for`/`value_hint`
    include universal title/text; `members` reads `contains` with notes
    phrased `<child> inside <kind>`; `kind`-bucket sibling inference and
    the `related()` API removed. Backends untouched (they never read
    `contains`).
110. **Tests:** DictionaryTests rewritten — title/text are properties,
    header suggests logo/navigation as children, card suggests no
    title/text children, member suggestions use `child inside parent`,
    sibling inference gone, universal property suggestions work. 154
    tests pass; all four goldens (hello/topbar/hero/cards) rebuild
    byte-identical.

---

### Session 26 (reverse containment in the dictionary)

111. Closed the §36 usability gap (report D): placement was only
    discoverable one way (`ine --dict <parent>` lists children; the
    reverse never existed, and `card-group`/`section` had no parent at
    all).
112. **Data changes, grounded only where a demonstrated example exists:**
    `page.json` contains now includes `section` (grounded by
    `examples/dictionary-demo.ine`, built/rendered in Session 25);
    `container.json` contains now includes `card-group` (grounded by
    `cards.ine`). No new schema.
113. **Reader:** added `parents(kind)` to `src/ine/dictionary.py` — the
    reverse of `members`, derived by inverting `contains` over regular
    kinds (ambient/pseudo entries excluded).
114. **CLI:** `ine --dict <kind>` prints a "belongs inside:" block, e.g.
    `section inside page`, `card-group inside container` — containment is
    now discoverable in both directions.
115. **Tests:** five new DictionaryTests (reverse direction for known
    relationships, card-group→container + section→page, roots/unknowns/
    ambient return [], content concepts title/text/description are never
    parents). 159 tests pass; all goldens and the demo render unchanged.
    No syntax/parser/semantic/backend changes.

---

### Session 27 (the editor experience: Ine VS Code autocomplete)

116. **Goal:** cross the line where Ine stops being a language with a CLI
    and becomes a usable programming environment — the smallest possible
    editor completion, so a user can open a `.ine` file and have the
    dictionary help *while typing*. No AI, synonyms, fuzzy matching,
    diagnostics, formatting, hover, or packaging; the interaction is the
    test.
117. **Architecture (investigated before coding, then decided):** the
    extension must NOT hold a second vocabulary. Reading
    `dictionary/*.json` from TypeScript was rejected — the raw JSON is
    only the data; re-deriving makeable-filtering, universal title/text
    merging, member phrasing and `parents()` in another language is
    exactly how "Ine says X, VS Code says Y" starts. Instead the
    extension spawns the existing Python package as a JSON subprocess and
    renders its answer; TypeScript is a pure proxy with zero Ine
    vocabulary. `src/ine/autocomplete.py` decides which dictionary query
    a cursor maps to (make → `makeable()`, kind → `suggest(kind)`,
    inside → `parents(kind)`) and answers one stdin/stdout JSON query.
118. **Engine (`src/ine/autocomplete.py`, new):** lenient entity
    resolution with no full parse — a name is a dictionary kind, an
    entity from `make name [kind]`, a numbered entity from
    `make <count> <kind>` (`make 2 card` → `card-1`), or a group whose
    members share a kind. Unknown names → empty suggestions. Errors never
    break the protocol (`{"error": ..., "items": []}`). The module
    self-prepends its `src/` to `sys.path`, so it is immune to the root
    `ine.py` launcher shim shadowing the `ine` package.
119. **Extension (`editor/vscode-ine/`, new):** `extension.js` forwards
    `{buffer, line, column}` to `python src/ine/autocomplete.py` under
    the workspace root and maps items to `CompletionItems`. Activates
    only for `.ine` (`onLanguage:ine`); `INE_PYTHON` overrides the
    interpreter.
120. **Tests:** 31 new (`tests/test_autocomplete.py`) — context
    detection, entity resolution (kind / make-with-kind / multiplicity /
    group / unknown / digits-as-counts), completion content and types for
    the three contexts, and the stdin/stdout protocol contract including
    a garbage-input guard. **190 tests pass** (159 + 31).
121. **Verified end-to-end via the extension's exact subprocess path:**
    `make he` → kinds incl. `header`; `header inside p` → `page`;
    `header ` → `logo`, `navigation`, `height`, `title`, `text`, ...;
    `card-1 ` (from `make 2 card`) → card properties; `cards inside `
    (group) → `card-group`. All goldens byte-identical; the dictionary
    and its data are unchanged. No syntax/parser/semantic/backend change.

---

### Session 28 (autocomplete responsiveness)

122. **Manual UX test found two gaps, both editor-harness, not
    dictionary:** (1) completion only auto-triggered after a space —
    typing `make h` never asked the dictionary; (2) one fresh Python
    process per keystroke (~140 ms; felt slow).
123. **Trigger fix:** the provider registers `" "` plus the ASCII letters
    as trigger characters (generic editor characters, zero Ine
    vocabulary), so `make h` now pops up while the word is being typed.
124. **Latency fix:** one long-lived Python process. `autocomplete.py`
    answers a JSON-lines request stream in `main()` (one request → one
    response; EOF still exits for one-shot use — the Session-27 protocol
    tests still pass unmodified). `extension.js` gained a `DictionaryWorker`
    (FIFO queue, in-order matching, 4 s timeout, auto-respawn, eager start,
    killed on deactivate).
125. **Measured:** warm-session query **0.3 ms** vs **~140 ms** fresh
    process (`tmp probe .tmp/latency_probe.py`). First keystroke still
    pays Python startup; the rest are essentially free.
126. **Tests:** three new ProtocolTests — persistent multi-line answers,
    `id` echo, error line doesn't kill the loop. **193 tests pass**; all
    goldens byte-identical; `ine --dict` unchanged. No dictionary,
    syntax, parser, semantic, or backend change.

---

### Session 29 (property completions insert the value shape)

127. **Goal:** selecting a property like `title` should insert the value
    shape — `page title ""` with the cursor (placeholder) *between the
    quotes*, so the author sees `title` expects text and can type
    immediately.
128. **Investigation (before coding):** `value_hint()` returns a hint
    string, not a type; NO program-writable property has a machine-
    readable value shape in the dictionary (only ambient `viewport.json`
    has `properties: {width/height: "length"}`, and it is not makeable).
    The only defensible text signal is `universal.json` `meaning`, which
    documents `title`/`text` with quoted-string examples, and real
    programs always write them quoted.
129. **Decision (conservative, dictionary untouched):** the engine marks
    only `title`/`text` as text-shaped — `_value_shape()` in
    `src/ine/autocomplete.py` derives this from
    `dictionary._universal_defaults()`. Property items carry an optional
    `value_shape: "text"`; everything else is `None`/absent and behaves
    exactly as before. No invented placeholders.
130. **Editor adapter only:** `extension.js` renders a text-shaped item as
    `SnippetString('title "${1}"')` — the cursor lands between the quotes
    (not after them). VS Code snippet syntax stays isolated in the
    adapter; the engine only reports shapes.
131. **Tests:** six new ValueShapeTests (title/text text-shaped on any
    kind, height/logo none, kind items no shape, labels/inserts
    unchanged). **199 tests pass**; all goldens byte-identical;
    `ine --dict` unchanged. No dictionary, syntax, parser, semantic, or
    backend change.

---

### Session 30 (value shapes move into the dictionary)

132. **Goal:** stop deriving value shapes as a special case in
    `autocomplete.py`; the dictionary itself should describe what kind of
    value a property expects (and eventually which values are allowed).
133. **Evidence survey:** only the two universal content properties have
    value evidence — `universal.json` `meaning` documents `title`/`text`
    with quoted-string examples and every real program quotes them;
    `viewport.json` already carries a `properties` block
    (`width`/`height` → `"length"`), the same idea. `card-group layout`
    is a single `"row"` string, not a set; no safe choice exists.
134. **Dictionary data (one file):** `universal.json` gains
    `"properties": {"title": "text", "text": "text"}` — mirroring the
    `viewport` precedent. A `properties`-block value is a value kind
    (string) or a list of allowed options (future `"choice"`,
    e.g. `"layout": ["row", "column"]`).
135. **Reader:** new public `ValueShape(type, choices)` dataclass,
    `_shape_from()` normalizer (string → named kind, string-list →
    choice, else unknown), and `value_shape(kind, prop)` reader — kind's
    own `properties` block, then the universal entry's. `value_hint`/
    `properties_for` untouched; read from metadata only, never inferred.
136. **Consumers:** `autocomplete.py` no longer knows `title`/`text` — a
    property item's `value_shape` comes from `value_shape(kind, prop)`.
    `extension.js` unchanged (still renders `value_shape: "text"` as the
    `title "${1}"` snippet).
137. **Tests:** 5 new reader tests incl. `_shape_from` capacity (list →
    choice; junk → unknown; existing viewport `"length"` read back).
    **204 tests pass** (199 + 5). Goldens byte-identical;
    `ine --dict <real kind>` unchanged. No syntax/parser/semantic/backend
    change; autocomplete UX unchanged (behavior preserved, provenance
    moved to the dictionary).

---

## 12. Next Step

**DONE (Session 8):** First real MyLanguage program — the homepage's
semantic representation lives in `examples/homepage/`.

**DONE (Session 9):** the smallest Entity/Property toolchain exists and
works: `.ine` read → understood → emits verified HTML.

**DONE (Session 10):** the requested Say vertical slice exists and is
verified: `say "..."` → lexer → parser → AST → interpreter → stdout.

**DONE (Session 11-12):** the smallest native slice is BUILT AND
VERIFIED: `python mylang.py <file.ine> --native` → emit C → `zig cc` →
native `.exe` → runs on CPU. `Hello, native machine code` observed on
stdout from a real PE binary. HTML pipeline untouched and still green.

**DONE (Session 13):** values are now typed — strings and numbers. The
user's `make person` / `person name "Alice"` / `person age 25` program
builds a real model with a numeric age, and native `say 25` prints from
machine code.

**DONE (Session 14):** describing feeds doing — `say person age` resolves
the stored property at COMPILE time and prints it natively. The workbook
§26 question has its first concrete answer.

**DONE (Session 15):** audit closed the coverage gap — every implemented
capability (make/kind, str/int/float properties, say literal, say name
property, native + HTML targets) is now exercised by a real example.
`examples/alice/alice.ine` is the unifying smallest program.

**DONE (Session 16):** the real homepage task started — smallest slice
(`page > header > logo + navigation`) with the first Relationship
(`inside`, containment) and the first real dictionary use. One `.ine`
program now renders nested HTML AND compiles to native.

**DONE (Session 17):** visual renderer experiment — smallest possible
proof that the semantic Model drives a non-HTML target. tkinter window
opens, shows the hero program visually. 90 tests pass. HTML and native
backends untouched. No new language concepts added.

**DONE (Session 18):** three-cards slice — handwritten three-card
homepage using existing concepts only. Documented 4 pain points: no
side-by-side layout (measured), card titles dropped by both backends,
repetition needing Multiplicity, unpinned footer. 94 tests pass.
Options proposed, nothing decided.

**DONE (Session 19):** cards made to work with backend/dictionary-only
changes — NO language feature added. Card-group emits flex row (HTML)
/ side-by-side row (visual), card `title` renders as `h3` (HTML) and a
bold heading (visual), footer pinned to the bottom edge in the visual
window. Measured: cards side-by-side, footer at y=561/600. Delay/latency:
102 tests pass.

**DONE (Session 21):** Multiplicity is implemented as `make <count>
<kind>` — creation sugar that expands into numbered entities
(`make 3 card` → card-1/2/3), parser-only, no new keyword. `cards.ine`
now uses it and the golden HTML is byte-identical (proof it is sugar
over the same model). 113 tests pass; native probe verified on the CPU.

**DONE (Session 22):** Collection & Group semantics — `group <name> =
<m1> <m2> ...` names a collection; `cards inside card-group` and
`cards text "..."` expand to one per-member statement. Golden `cards.html`
unchanged. 130 tests pass; native probe verified on the CPU.

**DONE (Session 25):** the dictionary correction — `contains` now holds
structural children only (re-grounded in real programs); `title`/`text`
are universal content properties; sibling inference removed; dictionary
stays advisory. `ine --dict` no longer implies `title inside card`. All
four goldens byte-identical; 154 tests pass. No syntax, parser, or
backend changes.

**DONE (Session 26):** reverse containment — `ine --dict <kind>` now
reports "belongs inside" (e.g. `section inside page`, `card-group inside
container`), derived by inverting `contains`, with the two previously
orphan kinds grounded in demonstrated examples. 159 tests pass; goldens
unchanged.

**DONE (Session 27):** the editor experience — smallest Ine VS Code
autocomplete prototype. The extension holds no vocabulary: it shells out
to `src/ine/autocomplete.py`, which queries the real `ine.dictionary`
(make → kinds, kind → properties/members, inside → parents) over a JSON
stdin/stdout protocol. 190 tests pass; goldens byte-identical; the
dictionary and its data unchanged. Ine starts becoming a usable
programming environment.

**DONE (Session 28):** autocomplete responsiveness — completions now
auto-trigger while typing words (`make h`) via generic letter/space
trigger chars, and the per-keystroke Python spawn became one long-lived
JSON-lines process (0.3 ms warm vs ~140 ms fresh). 193 tests pass;
goldens byte-identical; dictionary and data unchanged.

**DONE (Session 29):** property completions reveal the value shape —
selecting `title`/`text` inserts `title ""` with the cursor between the
quotes (a snippet, isolated in the editor adapter). Shape is derived in
the engine from `_universal_defaults()`; no dictionary change, no
invented placeholders. 199 tests pass; goldens byte-identical.

**DONE (Session 30):** value shapes moved into the dictionary —
`universal.json` now declares `title`/`text` → `"text"` in a `properties`
block (mirroring the existing `viewport` precedent); new public readers
`ValueShape`/`value_shape`/`_shape_from`; `autocomplete.py` dropped its
title/text special case and consumes `value_shape(kind, prop)`
generically. The representation already describes future enumerated
choices (`"layout": ["row", "column"]`), though none is declared yet for
lack of evidence. 204 tests pass; goldens byte-identical.

**NEXT concrete step (user picks):** the editor prototype (Session 27)
works — dictionaries answer at the cursor from within VS Code, and the
language now has a usable authoring surface. Smallest next candidates:
(a) property *value* completions (`page title "..."` suggests values from
`value_hint`); (b) suggest the second argument of `make name <kind>`;
(c) editor-side warm-up/caching so completion stops spawning a process per
keystroke. On the rendering side the homepage gaps remain: (d) HTML/CSS
fidelity (no stylesheet file, no viewport meta, no media queries);
(e) conditions/state — "cards stack on a narrow screen" has no `.ine`
form; (f) multi-group operations. Nothing is locked.

---

## 13. Open Questions for Next Session

### Answered by the real homepage (Session 2)

1. ~~Can the 6 concepts represent a real homepage? What breaks?~~ Yes,
   partially. It CAN represent structure. It CANNOT faithfully represent
   per-instance data (three distinct cards) or constraints (equal width).
   See `.tmp/homepage-experiment/FINDINGS.md`.

3. ~~How does the model handle "make three cards" — does multiplicity
   need to be on the entity, or is it a separate concept?~~ Partially
   answered: multiplicity as a scalar count is insufficient because the
   three cards have distinct content, and there is no way to assign
   distinct property values to distinct instances. This is now a real
   finding, not a hypothesis.

4. ~~What does "stays at bottom" mean semantically — is it a
   constraint, a state, or a relationship?~~ Findings: none of the 6
   concepts fits naturally. It is a positional intent with no home.

### Still open (not resolved by the homepage)

2. Is a 7th concept needed? The homepage now provides CONCRETE evidence
   for two candidates: **Constraint** (equal width = prohibition) and
   **Instance** (distinct cards). But this is NOT yet decided — it is
   the user's decision.

5. How do conditional constraints differ from regular constraints in
   the model? — not directly tested.

6. Should the model have a separate "constraint" concept, or is it just
   a condition that always holds? — raised, not decided.

7. What is the smallest real program that tests all 6 concepts? —
   partially answered: the homepage used all 6 of them (all were
   necessary).

8. Should we start with a web homepage (HTML/CSS/JS target) even though
   the target is undecided? — partially answered: the experiment used
   HTML/CSS/JS as the concrete test bed, which is acceptable for testing
   the semantic model without locking the target decision.

### New questions raised by Session 2

9. How should distinct instances of a group be represented (entity
   identity, Entity + instance id, or per-instance parameters)?

10. Are ambient/provided entities (screen, viewport, clock) part of the
    semantic model, or dictionary vocabulary?

11. Is "state changes over time" different from "conditional property
    that is true in a given context"? The responsive layout suggests
    they should be distinguished.

### Updated by Sessions 3-5 (findings, not decisions)

The homepage's "constraint" and "instance" evidence was refined: 3 of 4
gaps dissolved under reinterpretation, "equal width" is expressible as a
group Property, and the three-rules test narrowed the genuine candidate
to program-imposed predicates over collection members.

12. ~~Do we need members of a collection to be indexable/referable
    ("every product", "each product's name")?~~ ANSWERED (Session 6):
    member indexing is NOT a semantic requirement. "All products" = the
    collection as a whole + a dictionary-defined predicate; enumerating
    members is engine implementation (same class as an SQL UNIQUE
    index).

13. Should the "must" force reuse workbook §8's
    MUST/SHOULD/PREFER/ALLOW/AVOID/NEVER hierarchy rather than a new
    concept? §8 is PROPOSED, NOT DECIDED. Sharpened (Session 6): the
    open point is whether §8 priorities may attach to PROPOSITIONS
    (truth-claims about an entity's values), not just behaviors.

14. Which rules can be pushed into the dictionary (domain knowledge —
    "price is by definition positive") or templates ("product template
    includes image") instead of the semantic core?

15. ~~Is "product names must be unique" genuinely inexpressible, or only
    unexpressed so far?~~ ANSWERED (Session 6): inexpressible with the
    six ALONE; expressible by composition (Entity + Multiplicity +
    Dictionary predicate + §8 MUST) IFF priorities can attach to
    propositions. The genuinely new element is the PROPOSITION.

16. What is the human-facing surface of all this? (User: JSON complexity
    is fine if internal. The six concepts + machinery are Level 2; the
    human writes Level 1 intent like "price must be positive".)

### New questions raised by Session 6

17. Is the "obligated proposition" (a truth-claim over an entity's /
    collection's values, carrying a priority) best added as a 7th core
    concept, or as a completion of the PROPOSED §8 priority model +
    dictionary predicates? This is the decision before the user.

18. If priorities attach to propositions, what is the exact set of
    things a priority may modify (behaviors, intents, propositions,
    properties)?

### Raised by the user in this window (PROPOSED, not decided)

19. The **intent-expression spectrum**: users can express the same intent
    at different levels — too low-level (`box-sizing`, `display:flex`,
    `justify-content`) vs reasonable (height, inner space, logo left, nav
    right) vs very intent-oriented (make header / breathing room).
    User's test: "Would a normal person naturally say it this way?"
    Recorded in WORKBOOK §2a/§2b.

20. **Minimum-utterance experiment (PENDING, not yet run):** take a real
    HTML/CSS page and measure how little the human must say for the AI to
    reproduce it correctly. Proposed as a better definition of "easy"
    than counting semantic concepts. User's exact framing: "How little
    does the human need to say for the AI to reproduce it correctly?"
    (Suggested scope at proposal time: header example + the existing
    homepage; general method = pick page → minimal natural intent → AI
    reproduces from intent alone → compare structure/content/assumed
    defaults → report.)

### Added by Session 7 (minimum-utterance experiment)

21. **RAN.** Folder: `.tmp/minimum-utterance-experiment/`. Minimum
    utterance for the homepage ≈ 50 words (content + structure +
    multiplicity/per-instance shape + ONE behavior). All CSS was correctly
    inferred. Two open threads from the results:

22. When a collection's members are described only by their SHAPE ("three
    cards, each with its own title and description") and no content is
    given, should the system (a) ask the human for content, (b) use
    marked placeholders, or (c) both? This is an open question — the
    experiment proved the under-determination exists but did not decide
    the handling. (Relates to workbook §9 ambiguity/clarification.)
    **Session 8 note:** in practice the semantic program just carries the
    content values (here: placeholder card text). The question is about
    the authoring interface, not the representation; still open.

23. Is mobile-responsiveness a requirement the human ALWAYS states, or
    should certain behavior templates (section, card row, navigation) be
    responsive-BY-DEFAULT? The probe showed it is NOT currently an
    inferred default. Whether "be responsive on small screens" becomes a
    template default is UNDECIDED — evidence now exists on both assumptions.
    **Session 8 tension (flagged):** the `card-group` dictionary entry
    written while building the homepage DOES carry `narrow-layout: stack
    members` as a default. If an engine applies that, stacking comes for
    free — which contradicts the Session 7 measurement (omitting the line
    broke the page). The two are not the same thing: Session 7 measured a
    generic AI generator; the dictionary would encode a deliberate engine
    default. Which behavior MyLanguage should have is UNDECIDED and is now
    a visible design choice, not an accident.
