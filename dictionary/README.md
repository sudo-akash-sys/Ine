# The Ine dictionary

The dictionary is **the single discoverable vocabulary** of Ine. Every
file in this directory declares one concept — usually a kind a program can
create with `make`, but also ambient concepts and the universal-properties
pseudo-entry. `src/ine/dictionary.py` is the only place that reads these
files, and it answers discovery questions from them alone:

- what can follow `make`?                               (`makeable`)
- what properties does a kind accept?                   (`properties_for`)
- what value does a property expect?                    (`value_shape` / `value_hint`)
- which children belong inside a kind?                  (`members` / `parents`)

The dictionary is **advisory, never a validator**. It guides completion and
rendering hints; it does not reject programs. A kind with no dictionary entry
simply has no suggestions (see `examples/alice/alice.ine` for a program that
uses kinds the dictionary does not declare, on purpose).

## The JSON schema

Each `.json` file in this directory declares one entry. A typical entry looks
like this (abridged from `dictionary/header.json`):

```json
{
  "term": "header",
  "kind": "bar",
  "element": "header",
  "meaning": "A bar spanning the top edge of its container, holding brand and primary navigation.",
  "defaults": {
    "height": "compact",
    "orientation": "horizontal",
    "contains": ["logo", "navigation"]
  },
  "implementation": {
    "html": "header element",
    "guess": ["display: flex", "align-items: center"]
  }
}
```

Every field is optional except `term` and `meaning`. Files that fail to
parse, are not JSON objects, or lack a `term` are skipped with a `warning`
naming the file — a broken file never raises or stops the editor.

| Field           | Meaning                                                                                              |
| --------------- | ---------------------------------------------------------------------------------------------------- |
| `term`          | Unique identifier for the concept — the kind name a program writes (`make header`).                  |
| `kind`          | Informational category (`container`, `bar`, `surface`, `ambient`, ...). Not used for inference.      |
| `element`       | The HTML element tag the backend renders this kind with (`header`, `article`, `div`, ...).           |
| `meaning`       | Human-readable description; shown as the completion detail for a suggested kind.                     |
| `defaults`      | Property hints for completion. Each value is a short hint string; supported by `properties` for the actual value shape. |
| `defaults.contains` | Structural children that belong inside this kind (`contains: ["logo", "navigation"]`). Drives `members` and `parents`. |
| `properties`    | Typed property declarations (see "Value shapes" below). Drives `value_shape()` / `value_hint()`.     |
| `implementation`| Renderer notes and guessed CSS; informational only, no backend reads it today.                       |
| `provided-by`   | Marker for ambient entries: the concept is supplied by the host environment, so it is excluded from `makeable()`. |
| `universal`     | `true` on the special universal-properties pseudo-entry (see below).                                 |

Anything not in this table is ignored by the reader – keep unknown fields
out or accept that they only serve as notes.

### Value shapes (`properties`)

A `properties` block maps a property name to its value shape. Three shapes
exist today:

```json
"properties": {
  "title": "text",          "headline": "a quoted string of content",
  "width": "length",        "length": "a measurement",
  "layout": ["row", "column"]
}
```

| Shape            | JSON form                         | Meaning                                  |
| ---------------- | --------------------------------- | ---------------------------------------- |
| `text`           | `"title": "text"`                 | A quoted string (universal `title`/`text`). |
| `length`         | `"width": "length"`               | A measurement (ambient `viewport`).      |
| `choice`         | `"layout": ["row", "column"]`     | A known set of bare-word options.        |

No entry declares a `choice` value yet — the value-shape reader can express
them (`value_shape(kind, prop)` returns `ValueShape("choice", (...))`), the
representation is decided, but no property carries evidence for more than its
documented value. Do not invent one without a real program or a WORKBOOK
decision.

### Ambient entries (`provided-by`)

Ambient kinds are supplied by the host environment, not declared by the
program. `dictionary/viewport.json` is the example:

```json
{
  "term": "viewport",
  "kind": "ambient",
  "provided-by": "environment",
  "properties": { "width": "length", "height": "length" }
}
```

Ambient entries are excluded from `makeable()` (a program cannot `make
viewport`), but their declared properties are still suggested and typed.

### The universal entry

`dictionary/universal.json` is a pseudo-entry (`"universal": true`) that owns
the universal content properties available on **every declared kind**:

```json
{
  "term": "universal",
  "universal": true,
  "properties": { "title": "text", "text": "text" },
  "defaults": {
    "title": "the heading or name of the thing",
    "text": "the thing's readable content"
  }
}
```

It never appears in `makeable()`. `title`/`text` are the only text-shaped
properties today, by the Session 25 evidence rule.

## Add a new kind (walkthrough)

This is the shortest path from a real need to a discoverable kind.

1. **Write the file** `dictionary/<term>.json`. Every kind needs `term`,
   `meaning`, and a declared `element`. Add a `contains` list only if a real
   program puts children inside it — containment is structural children only,
   never inferred.

2. **See it surface.** From the repository root run:

   ```console
   python -m ine --dict <term>
   ```

   Your kind appears under "what can follow 'make'", and `ine --dict` (no
   argument) reports the new count. Completion (the editor engine) picks it
   up from the same data automatically — there is nothing else to register.

3. **Run the dictionary tests.** The suite asserts the dictionary is intact
   end to end:

   ```console
   python -m pytest tests/test_ine.py -k dictionary
   ```

   The integrity guard (`-k integrity`) additionally checks every real file:
   unique `term`s, `term` + `meaning` present, containment members resolve,
   and makeable kinds declare an `element`.

## Rules

- The dictionary is **advisory** — never raise, never validate with it.
- **Evidence rule:** no value shape or containment entry is declared without
  support in existing dictionary data or real programs (Session 25 decision).
- No second vocabulary anywhere: the extension and the editor are pure
  proxies that consume this data; they must never hold their own copy.
- Test counts and commands: the canonical runner is `python -m pytest tests`
  from the repository root.