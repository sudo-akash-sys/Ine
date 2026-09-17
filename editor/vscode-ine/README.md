# Ine autocomplete for VS Code (prototype)

The smallest possible editor completion for `.ine` files. It proves the
interaction: open a `.ine` file, type, and the dictionary answers —
without leaving the editor and without the extension holding any Ine
vocabulary.

## How it works

The extension holds **no Ine vocabulary**. On every completion it forwards
the buffer and cursor to a single long-lived Python process (one JSON
object per line) and renders whatever it returns.

```
your buffer (current .ine file)
      |
      v
python src/ine/autocomplete.py     <- long-lived process; imports ine.dictionary
      |  {"buffer","line","column","id"}\n     completion query (per keystroke)
      |  {"id","line","column","context","items":[{label,insert,detail,type,"value_shape"}...]}\n
      |  {"validate":true,"buffer","id"}\n     diagnostics query (lex + parse)
      |  {"validate":true,"diagnostics":[{"line","column","message"}...]}\n
      v
extension.js (pure proxy)
      |
      v
VS Code completion popup / diagnostics
```

Completion triggers on a space (`make `, `header `, `inside `) *and* on
letters, so `make h` asks the dictionary while the word is still being
typed.

`src/ine/autocomplete.py` is the single place that decides which dictionary
query a cursor position maps to:

- after `make ` (or a partial kind)       -> makeable kinds
  (`dictionary.makeable()`)
- after a declared kind / entity          -> its properties + members
  (`dictionary.suggest(kind)`)
- after `kind property `                  -> the property's value shape
  (`dictionary.value_shape`): `text` -> `""`, `choice` -> its options
- after `inside `                         -> valid parents
  (`dictionary.parents(kind)`), via the dictionary's reverse containment
- after a COMPLETE `make` statement       -> no context. `make header ` and
  `make hero banner ` return nothing (corrected: `make` + a second word is
  never a value site, Mission 43). Only a partial word still counts as a
  kind context (`make h<...>`).

## Diagnostics (engine `validate` query)

A query carrying `{"validate": true, "buffer": ...}` answers with
parse-level diagnostics instead of completions:

```
{"validate": true, "diagnostics": [{"line", "column", "message"}, ...]}
```

Diagnostics are lex + parse ONLY — never semantic — so the dictionary
never red-underlines (advisory stays advisory). Lines and columns are
0-based to match the completion protocol; a lex error carries both a line
and a column, a syntax error carries a line only. An `id` on the request
is echoed on the response. A buffer that lexes and parses cleanly returns
`[]`. The extension currently consumes completions; the query is the
engine-side surface ready for a diagnostics provider.

## Supported contexts

1. `make he<...>`                    -> `header`
2. `header <...>`                    -> `logo`, `navigation`, `title`, `text`, ...
3. `header inside p<...>`            -> `page`
4. `page title <...>`                -> `""` (quoted placeholder for text values)
5. `make header ` / `make hero banner ` -> no context (Mission 43)

Entities declared by `make name kind`, multiplicity (`make 2 card` ->
`card-1 ...`), and groups (`group cards = ...`) are resolved from the
current buffer — including declarations on earlier lines, so `card-1 titl`
on a later line still reaches the card vocabulary (Mission 46).

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

Prototype. No packaging, no formatting/hover, no config. One warm Python
process is started on activation and reused across keystrokes (it
respawns automatically if it dies); the first suggestion still pays
Python startup. Contexts 1-5 work — property *values* are suggested
(`page title ` inserts `""`; for `length`-shaped properties current
dictionary entries declare no completion). Optional `"choice"` values are
supported by the engine (each option becomes a suggestion) but no
dictionary entry uses them yet, so nothing offers them today. The engine
also answers the `validate` query (parse-level diagnostics).

Not attempted yet: property-name completion while typing (cursor short of
the trailing space), multi-kind `make` arguments, statement-start
keywords (`make`/`say`/`group` — a syntax feature on the pure-proxy
boundary), and wiring the `validate` query into a VS Code diagnostics
provider.