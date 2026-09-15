# .agent/BLOCKERS.md

Open issues, unstarted work, and anything waiting on evidence. Update as
items resolve. Nothing here is a commitment — blocked means: not done,
not no.

## Blocked on evidence

- **First enumerated `choice` value.** The value-shape representation
  **can** express choices — a `properties`-block value that is a list of
  strings becomes a `"choice"` shape (e.g. `"layout": ["row", "column"]`).
  But **no current dictionary entry declares one**: no property carries
  enough evidence, and `layout` still documents only a single `"row"` option.
  Declaring a choice requires either a real program using a second option
  (e.g. `layout column`) or a deliberate WORKBOOK decision. Blocked until
  then.

## Not started / deferred (no decision)

- **Conditions / state** ("cards stack on narrow") — would be a fifth
  construct; needs a WORKBOOK §25 decision, not just vocabulary.
- **HTML fidelity pass** (fixed header shadow, stylesheet, palette) —
  UNDECIDED scope; goldens are intentionally minimal.
- **Diagnostics, formatting, packaging** of the VS Code extension.
- **Native target** is research-only; no runtime for arbitrary `.ine`.

## Coverage reconciliation (Session 31) — evidence-gated, correctly undeclared

- **`search` (header member):** WORKBOOK proposes it throughout (a header
  carries logo, navigation, search; `make search inside header`), but no real
  `.ine` program has ever used it and no dictionary entry exists. Declaring
  it needs a real program or a WORKBOOK decision. Blocked.
- **`subtitle` / `description` (content properties):** WORKBOOK §36 stripped
  them from `contains` and re-grounded only `title`/`text` (no evidence);
  they remain absent today, by decision. Blocked on evidence.
- **`button inside header` (WORKBOOK L544) vs `button inside section`
  (dictionary, evidence = dictionary-demo.ine):** the proposed roadmap and
  evidence-grounded containment disagree. Do not change containment without a
  real program or a WORKBOOK decision.
- **Custom domain kinds (`person`, `name`, `age`, `height` in
  examples/alice/alice.ine):** the dictionary enumerates a guided footprint,
  not user domains; arbitrary kinds are a first-class language feature, so
  this is a scope boundary, not a coverage gap.

## Constraints that are easy to forget

- No edits to `parser.py`, `semantic.py`, `backend_html.py`,
  `backend_visual.py` for dictionary/editor work (Session 25 freeze).
- Extension.js must stay a pure proxy — it may consume `value_shape`/
  `context` from the engine but must never hold its own Ine knowledge.
- Parser/semantic/backends restrict `title`/`text` to quoted strings;
  `value_shape` is advisory metadata, not enforcement.