# SESSION_STATE.md

Last updated: 2026-09-08

This file captures the complete project state so any AI session can
continue without losing context. It is NOT a conversation summary.
It IS the project's working memory.

---

## 1. Project Identity

**Working name:** Intent-First Programming Language (temporary)

**Core mission:** Create a simple way for a person to describe what
software should be, how it should behave, what constraints matter, and
what it should look like — without requiring deep knowledge of
implementation syntax.

**Status:** Building. First real MyLanguage program exists
(`examples/homepage/`): the semantic representation of the homepage
(hand-authored, no tool reads it yet). A real toolchain exists in
`src/mylang/` (Session 9): lexer → parser → semantic → HTML backend → CLI.
Session 10 added the requested **Say vertical slice**: `say "..."` →
lexer → parser → interpreter → stdout, verified. The language now has
two kinds of statements (describing: `make`/property → model → target;
doing: `say` → execution → stdout). File extension under use (PROPOSED):
`.int`.

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

**PROPOSED (working choice, Session 9):** `MyLanguage source files use
the extension `.int` (`int` = intent), e.g. `hello.int`,
`homepage.int`. The user directed this as the current working choice;
record it as PROPOSED, not final, until explicitly decided. Do NOT use
`.semantic.json` as the human-written source format going forward — JSON
was a prototype of meaning; `.int` is the actual language humans write.

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
    it. `.int` (intent) is the working file-extension choice (PROPOSED).
    Do NOT build "natural language → HTML"; HTML is one target of a real
    language pipeline.
32. **Smallest useful program:** `examples/hello/hello.int`:
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
    (command line). Entry: `python mylang.py <file.int> [-o out]`.
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
    reaches HTML. `examples/say/say.int` added; existing
    `examples/hello/hello.int` untouched.
38. **Verified:** 33 tests pass (24 preserved + 9 new for `say`).
    `python mylang.py examples/say/say.int` prints `Hello, world!` to
    stdout; `python mylang.py examples/hello/hello.int` still writes
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
43. **Built the smallest native slice:** `.int → lexer/parser →
    backend_c.emit → external C compiler → .exe → run on CPU`.
    - `src/mylang/backend_c.py` — lowers `say` statements to
      `printf("%s\n", "value")` (value is DATA, never format — a
      correctness detail found while building).
    - `src/mylang/native.py` — compiler discovery (`MYLANG_CC`, `zig`,
      `clang`, `gcc`), compile, run. All artifacts to `.tmp/native/`.
    - `src/mylang/cli.py` — added `--native` flag; HTML path untouched.
    - `examples/native/hello.int` — `say "Hello, native machine code"`.
    - 39 tests pass (native e2e test skipped: no compiler on machine).
44. **Tooling blocked (found, not predicted):** clang was installed but
    cannot link on this machine — missing MSVC runtime `libcmt.lib`. The
    chosen toolchain is **Zig** (`zig cc`): bundles clang + lld + libc,
    produces native Windows executables with no extra SDK. When the user
    installs it, `test_native_executable_prints_on_the_cpu` must run
    green and `python mylang.py examples/native/hello.int --native`
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
    `python mylang.py examples/native/hello.int --native` →
    lexer → parser → `backend_c.emit` → `.tmp/native/hello.c` →
    `zig cc` → `.tmp/native/hello.exe` → CPU → stdout
    `Hello, native machine code`, exit 0. The `.exe` is a valid Windows
    PE binary (first two bytes `4D 5A`, ~778 KB, x86-64 machine code),
    not a script. It runs standalone.
49. **HTML backend still verified** alongside: `hello.int` still writes
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
    `hello.int` golden output untouched.
59. **Recorded design facts:** resolve is COMPILE-TIME only. The
    interpreter/backends only ever see literal values; `say person age`
    and `say 25` lower to identical output (`printf("%d\n", 25)`).

---

## 12. Next Step

**DONE (Session 8):** First real MyLanguage program — the homepage's
semantic representation lives in `examples/homepage/`.

**DONE (Session 9):** the smallest Entity/Property toolchain exists and
works: `.int` read → understood → emits verified HTML.

**DONE (Session 10):** the requested Say vertical slice exists and is
verified: `say "..."` → lexer → parser → AST → interpreter → stdout.

**DONE (Session 11-12):** the smallest native slice is BUILT AND
VERIFIED: `python mylang.py <file.int> --native` → emit C → `zig cc` →
native `.exe` → runs on CPU. `Hello, native machine code` observed on
stdout from a real PE binary. HTML pipeline untouched and still green.

**DONE (Session 13):** values are now typed — strings and numbers. The
user's `make person` / `person name "Alice"` / `person age 25` program
builds a real model with a numeric age, and native `say 25` prints from
machine code.

**DONE (Session 14):** describing feeds doing — `say person age` resolves
the stored property at COMPILE time and prints it natively. The workbook
§26 question has its first concrete answer.

**NEXT concrete step (user picks):** the compile-time resolve is static —
the exe cannot change. The natural next real slices:
- A `page` program that prints its own title (`say page title` → already
  works with the new resolve), tying describing → HTML and describing →
  native together in one program.
- Lower the model itself to native (a real `person` struct at runtime),
  if/when a program needs the data to exist at runtime.
Nothing is locked; the next step comes from the next real `.int`
program that hits a wall.

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
