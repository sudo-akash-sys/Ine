# A whole page, built by using the language

`site.ine` is not an experiment about one feature. It is a complete small
site — header, hero, two rows of cards, a call to action, a footer —
written to find out what Ine is like to actually use for the thing it
exists to do.

It uses no vocabulary the dictionary does not already declare, and no
concept beyond the four: entity, kind, property value, containment.

## What the program does not say

Not one word about appearance. Card padding, card borders, corner radii,
the header's row layout, the logo's weight, the footer's centring and the
alternating rows are all absent from `site.ine`. They come from the
`style` block each kind already declares, applied by the HTML backend.

This is the claim the language makes — *describe what, not how* — and after
this pass it is measurably true rather than aspirationally true.

## Writing it surfaced three things

1. **A group is a bulk-assignment statement.** `group approach-set = a1 a2
   a3`, then `approach-set inside approach`, then `approach-set padding
   "compact"`, and all three cards get it. This was already implemented and
   had never been exercised on physical properties. It is the reason the
   second row can differ from the first in two lines instead of six.

2. **`make 3 card` still cannot be used twice.** The program needs two
   rows of three cards, and a second `make 3 card` would collide with the
   first batch's `card-1`..`card-3`. So both rows are named by hand
   (`f1`..`f3`, `a1`..`a3`) and grouped. The friction is real, it is
   worked around, and it costs about six extra lines. This is the one
   genuine core defect the program met, and it has no PLAN item.

3. **The navigation holds text where links belong.** There is no link
   syntax and no `link` kind is in use, so `nav text "Work, Studio,
   Notes"` renders three words in a `<nav>` that go nowhere. The header
   reads correctly and does not work. Recorded rather than hidden.

## Known limits, stated plainly

- **There is one colour, and it is not the dictionary's.** Every declaration
  here is structural — space, frames, alignment — except a single hairline,
  `#e2e8f0`, resolving the dictionary's pre-declared `border: "subtle"` hint.
  The hint word was already declared; that hex was authored in Session 42 and
  is **the agent's choice, not the dictionary's**. The palette itself remains
  UNDECIDED (`.agent/DECISIONS.md`), and the whole mapping is awaiting a
  commander decision — see `.agent/BLOCKERS.md` (Session 42).
- **Nothing reflows.** The card rows are `flex` with `flex:1` members; on a
  narrow screen three cards squish rather than stack. The dictionary does
  declare `narrow-layout: "stack members"` on `card-group`; no backend
  reads it yet, and conditions/state remain an undecided fifth construct.
- **One page only.** The HTML backend requires exactly one `page` entity,
  so this site cannot have a second page.
- **The button is unstyled.** `button` declares no physical values it could
  paint from, so it renders as the browser's default control.

## Status

`tests/expected/site.html` is the byte-identical golden; the output is
deterministic and the program is covered by `SiteExampleTests`.
