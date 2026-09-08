# Intent-First Programming Language --- Guidebook & Workbook

A working specification for a simple, AI-native, behavior-oriented
software language

## 0. Project Identity

Working name: Intent-First Programming Language (temporary name).

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
`examples/hello/hello.int` (`make page` / `page title "Hello,
MyLanguage"`), verified by 24 tests and in a browser.

Recorded here as decisions/high-level facts:

- **File extension `.int` (PROPOSED, working choice).** Means intent.
  `.semantic.json` is retired as the human source format (it was a
  prototype of meaning; `examples/homepage/` keeps it as reference).
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

- **MyLanguage is its own language and semantic system.** Existing
  languages, APIs, runtimes, browsers, and machine-code technologies are
  things MyLanguage can interoperate with or target — they DO NOT define
  what MyLanguage means.
- The old framing "a translation layer into existing implementation
  technologies" is now treated as an EARLIER WORKING HYPOTHESIS, not the
  final definition.
- HTML is one backend, not the destination. The durable center is:
  `.int → lexer/parser → MyLanguage semantics → execution → targets`
  (native CPU code, browser runtime, existing languages).

**Priority confirmed by the user for the CURRENT phase:** actual
execution over exhaustive testing. The first proof must show that
MyLanguage source becomes something the real computer executes.

**First native milestone (Session 11, implemented):** the smallest
working slice `.int → native executable → CPU`, built by a NEW emit-C
target that coexists with the HTML backend:

```
say "Hello, native machine code"   →    .int
      → lexer → parser                    (unchanged)
      → backend_c: emit C                 (printf("%s\n", ...))
      → external C compiler                (zig cc / clang / gcc)
      → native .exe → CPU
```

- Invoked as `python mylang.py <file.int> --native`.
- All generated artifacts (emitted `.c`, compiled `.exe`) live in the
  project `.tmp/native/` — never committed. The original `mylang.py
  <file.int> [-o out.html]` HTML path is untouched and still tested.
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

- `python mylang.py examples/native/hello.int --native` emits C, Zig
  compiles a native Windows PE binary (`4D 5A` magic, x86-64 machine
  code), and the CPU runs it: stdout shows `Hello, native machine code`,
  exit 0.
- All 39 tests pass with none skipped; the HTML backend still writes
  `output/hello.html` byte-identical.
- This is the first real confirmation of the Session 11 direction:
  **MyLanguage source demonstrably becomes something the actual computer
  executes.** The emit-C route is a genuine compilation path (the C backend
  is our front end; clang inside `zig cc` is the machine-code back end),
  so the `.int → machine code` claim is now real, not a plan.

**Side observation (OPEN, not a decision):** the language still carries
the two statement kinds from §26. The native milestone did NOT try to
solve that composition question — `say` was lowered directly, `make`
stayed in the model. The next real program should answer it.

**Temporary-File Policy (permanent rule):** all MyLanguage-generated
probes, generated source, executables, object files, compiler tests,
and intermediate artifacts go into the project `.tmp/` directory. Final
committed outputs stay in `output/`. `.tmp/` is gitignored. (Recorded
in AGENTS.md.)
