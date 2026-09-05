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
statement   := make-stmt | property-stmt | say-stmt
make-stmt   := "make" name [kind]
property-stmt := name property "value"
say-stmt    := "say" "value"
name        := identifier          (letters, digits, "_", "-"; not starting with a digit)
```

- One statement per line. Blank lines and `#` comments are allowed.
- `make <name>` declares an entity; its kind defaults to its name.
  `make <name> <kind>` declares an entity of an explicit kind.
- `<name> <property> "value"` sets a property on an existing entity.
  Values must be quoted strings (values of other kinds do not exist yet).
- `say "value"` prints the value to stdout when the program runs.
- Each statement occupies exactly one line; extra text is a syntax error.

## 4. Semantics (current, EXPERIMENTAL)

A program builds a Model containing:

- Entities: each declared once, with an id and a kind.
- Properties: stored per entity (`(entity, property) → value`).

Validation the model performs (real meaning, not text matching):

- a property on an entity that was never declared → error
- an entity declared more than once → error
- syntax the tool does not recognize → error with line number

## 5. Concepts actually in use

Of the six PROPOSED semantic concepts (Entity, Property, Relationship,
State, Condition, Multiplicity), the implementation currently exercises:

- Entity — `make`
- Property — `<name> <property> "value"`

Relationship, State, Condition, Multiplicity: not yet expressible in
`.int`. They will be added when a real program needs them.

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

The HTML backend currently understands exactly one kind: `page`. A
program must declare exactly one page entity. Rendering: the page's
`title` property becomes the document `<title>` and the page heading.
Any other kind is rejected with "the html backend does not support this
kind yet".

The dictionary (`dictionary/*.json`, 9 kinds) is NOT yet read by the
engine; kind behavior and defaults are hard-coded in the backend for now.

## 7. Known limits (as of Session 10)

- Only string literal values (for properties and `say`).
- Only kind `page` renders to HTML.
- No relationships (nothing can be `inside` anything), so a page cannot
  yet contain children.
- No escaping inside string literals.
- `say` runs top-to-bottom in program order (execution order beyond that
  is not decided).