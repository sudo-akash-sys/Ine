# RESEARCH_LOG.md

This file records research sessions. Each session captures what was
investigated, what was found, and what changed.

---

## Session 1 — Semantic Foundation Research

**Date:** 2026-09-04
**Duration:** Extended multi-turn analysis
**Status:** Complete

### What was investigated

The semantic building blocks of the Intent-First Programming Language.
Starting from the 12 primitives in WORKBOOK.md (Entity, Property,
Relation, Action, Event, Condition, Constraint, Context, Asset, Target,
State, Intent), we investigated what concepts are genuinely needed to
represent program meaning.

### What was found

1. **The 12 workbook primitives overlap.** Some are the same concept
   (Action/Event), some are vocabulary not structure (User, Asset),
   some are implementation concerns (Target).

2. **Property was missing from the original list.** The workbook does
   not explicitly list "Property" as a primitive, yet nearly every
   example requires it (width, price, size, visibility). Property is
   more fundamental than many of the listed primitives.

3. **Reference is a representation mechanism, not a semantic concept.**
   It is needed to build a model but is not part of what the model
   means.

4. **Action and Event are derivable.** Action = Entity + State change.
   Event = Entity + State change + Condition. They do not need to be
   separate primitives.

5. **The 6-concept foundation emerged:** Entity, Property, Relationship,
   State, Condition, Multiplicity.

6. **The adversarial test found 2 genuine gaps:**
   - Nondeterminism (the result is uncertain)
   - Prohibition (must not)

   Whether these require a 7th concept is UNDECIDED.

### What changed

- AGENTS.md created with authority rules
- Project directory structure created (dictionary/, templates/,
  examples/, output/)
- SESSION_STATE.md created to preserve project state
- RESEARCH_LOG.md created (this file)

### What was NOT changed

- WORKBOOK.md — not modified
- LANGUAGE.md — still empty (not started)
- No code written
- No syntax designed
- No file extension chosen
- No compilation target chosen

### Key reasoning preserved

The reduction from 12 to 6 concepts was not arbitrary. Each
elimination was tested against 18-30 examples. Concepts were
eliminated only when they could be shown to be:
- Derivable from other concepts (Action, Event, Reference)
- Vocabulary, not structure (User, Asset, Visibility)
- Implementation concerns (Target, specific UI mechanisms)

The 6 remaining concepts survived every test. They could not be
eliminated without losing fundamental meaning.

### What the user wants next

**Stop abstract testing. Build one real small homepage. Test it. See
what the language is actually missing.**

---

## Session 2 — Real Homepage Semantic Experiment

**Date:** 2026-09-04
**Status:** Complete

### What was investigated

Whether the 6 proposed semantic concepts (Entity, Property,
Relationship, State, Condition, Multiplicity) can faithfully represent
a real, concrete homepage. The experiment deliberately avoided
inventing syntax and avoided abstract testing.

### The homepage

- header, logo, navigation
- main content, hero section
- three cards with DISTINCT content (Card 1/2/3, each with own title
  and description)
- footer
- responsive: cards stack vertically below 768px

Full analysis: `.tmp/homepage-experiment/SEMANTIC-ANALYSIS.md`
Findings: `.tmp/homepage-experiment/FINDINGS.md`
Implementation: `.tmp/homepage-experiment/index.html` (verified in
browser — works, 3 equal cards in a row on desktop, column on mobile)

### What was found

The homepage was representable in some form, but SEVEN concrete
problems surfaced. Four classified as GENUINE semantic gaps:

1. **Per-instance data (MISSING CAPABILITY).** Three cards with
   different content cannot be represented. There is one `card`
   entity; multiplicity says "3" but there is no concept of WHICH
   instance has WHICH title. Must hack arrays into property values.

2. **Constraints (MISSING CAPABILITY).** "Equal width" cannot be
   expressed. It is not a property (no single card "is equal"), not a
   relationship, not a state. It is a CONSTRAINT — the rule that all
   three cards must share the same width. This is exactly the
   prohibition/constraint gap the adversarial test flagged as
   UNDECIDED. It appeared in the first concrete example.

3. **Position intent (MISSING CAPABILITY).** "Footer stays at bottom"
   has no home. Forced into a property (position) or smuggled via
   implementation (flexbox ordering).

4. **Ambient entities (MISSING CAPABILITY).** The responsive condition
   needs "screen.width < 768px," but there is no `screen` entity. The
   model has no way to declare provided/ambient entities.

Three classified as representational/implementation or partial:

5. **"Beside / in a row" is ambiguous.** Symmetric relation, no
   ordering, no group property. Orders/groups are the UNDECIDED
   Multiplicity-necessity question. Partly representational, partly a
   gap (no ordered-set concept).

6. **"Full viewport height"** requires naming implementation (100vh).
   Folds into #4 (viewport as ambient entity).

7. **Text content** (logo text, footer text) — Property works fine.
   Not a gap.

### Key takeaways

- The 6 concepts are ALL used in the homepage and none is unnecessary.
- BUT two genuine gaps appeared immediately in a real example, both of
  which the abstract adversarial test had flagged as UNDECIDED:
  - Constraint/prohibition ("equal width")
  - Per-instance identity/distinct instances ("Card 1, Card 2, Card 3")
- This is strong concrete evidence these are NOT abstract edge cases
  but real semantic requirements.
- The model conflates "state changes over time" with "conditional
  property is true in a context" (responsive layout).

### What was changed

- Created `.tmp/homepage-experiment/` with analysis, findings, and a
  working verified homepage.

### What was NOT changed

- WORKBOOK.md — not modified
- LANGUAGE.md — still empty (not started)
- No language syntax designed
- No decisions made — findings only. Proposed-to-decided conversion is
  the user's call.

### Proposed candidate 7th concepts (NOT DECIDED)

- **Instance** — entity identity so N distinct instances can each carry
  their own property values.
- **Constraint** — a rule that must hold (equal width, stays at bottom).

Both match the two UNDECIDED directions already in SESSION_STATE.md.

---

## Session 3 — Gap Reanalysis (No decisions changed)

**Date:** 2026-09-04
**Status:** Complete (analysis only)

### What was investigated

Whether the four reported homepage gaps could be expressed by
REINTERPRETING or COMPOSING the existing six concepts, without losing
meaning — BEFORE any language-design decision (no 7th concept added).

### Verdicts

Full analysis: `.tmp/homepage-experiment/GAP-REANALYSIS.md`

1. **Distinct instances — PRESERVED WITH COMPOSITION.**
   A multiplicity of 3 IS three distinct things. Declaring one Entity
   per instance (card_1/2/3) + Properties + Relationships expresses the
   distinct content naturally, with no array hack and no new concept.
   Identity/reference is the existing REFERENCE concept (already
   representation, not semantic). Genuine residual cost: expressing
   "these three are the SAME KIND" needs a group entity or shared
   property — composition, not a new concept. The original array-hack
   gap was a representational choice, not a hard semantic limit.

2. **Constraints (equal width) — PRESERVED WITH COMPOSITION.**
   "All three equal width" is expressible as a Property of a GROUP
   entity (minus the group: `width-uniform: true`), which stays within
   Entity + Property + Relationship. Condition is the wrong vessel (a
   constraint is a persistent invariant; a condition fires on change).
   The NORMATIVE "must not be violated" force is a separate matter and
   is NOT required to make this homepage render correctly.

3. **Positional intent — PRESERVED.**
   Position is a Relationship (spatial relation to a container):
   `footer at-bottom-of page`, with "at-bottom-of" a vocabulary term
   taking an existing concept slot. "Stays" is State (persistence).
   Relationship + State, both natural.

4. **Ambient/provided entities — PRESERVED.**
   Screen/viewport is an Entity supplied by the environment; its width
   is a Property; the responsive behavior is a Condition referencing
   that Property. Only a DICTIONARY/CONVENTION marker is needed to
   distinguish environment-supplied from user-declared entities — not a
   new semantic concept. Who fills the value is implementation/target.

### Central finding of this session

**3 of the 4 gaps dissolve** once re-read through the existing six
concepts (position = Relationship, ambient = Entity supplied by
environment, distinct instances = one Entity per instance).

**The concept that actually weakened was Multiplicity itself**, not the
missing-instance idea. If distinct instances are three Entities, then
Multiplicity is no longer needed for correctness — its only value is the
"there are N of the SAME KIND" convenience, which must be re-expressed
via a group entity.

**Constraints remain the most genuinely strained area**, but even they
are expressible (as a group property) for layout-like facts. The
residual hard part is the NORMATIVE force ("must never be violated"),
which the simple homepage does not require to be modeled.

### What was changed

- Created `.tmp/homepage-experiment/GAP-REANALYSIS.md` (the analysis).

### What was NOT changed

- No project decisions changed. No 7th concept added. WORKBOOK.md and
  LANGUAGE.md untouched. The verdicts and implications remain analysis;
  design direction is the user's call.

---

## Session 4 — Product-List Semantic Experiment

**Date:** 2026-09-04
**Status:** Complete (analysis only)

### What was investigated

Whether the six concepts can represent a data-driven product list that
deliberately stresses the weakest points found in Sessions 2-3:
unbounded multiplicity, shared schema with varying per-instance values,
and a normative invariant ("price must be positive"). No implementation
was built — the load-bearing parts (schema, dynamic count, invariants)
are not UI behaviors, so an HTML page would not verify them.

Full analysis: `.tmp/product-list-experiment/SEMANTIC-ANALYSIS.md`

### Requirements tested

- make product list
- there are many products (INDETERMINATE count)
- each product has name, price, image (shared schema)
- products have different values (per-instance variation)
- products are equal width
- when screen is small, stack products
- price must be positive (universal invariant + "must" force)

### Findings

1. **The Session 3 enumeration-composition does not survive.**
   Naming each instance as its own Entity works for THREE known cards;
   it cannot work for MANY unknown products. The schema + varying-values
   meaning therefore shifts its entire weight onto Multiplicity: it must
   mean "an indeterminate number of INDEPENDENT entities sharing a
   kind's schema." That is a stronger reading than "how many."

2. **First genuinely MISSING requirement found.**
   "Price must be positive" cannot be expressed:
   - Condition: an invariant has no trigger.
   - Group Property: it must hold per MEMBER, not per group.
   - Relationship: not entity-to-entity.
   Requires universal quantification ("for every product p, p.price > 0")
   plus normative force. The six have no vessel. This is the constraint
   gap in a form that cannot be deferred or folded into a group property.

3. **The "must" force can no longer be set aside.** Session 3 noted the
   normative force was not needed by the homepage; this example makes it
   an explicit requirement.

4. **Ambiguity exposed: "products have different values."** Means either
   (a) each product has its own values (instance independence), or (b)
   no two products share a value (mutual distinctness — a pairwise
   constraint). Materially different; the six cannot even STATE reading
   (b). The language must be able to disambiguate this.

5. **Layout requirements hold.** Row/column, equal width (as a group
   property), and responsive stacking remain expressible — consistent
   with Sessions 2-3.

6. **Data-driven values are not a gap.** The count and values being
   data-dependent is fine as long as entities may carry non-constant
   values. Data sourcing is implementation.

### Verdicts

| Requirement | Verdict |
|-------------|---------|
| make product list | PRESERVED |
| there are many products | PRESERVED WITH COMPOSITION |
| each product has name/price/image | PRESERVED WITH COMPOSITION |
| products have different values | PRESERVED (a) / MISSING (b) |
| products are equal width | PRESERVED WITH COMPOSITION |
| when screen is small, stack products | PRESERVED |
| **price must be positive** | **MISSING** |

### What was changed

- Created `.tmp/product-list-experiment/SEMANTIC-ANALYSIS.md`.

### What was NOT changed

- No decisions, no 7th concept, no implementation changes, no
  WORKBOOK.md/LANGUAGE.md changes. Whether the MISSING cases tip the
  balance toward a constraint capability or toward dictionary/vocabulary
  handling (e.g., be demanding "price" as a domain concept) is the
  user's call.

---

## Session 5 — Three Rules Analysis (No decisions changed)

**Date:** 2026-09-04
**Status:** Complete (analysis only, nothing built)

### What was investigated

Whether three rules share a genuinely new kind of meaning or fall into
the existing concepts/mechanisms. Motivated by the user's caution: do
NOT jump from "price must be positive is missing" to "add Constraint";
distinguish domain knowledge ("what a price IS") from program rules
("what this program requires"); test several rules together; check
whether they fail in the same way or different ways.

Full analysis: `.tmp/rules-experiment/THREE-RULES-ANALYSIS.md`

### The three rules

```
price must be positive
product names must be unique
every product must have an image
```

### Findings

1. **"price must be positive" is ambiguous between domain knowledge and
   a program rule.** Reading A (domain): a price is by definition
   non-negative → PRESERVED via the DICTIONARY (a PROPOSED mechanism) —
   no new concept needed. Reading B (explicit program rule) → MISSING
   under pure six. The sentence does not say which reading is meant.

2. **"product names must be unique" is a program-imposed rule about the
   COLLECTION.** Uniqueness is NOT intrinsic to the meaning of a product
   name — the dictionary cannot know it. This is the ONE rule that
   genuinely lacks a home: it requires referring to members of a
   collection ("every product", "each product's name") and stating a
   predicate over them. MISSING, and the strongest genuine signal.

3. **"every product must have an image" splits into schema + requiredness.**
   The image SLOT exists as a Property (PRESERVED). The "must"
   (requiredness of the slot) is not in the six (MISSING under pure
   six), but a product TEMPLATE (PROPOSED mechanism) can absorb it.

4. **Failure shape: SAME skeleton, DIFFERENT mechanism.**
   As pure program rules, all three collapse into one shape:
   "for every member m: P(m) must hold" — universal quantification over
   members + obligation force. But the predicate content comes from
   different places: dictionary (price), template (image), program
   (unique). So a single blunt "Constraint" would conflate three
   realities.

5. **"Group property" trick does not generalize.** "Equal width" was a
   DESIGN FACT the AI can generate. "Price positive / names unique" are
   facts about DATA the AI must verify against unknown members. A fact
   the AI can produce and an invariant it must check are different kinds
   of meaning. This distinction survived all three rules.

6. **"must" already has a PROPOSED home — workbook §8's priority model**
   (MUST/SHOULD/PREFER/ALLOW/AVOID/NEVER). Do not invent an "obligation"
   concept while that mechanism is available. The real question is what
   "must" attaches to.

7. **JSON complexity is acceptable.** Per the user: the six concepts +
   machinery are the AI's internal semantic layer (workbook §13 Level 2);
   the human surface stays simple (Level 1).

### Conclusion (analysis, not decision)

The genuine candidate for NEW meaning is narrow: program-imposed
predicates over the members of a collection — demonstrated ONLY by
"names must be unique." Two of the three rules can live in existing
PROPOSED mechanisms (dictionary, template), and the "must" force can
live in workbook §8's priority model. The pre-requisite to even test
"every product / each product" is member indexing of collections.

### What was changed

- Created `.tmp/rules-experiment/THREE-RULES-ANALYSIS.md`.

### What was NOT changed

- No concept added, no decision made, nothing built. Dictionary,
  templates, and the §8 priority model remain PROPOSED (not decided).

---

## Session 8 — First Real MyLanguage Program

**Date:** 2026-09-05
**Status:** Building, this milestone complete

### Direction change (user)

Stop running experiments as the goal. Process is now:
**have an idea → make it real → hit a problem → solve it → continue.**
HTML was only a concrete target for visual verification — HTML is NOT
MyLanguage. The architecture stays:
Human intent → MyLanguage semantic representation → AI/engine
implementation → HTML/CSS/JS/etc.

### What was built

The homepage is now the first real piece of software written in
MyLanguage.

- `examples/homepage/homepage.semantic.json` — the semantic program
  (the meaning; only intent; no pixels, no CSS, no implementation text).
- `dictionary/*.json` — 9 starter entries actually used by the program
  (page, header, logo, navigation, banner, card, card-group, footer,
  viewport). Kinds + reusable defaults live here, not in the program.
- `examples/homepage/homepage.html` — the verified reference
  implementation, kept byte-identical, as the target output. NOT the
  language.
- `examples/homepage/BUILD-NOTES.md` — the build record.
- `.tmp/minimum-utterance-experiment/ADDENDUM-WHAT-THIS-SHOWS.md` —
  corrects how to read Session 7 (HTML was the target, not the language).

### How the 6 concepts carried the homepage

Entity (one per thing, incl. environment-supplied viewport), Property
(content only), Relationship (containment + group membership), Multiplicity
(`cards: 3 of kind card`), State (`cards.layout` row/column), Condition
(`viewport.width == narrow → cards.layout = column`).

### Concrete problems met while writing it, and the smallest fix

1. **Three cards, each with its own content (the old "distinct
   instances" gap).** Resolved with existing tools: one Entity per
   instance, `kind` = shared schema, card-group + multiplicity tie them.
   No new concept. The schema lives in the card dictionary entry; the
   values are per-instance Properties.
2. **Side by side / equal width / even spacing.** Not said by the user at
   L2 — a `card-group` dictionary default. Kept out of the program.
3. **Footer stays at bottom.** Dissolved: `footer` as a kind means bottom
   bar; the `page` default (vertical stack + growing middle child) pins
   it. No position property needed. (Earlier sessions called positional
   intent a hard gap; with vocabulary in the dictionary it did not
   appear.)
4. **Cards stack on mobile.** `viewport` is environment-provided;
   `narrow` is a dictionary class — the 768px number stays out of the
   program. Condition + State carry it exactly.
5. **Dark look.** Absent from the program (inferred default); no theme
   mechanism exists yet. Noted, not a blocker.
6. **Provenance of values (intent vs default).** Solved structurally: the
   program IS intent; the dictionary IS defaults. A per-property `source`
   tag was considered and dropped as noise.

### Verification

- Program JSON valid; every entity reference resolves; every content
  property matches the verified `homepage.html` (logo, hero, nav links,
  3 card titles + descriptions); responsive condition maps to the
  media-query behavior already browser-verified in Session 7.
- No engine/parser/validator exists — `homepage.html` was written by the
  AI from the intent, and the program is hand-authored. Fine for now.

### What was NOT done

- No syntax, compiler, runtime, parser, extension, or stdlib started.
- No concept finalized, LANGUAGE.md still empty. The dictionary + shape
  here are the language being used, not a spec.

---

## Session 7 — Minimum-Utterance Experiment

**Date:** 2026-09-05
**Status:** Complete (experiment run, findings only, no design decisions)

### What was investigated

How little does a human need to say for the AI to reproduce a real
HTML/CSS page correctly? This tests the central MyLanguage hypothesis:
human intent should be sufficient while implementation details remain the
AI's responsibility. The metric is the minimum utterance, not syntax or
compiler design.

Full record: `.tmp/minimum-utterance-experiment/` (EXPERIMENT-DESIGN.md,
L0/L1/L2/L2+ utterance files, impl-L0..L2plus.html, RESULTS.md,
INFERENCES.md, screenshots).

### Method (as run)

1. Baseline: the existing verified homepage
   (`.tmp/homepage-experiment/index.html`).
2. Defined "correct reproduction" BEFORE minimizing: structure, content,
   relationships, visual behavior, responsive behavior, reasonable
   defaults — 7 axes, exact pixels NOT target.
3. Generated four implementations from progressively smaller natural
   utterances: L0 (over-specified, all CSS mechanisms spelled out), L1
   (reasonable: structure + content + design intent), L2 (minimal natural:
   content + structure + one behavior), L2+ (probe: L2 minus the responsive
   line).
4. Verified ALL pages in a real browser against the reference on the 7
   axes, at desktop (1200px) and mobile (400px) viewports. 0 console
   errors everywhere.

### Findings

1. **L0, L1, L2 all reproduce the page correctly.** Nothing failed at
   these three levels. The difference is purely how much the human had to
   say (~150 / ~90 / ~50 words).
2. **Minimum utterance ≈ 50 natural words**: the content the person owns
   (name, nav labels, hero text, footer text) + entity structure
   (header/nav/hero/cards/footer) + multiplicity + per-instance shape
   ("three cards, each with its own title and description") + ONE behavior
   ("on mobile the cards should stack").
3. **Implementation detail contributed ZERO necessary words.** The AI
   correctly inferred every CSS mechanism (flex row, media query, spacing,
   colors, equal widths, footer pinning, breakpoint ~768px). The 3-way
   boundary is crisp for this page: nothing the human said was
   implementation, everything implementation was inferred correctly.
4. **Card content is a genuine under-determination.** The human says
   "three cards, each with its own title and description" but gives no
   content; the AI must either invent placeholder or ask (workbook §9).
   The reference's own content ("Card 1/Desc 1") is placeholder too. The
   SHAPE is intent; the CONTENT is either the person's data or a
   placeholder the system must flag.
5. **Mobile responsiveness is NOT an inferred default (measured).** In L2+
   (responsive line dropped) there was NO media query at all. The mobile
   view survived only because a flex-wrap default happened to wrap the
   cards. A plain 3-equal-card row would have rendered broken on mobile.
   The human MUST say the responsive intent. This is the sharpest single
   result.
6. **"Each with its own" is human-trivial but model-hard.** The natural
   sentence is easy to SAY; the internally-strained part is the semantic
   representation of per-instance property values across a collection —
   the same distinct-instances topic Sessions 2-4 flagged. The experiment
   locates the difficulty in the MODEL, not in the human interface.
7. **No new "constraint" capability was needed for this page.** "Equal
   width" was correctly inferred as a default; nobody had to say "must".
   Consistent with Session 5: the homepage never needed the normative force.
8. **Boundary classification result:** (a) implementation knowledge the
   human should NOT need: all of CSS — proven unnecessary. (b) reasonable
   descriptive info the human WOULD provide: content, structure,
   multiplicity, the responsive behavior. (c) genuine intent the system
   must understand: "N entities, each with its own P" and "X stacks on
   small screens".

### Strengths / limits of the experiment

- Real page, real browser verification, multiple naturalness levels, and
  a deliberate probe for default-inference. Strong evidence the core
  hypothesis survives a simple real case.
- ONE simple page is not a proof. Only the homepage so far. No
  decision-making, no LANGUAGE.md change, no concept finalized.

### What was changed

- Created `.tmp/minimum-utterance-experiment/` (design, 4 utterances,
  4 impls, results, inference record, screenshots/browser evidence).

### What was NOT changed

- WORKBOOK.md, LANGUAGE.md untouched. No semantic concept finalized. No
  decisions. Findings and open questions only.

---

## Session 6 — Single-Problem Analysis: `products must have unique names`

**Date:** 2026-09-04
**Status:** Complete (analysis only, nothing implemented)

### What was investigated

Exactly one requirement — `products must have unique names` — to
determine whether it is genuinely inexpressible with the six concepts,
trying multiple representations before concluding. No new concept. No
syntax invented.

Full analysis: `.tmp/unique-names-experiment/UNIQUE-NAMES-ANALYSIS.md`

### The meaning

The name-mapping on the product collection is injective: distinct
products have distinct name values, and this is required (obligation,
not description). Parts: a collection (Entity + Multiplicity), a name
value (Property slot), a truth-claim over values (NOT one of the six),
an obligation (PROPOSED §8).

### Representations tried

1. **Collection predicate + §8 MUST (STRONGEST).** `products is
   name-unique`, predicate meaning in Dictionary, obligation from MUST.
   Works IF priorities may attach to propositions.
2. State invariant (holds/violated) — AWKWARD: models the forbidden
   state as reachable; State is for change over time.
3. Pairwise Relationships (p1 diff-name p2 for all pairs) — FAILS:
   unbounded enumeration, loses "for all", value comparison smuggled
   into relation vocabulary.
4. Pure Dictionary default (uniqueness intrinsic to product) — FAILS:
   uniqueness is program-imposed, not world-intrinsic.

### Findings

1. NOT expressible by the six concepts alone.
2. Expressible by composition IF one small element is completed: an
   OBLIGATED TRUTH-CLAIM (proposition) over the values of a
   collection, with priority attachment — the genuinely new element is
   the PROPOSITION, not "constraint" as a blob.
3. Dictionary CAN define the predicate but CANNOT decide this program
   requires it (two products may legitimately share a name in the
   world). Templates only transport the rule; they cannot create the
   missing home for meaning.
4. MUST (PROPOSED §8) can provide the obligation; Entity+Multiplicity
   provides scope; Dictionary provides predicate meaning — provided the
   priority model is (re)defined to attach to propositions, not only
   behaviors.
5. **Member indexing is NOT a semantic prerequisite** (REVISES
   Sessions 4–5). "All products" = the collection whole + dictionary
   predicate; enumerating members to check duplicates is engine
   implementation (same class as an SQL UNIQUE index).
6. **Refinement of Session 5:** "equal width" vs "unique names" have the
   SAME semantic shape (both `MUST · proposition over a collection`);
   the generation-vs-verification difference is an enforcement/
   implementation classification, not a semantic one.

### Conclusion (analysis, not decision)

Convergent evidence across three experiments (equal width, price
positive, image required, unique names) shows a real, recurring shape.
But the gap is narrow and localizable: a home for an obligated
truth-claim over values + §8 priority attachment to propositions. That
may be completable by extending PROPOSED §8 rather than adding a 7th
core primitive. Whether it becomes a new concept is the user's decision.

### What was changed

- Created `.tmp/unique-names-experiment/UNIQUE-NAMES-ANALYSIS.md`.

### What was NOT changed

- No concept added, no decision made, nothing implemented.
  WORKBOOK.md / LANGUAGE.md untouched.

---

## Session 9 — First Real Implementation (the smallest working pipeline)

**Date:** 2026-09-05
**Status:** The smallest real MyLanguage implementation exists and works.

### Direction change (user)

MyLanguage is no longer primarily a research/prototype exercise — build
it as a real programming language. The working file extension is `.int`
(`int` = intent), PROPOSED. Do NOT build "natural language → HTML";
HTML is one target of a real language pipeline. Build simple →
complicated from real programs.

### What was built

A tiny real toolchain that reads `.int`, understands meaning, and emits
a verifiable result:

- `src/mylang/lexer.py` — text → tokens. Token kinds: KEYWORD (`make`),
  IDENT (letters/`_`/`-`/digits), NUMBER, STRING, NEWLINE, EOF. `#`
  line comments.
- `src/mylang/parser.py` — tokens → syntax statements.
  `make <name> [kind]` (kind defaults to the name) and
  `<name> <property> "value"`. Anything else is a syntax error with a
  line number.
- `src/mylang/semantic.py` — statements → Model (entities + properties).
  Genuine understanding, not string matching: a property on a
  undeclared entity is rejected; duplicate entity is rejected; repeated
  property overrides.
- `src/mylang/backend_html.py` — Model → HTML (the first target).
- `src/mylang/cli.py` — command line. Entry:
  `python mylang.py <file.int> [-o out.html]`.
- `examples/hello/hello.int` — the smallest real program:
  `make page` / `page title "Hello, MyLanguage"`.
- `tests/test_mylang.py` — 24 unit + end-to-end tests, including a
  golden-output comparison (`tests/expected/hello.html`).

### What was found (by using it, not by speculating)

1. The two-statement program the user proposed (Stage 2 in their brief)
   was genuinely the smallest useful one: entity + property. It
   exercises every pipeline stage and produces real output.
2. Browser-verified: `output/hello.html` renders — document title and
   page heading both "Hello, MyLanguage", 0 console errors.
3. The first REAL limitation is concrete and was encountered, not
   predicted: the HTML backend only knows kind `page`. `make header`
   fails with "the html backend does not support this kind yet". The
   dictionary (`dictionary/*.json` — 9 kinds) is NOT consulted by the
   engine yet; the page mapping is hard-coded in the backend.
4. Secondary current limits: property values are strings only; no
   relationship statements exist (`inside`), so nothing can nest inside
   a page.

### What was changed

- Created `src/mylang/` (the implementation), `mylang.py` (root
  launcher), `examples/hello/hello.int`, `tests/test_mylang.py`,
  `tests/expected/hello.html`, `output/hello.html`.
- Updated SESSION_STATE.md (status, §8 extension → PROPOSED `.int`,
  Session 9 record, next step).
- Updated WORKBOOK.md (§26 first-milestone note) and wrote the first
  real content of LANGUAGE.md (current implemented spec, marked
  EXPERIMENTAL).

### What was NOT changed

- No semantic concept finalized. The 6 concepts remain PROPOSED. The
  `.int` extension is PROPOSED, not decided. The compiler architecture
  is not finalized — the implemented stages are the first real instance
  of it, not a commitment to the rest.
- `examples/homepage/` untouched (still the reference representation +
  target).

---

## Session 10 — The Say Vertical Slice (correction)

**Date:** 2026-09-05
**Status:** Complete. `say` is implemented, tested, and verified on
stdout.

### Correction (user)

Session 9 implemented a DIFFERENT milestone than requested. The request
was the Say vertical slice:

```
say "Hello, world!"
  → lexer → parser → AST → interpreter → stdout
```

Session 9 built `make page` / `page title "..."` → Entity/Property model
→ HTML instead. The existing work is NOT deleted — it is a genuinely
useful second vertical slice (describe-a-thing → model → target) and its
tests are preserved. The user's explicit instructions: add `say` as the
next real language capability; do NOT translate `say` into HTML; do NOT
make `say` another entity/property; `say` executes and prints to stdout;
run it and show the actual stdout; do not move to relationships/
dictionaries/HTML expansion/homepage until this is verified.

### What was built (smallest change)

- `KEYWORDS = {"make", "say"}` in the lexer.
- `SayStatement` in the parser; grammar `say-stmt := "say" "value"`.
- New pipeline stage `src/mylang/interpreter.py` (`execute`) producing
  runtime output values for `say` statements.
- CLI rework: execution output is printed to stdout before the summary;
  a program with no declared page produces no target (HTML is only a
  target when the program describes a page). `say` never reaches HTML.
- `examples/say/say.int` — the requested program.
- `tests/test_mylang.py` — 9 new tests (keyword, parse, value-required,
  extra-text, ordered outputs, empty-output program, model exclusion,
  HTML exclusion, e2e execute-with-no-target). 33 total, all pass.

### Verification (actual runs)

```
$ python mylang.py examples/say/say.int
Hello, world!
read:       examples/say/say.int
entities:   0
properties: 0
target:     the program does not describe a page

$ python mylang.py examples/hello/hello.int   (unchanged)
read:       examples/hello/hello.int
entities:   1
properties: 1
wrote:      output\hello.html
```

A `.tmp` program containing `make page` + `say "..."` ran both: printed
the say line to stdout AND wrote `output/both.html`, exit 0.

### What the language revealed (OPEN, not decided)

Building `say` forced the language to carry two kinds of statements side
by side:

- **Describing** — `make page`, `page title "..."`: build the model,
  then a target.
- **Doing** — `say "..."`: execute, produce stdout.

The user explicitly said this is a real problem the language revealed,
and NOT to solve it abstractly. It is recorded as an open question
(WORKBOOK §26, LANGUAGE.md §5a), not a design decision.

### What was changed

- Added `say` (lexer/parser/interpreter/CLI), `examples/say/say.int`,
  tests.
- Updated SESSION_STATE.md, LANGUAGE.md, WORKBOOK.md (§26).

### What was NOT changed

- `examples/hello/hello.int` and the Session 9 pipeline/tests — preserved
  in full.
- No relationship/dictionary/HTML/homepage work started, per instruction.
- No semantic concept finalized; architecture still not finalized.

---

## Session 11 — Native-execution direction + the emit-C target

**Date:** 2026-09-08
**Status:** Built; end-to-end verification blocked on missing toolchain.

### Direction refinement (user)

MyLanguage is its own language and semantic system — existing languages,
APIs, runtimes, browsers, and machine-code technologies are targets it
can interoperate with, not what defines its meaning. The old "translation
layer" framing is an earlier working hypothesis. HTML is one backend, not
the destination. User priority for this phase: actual execution over
exhaustive testing — prove that MyLanguage source becomes something the
real computer executes.

### What was built

The smallest native slice: `.int → lexer/parser → emit C → external C
compiler → .exe → CPU`.

- `src/mylang/backend_c.py` — lowers `say` statements to
  `printf("%s\n", "value")`. A correctness detail found while building:
  values are emitted as DATA (the `%s` argument), never as format text,
  so user input like `100%` cannot become a C format specifier.
- `src/mylang/native.py` — compiler discovery (`MYLANG_CC` env var, then
  `zig`, `clang`, then `gcc`), compile, run. Generated artifacts
  (`.c`, `.exe`) always go to project `.tmp/native/`.
- `src/mylang/cli.py` — added `--native`. HTML path untouched.
- `examples/native/hello.int` — the smallest native program.
- `tests/test_mylang.py` — NativeBackendTests (5 emission tests, 1
  skipped e2e compile+run). 39 total pass.

### What was found (by building, not by speculating)

1. **The machine has no usable C compiler.** clang (LLVM 22.1.8) was
   installed but cannot link on Windows: `ld.lld: could not open
   'libcmt.lib'` — the MSVC runtime is absent. Verified by probe compile.
2. **Zig is the clean fix:** single download, `zig cc` wraps clang + lld
   + a bundled libc, produces native Windows executables with no extra
   SDK. Recommended toolchain.
3. The HTML pipeline is provably untouched: `hello.int` still writes
   `output/hello.html` byte-identical to the golden file (all pre-names
   tests still green).
4. The emitted C for the example is exactly the expected standalone
   program (written to `.tmp/native/hello.c`).

### Verification status

- 39 unit tests pass (1 native e2e test skipped: no compiler installed).
- CLI `--native` reaches the tooling gate and reports a clear install
  hint instead of failing silently.
- End-to-end `.int → .exe → CPU` NOT yet observed. Blocked until Zig is
  installed.

### Session 12 addendum (VERIFIED)

- User installed Zig 0.16.0 (user PATH). `MYLANG_CC` not needed —
  `zig` auto-detected.
- All 39 tests pass, none skipped. The native e2e test now compiles with
  Zig and runs on this machine.
- Targeted run confirmed: `python mylang.py examples/native/hello.int
  --native` → `Hello, native machine code` on stdout, exit 0.
  `.tmp/native/hello.exe` is a valid PE binary (`4D 5A` magic, ~778 KB,
  x86-64), runs standalone as native machine code — not a script.
- HTML backend still verified: `hello.int` writes `output/hello.html`
  byte-identical to the golden file.
- First confirmation of the Session 11 direction at the machine level.

### Session 13 addendum (typed values)

**Date:** 2026-09-08
**Status:** Complete. Values are now typed (strings + numbers).

The user drove this: they wrote `make person` / `person name "Alice"` /
`person age 25` and hit the "property value must be written in quotes"
wall. The wall was genuine — an age is a number, not a string. The user
decided to add numbers and keep the language simple and efficient.

**Implemented (smallest change):**

- `parser.py`: property and `say` accept NUMBER tokens. `_literal()`
  converts to `int` unless the text has `.`/`e`, then `float`.
- `semantic.py`: model stores typed values unchanged.
- `backend_c.py`: `printf("%s\n")` strings, `printf("%d\n")` integers,
  `printf("%.17g\n")` decimals.
- `backend_html.py`: `str(value)` before HTML-escaping.
- Tests: 47 total (3 new parser, 2 new interpreter, 2 new native e2e).

**Verified:** user's program builds a model with `age: 25` (int);
native `say 25` prints `25` from real PE machine code.

**Left alone (per method):** `say person age` is still invalid — reading
a stored property at runtime is the workbook §26 describing/doing
composition question, deliberately not solved abstractly. No new types
beyond str/int/float. Nothing committed.

### Session 14 addendum (say name property — compile-time feed)

**Date:** 2026-09-08
**Status:** Complete. Describing now feeds doing, at compile time.

The user drove the question: the program `make person` / `person name
"Alice"` / `person age 25` / `say person age` hit "expected a string or
a number after 'say'". The user chose **Choice A: compile-time property
resolution** with compile-time errors for missing properties, minimal.

**Implemented (smallest change):**

- `parser.py`: `say-stmt := "say" value | "say" name property`. A
  `PropertyRef(target, name, line)` dataclass holds the reference until
  resolution.
- `semantic.py`: `resolve(statements, model)` replaces each `PropertyRef`
  with the model's stored literal. Missing property or undeclared entity
  → `SemanticError` with line number.
- `cli.py`: both paths (`--native` and HTML) resolve before execute.
- No runtime model, variables, mutation, expressions, or dynamic lookup.

**Verified (57 tests):**

- Unit: parse ref; resolve string/int/float; missing property → error;
  undeclared entity → error; literals untouched; resolve feeds execute.
- Native e2e: the real program prints `Alice` and `25` from a PE exe.
- Exact wall case: `say person age` → prints `25`; `say person height`
  → compile error; `say ghost age` → compile error, both exit 1.

**Findings:**

1. Describing→doing composition survives contact with a real program and
   the smallest possible implementation was exactly sufficient.
2. The resolve is compile-time only; `say person age` and `say 25` lower
   to identical C. The two statement kinds stay syntactically distinct
   but now compose.
3. No new core concept was needed — the workbook §26 question was answer
   able without adding to the six. (Recorded as observed, still not a
   design decision about §26's full scope.)

### What was changed

- Added `src/mylang/backend_c.py`, `src/mylang/native.py`, `--native`
  CLI flag, `examples/native/hello.int`, native tests, `.tmp/native/`
  artifacts (gitignored).
- Updated WORKBOOK.md (§27), LANGUAGE.md (§6a, §7), SESSION_STATE.md,
  RESEARCH_LOG.md, AGENTS.md (permanent Temporary-File Policy).

### What was NOT changed

- The decide-a-thing (make → model → HTML) pipeline and all prior tests.
- No semantic concept finalized; the native direction is recorded
  PROPOSED pending the user's architecture decision.
- Nothing committed to Git.
