# .agent/MISSION.md

## What Ine is

Ine (Intent Expression, `.ine`) is a programming language whose human-facing
surface is **intent**, not implementation. The author writes what they want
(entities, kinds, properties, containment), and implementations render or
execute it. One source, multiple targets (HTML, native, visual).

The guiding test (WORKBOOK §2, §25): "Would a normal person naturally say it
this way?" — the language is measured by how little someone must say for the
system to produce the right thing.

## What we are building toward

1. The **dictionary** (`src/ine/dictionary/*.json`) is the single discoverable
   knowledge base: kinds, properties, value shapes, and containment.
2. The **editor** consumes that dictionary (and only that dictionary) so
   Ine stops being a language with just a CLI and becomes a usable
   programming environment.
3. Every feature is added as the **smallest experiment that produces real
   evidence** — real programs come first, claims are grounded in them.

## Non-negotiables

- The dictionary is the source of truth; no second vocabulary anywhere
  (not in the extension, not in the editor harness).
- The dictionary is **advisory**, never a validator.
- Distinguish DECIDED / PROPOSED / EXPERIMENTAL / UNDECIDED; a chat about an
  idea is not a decision.
- Do not invent semantics without evidence from the existing dictionary or
  real programs.
- Do not convert a possibility discussed in conversation into a mandatory
  architectural requirement.
- Minor, low-consequence implementation work proceeds directly; anything with
  significant architectural consequence gets options + trade-offs presented
  first.

See `AGENTS.md` (root) for the permanent working rules, and `WORKBOOK.md` for
the full vision and decision records.