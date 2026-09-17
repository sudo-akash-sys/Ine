# Homepage — First MyLanguage Program (build notes)

This folder is the first real piece of software written in MyLanguage.
It is NOT an experiment. It is the language being built by using it.

## The three layers, kept separate

| Layer | Where it lives | What it is |
|-------|---------------|------------|
| Intent (human) | `homepage.semantic.json` → `"source"` | The L2 minimum utterance |
| **MyLanguage program** | `homepage.semantic.json` | The meaning, expressed with Entity / Property / Relationship / State / Condition / Multiplicity |
| Defaults & vocabulary | `src/ine/dictionary/*.json` | What kinds mean and their reusable defaults |
| Implementation (target) | `homepage.html` | One generated-by-AI output; NOT the language |

The program contains only intent. Every look/measure/mechanism (colors,
heights, gutter, breakpoint, flex, boxes) is absent from the program and
lives in the dictionary's `defaults` or in the implementation. That split
is what makes the program durable.

## How the 6 concepts carried the homepage

- **Entity** — one per thing: page, header, logo, navigation, main, hero,
  cards, card-1/2/3, footer, viewport.
- **Property** — the content: logo text, nav links, hero title+subtitle,
  each card's title+description, footer text.
- **Relationship** — `X inside Y` containment; cards group ↔ its members.
- **Multiplicity** — `cards: 3 members of kind card` (the "same kind" tie).
- **State** — `cards.layout` ∈ {row, column}, initial row.
- **Condition** — `viewport.width == narrow → cards.layout = column`.

## Concrete problems met while writing it, and the smallest fix

1. **Three cards, each with its own title/description.** Used one Entity
   per instance (card-1/2/3) + `kind: card` as the shared schema +
   `card-group` + `multiplicity: 3`. No new concept. This is the old
   "distinct instances" gap, resolved with existing tools — the shared
   schema is the kind, and the values are the per-instance Properties.
2. **Cards side by side / equal width / evenly spaced.** Not intent the
   user said at L2 — a `card-group` dictionary default (`row`,
   `member-width: equal`, `member-spacing: even`). Kept OUT of the
   program.
3. **Footer stays at bottom.** Dissolved structurally: `footer` as a kind
   MEANS bottom bar, and the `page` default (vertical stack, growing
   middle child) pins it. No position property, no "at-bottom"
   relationship. (Earlier sessions called positional intent a gap; with
   vocabulary in the dictionary it did not appear here.)
4. **Cards stack on mobile.** `viewport` is an environment-provided
   Entity; `narrow` is a dictionary class (the 768px number is an
   implementation detail and stays out of the program). Condition + State
   carry it, matching the concepts exactly.
5. **The dark look.** Absent from the program — it was an inferred default
   in the minimum-utterance work, and the theme mechanism does not exist
   yet. Not a blocker; noted only.
6. **Provenance.** Solved structurally, not with annotations: whatever is
   in the program is intent; whatever is in the dictionary is a default.
   (A per-property `source` tag was considered and dropped as noise.)

## Honest status

- No engine reads this file. No parser, validator, or adapter exists.
  `homepage.html` was written by the AI to match the intent, the same way
  the minimum-utterance experiment produced it.
- The dictionary entries are hand-written starts, not a complete library.
- Nothing here is a finalized concept. This is the language being used,
  so its real problems can surface.
- `viewport` as a `kind` and `provided-by: environment` is a convention,
  not a decided feature.