# .agent/HISTORY.md

Running log of what happened and why. Sessions 21+ are precise (project
work); a compact digest is retained instead of full detail for the earlier
design arc — see RESEARCH_LOG.md / WORKBOOK.md for that era.

- **1–8 (design arc):** language identity, the `.ine` / `ine` naming, going
  native vs keeping one source with many targets, motivating examples, the
  start of the dictionary idea. Full detail lives in RESEARCH_LOG.md.
- **9–20:** the semantic model takes shape — Entity/Kind/Property/Container,
  the four-construct discipline, Say, multiplicity, groups, HTML backend
  with byte-identical goldens, the visual backend.
- **21:** multiplicity `make 4 cards` → `card-1…card-N` (kind names carry
  the index).
- **22:** groups — `card-group with 4 cards` produces one entity owning the
  set; dictionary vocabulary added around them.
- **23:** official naming — Ine, `.ine`, CLI `ine` (filename flip
  `mylang.py` → `ine.py`).
- **24:** goldens + dictionary-demo; the dictionary becomes a real layering
  between the model and the backends.
- **25 (decision session):** the four-construct spine, `title`/`text`
  universal content properties, dictionary is advisory (never validator),
  `contains` = structural children only, an evidence rule for vocabulary.
- **26:** reverse containment — `parents(kind)`, `--dict` prints
  `belongs inside:`; added page→section, container→card-group (159 tests).
- **27:** first editor prototype — `src/ine/autocomplete.py` engine +
  `editor/vscode-ine`; extension is a pure proxy; `make` / kind / inside
  contexts over JSON-lines (190 tests).
- **28:** responsiveness — generic space/letter triggers, one persistent
  worker (FIFO, 4 s timeout, respawn); 0.3 ms warm vs 140 ms cold (193
  tests).
- **29:** value-shape snippets — `value_shape: "text"` for title/text →
  `title "${1}"` with cursor between the quotes (199 tests).
- **30:** value shapes move into the dictionary — `universal.json`
  `properties: {title: "text", text: "text"}`, new readers
  `ValueShape` / `value_shape` / `_shape_from`, autocomplete.py special
  case removed. Representation already supports enumerated `"choice"`
  lists, none declared yet (204 tests).
- **31:** property-value completion + dictionary coverage reconciliation.
  Engine gained a `value` completion context — `<name> <property> ` answers
  from `value_shape(kind, prop)`: text → `""` quoted placeholder (detail =
  `value_hint`), choice → one item per allowed option, unknown → empty; the
  extension needed no change (a thin proxy surfaces value items for free).
  8 tests, 212 total. Coverage check reconciled every real program:
  all properties and containment pairs are dictionary-covered (entity
  aliases hero/main → banner/container resolve cleanly); two stale
  self-flags in dictionary-demo.ine corrected (card-group/section now have
  dictionary parents); `search`, `subtitle`/`description`, and WORKBOOK's
  `button inside header` confirmed evidence-gated and left undeclared;
  alice's `person` vocabulary flagged as a scope boundary, not a gap. Per
  the PLAN selection rule, nothing EXECUTABLE remains — session ends.
- **32:** the `ine-agent` autonomous supervisor (developer tooling, NOT
  the language). `.agent/` control-plane created (MISSION/STATE/PLAN/
  DECISIONS/BLOCKERS/HISTORY); AGENTS.md is the agent entry point and
  operating rules. `src/ine_agent/` implements the loop: read `.agent/`
  state every cycle, pick the first EXECUTABLE task (deterministic, list
  order; unmarked items are executable, `CLAUDE_REVIEW` triggers an
  optional Claude review then the implementation worker), run exactly one
  worker per cycle (sequential, never concurrent), reread state, stop
  cleanly. Stop conditions: no executable work (exit 0),
  `HUMAN_DECISION_REQUIRED` marker in output or `.agent/` files (exit 2),
  no plan progress after `--max-attempts` (exit 1), or `--cycle-limit`.
  Routing is deterministic per task tag, never an AI classifier. OpenCode
  is the default implementation worker; Claude only for review. Guardrails
  are hard-coded in the worker prompts. 22 focused tests (scripted stubs,
  no real agent ever launched), installed entry point
  `ine-agent = "ine_agent.cli:main"`, live smoke test on the real repo
  exits 0. 234 tests total — session ends.
- **33:** dictionary/editor stabilization under `ine-agent`. Fixed `_shape_from`
  to reject non-standard value kinds — a plain string like `"row"` now yields
  `ValueShape()` (unknown) instead of a bogus `ValueShape("row")`, so only
  declared value kinds (`"text"`, `"length"`) and list-style `choice`s survive;
  regression assertions added (`_shape_from("row")`, `_shape_from("length")`).
  A companion change that declared `card-group layout: "text"` to "unblock
  editor completion" was found to contradict WORKBOOK §40–41 — only universal
  `title`/`text` are text-shaped; `layout` is a bare-word renderer hint — and
  was reverted. `value_shape("card-group", "layout")` returns `unknown` again;
  the first `choice` value remains BLOCKED on evidence. PLAN renumbered
  (10 executable items + the blocked choice). 242 tests — session ends.
- **33 (addendum):** captured the commander's next-stage plan as a
  `## Candidate missions` section in PLAN.md — Ine authoring & UI capability:
  character-based completion and context-aware ranking, automatic
  value/structure/choice completion, basic visual intent (not "add CSS"),
  realistic UI structures (dashboard, tables, forms), responsive intent, and
  tooling (diagnostics, formatting, hover, packaging, CI). Each candidate has a
  five-point verification gate (real-example evidence, architecture fit,
  no conflict with DECIDED principles, no invented semantics, value vs. the
  next available mission) and must graduate to Active before implementation.
  The section is outside Active on purpose, so the selection rule never picks
  candidates as executable work; overlapping active research missions are
  cross-referenced instead of duplicated.