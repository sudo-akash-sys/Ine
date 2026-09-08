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
property-stmt := name property value
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

Validation the model performs (real meaning, not text matching):

- a property on an entity that was never declared → error
- an entity declared more than once → error
- syntax the tool does not recognize → error with line number

## 5. Concepts actually in use

Of the six PROPOSED semantic concepts (Entity, Property, Relationship,
State, Condition, Multiplicity), the implementation currently exercises:

- Entity — `make`
- Property — `<name> <property> value`
- **Describing feeds doing (EXPERIMENTAL, implemented):** `say name
  property` resolves at compile time to the stored literal value. This is
  the first concrete answer to the workbook §26 "describing vs. doing"
  question — one kind of statement can now feed the other — but it is a
  COMPILE-TIME resolve only. There is no runtime model, no variables, no
  mutation, and no dynamic lookup yet.

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
  cannot link (needs the MSVC runtime); `zig cc` is the recommended
  toolchain because it bundles clang + lld + libc.
- Every generated artifact (`.c`, `.exe`) is written to the project
  `.tmp/native/` directory. Nothing generated here is committed.

## 7. Known limits (as of Session 12)

- Only strings and numbers as values. No booleans, lists, or other
  types yet.
- Only kind `page` renders to HTML.
- Only `say` lowers to native; `make`/property are not yet lowered.
- `say name property` resolves at COMPILE time only — the value is
  baked into the emitted program. No runtime model, variables, mutation,
  expressions, or dynamic lookup.
- No relationships (nothing can be `inside` anything), so a page cannot
  yet contain children.
- No escaping inside string literals.
- `say` runs top-to-bottom in program order (execution order beyond that
  is not decided).
- Native target requires an external C compiler (Zig recommended); the
  end-to-end native test is skipped when none is installed.