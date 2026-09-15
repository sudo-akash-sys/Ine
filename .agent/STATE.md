# .agent/STATE.md

Current ground truth as of autonomous Session 33 (dictionary/editor stabilization).

## Current focus

Autonomous improvement and stabilization of the Ine dictionary/editor system.
Session 33:
- Fixed `_shape_from` to reject non-standard value kinds (correct, kept)
- Attempted a `properties` block declaring `card-group layout: "text"` — this was a
  contradiction and has been **reverted**: evidence (WORKBOOK §40–41) classifies
  `layout` as a bare-word renderer hint, not a text value; the enumerated `choice`
  path stays BLOCKED (PLAN item 7).
- Added a `## Candidate missions` section to PLAN.md capturing the commander's
  next-stage direction (Ine authoring & UI capability: character-based
  completion, context-aware ranking, value/structure/choice completion, basic
  visual intent, realistic UI structures, responsive intent, tooling). These are
  candidates, not commitments: each must clear the five verification gates and
  graduate to Active before an agent implements it. They are deliberately outside
  the Active section so the selection rule does not pick them up prematurely. The
  operating rule mirrors MISSION_PROMPT.md: verify before implementing, preserve
  discoveries, keep blocked work blocked.

**PLAN expanded (Session 34):** 30 total active items (10 quick wins + 20 research/investigation missions).
Quick wins 1-10 remain executable. Research missions 11-30 cover dictionary robustness, autocomplete
edge cases, editor diagnostics, documentation gaps, real-world examples, responsive UI, styling,
infrastructure, native backend, performance, and ine-agent reliability.

## Health

- Test suite: **242 passing** (`python -m pytest tests`) — lexer, parser,
  semantic, dictionary, CLI, autocomplete, extension protocol, ine-agent.
  (Count unchanged — PLAN expansion adds missions, not tests yet.)
- Goldens (hello, topbar, hero, cards) **byte-identical**; `dictionary-demo.ine`
  renders.
- Environment: Windows / PowerShell 5.1, Python 3.13.14, node v24.17.0.
  Repo-root `ine.py` is a tracked shim that inserts `src/` into `sys.path`
  (it shadows the `ine` package — engine run as a script self-prepends `src/`).

## Pipeline & entry points

- `src/ine/lexer.py` → `parser.py` → `semantic.py` → `backend_*.py`.
- `src/ine/cli.py`: `ine run <file>`, `ine render <file> -o out.html`,
  `ine visual <file>`, `ine --dict [kind|file]`.
- `src/ine/autocomplete.py`: stdin JSON-lines `{buffer, line, column, id?}`
  → stdout `{id?, line, column, context, items[]}` per line; 4 contexts
  (`make`→makeable, kind→members/properties, `value`→shape options,
  inside→parents). One-shot and streaming both work; worker persists across
  requests.

## Dictionaries (15 files)

- Base kinds: page, header, section, hero, container, card-group, card,
  card-1, copy, footer.
- Concepts: universal (content properties `title`/`text`, both shaped
  `"text"` in a `properties` block), ambient (viewport `width`/`height` →
  `"length"`), entity (the run), misc (logo, link, thumbnail), wizard.
- Reader API: `makeable`, `find`, `properties_for`, `value_hint`,
  `suggest` (`Suggestion(text, source, note)`), `for_model`, `members`
  (structural children), `parents` (reverse containment),
  `ValueShape(type, choices)` + `value_shape(kind, prop)`.

## Editor prototype

- `editor/vscode-ine/`: extension.js is a pure proxy (zero Ine vocab);
  DictionaryWorker spawns `python <root>/src/ine/autocomplete.py`, FIFO
  queue, 4 s timeout, respawn on death, `" "` + ASCII-letter triggers,
  snippets: `value_shape == "text"` → `SnippetString('title "${1}"')`.

## ine-agent (developer tooling, Session 32)

- `python src/ine_agent/cli.py run` (or `ine-agent run` once installed):
  reads `.agent/`, applies the PLAN selection rule (first EXECUTABLE item,
  in list order), launches exactly one worker per cycle (sequential, never
  concurrent), rereads `.agent/` state after each cycle, and stops on the
  defined conditions. Exit codes: 0 = normal/no-work, 1 = error/bounded
  stop, 2 = HUMAN_DECISION_REQUIRED gate.
- Routing is deterministic: OpenCode is the implementation worker
  (`opencode run <prompt> --pure --dir <root>`); Claude is used only for
  `CLAUDE_REVIEW`-tagged tasks (review step, never implementation). No AI
  task classifier. Optional `--dry-run` prints the first executable task
  without launching anything.
- Files: `src/ine_agent/` — `state.py` (PLAN/STATE/HISTORY/BLOCKERS
  readers, Task/Plan), `supervisor.py` (loop, stop conditions, prompt
  builders), `worker.py` (OpenCode/Claude subprocess workers + stubs),
  `cli.py` (argparse entry, `--root`, `--worker`, `--dry-run`,
  `--cycle-limit`, `--max-attempts`). Guardrails hard-coded in prompts:
  never invent semantics, never unblock evidence-gated work, never modify
  DECISIONS.md, keep temp artifacts under `.tmp/`.

## Session 33 changes

1. **Fixed `_shape_from` non-standard type handling** (src/ine/dictionary.py:162-173):
   - Previously returned `ValueShape("row")` for any string from `defaults`
   - Now validates against known value kinds (`"text"`, `"length"`)
   - Non-standard strings (like "row") return `ValueShape()` (unknown)
   - Hint strings remain accessible via `value_hint()` as intended
   - Added regression assertions `_shape_from("row") == ValueShape()` and
     `_shape_from("length") == ValueShape("length")`.

2. **`card-group layout` stays untyped (reverted).** A temporary change declared
   `"layout": "text"` in card-group's `properties` to "unblock editor completion".
   This contradicted the evidence rules: WORKBOOK §40–41 state only universal
   `title`/`text` are text-shaped ("every real program writes them quoted");
   `card-group layout` "is a single `"row"` string, not a known set" and takes
   bare words. Reverted the `properties` block; `value_shape("card-group",
   "layout")` returns `unknown` again, and the FIRST `choice` value stays on the
   evidence-gated BLOCKED item (PLAN item 7). The `_shape_from` fix from item 1
   makes the bad classification structurally unrepresentable, so it cannot
   silently reappear.

## Known caveats

- `ine --dict universal` (pseudo-entry) shows `a text` for title/text since
  universal.json now owns a `properties` block — valid, intended side
  effect.
- No value kinds beyond `text` (and ambient `length`) are declared — no
  evidence supports more.
- `button label` is dictionary-suggested, but renderers surface `text`.
- `group` and `say` keyword contexts still return incorrect completions in
  autocomplete.py (missions 3-4 in PLAN.md).

## Coverage (reconciled, Session 31)

All property and containment usage across every real program (hello, topbar,
hero, cards, dictionary-demo) is fully covered by the dictionary. Entity
aliases (`main` → `container`, `hero` → `banner`) resolve cleanly. `search`,
`subtitle`/`description`, and the WORKBOOK `button inside header` layout
are evidence-gated proposals that remain correctly undeclared — see
`.agent/BLOCKERS.md`. Custom domain vocabulary (`person`/`name`/`age` in
alice.ine) is a scope boundary of the advisory dictionary, not a gap.

## Records

- WORKBOOK.md §1–§41 (decisions/architecture).
- SESSION_STATE.md Sessions 1–30 (§12 tracks DONE bullets; Session 30 DONE).
- RESEARCH_LOG.md, LANGUAGE.md (spec), README.md.
