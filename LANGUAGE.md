# MyLanguage — Language Specification

Status: everything in this file describes what is ACTUALLY IMPLEMENTED
in `src/mylang/` so far. It grows as the language grows. Nothing here is
final — the whole language (concepts, syntax, architecture) is still
PROPOSED / EXPERIMENTAL.

## 1. Files

A MyLanguage program is a text file. Extension: `.int` (int = intent).
PROPOSED — the current working choice, not final.

## 2. Pipeline (as implemented)

```
.int source
    → lexer       (text → tokens)
    → parser      (tokens → syntax statements)
    → semantic    (meaning: model statements → model; validates meaning)
    → interpreter (execution: say statements → stdout)
    → backend     (target: model → output; currently HTML when the program describes a page)
```

Invoked as `python mylang.py <file.int> [-o out.html]`.

## 3. Grammar (current, EXPERIMENTAL)

```
program     := statement*
statement   := make-stmt | property-stmt | rel-stmt | say-stmt
make-stmt   := "make" name [kind]
property-stmt := name property value
rel-stmt    := name "inside" name
say-stmt    := "say" value | "say" name property
name        := identifier          (letters, digits, "_", "-"; not starting with a digit)
value       := "string" | number   (number: integer or decimal, e.g. 25 or 1.75)
```

- One statement per line. Blank lines and `#` comments are allowed.
- `make <name>` declares an entity; its kind defaults to its name.
  `make <name> <kind>` declares an entity of an explicit kind.
- `<name> <property> value` sets a property on an existing entity. Values
  are typed: quoted strings, or numbers. A number becomes an integer
  when it has no `.`/`e`, otherwise a decimal.
- `name inside name` declares containment: the first entity lives inside
  the second. Both entities must already be declared. An entity can be
  inside at most one parent, cannot be inside itself, and containment
  must not form a cycle. `inside` is a reserved word.
- `say value` prints the value to stdout when the program runs (strings,
  integers, and decimals all work).
- `say name property` prints a value from the model: the referenced
  entity's property, **resolved at compile time** into its literal value.
  Both `say` forms print exactly the same result for the same value.
- Each statement occupies exactly one line; extra text is a syntax error.

## 4. Semantics (current, EXPERIMENTAL)

A program builds a Model containing:

- Entities: each declared once, with an id and a kind.
- Properties: stored per entity `(entity, property) → value`.
  Property values are typed (str / int / float).
- Relationships: stored as `child → parent` (containment). A child has
  exactly one parent; containment is a tree (no self-parenting, no
  cycles).

Validation the model performs (real meaning, not text matching):

- a property on an entity that was never declared → error
- an entity declared more than once → error
- `inside` referencing an undeclared entity → error
- an entity inside more than one parent → error
- an entity inside itself → error
- a containment cycle → error
- syntax the tool does not recognize → error with line number

## 5. Concepts actually in use

Of the six PROPOSED semantic concepts (Entity, Property, Relationship,
State, Condition, Multiplicity), the implementation currently exercises:

- Entity — `make`
- Property — `<name> <property> value`
- Relationship — `name inside name` (CONTAINMENT only, implemented in
  the homepage-topbar slice). This is the smallest real slice of the
  workbook homepage task: page → header → (logo, navigation). One child
  per parent; a tree, not any graph.
- **Describing feeds doing (EXPERIMENTAL, implemented):** `say name
  property` resolves at compile time to the stored literal value. This is
  the first concrete answer to the workbook §26 "describing vs. doing"
  question — one kind of statement can now feed the other — but it is a
  COMPILE-TIME resolve only. There is no runtime model, no variables, no
  mutation, and no dynamic lookup yet.

State, Condition, Multiplicity: not yet expressible in `.int`. They will
be added when a real program needs them.

### 5a. Two kinds of statements (EXPERIMENTAL, observed — not decided)

Building the `say` capability revealed the language currently carries
two different kinds of statements:

- **Describing** — `make` / property: build the model. Translated to a
  target (HTML) when the program describes a page.
- **Doing** — `say`: executed. Prints to stdout. Never translated into
  HTML; it is not part of the model.

Yes, both may appear in the same program and both happen. Whether these
are really one kind of statement or two, and how they should compose, is
an OPEN QUESTION the language revealed through building — deliberately
NOT decided yet (workbook §26).

## 6. Target: HTML (current)

The HTML backend renders one entity of kind `page`, then nests every
entity that is `inside` it (recursively) as child elements. Supported
kinds come from `dictionary/*.json`: each dictionary entry that declares
an `element` can be rendered; a declared kind with no dictionary entry is
rejected with "the html backend does not support this kind yet". The
page's `title` property becomes the document `<title>` and the page
heading; a child's `text` property becomes its element content, and a
non-leaf/leaf child's `title` property renders as an `<h3>`.

Kinds currently declared in the dictionary: page, header, logo,
navigation, banner, container, card, card-group, footer, viewport.

The dictionary is consulted by the engine for the element mapping and
for two machine-readable layout hints (same class of backend detail as
`element`): a top-level `layout: "row"` marks a kind whose children
render side by side (`card-group`), and a top-level `position: "bottom"`
marks a kind that is pinned to the bottom edge (`footer`). The `defaults`
and `guess` fields are not yet applied (no CSS stylesheet generation);
nodes and children in a row get inline flex styles instead.

## 6a. Target: native executable (current, EXPERIMENTAL)

Invoked as `python mylang.py <file.int> --native`.

Pipeline for the native target:

```
statements → backend_c.emit → .c file → external C compiler → .exe → run on CPU
```

- Lowers only `say` statements today. `make`/property statements produce
  no native output yet (the semantic model is not yet lowered).
- Emission is a designed-in chunk of the lowering: string values become
  `printf("%s\n", "value")`, integers become `printf("%d\n", 25)`, and
  decimals become `printf("%.17g\n", 1.5)`. Strings are DATA (the `%s`
  argument), never format text, so input like `100%` can never be parsed
  as a C format specifier.
- The external compiler is found in this order: `MYLANG_CC` environment
  variable, then `zig`, then `clang`, then `gcc`. On Windows, clang alone
  cannot link (needs the MSVC runtime `libcmt.lib`); `zig cc` is the
  recommended toolchain because it bundles clang + lld + libc.
- Every generated artifact (`.c`, `.exe`) is written to the project
  `.tmp/native/` directory. Nothing generated here is committed.

## 6b. Target: visual window (current, EXPERIMENTAL)

Invoked as `python mylang.py <file.int> --visual`.

Pipeline for the visual target:

```
Model → backend_visual.render → tkinter window (real OS window)
```

- Consumes the SAME Model that the HTML backend consumes. Reads
  entities, properties, and relationships. No new language concepts.
- Each dictionary kind maps to a color and layout rule (page→white,
  header→dark gray, banner→blue, etc.). The mapping is a backend
  concern, not a language concern.
- Children of a `layout: "row"` entity (card-group) are packed
  side-by-side with equal width; entities whose dictionary entry declares
  `position: "bottom"` (footer) are pinned to the bottom edge. A `card`
  renders its `title` property as a bold heading above its `text`.
- The containment tree is walked recursively, the same way as the HTML
  backend. The renderer is a pure adapter experiment.
- Returns the `tk.Tk` root so callers can inspect or destroy it without
  running mainloop. The CLI path calls `show()` which runs mainloop
  (blocking).
- Currently requires a display server (tkinter). No headless mode yet.

## 7. Known limits (as of Session 19)

- Only strings and numbers as values. No booleans, lists, or other
  types yet.
- HTML renders only kinds declared in `dictionary/*.json` with an
  `element`; only `page` is a guaranteed root. `text`/`title` feed
  content; `layout: "row"` and `position: "bottom"` hints produce inline
  flex styles (a `title` renders as an `<h3>`). The `defaults`/`guess`
  fields, fully external CSS, and the `page title` ↔ `<h1>` heading are
  still basic.
- Only `say` lowers to native; `make`/property/`inside` are not yet
  lowered.
- `say name property` resolves at COMPILE time only — the value is
  baked into the emitted program. No runtime model, variables, mutation,
  expressions, or dynamic lookup.
- Relationship is CONTAINMENT only: one parent per entity, tree-shaped.
  No `beside`, `opens`, non-containment relationships, or multiplicity
  (a "group with three members" cannot be expressed yet).
- No escaping inside string literals.
- `say` runs top-to-bottom in program order (execution order beyond that
  is not decided).
- Native target requires an external C compiler (Zig recommended); the
  end-to-end native test is skipped when none is installed.
- Visual target requires a display server (tkinter); no headless mode.