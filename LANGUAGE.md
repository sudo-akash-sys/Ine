# Ine — Language Specification

Status: everything in this file describes what is ACTUALLY IMPLEMENTED
in `src/ine/` so far. It grows as the language grows. Nothing here is
final — the whole language (concepts, syntax, architecture) is still
PROPOSED / EXPERIMENTAL.

## 1. Files

An Ine program is a text file. Extension: `.ine` (the language's
name is Ine; the extension spells it). DECIDED.

## 2. Pipeline (as implemented)

```
.ine source
    → lexer       (text → tokens)
    → parser      (tokens → syntax statements)
    → semantic    (meaning: model statements → model; validates meaning)
    → interpreter (execution: say statements → stdout)
    → backend     (target: model → output; currently HTML when the program describes a page)
```

Invoked as `ine <file.ine> [-o out.html]`.

## 3. Grammar (current, EXPERIMENTAL)

```
program     := statement*
statement   := make-stmt | property-stmt | rel-stmt | say-stmt | group-stmt
make-stmt   := "make" name [kind]
             | "make" count kind      (multiplicity)
property-stmt := name property value
rel-stmt    := name "inside" name
say-stmt    := "say" value | "say" name property
group-stmt  := "group" name "=" name+
name        := identifier          (letters, digits, "_", "-"; not starting with a digit)
value       := "string" | number   (number: integer or decimal, e.g. 25 or 1.75)
count       := positive whole number, e.g. 3 (not 0, not 3.5)
```

- One statement per line. Blank lines and `#` comments are allowed.
- `make <name>` declares an entity; its kind defaults to its name.
  `make <name> <kind>` declares an entity of an explicit kind.
- `make <count> <kind>` declares `<count>` entities (multiplicity). Their
  ids are `<kind>-1`, `<kind>-2`, ..., `<kind>-<count>` and their kind is
  `<kind>`. The count must be a positive whole number. This is parser
  sugar: it expands into `<count>` ordinary `make` statements, so the
  model holds one entity per member — identical to writing them by hand.
- `group <name> = <member> ...` names a collection (group semantics). All
  members must already be declared with `make`. Group names live beside
  entity names: a group is not an entity, and a name cannot be both. Once
  named, the group may be used as a target:
  - `<group> inside <parent>` places every member inside the parent.
  - `<group> <property> <value>` applies the property to every member.
  Both expand — at semantic-analysis time — to one ordinary statement per
  member, then follow every existing rule (undeclared, self-parenting,
  double-parenting, cycles). The model records the group in `groups` but
  otherwise backends never see groups.
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

- Entity — `make`, and `make <count> <kind>` for an explicit group
- Property — `<name> <property> value`
- Relationship — `name inside name` (CONTAINMENT only, implemented in
  the homepage-topbar slice). This is the smallest real slice of the
  workbook homepage task: page → header → (logo, navigation). One child
  per parent; a tree, not any graph.
- Multiplicity — `make <count> <kind>` (creation sugar, added Session
  21). It answers the measured "three cards cost nine statements" pain:
  a group is written as ONE statement, and the model still holds one
  entity per member.
- Collection/Group — `group <name> = <members>`, then group targets on
  `inside` and properties (added Session 22). Together, `make 3 card` +
  `group cards = ...` + `cards inside card-group` replace the original 9
  handwritten statements with 3, and a property on the group applies to
  every member.
- **Describing feeds doing (EXPERIMENTAL, implemented):** `say name
  property` resolves at compile time to the stored literal value. This is
  the first concrete answer to the workbook §26 "describing vs. doing"
  question — one kind of statement can now feed the other — but it is a
  COMPILE-TIME resolve only. There is no runtime model, no variables, no
  mutation, and no dynamic lookup yet.

State, Condition: not yet expressible in `.ine`. They will be added
when a real program needs them.

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
navigation, banner, container, card, card-group, footer, title, button,
image, section, viewport.

The dictionary is consulted by the engine for the element mapping and
for two machine-readable layout hints (same class of backend detail as
`element`): a top-level `layout: "row"` marks a kind whose children
render side by side (`card-group`), and a top-level `position: "bottom"`
marks a kind that is pinned to the bottom edge (`footer`). The `defaults`
and `guess` fields are not yet applied (no CSS stylesheet generation);
nodes and children in a row get inline flex styles instead.

A single reader — `src/ine/dictionary.py` — loads every entry and answers
deterministic discovery questions from the data alone (no AI, no
hardcoded lists): which kinds can follow `make`, which properties a kind
accepts, which structural children belong inside a kind, and (by
reversing `contains`) which kinds a child can live inside. Query it
with `ine --dict [kind | file.ine]`, or in code via
`ine.dictionary.{suggest, properties_for, value_hint, members, parents,
for_model}`. The dictionary is advisory: it never rejects a kind or
property (see the `person` kind in examples/alice).

The dictionary keeps three categories separate:

- **Kinds** — entities a program can declare with `make`.
- **Properties** — `<name> <property> <value>` statements. `title` and
  `text` are universal content properties: every declared kind may take
  them (`page title "Hello"`, `card-1 title "Fast"`, `card-1 text
  "Something"` — a title is a property, not a child). All other
  properties are kind-specific advisory hints.
- **Structural members** — child kinds that belong inside a kind,
  stated in the direction Ine writes relationships: `<child> inside
  <parent>` (e.g. `logo inside header`, `card inside card-group`).
  `defaults.contains` lists only these. No siblings are inferred from a
  kind's `kind` bucket. Containment is discoverable in both directions:
  querying a parent shows its children (`ine --dict page` lists
  "section inside page"), and `ine --dict <child>` reports where it
  belongs (`belongs inside`), derived by inverting `contains`. Child
  relationships are grounded in real programs (e.g. `card-group inside
  container` from cards.ine, `section inside page` from
  dictionary-demo.ine).

## 6a. Target: native executable (current, EXPERIMENTAL)

Invoked as `ine <file.ine> --native`.

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
- The external compiler is found in this order: `INE_CC` environment
  variable, then `zig`, then `clang`, then `gcc`. On Windows, clang alone
  cannot link (needs the MSVC runtime `libcmt.lib`); `zig cc` is the
  recommended toolchain because it bundles clang + lld + libc.
- Every generated artifact (`.c`, `.exe`) is written to the project
  `.tmp/native/` directory. Nothing generated here is committed.

## 6b. Target: visual window (current, EXPERIMENTAL)

Invoked as `ine <file.ine> --visual`.

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

## 7. Known limits (as of Session 22)

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
  No `beside`, `opens`, or other non-containment relationships yet.
- Groups are a naming/expansion mechanism only. A group cannot itself be
  `say`n (`say cards title` is an error) and cannot be a member of
  another group. There is no `every` keyword and no way to address "all
  members of every group" as a single target.
- No escaping inside string literals.
- `say` runs top-to-bottom in program order (execution order beyond that
  is not decided).
- Native target requires an external C compiler (Zig recommended); the
  end-to-end native test is skipped when none is installed.
- Visual target requires a display server (tkinter); no headless mode.