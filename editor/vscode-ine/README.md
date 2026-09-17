# Ine autocomplete for VS Code (prototype)

The smallest possible editor completion for `.ine` files. It proves the
interaction: open a `.ine` file, type, and the dictionary answers —
without leaving the editor.

## How it works

The extension holds **no Ine vocabulary**. On every completion it forwards
the cursor position to a single long-lived Python process (one JSON object
per line) and renders whatever it returns.

```
your buffer (current .ine file)
      |
      v
python src/ine/autocomplete.py     <- long-lived process; imports ine.dictionary
      |  {"buffer","line","column","id"}\n  (streamed, one per keystroke)
      |  {"id", ..."items":[{label,insert,detail,type}...]}\n
      v
extension.js (pure proxy)
      |
      v
VS Code completion popup
```

Completion triggers on a space (`make `, `header `, `inside `) *and* on
letters, so `make h` asks the dictionary while the word is still being
typed.

`src/ine/autocomplete.py` is the single place that decides which dictionary
query a cursor position maps to:

- after `make `                      -> makeable kinds (`dictionary.makeable()`)
- after a declared kind / entity     -> its properties + members
  (`dictionary.suggest(kind)`)
- after `kind property `             -> the property's value shape
  (`dictionary.value_shape`): text -> `""`, choice -> its options
- after `inside `                    -> valid parents (`dictionary.parents(kind)`),
  powered by the dictionary's reverse containment

## Supported contexts

1. `make he<...>`                    -> `header`
2. `header <...>`                    -> `logo`, `navigation`, `title`, `text`, ...
3. `header inside p<...>`            -> `page`
4. `page title <...>`                -> `""` (quoted placeholder for text values)

Entities declared by `make name kind`, multiplicity (`make 2 card` ->
`card-1 ...`), and groups (`group cards = ...`) are resolved from the
current buffer.

Selecting a text property (`title`, `text`) inserts a snippet that places
the cursor between the quotes — `page title "|"` — so the expected value
shape is visible immediately and the user can start typing.

## Run it

Requires: VS Code, and `python` on `PATH` that can import the `ine`
package (open the repository root as your workspace; the extension invokes
`<workspace>/src/ine/autocomplete.py`).

1. Open this folder (`editor/vscode-ine`) in VS Code.
2. Press F5 (Extension Development Host).
3. In the new window, open any `.ine` file and type.

Optional: set `INE_PYTHON` to a specific Python executable.

## Status

Prototype. No packaging, no diagnostics/formatting/hover, no config. One
warm Python process is started on activation and reused across keystrokes
(it respawns automatically if it dies); the first suggestion still pays
Python startup. Contexts 1-4 work — property *values* are suggested
(`page title ` inserts `""`; for `length`-shaped properties current
dictionary entries declare no completion). Optional `"choice"` values are
supported by the engine (each option becomes a suggestion) but no
dictionary entry uses them yet, so nothing offers them today. Multi-kind
`make` arguments and completion while typing a property name (cursor short
of the trailing space) are not suggested.