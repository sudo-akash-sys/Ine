# Ine --- Guidebook & Workbook

A working specification for a simple, AI-native, behavior-oriented
software language

> **Living design document.** This workbook is the project's own
> thinking: it mixes DECIDED decisions, PROPOSED designs, and open
> questions. It is not a finished specification. For what is actually
> implemented and working today, read [LANGUAGE.md](LANGUAGE.md).

## 0. Project Identity

Working name: Ine.

Core mission: Create a simple way for a person to describe what software
should be, how it should behave, what constraints matter, and what it
should look like---without requiring deep knowledge of implementation
syntax.

The system should not be limited to one implementation technology. It
should be able to work with HTML/CSS/JavaScript and, later, other
languages, frameworks, libraries, runtimes, and platforms.

The language is therefore best understood as an intent/semantic layer
rather than merely another conventional programming language.

Primary design goal: Usability first. The system should be easy to
understand, easy for AI to generate, easy for humans to inspect, and
capable of producing technically sophisticated software underneath.

Secondary goals: - Reduce unnecessary syntax and repetitive
implementation detail. - Standardize concepts so equivalent intentions
map to the same meaning. - Allow AI to perform implementation work while
remaining constrained by explicit intent and rules. - Accept text,
structured input, and visual references such as screenshots or generated
assets. - Support progressive complexity: beginners can stay simple;
advanced users can specify more. - Interoperate with existing
technologies instead of requiring the ecosystem to be rebuilt from zero.

## 1. What This Project Is --- and Is Not

This is NOT simply: - a new syntax for JavaScript; - a replacement for
HTML; - a visual drag-and-drop editor; - an LLM that blindly writes
code; - a collection of shortcuts for CSS; - a prompt wrapper around an
existing coding model.

It IS intended to become: - a semantic representation of software
intent; - a human-friendly language for describing entities,
relationships, properties, behaviors, constraints, context, and desired
outcomes; - an AI-friendly intermediate representation; - a translation
layer into existing implementation technologies; - potentially a
multimodal programming interface where text and images can describe
desired software; - eventually, a versioned project model in which
meaningful intent changes can be tracked and reviewed.

## 2. The Central Principle

The fundamental rule is:

Describe WHAT the software should do before describing HOW it should do
it.

Traditional programming usually requires the programmer to select
implementation mechanisms directly. This project attempts to move the
programmer upward in abstraction.

Example:

make footer height 20px stay at bottom

The user should not need to know whether the implementation requires CSS
flexbox, grid, absolute positioning, or another mechanism.

The implementation engine may decide the HOW, subject to constraints.

However, the language must not become vague natural language with no
guarantees. The key challenge is:

Human-friendly expression + machine-checkable meaning.

Natural language may be accepted at the interface, but the system should
normalize it into a structured semantic representation that can be
validated.

### 2a. The Intent-Expression Spectrum (PROPOSED)

The Central Principle implies a spectrum of how a user may express the
same inten t, from implementation-level to intent-level.

TOO LOW-LEVEL (implementation knowledge leak):
header.box-sizing = border-box
header.display = flex
header.justify-content = space-between

REASONABLE:
header height 60px
header has 20px inner space
logo left
navigation right

VERY INTENT-ORIENTED:
make header
logo on the left
navigation on the right
give the header some breathing room
header 60 pixels tall

The AI should understand "space around its contents" and decide that it
corresponds to padding, rather than forcing the human to know CSS.

User's guiding test for any expression level: "Would a normal person
naturally say it this way?"

### 2b. A Better Definition of "Easy": Minimum Utterance (PROPOSED)

A useful working definition of how easy the language is:

> How little does the human need to say for the AI to reproduce a real
> page correctly?

Proposed experiment (PENDING, not yet run):
take a real HTML/CSS page and ask: what is the minimum human utterance
needed for the AI to reproduce it correctly? This measures the value of
the abstraction more directly than counting semantic concepts.

Note: the semantic JSON itself may become complex. That is acceptable
as long as it stays the AI's internal Level-2 representation and the
human-facing surface stays simple.

The initial semantic primitives should be kept deliberately small.

ENTITY Something that exists in the software. Examples: page, header,
button, user, image, database, search box.

PROPERTY A characteristic of an entity. Examples: height, width, color,
title, visibility, speed.

RELATION How entities are connected. Examples: inside, beside, contains,
belongs_to, uses, opens.

ACTION Something the system can do. Examples: show, hide, open, close,
save, search, move.

EVENT Something that triggers behavior. Examples: click, submit, load,
scroll, resize, login.

CONDITION A circumstance under which behavior changes. Examples: when
screen is small; when user is logged in; when data is unavailable.

CONSTRAINT A rule that must not be violated. Examples: accessible,
mobile-compatible, under a size limit, do not remove existing behavior.

CONTEXT Information that changes interpretation. Examples: website,
mobile app, dashboard, ecommerce, accessibility requirements.

ASSET An external or visual input. Examples: image, screenshot, icon,
video, design reference.

TARGET The implementation environment. Examples: HTML/CSS/JS, React,
Flutter, Python, a specific API, or another runtime.

STATE A meaningful condition that can change over time. Examples:
menu=open, user=logged_in, search=expanded.

INTENT The desired outcome or purpose.

These primitives are hypotheses, not final syntax. The project should
test whether they are sufficient before adding many more.

## 4. The Dictionary System

The dictionary is a central component, not merely autocomplete.

A dictionary entry maps a human-friendly concept to a defined semantic
meaning and may include defaults, alternatives, constraints, templates,
and implementation hints.

Example concept:

small button

Possible semantic definition: - visual scale: compact - preferred
height: 32px - compact horizontal padding - readable text - preserve
usability on touch devices - allow target-specific adaptation

The exact values should not be hard-coded into the language core unless
necessary. They can live in dictionaries/templates that can evolve.

Important distinction:

LANGUAGE CORE Defines what concepts mean.

DICTIONARY Defines reusable vocabulary and domain conventions.

TEMPLATE Provides a starting structure that can be customized.

TARGET ADAPTER Explains how semantic concepts map to a particular
technology.

This makes the system extensible.

Synonyms may be accepted at the interface: home, homepage, landing page,
main page

They should normalize to a canonical concept when their intended meaning
is equivalent.

The system should avoid pretending that all synonyms are always
equivalent. Context can disambiguate them, and the user should be asked
only when the difference matters.

## 5. Templates and Defaults

Templates are likely to be more useful than forcing users to specify
every field.

For example, a user might request:

make search

The system can instantiate a search template containing: - input -
submit behavior - result area - loading state - empty state - error
state - responsive behavior - accessibility defaults

The user can then override only what matters:

make search inside header compact collapse when space is insufficient

Templates should be: - inspectable; - editable; - versioned; -
replaceable; - target-aware where necessary; - capable of inheriting
from broader templates.

A template is not a prison. It is a starting point.

The guiding rule is: Good defaults reduce complexity; explicit overrides
preserve control.

## 6. Image and Multimodal Programming

Visual input should eventually be treated as structured intent, not
merely as a picture to imitate.

Possible workflow:

image/screenshot → visual analysis → detect regions and components →
infer semantic entities → infer relationships → infer approximate
properties → create semantic representation → ask for clarification
where confidence is low → compile to target technology

Example:

A screenshot contains: - header - logo - navigation - search - hero
section - card grid - footer

The system should attempt to represent these as semantic entities rather
than immediately producing raw CSS.

Image inputs may also be used as: - design references; - exact asset
sources; - layout constraints; - style references; - editable
components; - examples of desired behavior.

Image understanding is expected to be one of the technically difficult
parts of the project. It should therefore be isolated behind a
multimodal adapter rather than embedded into the language core.

## 7. AI as an Execution/Translation Partner

AI should not merely generate final code from a prompt.

A stronger architecture is:

Human intent → AI interpretation → structured semantic program →
validation → implementation planning → code generation → execution/build
→ verification → visual/behavioral comparison → correction

The AI may choose implementation details, libraries, algorithms, or
patterns when allowed by the context.

But the system should preserve: - the user's intent; - explicit
constraints; - important decisions; - the semantic representation; -
generated implementation; - verification results.

The prompt is temporary. The structured intent should be durable.

This distinction is important because prompts are conversational and
ambiguous, while a stored semantic representation can be inspected,
edited, versioned, tested, and reused.

## 8. Intended vs Non-Intended Behavior

This is a key design idea.

A program should be able to describe: 1. intended behavior; 2. preferred
behavior; 3. fallback behavior; 4. prohibited behavior; 5. behavior when
information is missing.

Example:

make navigation desktop: horizontal small screen: collapse when
collapsed: allow expansion do not hide primary navigation permanently

This can be represented as preferences and constraints.

Potential priority model:

MUST The system must satisfy it.

SHOULD The system should satisfy it unless doing so conflicts with a
stronger rule.

PREFER A desirable default.

ALLOW An acceptable alternative.

AVOID Do not choose unless necessary.

NEVER Explicit prohibition.

This hierarchy can make natural, flexible instructions more precise
without forcing users into traditional programming syntax.

## 9. Ambiguity and Clarification

The system should not guess silently when an ambiguity can materially
change the result.

Example:

make footer 20 pixels

Possible meanings: - height = 20px - padding = 20px - margin = 20px

If context cannot resolve this safely, the system should ask a compact
question or show a small field editor.

The interface should prefer: - one focused clarification; - sensible
defaults; - previews; - editable fields; - explanations only when
needed.

It should avoid giant configuration forms.

An ambiguity can also be resolved by dictionary context: '20 pixels
tall' → height '20 pixels from edge' → margin/padding depending on
relation '20 pixel text' → font size

The long-term objective is to make clarification increasingly rare
without making the system dangerously presumptive.

## 10. Interoperability

The project should be designed around adapters.

Core: Intent / semantic representation

Adapters: HTML/CSS JavaScript/TypeScript React Vue Python Flutter native
platforms libraries APIs other future targets

The same semantic intent should be capable of having multiple
implementations.

Example:

make responsive navigation

Target A: HTML + CSS + JavaScript

Target B: React

Target C: Flutter

The user should ideally care about the behavior, not the target-specific
syntax unless they intentionally request implementation control.

The target adapter may expose target-specific capabilities when needed.

## 11. Suggested Architecture

A practical first architecture:

1.  INPUT LAYER Text, structured commands, images, existing code, or
    other assets.

2.  INTERPRETATION LAYER AI converts input into a structured semantic
    intent.

3.  NORMALIZATION LAYER Synonyms, defaults, templates, and domain
    vocabulary are normalized.

4.  SEMANTIC MODEL A canonical representation of entities, properties,
    relationships, events, actions, state, constraints, context, assets,
    and intent.

5.  VALIDATOR Checks whether the representation is complete, coherent,
    and compatible with constraints.

6.  PLANNER Determines an implementation strategy.

7.  TARGET ADAPTER Maps the plan to HTML/CSS/JS or another target.

8.  GENERATOR Produces implementation artifacts.

9.  VERIFIER Checks behavior, constraints, tests, and optionally visual
    similarity.

10. VERSION SYSTEM Stores meaningful states and changes to the semantic
    project.

11. USER INTERFACE Shows the semantic model, preview, changes,
    questions, and generated result.

The semantic model should be the durable center of the system.

## 12. The Version-Control Idea

A native version system could be more meaningful than simply tracking
text-file diffs.

Git is fundamentally a history/version-control system built around
snapshots, commits, branches, and related objects. Git's documentation
explicitly describes commits as snapshots of project state rather than
merely lists of line-by-line changes.

For this project, a future 'Intent Git' could additionally understand
semantic changes.

Instead of only: - file changed; - line 82 changed; - CSS property
changed;

it could show: - header changed from fixed to adaptive; - search moved
inside header; - button behavior changed from navigate to open; -
template version changed; - visual asset replaced; - constraint added:
mobile compatible.

Possible future concepts: SNAPSHOT A complete semantic project state.

CHANGE A semantic modification.

BRANCH An alternative design/implementation direction.

MERGE Combine compatible intent changes.

CHECKPOINT A known-good semantic state.

ROLLBACK Return to an earlier project state.

COMPARE Compare intent, implementation, behavior, and visual result.

This should not replace Git initially. The first implementation can
simply coexist with Git and later add semantic capabilities on top.

## 13. Why This Is Different From a Normal Programming Language

A conventional language generally asks the programmer to express
computation in a formal syntax.

This project attempts to make the primary abstraction: - intent; -
behavior; - relationships; - constraints; - context; - outcomes.

The system may still eventually have a formal syntax. In fact, a formal
representation is important for determinism and tooling.

But the human authoring surface does not need to expose all of that
syntax.

Think of three levels:

LEVEL 1 --- Human interface Simple language, prompts, images, visual
editing.

LEVEL 2 --- Semantic language Strict structured representation with
defined meanings.

LEVEL 3 --- Implementation HTML/CSS/JS, Python, libraries, native code,
etc.

The human can operate mostly at Level 1. AI and tools operate heavily at
Level 2. Compilers/adapters operate at Level 3.

## 14. What You Need to Learn

You do NOT need to master JavaScript, Python, CSS, compilers, or every
existing language before starting.

Learn concepts as the project requires them.

High-priority concepts: - variables and values; - entities/objects; -
functions/actions; - conditions; - events; - state; - data; -
relationships; - input/output; - APIs; - errors; - parsing; - abstract
syntax trees; - intermediate representations; - compilers/transpilers; -
runtimes; - testing; - version control.

For the web, learn the roles of: HTML = structure CSS =
presentation/layout JavaScript = behavior browser APIs = capabilities

Syntax memorization is secondary.

The goal is to understand what existing technologies are capable of so
that the new semantic layer can use them effectively.

## 15. Development Roadmap

PHASE 0 --- Definition Write the philosophy, primitives, vocabulary, and
constraints.

PHASE 1 --- Tiny semantic model Represent entities, properties,
relations, actions, events, state, and constraints in JSON or another
simple structured format.

PHASE 2 --- Tiny parser Accept a very small human-friendly syntax.

Example: make page make header make search inside header make footer
height 20px

PHASE 3 --- First target Compile the semantic representation into a
basic HTML/CSS/JS website.

PHASE 4 --- Templates Add reusable components and defaults.

PHASE 5 --- Behaviors Add events, state, conditions, and fallbacks.

PHASE 6 --- AI translation Allow an AI model to turn natural-language
requests into the semantic representation.

PHASE 7 --- Verification Validate semantic intent before implementation
and test the result afterward.

PHASE 8 --- Image input Turn screenshots/design references into semantic
structures.

PHASE 9 --- Multiple targets Add adapters for additional
frameworks/languages.

PHASE 10 --- Semantic version control Build project snapshots, semantic
diffs, branches, and rollback.

Do not attempt all phases simultaneously.

## 16. MVP Definition

The first useful prototype should be extremely small.

Input:

make page make header make search inside header make button inside
header make footer height 20px

Output: A working web page.

Then allow:

make search collapse when space is insufficient expand on selection

Output: A working responsive interaction.

Then:

make page from image

Output: A rough semantic decomposition and generated page.

The MVP is successful if a user can describe a simple interface without
needing to know the underlying HTML/CSS/JS implementation.

## 17. Design Rules --- Non-Negotiable Candidates

1.  Simplicity beats cleverness.
2.  The user should specify intent before implementation.
3.  The semantic meaning must be more stable than the surface wording.
4.  AI should be allowed to implement, but not silently redefine
    important intent.
5.  Ambiguity should be resolved explicitly when it matters.
6.  Defaults should be strong but overridable.
7.  Templates should accelerate creation, not restrict creativity.
8.  Existing technologies should be usable rather than discarded.
9.  The system should degrade gracefully when AI is unavailable.
10. The semantic representation should be inspectable by humans.
11. Generated code should remain ordinary, usable code.
12. The system should preserve reproducibility where possible.
13. Security and permissions must be explicit for AI-driven actions.
14. Complexity should be optional: simple tasks stay simple; advanced
    tasks can expose deeper control.
15. Every major abstraction should earn its existence by reducing user
    effort.

## 18. Questions to Resolve Before Syntax

These are workbook questions, not assumptions.

A. What exactly is an 'intent'? B. What is the smallest possible
semantic primitive? C. Which concepts are universal across web, mobile,
backend, and other software? D. Which concepts belong only in
dictionaries/templates? E. When should the system ask a question instead
of guessing? F. How should conflicts between user instructions be
resolved? G. How should priorities such as MUST/SHOULD/PREFER work? H.
How should state be represented? I. How should asynchronous behavior be
represented? J. How should errors and failure behavior be described? K.
How should security constraints be expressed? L. How should permissions
be expressed? M. What should happen when the target technology cannot
directly implement an intent? N. How much implementation control should
advanced users receive? O. How should image-derived structures express
uncertainty? P. How should semantic changes be versioned? Q. What should
an AI be allowed to modify automatically? R. How do we verify that the
generated implementation actually satisfies the intent?

## 19. Similar Work to Study

This idea is not appearing in a vacuum. Recent work already explores
closely related territory.

Microsoft Research's Programming with Representations (PwR) describes a
domain-specific representation between natural-language intent and
generated code, with an explicit intermediate representation that users
can inspect and modify. This is particularly relevant to the proposed
architecture.

There are also newer projects and papers using terms such as
intent-oriented programming, intent-aware programming, semantic
compilers, and AI-native programming. Some are close to the project in
philosophy, while differing substantially in implementation, target
level, verification strategy, or scope.

Important examples found during research: - Microsoft Research ---
Programming with Representations (PwR). - ThunderLang --- an emerging
intent-oriented programming language/project. - Decrypt --- an
intent-aware language focused on translating goals and constraints into
implementations. - Semantic Compiler --- a 2026 proposal focused on
comparing semantic intent with generated executable representations. -
Sigil --- an experimental AI-native language focused on a lower-level
execution representation.

These should be treated as adjacent work to study, not as proof that the
proposed design is identical to any of them.

The opportunity is therefore not 'nobody has thought of intent-based
programming.' The opportunity is to determine whether a particularly
simple, multimodal, interoperable, template/dictionary-driven,
user-oriented version can solve problems that existing approaches do
not.

## 20. Commercial and Open-Source Strategy

If an open model is used, commercial use depends on the specific model's
license. 'Free', 'open weights', and 'open source' are not
interchangeable legal categories.

Before adopting a model, check: - commercial-use permission; -
redistribution terms; - modification terms; - attribution
requirements; - acceptable-use restrictions; - model-weight licensing; -
dataset/license considerations; - API or hosted-service terms if
applicable.

Keep the language's own license separate from the AI model's license.

A good early strategy is to make the semantic language and core tooling
independently useful. Then AI models can be replaceable adapters rather
than a permanent dependency.

## 21. Cost Strategy

The project can begin as a low-cost software experiment.

Early costs can be close to zero if development uses: - local
development tools; - open-source compilers/parsers; - local/open models
where practical; - ordinary Git hosting or local Git; - static hosting
for prototypes.

Costs increase when adding: - hosted model inference; - large-scale
image processing; - cloud build infrastructure; - persistent project
storage; - collaboration; - deployment; - monitoring; - security; -
high-volume users.

Do not spend heavily before proving the semantic model and MVP.

The first objective is not to build a company-scale platform. It is to
prove that the abstraction actually makes software creation simpler.

## 22. Working Method for the Project

When developing this project with an AI assistant, use the assistant
primarily for: - explaining programming concepts; - challenging
assumptions; - proposing alternatives; - designing semantic models; -
testing examples; - researching existing approaches; - generating small
prototypes; - reviewing architecture; - identifying edge cases.

Do not let the assistant silently make major philosophical decisions.

For every major feature, ask: 1. What problem does this solve? 2. Does
it reduce user complexity? 3. Does it preserve precise meaning? 4. Can
an AI generate it reliably? 5. Can a compiler validate it? 6. Can humans
inspect it? 7. Can it map to multiple targets? 8. What happens when it
fails? 9. Can it be versioned? 10. Does it belong in the core language,
dictionary, template, adapter, or UI?

## 23. First Workbook Exercise

Design the semantic meaning of this example without worrying about
syntax:

make a website

make header put search inside header make search make button button
opens search

make content make cards

make footer small stay at bottom

mobile: collapse header keep search accessible

Questions: - Which words are entities? - Which are properties? - Which
are relations? - Which are actions? - Which are events? - Which are
conditions? - Which are constraints? - Which parts should come from a
dictionary? - Which parts should come from a template? - Which parts
require clarification? - What should the internal representation look
like?

Do not solve this by writing HTML/CSS/JS. The exercise is specifically
to design the meaning first.

## 24. The Core Hypothesis to Test

The project's central hypothesis is:

A sufficiently small, structured, extensible language of intent can
allow people to describe sophisticated software more simply than
conventional implementation languages, while AI and target adapters
translate that intent into reliable implementations.

The hypothesis is only valuable if it survives difficult examples.

Therefore, the project should continuously test: - simple UI; -
responsive UI; - interactive UI; - data-driven applications; - APIs; -
authentication; - error handling; - accessibility; - performance
constraints; - image-driven interfaces; - modifications to existing
projects; - multi-target generation.

If the abstraction works only for simple websites, it is a UI DSL.

If the abstraction remains useful across fundamentally different
software domains, it may be a general-purpose intent-oriented
programming system.

## 25. One-Sentence North Star

Make software describable in terms of what it should mean and do, while
allowing humans to remain simple and expressive and allowing AI and
machines to handle the implementation complexity.

## 26. First Real Implementation (Session 9)

The project moved from research to building. What now exists is a small
real toolchain in `src/mylang/` (lexer → parser → semantic → HTML
backend → CLI) that processes the smallest real program,
`examples/hello/hello.ine` (`make page` / `page title "Hello,
MyLanguage"`), verified by 24 tests and in a browser.

Recorded here as decisions/high-level facts:

- **File extension `.ine` (DECIDED).** Means intent
  expression. `.semantic.json` is retired as the human source format (it
  was a prototype of meaning; `examples/homepage/` keeps it as
  reference).
- **The implemented pipeline is the first real instance of the
  proposed architecture, not a commitment to the whole.** Stages are
  added when a real program needs them.
- **First limitation is real and concrete:** the HTML backend only
  renders kind `page`; the dictionary is not wired into the engine yet.

The design philosophy (what-to-before-how, Level 1/2/3, dictionary as
defaults, §8 priorities) is unchanged and still PENDING real programs
that exercise each piece. This milestone matches the workbook roadmap
Phase 1 → Phase 2 → Phase 3 (tiny model, tiny parser, first target) —
reached by building, not by planning.

### §26a. The requested milestone was different — and that mattered

The milestone actually requested for the first build was the **Say
vertical slice** (`say "Hello, world!"` → lexer → parser → AST →
interpreter → stdout), not the Entity/Property → HTML slice. Both are
now implemented (`say` added in Session 10); the Entity/Property work
was kept, not discarded, because it is a genuine second capability.

**What this surfaced (OPEN, observed, not a decision):** the language, as
actually built, now contains two different kinds of statements:

- **Describing a thing** — `make page`, `page title "Hello"` → model →
  target (HTML).
- **Doing something** — `say "Hello"` → execution → stdout.

The user's framing: this is exactly the kind of real problem the build
process was meant to reveal, and it should NOT be solved abstractly
ahead of more real programs. It is recorded here as an open question to
be answered by the next tiny real program — not a design decision.

## 27. The native-execution direction (Session 11)

The user corrected the project's self-understanding (recorded PROPOSED,
not yet a locked decision):

- **Intent Expression is its own language and semantic system.** Existing
  languages, APIs, runtimes, browsers, and machine-code technologies are
  things Intent Expression can interoperate with or target — they DO NOT define
  what Intent Expression means.
- The old framing "a translation layer into existing implementation
  technologies" is now treated as an EARLIER WORKING HYPOTHESIS, not the
  final definition.
- HTML is one backend, not the destination. The durable center is:
  `.ine → lexer/parser → Intent Expression semantics → execution → targets`
  (native CPU code, browser runtime, existing languages).

**Priority confirmed by the user for the CURRENT phase:** actual
execution over exhaustive testing. The first proof must show that
Intent Expression source becomes something the real computer executes.

**First native milestone (Session 11, implemented):** the smallest
working slice `.ine → native executable → CPU`, built by a NEW emit-C
target that coexists with the HTML backend:

```
say "Hello, native machine code"   →    .ine
      → lexer → parser                    (unchanged)
      → backend_c: emit C                 (printf("%s\n", ...))
      → external C compiler                (zig cc / clang / gcc)
      → native .exe → CPU
```

- Invoked as `python mylang.py <file.ine> --native`.
- All generated artifacts (emitted `.c`, compiled `.exe`) live in the
  project `.tmp/native/` — never committed. The original `mylang.py
  <file.ine> [-o out.html]` HTML path is untouched and still tested.
- `backend_c.py` lowers only `say` statements today; `make`/property
  produce no native output yet (the model is not yet lowered).
- A correctness detail found while building: user text is emitted as
  `printf("%s\n", "...")` (data, not format) so `%` in input can never
  be parsed as a C format specifier.
- **The verification step is blocked on tooling:** the machine has no C
  compiler. clang was installed but cannot link (missing MSVC runtime
  `libcmt.lib`). The chosen toolchain is **Zig** (`zig cc`), which
  bundles clang + lld + libc and produces native Windows executables
  with no extra SDK. Once installed, the end-to-end test
  (`test_native_executable_prints_on_the_cpu`, currently skipped) must
  run green.

### §27a. Verified (Session 12)

With Zig 0.16.0 installed by the user, the native slice is confirmed:

- `python mylang.py examples/native/hello.ine --native` emits C, Zig
  compiles a native Windows PE binary (`4D 5A` magic, x86-64 machine
  code), and the CPU runs it: stdout shows `Hello, native machine code`,
  exit 0.
- All 39 tests pass with none skipped; the HTML backend still writes
  `output/hello.html` byte-identical.
- This is the first real confirmation of the Session 11 direction:
  **Intent Expression source demonstrably becomes something the actual computer
  executes.** The emit-C route is a genuine compilation path (the C backend
  is our front end; clang inside `zig cc` is the machine-code back end),
  so the `.ine → machine code` claim is now real, not a plan.

**Side observation (OPEN, not a decision):** the language still carries
the two statement kinds from §26. The native milestone did NOT try to
solve that composition question — `say` was lowered directly, `make`
stayed in the model. The next real program should answer it.

**Temporary-File Policy (permanent rule):** all Intent Expression-generated
probes, generated source, executables, object files, compiler tests,
and intermediate artifacts go into the project `.tmp/` directory. Final
committed outputs stay in `output/`. `.tmp/` is gitignored. (Recorded
in AGENTS.md.)

## 28. The real homepage: smallest slice (Session 16)

The project's one real task — the homepage — drove the next step. The
user chose the smallest slice first instead of building the whole thing:

- **Entities:** page, header, logo, navigation.
- **One new concept:** Relationship via `name inside name` — CONTAINMENT
  only (a tree: one parent per entity, no self-parenting, no cycles).
  Recorded EXPERIMENTAL, not a decision about the full Relationship
  concept (beside, contains, opens stay future).
- **First real dictionary use:** `dictionary/*.json` now drives the HTML
  backend (a machine-readable `element` field per kind: page→div,
  header→header, logo→div, navigation→nav). Unknown kinds are rejected
  at render time.
- **Verification:** `examples/homepage-topbar/topbar.ine` renders a real
  nested page (golden `tests/expected/topbar.html`, byte-identical
  checked) AND compiles through C+Zig to a native exe that prints
  `Company Name`. 72 tests pass; `hello.ine` golden unchanged.
- **What it answered in practice:** the §26 describing/doing composition
  is alive — a describing program (page/inside) and a doing statement
  (`say page title`) coexist in ONE file and both work. The homepage's
  hero, cards, and footer are deliberately NOT built yet.

### §28a. The hero slice (Session 16b)

The homepage's next smallest slice: the hero region. `inside` now nests
three levels deep (`page > main > hero`). Two more dictionary kinds are
active (banner, container). **No new language concept was needed** —
this slice only required naming the kinds explicitly (`make main
container`, `make hero banner`), which is what make-with-kind already
existed for. Verified by golden output (`tests/expected/hero.html`) and
the native exe. The three cards remain the first slice that will
genuinely need **Multiplicity**.

### §29. The visual renderer experiment (Session 17)

A minimal direct visual renderer was built as a backend/adapter
experiment. It consumes the SAME semantic Model that the HTML backend
consumes and opens a real OS window (tkinter). **No new language
concepts were added.** The renderer is an implementation/backend
experiment, not a semantic rule.

**What it proved:**
- The Model-to-target adapter pattern works for a third target (HTML,
  native/C, visual/tkinter) without changing the Model or any existing
  backend.
- The dictionary kind → visual mapping is a backend concern, not a
  language concern. Each kind gets a color and layout rule in the
  renderer; the language does not know about colors.
- The containment tree (`inside` relationships) walks the same way for
  all three backends: find the page, walk children recursively. This is
  the adapter pattern the workbook proposed in §11.
- `python mylang.py examples/homepage-hero/hero.ine --visual` opens a
  real window with title "Company Name", a dark header bar with logo
  and navigation, a gray container, and a blue banner reading "Welcome
  to Our Site".

**What it did NOT change:**
- No new language syntax or semantics.
- No dictionary changes.
- No parser/lexer changes.
- HTML and native backends are byte-for-byte identical (golden tests
  still pass).

**Recorded as a permanent architectural observation:** the same `.ine`
program now drives three independent targets from the same Model. The
language is target-agnostic; the backends are adapters. This is the
workbook's §10 interoperability principle in its first real form.

### §30. The three-cards slice (Session 18)

The predicted first pain arrived. The homepage's next smallest slice —
three feature cards inside the main container — was written using EXISTING
concepts only: hand-written `make card-1 card` / `card-1 inside card-group`
per member. Four real pain points were documented (full details in
`.tmp/cards-slice-findings.md`), each with measured evidence:

1. **No side-by-side layout.** The `card-group` dictionary entry already
   declares `layout: row`, but neither backend applies it. Measured: all
   three cards render 784px wide, stacked at y=4/86/168. The workbook
   hinted at this ("flexbox/grid concepts"); the visual renderer made it
   concrete and measurable.
2. **Card titles silently dropped.** `card-1 title "Fast"` lives in the
   model but no backend renders it. Both backends only turn `text` into
   visible content (and `title` only at the page root). The dictionary
   says cards contain `["title", "description"]`; no engine reads that.
3. **Repetition.** Three cards cost 9 near-identical statements. This
   confirms the workbook's standing prediction (Sessions 16/16b): the
   three cards are the first real thing needing Multiplicity.
4. **Footer not pinned.** `footer.json` says "bottom of page, always";
   in 600px of space it renders at y=454.

**Decided nothing.** Worksheets §22 and the AGENTS.md authority rule: the
options are presented, the user picks. The candidates (in increasing
scope): (1) backends honor dictionary `layout: row`; (2) backends render
card titles as headings; (3) implement Multiplicity as the next language
feature.

### §31. Making the cards work — backend/dictionary only (Session 19)

The user directed: make the language functional as fast as possible,
"even if it is not exactly complete," and deferred the three §30 options
to the agent. The agent implemented options 1 + 2 — the fastest path to a
working homepage with zero language risk. Multiplicity stayed PROPOSED.

**What was done:**
- `dictionary/card-group.json` gained top-level `"layout": "row"`;
  `dictionary/footer.json` gained top-level `"position": "bottom"`.
  These are machine-readable renderer hints, the same class of backend
  detail as the existing `element` field — configuration for adapters,
  NOT language semantics (AGENTS.md guard respected).
- The HTML backend emits inline flex for a row-layout node and
  `flex:1` for its children; a child's `title` renders as `<h3>`. The
  visual backend packs row children side-by-side, pins `position:
  "bottom"` entities to the bottom edge, and renders `title` on a card
  as a bold heading.
- Measured in the visual window: cards moved from stacked full-width
  (y=4/86/168) to side-by-side in one row (x=6/289/547); footer moved
  from y=454 to y=561 of 600. Card titles visible in BOTH backends.

**Architectural observation:** the dictionary now holds two layers that
must not be conflated — semantic vocabulary (how the language describes
things: `defaults`. `guess`, the human `meaning` prose) and renderer
hints engineers and backends act on (`element`, `layout`, `position`).
Backends read the hints; the semantic layer stays unread by any target
so far. This is the §10 adapter pattern again, now with configuration.

**Still waiting on a language feature:** repetition. "Three cards" still
costs 9 statements; that remains the concrete, measured case for the
PROPOSED Multiplicity concept (§16/§30). The homepage WORKS today in all
three targets; nothing in the working slice requires the user to pick
the next feature yet.

## §32. Multiplicity is implemented (Session 21)

The user chose Multiplicity as the next feature and Option A for its
form. What now exists:

- **`make <count> <kind>` is real syntax** — `make 3 card` expands at
  parse time into `make card-1 card` / `card-2` / `card-3`. Parser-only:
  the model holds one entity per member, byte-identical to hand-writing.
  No new keyword, no lexer/semantic/backend changes.
- **`cards.ine` now uses it**, and the golden `cards.html` is unchanged —
  direct proof that multiplicity is sugar over the same model. The §30
  measured pain ("three cards cost nine statements") is solved: four
  statements became one.
- **113 tests pass.** A native probe verified the expanded entities
  resolve and print from a real PE executable.

**What multiplicity is NOT yet (PROPOSED, not decided):** the §30-§31
reading of the concept included grouping, a name for the collection,
"all members" addressing, and "every card has a title" per-member
application. Today those still use ordinary `inside`/property
statements. The collection/group semantics is the natural next slice —
the next real `.ine` program should decide whether it needs a group
entity or can keep composing from the six concepts.

## §33. Collection & Group semantics (Session 22)

The user's next architectural horizon: group naming, per-member property
application, and collective addressing. Option A (minimal scope) was
chosen, and it arrived as one new statement:

```
make 3 card
group cards = card-1 card-2 card-3
cards inside card-group     →  card-1 inside card-group  (once per member)
cards text "..."            →  card-1 text "..."         (once per member)
```

**Design decisions recorded:**
- `group <name> = <member> ...` names a collection of EXISTING
  entities. Groups live beside entities, not as entities: a group can be
  a statement target (`inside`, properties) but can never be `say`n,
  given a property of its own, or be a member of another group.
- Expansion is the Engine's job, at analysis time, BEFORE entity
  validation — so every existing rule (undeclared, one parent, no
  self-parenting, no cycles) applies unchanged to the per-member result.
  Backends never see groups (the model records them, targets materialize
  their members). This is the §10 adapter principle again.
- **A note on scope honesty:** the user picked "group only" — per-member
  properties were supposed to stay handwritten. Implementation added one
  small slice of that anyway: a property whose TARGET is a group applies
  to every member (the same 8-line expansion as collective `inside`). It
  satisfies the user's own stated goal 2 with no `every` keyword; it is
  flagged, not hidden, and the user may narrow it.

**What remains genuinely open (PROPOSED, not decided):** "every card
MUST have a title" (per-member obligation), collective `say`/
verification over a group's values, groups of groups, and "all members
of every group." None of these are needed by the homepage yet; the next
real program decides.

## §34. The language is named Ine (Session 23)

**DECIDED (user, Session 23).** The three names that public users will
touch are now uniform:

| Thing | Name |
|-------|------|
| Language | **Ine** |
| File extension | `.ine` |
| Terminal command | `ine` (`ine hello.ine -o hello.html`) |
| GitHub repository | `sudo-akash-sys/Ine` |

Two naming decisions deliberately pushed the project away from generic
branding: the working title "Intent Expression / Intent Language /
MyLanguage" was collapsed to a single short name, and the tool/project
name no longer differs from the language name (the old `mylang`
package/tool name existed precisely because "Intent Expression" was too
long to type). One name, three surfaces, no translation table for users.

**Engineering consequence (implemented):** `src/mylang/` → `src/ine/`
(a git rename, history preserved), root launcher `ine.py`, tests
`test_ine.py`, `pyproject.toml` with console script
`ine = "ine.cli:main"`, and `INE_CC` for the native toolchain override.
`python -m ine` is the documented fallback because Windows Store Python
installs `ine.exe` into a `Scripts/` directory that is not on PATH.
Backends, parser, and semantics were untouched — a rename of names, not
of architecture.

**Not decided yet:** a `pip install ine` PyPI release (the name may be
taken; the installable package could become `ine-lang` — the console
script stays `ine` either way), and whether the public repo keeps the
single-word branding in the long term.

## §35. The dictionary becomes a discoverable, queryable layer (Session 24)

The dictionary already existed as vocabulary data (`dictionary/*.json`,
10 entries) that backends read for renderer hints (`element`, `layout`,
`position`), but no engine read the semantic layer (`defaults`,
`contains`, `meaning`). The user asked for a deterministic discovery
system: given `make` or `make header`, what constructs are valid or
useful next — explicitly NOT an AI layer.

**What was done:**
- **`src/ine/dictionary.py`** — the single reader of `dictionary/*.json`
  (the backends' duplicated `DICTIONARY_DIR`/`_read_entry`/
  `_dictionary_entry` helpers now delegate to it). It answers, from data
  alone: `makeable()` (which kinds follow `make` — ambient `viewport` is
  excluded via its `provided-by: environment` field), `suggest(kind)`
  (properties from `defaults`, member concepts from `defaults.contains`,
  sibling kinds sharing the same semantic `kind` bucket), `properties_for`,
  `value_hint` (typed `properties` like viewport `width → "a length"`, or
  a `defaults` suggestion like header `height → "compact"`), `related`,
  and `for_model(model)` — what is valid in the context of a real program.
  All returned as `Suggestion(text, source, note)`.
- **`ine --dict [kind | file.ine]`** — new CLI query surface. No arguments
  lists the vocabulary; a kind name explains that kind; an `.ine` file
  explains what could be written next in that program. The `source`
  positional became optional (only for `--dict`).
- **Vocabulary data, all grounded in real programs or the user's brief:**
  new kinds `button`, `image`, `section`, `title`; `contains` added to
  `header` (logo, navigation, title — from topbar/cards), `page` (header,
  footer, title, section), `card-group` (card). Pure data; backends and
  golden outputs unchanged.
- **No language changes.** Parser, semantics, interpreter, all backends,
  multiplicity, and groups are untouched.

**Design choices (and why):**
- The dictionary stays a **companion, not a validator**: `alice.ine` uses
  `make alice person` with no `person` entry — the dictionary is advisory,
  never a rejection. This keeps recommendations additive and safe.
- Suggestions are **derived, not hardcoded**: adding a JSON entry
  automatically extends every query. Sibling relationships fall out of the
  existing semantic `kind` bucket (header/footer are both `"bar"`), no new
  schema.
- The two-layer dictionary already flagged in §31 stayed separate: this
  work reads the semantic layer for discovery; backends still read only
  renderer hints.

**Test results:** 151 tests pass (130 existing + 21 new `DictionaryTests`
covering lookups, makeable/vs-ambient, per-kind suggestions, value hints,
deduplication, members/related, model context, and the `--dict` CLI).

**What this is NOT yet (PROPOSED, not decided):** autocomplete wiring
into an editor, synonyms and ambiguity handling (§4), regex/prefix
matching and ranking, `defaults`-driven template instantiation (§5), and
any AI intent layer (§7). The next real experiment is likely synonym
normalization or prefix-completion over the same data — whichever the next
real `.ine` program exposes first.

## §36. The dictionary correction: properties vs structural members (Session 25)

The Session 24 discovery layer read mixed JSON faithfully: `defaults.contains`
blended content-property concepts (title, text, description, subtitle)
with genuine child entities (logo, navigation). The user's own programs
write `card-1 title "Fast"` as a PROPERTY, while the dictionary called
`title` a "member of card". A read-only semantics investigation answered
eight questions with parser/semantic/example evidence; this session
implemented its correction.

**DECIDED (user):** the language has exactly four semantic constructs
(Entity, Kind, Property, Relationship; Value attaches to a Property);
`title` and `text` are properties in real programs; `contains` means
structural child relationships only; the canonical relationship
direction is the one Ine writes (`child inside parent`); no siblings are
inferred from kind buckets; the dictionary stays advisory (never a
validator); no syntax change, no autocomplete, no synonym normalization.

**What was done:**
- **Data (`dictionary/*.json`):** removed `title`/`text`/`description`/
  `subtitle` from every `contains` list and re-grounded `contains` in
  real programs — page → header, footer, container; header → logo,
  navigation; container → banner (hero.ine); card-group → card; section
  → button, image. A new `dictionary/universal.json` declares `title`
  and `text` as universal content properties on every regular kind.
- **Booleans made honest:** `interactive` in button/logo was `true`/
  `false` — a value the language cannot express. Now a string hint
  stating it is not settable until Ine grows a boolean value type.
- **Reader (`src/ine/dictionary.py`):** `properties_for`/`value_hint`
  include universal `title`/`text`; `members` reads `contains` and notes
  are phrased `<child> inside <kind>`; the `kind`-bucket sibling
  inference and the `related()` API were removed. Backends untouched —
  they never read `contains` (still only `element`/`layout`/`position`).
- **Tests:** DictionaryTests rewritten to lock the distinction:
  title/text are properties, header suggests logo/navigation as
  children, card suggests no title/text children, member suggestions use
  `child inside parent` semantics, sibling inference is gone, universal
  property suggestions work. **154 tests pass.**

**Verification:** `ine --dict card` shows `title`/`text` as properties
and no "title inside card"; `ine --dict header` shows `logo inside
header` / `navigation inside header`. All four golden outputs (hello,
topbar, hero, cards) rebuild byte-identical — pure-data and
discovery-layer change, zero rendering change.

**Out of scope (per instruction, still PROPOSED later):** prefix
completion, synonym normalization, AI inference, parser changes, and a
broader semantic architecture.

## §37. Reverse containment in the dictionary (Session 26)

The §36 usability experiment's biggest gap (report D) was one-directional
placement discovery: `ine --dict <parent>` lists children, but
`ine --dict <child>` never said where the child could live — and
`card-group` and `section` had no dictionary parent at all, so a new user
could not be guided to place them.

**What was done:**
- **Data, re-grounded only where a demonstrated example exists:**
  - `page.json` `contains` → `["container", "footer", "header",
    "section"]` — `section inside page` is now demonstrated by
    `examples/dictionary-demo.ine` (built and rendered in Session 25).
    This restores `section` to page only because there is now real
    evidence for it; the §36 removal was evidence-motivated, not a
    permanent rule.
  - `container.json` `contains` → `["banner", "card-group"]` —
    `card-group inside container` is demonstrated by `cards.ine`
    (`card-group inside main`).
- **Reader (`src/ine/dictionary.py`):** new `parents(kind)` — the reverse
  of `members`, derived purely by inverting `contains` over regular
  kinds. No new schema, no new concepts.
- **CLI:** `ine --dict <kind>` now prints a "belongs inside:" block after
  properties/children (e.g. `section inside page`), so containment is
  discoverable in both directions.
- **Tests:** five new DictionaryTests (reverse direction for known
  relationships, the two formerly-orphan kinds, roots/unknowns/ambient
  are empty, content concepts like `title`/`text` are never parents).
  **159 tests pass.**

**Verification:** all four golden outputs (hello, topbar, hero, cards)
and the dictionary-demo build are unchanged. `ine --dict section` now
shows `belongs inside: page`; `ine --dict card-group` shows
`belongs inside: container`. No syntax, parser, semantic, or backend
change.

## §38. The editor experience: Ine VS Code autocomplete (Session 27)

The §35-§37 work made the dictionary discoverable from the CLI
(`ine --dict`). The next line to cross: the dictionary should help
*while editing*, not just from a terminal. Goal (deliberately tiny): a
user can open a `.ine` file, start typing, and get completions powered
by the existing dictionary — without leaving the editor.

**Architecture decision — the extension consumes the Python dictionary;
it does not own a second one.** Reading `dictionary/*.json` directly from
TypeScript was considered and rejected: the raw JSON is only half the
answer, and re-deriving `makeable`-filtering, universal `title`/`text`
merging, member phrasing and `parents()` inversion in TS is precisely
how "Ine says X, VS Code says Y" drift starts. Instead the extension
spawns the existing Python package as a JSON subprocess and renders what
it returns:

```
your buffer ──► python src/ine/autocomplete.py ──► VS Code popup
                    │
                    ▼
              ine.dictionary (the real dictionary, single source of truth)
```

- **`src/ine/autocomplete.py`** — new query backend. It decides which
  dictionary query a cursor position maps to and answers one JSON query
  per stdin/stdout round trip:
  - after `make `        → `dictionary.makeable()`
  - after a kind/entity  → `dictionary.suggest(kind)` (properties +
    structural members)
  - after `inside `      → `dictionary.parents(child_kind)` (the §37
    reverse containment, now doing real work in the editor)
  Entity resolution is lenient (no full parse): a name is a declared
  kind, an entity from `make name [kind]`, a numbered entity from
  `make <count> <kind>` (`card-1 ...`), or a group (`group cards = ...`)
  whose members share a kind. Unknown names → empty, never invented.
  No AI, synonyms, or fuzzy matching; the `.ine` grammar, parser,
  semantic engine and both backends are untouched.
- **`editor/vscode-ine/`** — the extension. `extension.js` is a pure
  proxy: it forwards `{buffer, line, column}` to the Python module under
  the workspace root and maps the response to `CompletionItem`s. It
  contains no Ine vocabulary. Activates only for `.ine` files
  (`onLanguage:ine`); `INE_PYTHON` env var overrides which Python runs.
- **Tests:** 31 new tests (`tests/test_autocomplete.py`) — context
  detection, entity resolution (kind / make-with-kind / multiplicity /
  groups / unknown), completion content and types for the three contexts,
  and the stdin/stdout protocol contract including a garbage-input guard.
  **190 tests pass** (159 + 31).

**Verified end-to-end** through the exact subprocess the extension uses:
`make he` → kinds (`header` among them); `header inside p` → `page`;
`header ` → `logo`, `navigation`, `height`, `title`, `text`, ...;
`card-1 ` (from `make 2 card`) → card properties; `cards inside `
(group) → `card-group`. All existing goldens byte-identical; the
dictionary and its data are unchanged — the editor now consumes the
one dictionary.

**Does not work yet:** property *values* (`page title "..."`), the
second argument of `make name kind`, completions while typing a property
name, caching/warm-up (one subprocess per keystroke), diagnostics and
formatting, and any packaging. All deliberately out of scope for the
prototype.

## §39. Autocomplete responsiveness (Session 28)

Manual testing of §38 found two UX gaps, both in the editor harness, not
the dictionary: (1) completion only auto-triggered after a space, so
typing `make h` never asked the dictionary; (2) each keystroke spawned a
fresh Python process (~140 ms measured), so suggestions felt delayed.

**Fixes, keeping the dictionary the single source of truth:**
- **Triggers:** the provider now registers `" "` *and* the ASCII letters
  as trigger characters — generic characters, not Ine vocabulary — so the
  editor asks the dictionary while a word is still being typed
  (`make h` → popup with `header`, ...). `extension.js` still holds zero
  language knowledge.
- **Duration:** one long-lived Python process. `src/ine/autocomplete.py`
  now answers a stream of JSON-lines queries (one request → one response;
  EOF after a request still exits, so the one-shot protocol is
  unbroken). `extension.js` gained a tiny `DictionaryWorker`: FIFO queue,
  responses matched in order, 4 s per-request timeout, respawn on death.
  The edit child is started eagerly at activation and killed on
  deactivate.
- **Measured:** warm-session query 0.3 ms vs ~140 ms fresh process
  (.tmp/latency_probe.py). The first keystroke still pays Python startup;
  every later one is effectively free.

**Tests:** three new ProtocolTests — a persistent process answers each
line in order, `id` is echoed back, and a garbage/error line does not
kill the loop (a later valid line is still answered). **193 tests pass**
(190 + 3). All goldens byte-identical; `ine --dict` unchanged; no
dictionary, syntax, parser, semantic, or backend change.

## §40. Property completions insert the value shape (Session 29)

After §38/§39 the dictionary suggested the right *property name*, but the
author still had to know (or remember) that `title` wants quotes. Next:
when a text property is selected, insert the expected value shape so the
cursor lands inside the quotes.

**Investigation first:** `value_hint()` returns a hint *string*, not a
value type; the dictionary has **no machine-readable type/shape
annotation** for program-writable properties. Only ambient `viewport.json`
carries `properties: {width: "length", height: "length"}` (not makeable,
so never completed). The one defensible text signal is `universal.json`
itself: its `meaning` text documents `title`/`text` usage with quoted
strings, and every real program writes them quoted. Everything else
(`layout: row`, `height: compact`, ...) takes bare words.

**Decision (conservative):** the engine marks *only* the two universal
content properties (`title`, `text`) as text-shaped. No dictionary file
changed — `_value_shape()` in `src/ine/autocomplete.py` derives the
shape from `dictionary._universal_defaults()`. Property items now carry
an optional `value_shape: "text"`; all other items keep `None`. Where the
dictionary has no signal, behavior is unchanged (no invented placeholders).

**Editor adapter only:** `extension.js` renders a text-shaped property as
a VS Code snippet — `insertText = new SnippetString('title "${1}"')` — so
selecting `title` yields `page title ""` with the cursor/placeholder
inside the quotes (typing fills the value). Snippet syntax stays isolated
in the extension; the engine only reports shapes.

**Tests:** six new ValueShapeTests — universal `title`/`text` are
text-shaped on any kind, regular properties (`height`) and concept items
(`logo`) are not, kind items carry no shape, and property labels/inserts
unchanged. **199 tests pass** (193 + 6). All goldens byte-identical;
`ine --dict` unchanged; no dictionary, syntax, parser, semantic, or
backend change.

## §41. Value shapes move into the dictionary (Session 30)

§29 hardcoded in `autocomplete.py` that `title`/`text` are text-valued.
This session removes that special case: the dictionary itself now
describes a property's value shape, and both readers consume it
generically. No autocomplete behavior was expanded.

**Evidence survey (all 15 dictionary files):** there is no program-
writable property with a machine-readable value type today except the two
universal content properties — `universal.json` `meaning` documents
`title`/`text` with quoted-string examples and every real program writes
them quoted. `viewport.json` already carries a `properties` block
(`width`/`height` → `"length"`), which is the same idea. Nothing else is
safe: `card-group layout` is a single `"row"` string, not a known set;
`height`/`padding`/`border` are prose defaults. No types were invented.

**Dictionary representation chosen** (mirrors the existing `viewport`
precedent):
```json
"properties": {
  "title": "text",
  "text": "text"
}
```
A `properties` block maps a property name to its value shape: a plain
string names a value kind (`"text"`, `"length"`, ...); a list of strings
names a `"choice"` with those allowed options (`"layout": ["row",
"column"]` would be the future form). The representation already
*describes* future enumerated choices even though no entry uses one yet.

**Reader (`src/ine/dictionary.py`):** new public `ValueShape` dataclass
(`type`, default `"unknown"`; `choices`), the normalizer `_shape_from`
(string → named type, list of strings → choice, else unknown), and the
reader `value_shape(kind, prop)` — a kind's own `properties` block first,
then the universal entry's for the content properties. Read from metadata
only, never inferred; `value_hint` (prose/default) and `properties_for`
are untouched.

**Consumers:** `autocomplete.py` dropped `_value_shape()` (no more
title/text knowledge); a property item's `value_shape` is now
`dictionary.value_shape(kind, item.text)`. `extension.js` unchanged — it
still turns `value_shape == "text"` into the `title "${1}"` snippet.

**Tests:** new DictionaryTests + `_shape_from` capacity tests (str →
kind, list → choice with options, non-data → unknown, existing viewport
`"length"` types read back). **204 tests pass** (199 + 5). All goldens
byte-identical; `ine --dict <real kind>` unchanged (the pseudo-entry
`--dict universal` now shows `a text` — a side effect of it owning a
`properties` block, still valid). No syntax, parser, semantic, backend,
or autocomplete-behavior change.

**Still inexpressible:** there is no evidence-based value kind beyond
`text` (and ambient `length`). `layout`, `height`, `padding`, `border`,
`orientation` etc. have only single prose defaults — declaring them as
choices would require confirming the option set from real programs first.

## §42. The value completion context and a dictionary coverage check (Session 31)

Autonomous session, following the PLAN selection rule onto the two
`EXECUTABLE` steps (§41-era plan): property-value completion, then the
dictionary coverage check.

**Property-value completion (§42a).** After §40's snippet, selecting a
text property inserts `title ""` with the cursor inside — but an author
who types the property by hand (or needs the shape on an existing line)
had no value-position completion. The engine now recognizes a new
context: a line ending `<name> <property> ` (trailing separator, two
words, not `inside`/`make`) maps to `dictionary.value_shape(kind, prop)`:

- `text`  → one item, label/insert `""`, detail = `value_hint(kind, prop)`
  (e.g. "the heading or name of the thing");
- `choice` → one item per allowed option (bare-word insert);
- `unknown` / unresolvable name → empty, never invented.

`autocomplete.py` only gains the `value` branch; the dictionary is queried
via the existing `value_shape` reader. **`extension.js` needed no change**:
item type `value` already falls through to VS Code's generic
`CompletionItemKind.Value` and the thin proxy surfaces the items as-is —
no second vocabulary, no snippet logic touched. Eight new tests (context
detection, text placeholder + hint, multiplicity resolution, unknown
property/name → empty, a patched `choice` shape listing its options, and
the `value` context echoed in the response). **212 tests pass** (204 + 8).
All goldens byte-identical; no dictionary, semantic, or backend change.

**Dictionary coverage check (§42b).** Reconciled every kind, property,
and containment pair in all real programs (`examples/**/*.ine`) plus
WORKBOOK/LANGUAGE mentions against the dictionary:

- **All real-program vocabulary is covered.** Every property written is
  in `properties_for(kind)` (or universal `title`/`text`); every
  containment pair resolves to a structural member (`header inside page`,
  `logo`/`navigation inside header`, `container`/`footer`/`section inside
  page`, `banner`/`card-group inside container`, `card inside card-group`,
  `button`/`image inside section` — with the entity aliases `hero`→`banner`
  and `main`→`container` resolving cleanly).
- **Two stale self-flags in `examples/dictionary-demo.ine` corrected.**
  The demo asserts "card-group has no dictionary parent" and "section has
  no dictionary parent" — both false since §37 gave `container → card-group`
  and `page → section`. Comments updated to match the dictionary (comments
  only; render unchanged).
- **Evidence-gated mentions stay undeclared (correctly).** `search`
  (WORKBOOK proposes it as a header member throughout, but no real `.ine`
  uses it), `subtitle`/`description` (stripped from `contains` in §36 for
  lack of evidence), and WORKBOOK L544's `button inside header` layout (vs
  the dictionary's evidence-grounded `button inside section`) are all
  recorded in `.agent/BLOCKERS.md` and left out of every dictionary file.
- **Scope boundary, not a gap:** `examples/alice/alice.ine` defines a
  custom kind `person` with `name`/`age`/`height` for the native target.
  The advisory dictionary enumerates a guided homepage footprint, not
  every user domain; arbitrary kinds are a first-class language feature.

After §42a + §42b, no `EXECUTABLE` item remains in `.agent/PLAN.md`; the
plan's selection rule therefore says stop and record — this session did.
